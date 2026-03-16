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
if 'fatiga_l' not in st.session_state: st.session_state['fatiga_l'] = 1.0
if 'fatiga_v' not in st.session_state: st.session_state['fatiga_v'] = 1.0
if 'market_bias' not in st.session_state: st.session_state['market_bias'] = None
if 'lineups' not in st.session_state: st.session_state['lineups'] = None

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE LÓGICA ELITE (BLINDADAS)
# =================================================================

def api_request_live(action, params=None):
    """Función robusta: garantiza que siempre devuelva una lista si falla la API"""
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY, "_ts": time.time()})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        # Si la API devuelve un error (dict), retornamos lista vacía para no romper el 'for'
        return data if isinstance(data, list) else []
    except: return []

@st.cache_data(ttl=300)
def api_request_cached(league_id):
    params = {"action": "get_standings", "APIkey": API_KEY, "league_id": league_id}
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

def get_lineups(match_id):
    """Obtiene las alineaciones (Formaciones) del partido"""
    # Esta petición específica sí devuelve un dict con IDs como llaves
    try:
        params = {"action": "get_lineups", "match_id": match_id, "APIkey": API_KEY}
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        if not data or not isinstance(data, dict): return None
        match_key = list(data.keys())[0]
        return data[match_key]
    except: return None

def get_fatigue_factor(team_id, match_date_str):
    last_matches = api_request_live("get_events", {
        "from": (datetime.strptime(match_date_str, '%Y-%m-%d') - timedelta(days=10)).strftime('%Y-%m-%d'),
        "to": (datetime.strptime(match_date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d'),
        "team_id": team_id
    })
    if not last_matches: return 1.0
    try:
        last_date = datetime.strptime(last_matches[-1]['match_date'], '%Y-%m-%d')
        target_date = datetime.strptime(match_date_str, '%Y-%m-%d')
        days_off = (target_date - last_date).days
        if days_off <= 3: return 0.92
        if days_off >= 7: return 1.05
        return 1.0
    except: return 1.0

def get_market_consensus(match_id):
    odds = api_request_live("get_odds", {"match_id": match_id})
    if not odds: return None
    try:
        o = odds[0]
        o1, ox, o2 = float(o['odd_1']), float(o['odd_x']), float(o['odd_2'])
        margin = (1/o1) + (1/ox) + (1/o2)
        return ((1/o1)/margin, (1/ox)/margin, (1/o2)/margin)
    except: return None

@st.cache_data(ttl=300)
def get_advanced_metrics(team_id, league_id, position):
    events = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=45)).strftime('%Y-%m-%d'), 
                                             "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": league_id, "team_id": team_id})
    if not events: return 1.0, 1.0
    finished = [e for e in events if e.get('match_status') == 'Finished']
    if not finished: return 1.0, 1.0

    momentum_gf = 0
    weights = [0.5, 0.3, 0.2]
    for i, m in enumerate(finished[-3:][::-1]):
        is_home = m['match_hometeam_id'] == team_id
        try:
            gf = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            momentum_gf += gf * weights[i]
        except: continue

    elo_strength = 1.15 if int(position) <= 4 else (1.05 if int(position) <= 8 else 0.95)
    return elo_strength, momentum_gf

@st.cache_data(ttl=300)
def get_h2h_data(team_id_l, team_id_v):
    # La acción H2H devuelve un dict, tratamos por separado
    try:
        params = {"action": "get_H2H", "firstTeamId": team_id_l, "secondTeamId": team_id_v, "APIkey": API_KEY}
        res = requests.get(BASE_URL, params=params, timeout=10)
        res_data = res.json()
        if not res_data or 'firstTeam' not in res_data: return 1.0, 1.0
        matches = res_data.get('firstTeam', []) + res_data.get('secondTeam', [])
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
                else: l_pts += 1; v_pts += 1
            except: continue
        total = l_pts + v_pts if (l_pts + v_pts) > 0 else 1
        return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)
    except: return 1.0, 1.0

