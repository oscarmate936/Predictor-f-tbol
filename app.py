import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from fuzzywuzzy import process
import time

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []
if 'match_id_sel' not in st.session_state: st.session_state['match_id_sel'] = None
if 'fatiga_dinamica' not in st.session_state: st.session_state['fatiga_dinamica'] = (1.0, 1.0)
if 'pts_gap_bias' not in st.session_state: st.session_state['pts_gap_bias'] = (1.0, 1.0)

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'fatiga_l': 1.0, 'fatiga_v': 1.0
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE LÓGICA ELITE (CORREGIDAS)
# =================================================================

def api_request_live(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        # Si la API devuelve un error (dict con 'error'), devolvemos lista vacía para evitar el TypeError
        if isinstance(data, dict) and 'error' in data:
            return []
        return data
    except:
        return []

@st.cache_data(ttl=300)
def get_advanced_metrics(team_id, league_id, position):
    events = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=45)).strftime('%Y-%m-%d'), 
                                             "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": league_id, "team_id": team_id})
    if not isinstance(events, list) or not events: return 1.0, 1.0, 1.0
    finished = [e for e in events if e.get('match_status') == 'Finished']
    if not finished: return 1.0, 1.0, 1.0

    momentum_gf = 0
    weights = [0.5, 0.3, 0.2]
    for i, m in enumerate(finished[-3:][::-1]):
        is_home = m['match_hometeam_id'] == team_id
        try:
            gf = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            momentum_gf += gf * weights[i]
        except: continue

    u_fecha = datetime.strptime(finished[-1]['match_date'], '%Y-%m-%d').replace(tzinfo=tz_sv)
    dias_descanso = (ahora_sv - u_fecha).days
    penalizacion_fatiga = 0.92 if dias_descanso < 4 else 1.0
    elo_strength = 1.15 if int(position) <= 4 else (1.05 if int(position) <= 8 else 0.95)
    return elo_strength, momentum_gf, penalizacion_fatiga