# =================================================================
# 3. MOTOR MATEMÁTICO (DIXON-COLES V4.5)
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

        if st.session_state['market_bias']:
            m1, mx, m2 = st.session_state['market_bias']
            p1 = (p1/total * 0.75) + (m1 * 0.25)
            px = (px/total * 0.75) + (mx * 0.25)
            p2 = (p2/total * 0.75) + (m2 * 0.25)
            total = p1 + px + p2

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
# 4. DISEÑO UI/UX
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; }
    .elite-alert { background: linear-gradient(90deg, rgba(212,175,55,0.15), rgba(0,255,163,0.05)); border: 1px solid var(--primary); }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; font-family: 'JetBrains Mono', monospace; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; text-transform: uppercase; letter-spacing: 3px; transition: 0.4s; width: 100%; }
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
                <div style="width: {p1}%; background: var(--secondary); box-shadow: 0 0 15px var(--secondary);"></div>
                <div style="width: {px_val}%; background: #444;"></div>
                <div style="width: {p2}%; background: var(--primary); box-shadow: 0 0 15px var(--primary);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 22px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #eee; margin-bottom: 8px;">
                <span style="font-weight: 600;">{label_over} <span style="color:{color};">{prob_over:.1f}%</span></span>
                <span style="color: #666;">{prob_under:.1f}% {label_under}</span>
            </div>
            <div style="display: flex; background: #111; height: 10px; border-radius: 5px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color};"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR (LOGICA PROTEGIDA)
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
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

    if isinstance(raw_events, list) and len(raw_events) > 0:
        # Usamos un try/except interno para mayor seguridad al mapear
        try:
            op_p = {f"({e['match_date']}) {e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events if 'match_hometeam_name' in e}
            if op_p:
                p_sel = st.selectbox("📍 Partidos Encontrados", list(op_p.keys()))

                if st.button("SYNC DATA"):
                    st.cache_data.clear()
                    with st.spinner("QUANTUM DEEP SYNC..."):
                        standings = api_request_cached(ligas_api[nombre_liga])
                        match_info = op_p[p_sel]

                        if standings:
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
                                elo_l, mom_l = get_advanced_metrics(dl['team_id'], ligas_api[nombre_liga], dl['overall_league_position'])
                                elo_v, mom_v = get_advanced_metrics(dv['team_id'], ligas_api[nombre_liga], dv['overall_league_position'])
                                st.session_state['fatiga_l'] = get_fatigue_factor(dl['team_id'], match_info['match_date'])
                                st.session_state['fatiga_v'] = get_fatigue_factor(dv['team_id'], match_info['match_date'])
                                st.session_state['market_bias'] = get_market_consensus(match_info['match_id'])
                                st.session_state['lineups'] = get_lineups(match_info['match_id'])

                                ph, pa = int(dl['home_league_payed']), int(dv['away_league_payed'])
                                st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/ph if ph>0 else 1.5) * 0.7 + (mom_l * 0.3)
                                st.session_state['lgc_auto'] = (float(dl['home_league_GA'])/ph if ph>0 else 1.0)
                                st.session_state['vgf_auto'] = (float(dv['away_league_GF'])/pa if pa>0 else 1.2) * 0.7 + (mom_v * 0.3)
                                st.session_state['vgc_auto'] = (float(dv['away_league_GA'])/pa if pa>0 else 1.3)
                                st.session_state['elo_bias'] = (elo_l, elo_v)
                                st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']

                                recent_league = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=10)).strftime('%Y-%m-%d'), "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": ligas_api[nombre_liga]})
                                st.session_state['audit_results'] = [e for e in recent_league if e.get('match_status') == 'Finished'][-5:]
                                st.rerun()
            else: st.warning("No hay datos de equipos disponibles.")
        except Exception: st.error("Error al procesar eventos de la API.")
    else:
        st.info("No hay partidos programados o error de conexión.")

# =================================================================
# 6. CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>PREDICTIVE ENGINE V4.5 QUANTUM + SYNC</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-right: 2px solid var(--secondary); text-align: right; padding-right: 15px; margin-bottom: 5px;'><h6 style='color:var(--secondary); margin:0; font-weight:900;'>LOCAL</h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("GF Local", 0.0, 10.0, key='lgf_auto'), lb.number_input("GC Local", 0.0, 10.0, key='lgc_auto')
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, key='ltj_auto'), lb.number_input("Corners L", 0.0, 20.0, key='lco_auto')

with col_v:
    st.markdown("<div style='border-left: 2px solid var(--primary); text-align: left; padding-left: 15px; margin-bottom: 5px;'><h6 style='color:var(--primary); margin:0; font-weight:900;'>VISITANTE</h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Nombre Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("GF Visita", 0.0, 10.0, key='vgf_auto'), vb.number_input("GC Visita", 0.0, 10.0, key='vgc_auto')
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, key='vtj_auto'), vb.number_input("Corners V", 0.0, 20.0, key='vco_auto')

p_liga = st.slider("Media de Goles de la Liga", 0.5, 5.0, key='p_liga_auto')

b_ex, b_wa = st.columns([3, 1])
with b_ex: generar = st.button("GENERAR REPORTE DE INTELIGENCIA")

if generar:
    motor = MotorMatematico(league_avg=p_liga)
    hfa, (h2h_l, h2h_v), (elo_l, elo_v), f_l, f_v = st.session_state['hfa_league'], st.session_state['h2h_bias'], st.session_state['elo_bias'], st.session_state['fatiga_l'], st.session_state['fatiga_v']

    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * hfa * h2h_l * elo_l * f_l
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/hfa) * h2h_v * elo_v * f_v

    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    sug = sorted([{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "Ambos Anotan", "p": res['BTTS'][0]}] + 
                 [{"t": f"Over {l}", "p": res['GOLES'][l][0]} for l in [1.5, 2.5]], key=lambda x: x['p'], reverse=True)[:6]
    
    encoded_msg = urllib.parse.quote(f"Picks: {nl_manual} vs {nv_manual}\nScore: {res['TOP'][0][0]}")
    with b_wa: st.markdown(f'<a href="https://wa.me/?text={encoded_msg}" target="_blank" class="whatsapp-btn">📲 COMPARTIR</a>', unsafe_allow_html=True)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary);'>💎 TOP SELECCIONES ({res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
        for s in sug: st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; text-align:center;'>🎯 SCORE</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6, t7 = st.tabs(["🥅 GOLES", "🏆 HANDICAP", "📊 1X2", "🚩 ESPECIALES", "🧩 MATRIZ", "🛡️ FORMACIÓN", "📈 AUDITORÍA"])
    with t1:
        ga, gb = st.columns(2)
        with ga: 
            for l in [1.5, 2.5, 3.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with gb: dual_bar_explicit("BTTS: SI", res['BTTS'][0], "BTTS: NO", res['BTTS'][1], color="#d4af37")
    with t6:
        st.markdown("<h4 style='color:var(--secondary);'>🛡️ ALINEACIONES</h4>", unsafe_allow_html=True)
        lineups = st.session_state['lineups']
        if lineups and 'lineup' in lineups:
            cla, cva = st.columns(2)
            for side, col, color, name in [('home', cla, 'var(--secondary)', nl_manual), ('away', cva, 'var(--primary)', nv_manual)]:
                with col:
                    team = lineups['lineup'][side]
                    st.markdown(f"<div style='text-align:center; background:rgba(255,255,255,0.05); padding:10px; border-radius:10px; border:1px solid {color};'><b>{name} - {team.get('system', 'N/A')}</b></div>", unsafe_allow_html=True)
                    for p in team.get('starting_lineups', []):
                        st.markdown(f"<div style='font-size:0.85em; border-bottom:1px solid #222;'>{p['lineup_number']} {p['lineup_player']}</div>", unsafe_allow_html=True)
        else: st.info("Alineaciones no disponibles.")
    with t7:
        if st.session_state['audit_results']:
            for m in st.session_state['audit_results']:
                st.markdown(f"<small>{m['match_date']}</small> - {m['match_hometeam_name']} {m['match_hometeam_score']}-{m['match_awayteam_score']} {m['match_awayteam_name']}", unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>OR936 ELITE v4.5 | QUANTUM ENGINE</p>", unsafe_allow_html=True)