@st.cache_data(ttl=300)
def get_h2h_data(team_id_l, team_id_v):
    res = api_request_live("get_H2H", {"firstTeamId": team_id_l, "secondTeamId": team_id_v})
    if not isinstance(res, dict) or 'firstTeam' not in res: return 1.0, 1.0
    matches = res.get('firstTeam', []) + res.get('secondTeam', [])
    if not matches: return 1.0, 1.0
    l_pts, v_pts = 0, 0
    for m in matches[:6]:
        try:
            h_s, a_s = int(m.get('match_hometeam_score', 0)), int(m.get('match_awayteam_score', 0))
            if h_s > a_s:
                if m['match_hometeam_id'] == team_id_l: l_pts += 3
                else: v_pts += 3
            elif h_s < a_s:
                if m['match_hometeam_id'] == team_id_l: v_pts += 3
                else: l_pts += 3
            else:
                l_pts += 1; v_pts += 1
        except: continue
    total = l_pts + v_pts if (l_pts + v_pts) > 0 else 1
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 3. MOTOR MATEMÁTICO (DIXON-COLES)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.16 if league_avg < 2.4 else -0.12

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]; h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}
        h_probs_l = {h: 0.0 for h in h_lines}; h_probs_v = {h: 0.0 for h in h_lines}

        for i in range(10): 
            fila = []
            for j in range(10):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                for h in h_lines:
                    if (i + h) > j: h_probs_l[h] += p
                    if (j + h) > i: h_probs_v[h] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# 4. UI STYLES
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; width: 100%; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background: #25D366; color: white !important; padding: 14px; border-radius: 14px; text-decoration: none; font-weight: 700; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin: 30px 0; background: #0a0c10; padding: 25px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #aaa; text-transform: uppercase; margin-bottom: 15px;">
                <span style="color:var(--secondary)">{n1}: <b>{p1:.1f}%</b></span>
                <span>{nx}: <b>{px_val:.1f}%</b></span>
                <span style="color:var(--primary)">{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 16px; border-radius: 50px; overflow: hidden; background: #1a1a1a;">
                <div style="width: {p1}%; background: var(--secondary);"></div>
                <div style="width: {px_val}%; background: #444;"></div>
                <div style="width: {p2}%; background: var(--primary);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 22px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #eee; margin-bottom: 8px;">
                <span>{label_over} <span style="color:{color};">{prob_over:.1f}%</span></span>
                <span style="color: #666;">{prob_under:.1f}% {label_under}</span>
            </div>
            <div style="display: flex; background: #111; height: 10px; border-radius: 5px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color};"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Saudi Pro League": 307, "Trendyol Süper Lig": 322, "Liga Mayor (El Salvador)": 601, "Copa Presidente (El Salvador)": 603,
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207, "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, 
        "UEFA Champions League": 3, "UEFA Europa League": 4, "UEFA Conference League": 683, "Copa Libertadores": 13,
        "Brasileirão Betano (Série A)": 99, "Brasileirão Série B": 100, "Brasileirão Série C": 103, "Copa de Brasil": 101,
        "FA Cup (Inglaterra)": 145, "EFL Cup (Inglaterra)": 146, "Copa del Rey (España)": 300, "Coppa Italia (Italia)": 209, "DFB Pokal (Alemania)": 177, "Coupe de France (Francia)": 169
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA CENTRAL", value=ahora_sv.date())
    f_desde = (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d')
    f_hasta = (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d')

    raw_events = api_request_live("get_events", {"from": f_desde, "to": f_hasta, "league_id": ligas_api[nombre_liga]})

    # VALIDACIÓN DE SEGURIDAD PARA LA LISTA DE PARTIDOS
    if isinstance(raw_events, list) and len(raw_events) > 0:
        op_p = {f"({e['match_date']}) {e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos Encontrados", list(op_p.keys()))
        st.session_state['match_id_sel'] = op_p[p_sel]['match_id']

        if st.button("SYNC DATA"):
            st.cache_data.clear()
            with st.spinner("QUANTUM DEEP SYNC..."):
                standings = api_request_live("get_standings", {"league_id": ligas_api[nombre_liga]})
                match_info = op_p[p_sel]

                if isinstance(standings, list) and standings:
                    h_goals = sum(int(t['home_league_GF']) for t in standings)
                    a_goals = sum(int(t['away_league_GF']) for t in standings)
                    total_pj = sum(int(t['overall_league_payed']) for t in standings)
                    avg_g = (h_goals + a_goals) / (total_pj / 2) if total_pj > 0 else 2.5
                    st.session_state['p_liga_auto'] = avg_g
                    st.session_state['hfa_league'] = float(h_goals / a_goals) if a_goals > 0 else 1.1

                    def buscar(n):
                        nombres = [t['team_name'] for t in standings]
                        m, s = process.extractOne(n, nombres)
                        return next((t for t in standings if t['team_name'] == m), None) if s > 65 else None

                    dl, dv = buscar(match_info['match_hometeam_name']), buscar(match_info['match_awayteam_name'])

                    if dl and dv:
                        st.session_state['h2h_bias'] = get_h2h_data(dl['team_id'], dv['team_id'])
                        elo_l, mom_l, fat_l = get_advanced_metrics(dl['team_id'], ligas_api[nombre_liga], dl['overall_league_position'])
                        elo_v, mom_v, fat_v = get_advanced_metrics(dv['team_id'], ligas_api[nombre_liga], dv['overall_league_position'])
                        
                        pts_l, pts_v = int(dl['overall_league_PTS']), int(dv['overall_league_PTS'])
                        gap = abs(pts_l - pts_v)
                        bias_pts = 1.0 + (gap * 0.005)
                        st.session_state['pts_gap_bias'] = (bias_pts if pts_l > pts_v else 1.0, bias_pts if pts_v > pts_l else 1.0)
                        
                        ph, pa = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/ph if ph>0 else 1.5) * 0.7 + (mom_l * 0.3)
                        st.session_state['lgc_auto'] = (float(dl['home_league_GA'])/ph if ph>0 else 1.0)
                        st.session_state['vgf_auto'] = (float(dv['away_league_GF'])/pa if pa>0 else 1.2) * 0.7 + (mom_v * 0.3)
                        st.session_state['vgc_auto'] = (float(dv['away_league_GA'])/pa if pa>0 else 1.3)
                        
                        st.session_state['elo_bias'], st.session_state['fatiga_dinamica'] = (elo_l, elo_v), (fat_l, fat_v)
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.rerun()
    else:
        st.warning("No hay partidos en el rango de fechas para esta liga.")

# =================================================================
# 6. CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px;'>PREDICTIVE ENGINE V4.5 QUANTUM</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    nl_manual = st.text_input("Local", value=st.session_state['nl_auto'])
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("GF L", 0.0, 10.0, key='lgf_auto'), lb.number_input("GC L", 0.0, 10.0, key='lgc_auto')
    ltj, lco = la.number_input("Tj L", 0.0, 15.0, 2.3), lb.number_input("Cr L", 0.0, 20.0, 5.5)
with col_v:
    nv_manual = st.text_input("Visita", value=st.session_state['nv_auto'])
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("GF V", 0.0, 10.0, key='vgf_auto'), vb.number_input("GC V", 0.0, 10.0, key='vgc_auto')
    vtj, vco = va.number_input("Tj V", 0.0, 15.0, 2.2), vb.number_input("Cr V", 0.0, 20.0, 4.8)

p_liga = st.slider("Media Liga", 0.5, 5.0, key='p_liga_auto')
generar = st.button("GENERAR REPORTE")

if generar:
    motor = MotorMatematico(league_avg=p_liga)
    hfa, (hl, hv), (el, ev), (fl, fv), (pl, pv) = st.session_state['hfa_league'], st.session_state['h2h_bias'], st.session_state['elo_bias'], st.session_state['fatiga_dinamica'], st.session_state['pts_gap_bias']
    
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * hfa * hl * el * fl * pl
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/hfa) * hv * ev * fv * pv
    
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    sug = sorted([{"t": k, "p": v} for k, v in [("1X", res['DC'][0]), ("X2", res['DC'][1]), ("BTS", res['BTTS'][0])] + [(f"O{l}", p[0]) for l,p in res['GOLES'].items() if 1.5<=l<=3.5]], key=lambda x: x['p'], reverse=True)[:5]
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown("#### 💎 TOP PICKS")
        for s in sug: st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("#### 🎯 SCORES")
        for sc, pr in res['TOP']: st.markdown(f'<div class="score-badge">{sc} ({pr:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl_manual, "X", nv_manual)

    t1, t2, t3, t4, t5, t6, t7 = st.tabs(["🥅 GOLES", "🏆 HDP", "📊 1X2", "🚩 ESP", "🧩 MATRIZ", "📈 AUDIT", "📋 LINEUPS"])
    with t1:
        ga, gb = st.columns(2)
        with ga: [dual_bar_explicit(f"O {l}", res['GOLES'][l][0], f"U {l}", res['GOLES'][l][1]) for l in [1.5, 2.5, 3.5]]
        with gb: dual_bar_explicit("BTS: SI", res['BTTS'][0], "BTS: NO", res['BTTS'][1])
    with t5:
        df_matriz = pd.DataFrame(res['MATRIZ'], index=[f"{i}" for i in range(6)], columns=[f"{j}" for j in range(6)])
        st.plotly_chart(px.imshow(df_matriz, text_auto=".1f", color_continuous_scale=['#05070a', '#d4af37']), use_container_width=True)
    with t7:
        if st.session_state['match_id_sel']:
            lps = api_request_live("get_lineups", {"match_id": st.session_state['match_id_sel']})
            if lps and str(st.session_state['match_id_sel']) in lps:
                d = lps[str(st.session_state['match_id_sel'])]
                c1, c2 = st.columns(2)
                with c1: st.write(f"**Titulares {nl_manual}**"); st.caption(", ".join([p['lineup_player'] for p in d['lineup']['localteam']['starting_lineups']]))
                with c2: st.write(f"**Titulares {nv_manual}**"); st.caption(", ".join([p['lineup_player'] for p in d['lineup']['visitorteam']['starting_lineups']]))
            else: st.info("Alineaciones no disponibles aún.")
