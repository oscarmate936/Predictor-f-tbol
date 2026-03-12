import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime
import urllib.parse
from fuzzywuzzy import process

# =================================================================
# CONFIGURACIÓN API & ESTADO
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except: return []

# =================================================================
# MOTOR MATEMÁTICO ELITE
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        if league_avg > 3.0: self.rho = -0.10
        elif league_avg < 2.2: self.rho = -0.18
        else: self.rho = -0.15

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        try: return (lam**k * math.exp(-lam)) / math.factorial(k)
        except: return 0.0

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}
        h_probs_l = {h: 0.0 for h in h_lines}
        h_probs_v = {h: 0.0 for h in h_lines}

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

        iteraciones = 15000
        sim_tj = np.random.poisson(tj_total, iteraciones)
        sim_co = np.random.poisson(co_total, iteraciones)
        tj_probs = {t: (np.sum(sim_tj > t)/iteraciones*100, np.sum(sim_tj <= t)/iteraciones*100) for t in [2.5, 3.5, 4.5, 5.5, 6.5]}
        co_probs = {t: (np.sum(sim_co > t)/iteraciones*100, np.sum(sim_co <= t)/iteraciones*100) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]}

        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}},
            "TARJETAS": tj_probs, "CORNERS": co_probs,
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# DISEÑO UI/UX
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
# SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Brasileirão Betano (Série A)": 99, "Brasileirão Série B": 100, "Brasileirão Série C": 103, "Copa de Brasil": 101,
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207, "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, 
        "UEFA Champions League": 3, "UEFA Europa League": 4, "UEFA Conference League": 683, "Copa Libertadores": 13,
        "FA Cup (Inglaterra)": 145, "EFL Cup (Inglaterra)": 146, "Copa del Rey (España)": 300, "Coppa Italia (Italia)": 209, "DFB Pokal (Alemania)": 177, "Coupe de France (Francia)": 169,
        "Liga Mayor (El Salvador)": 601, "Copa Presidente (El Salvador)": 603
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Evento en Vivo", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Sincronizando..."):
                standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
                if standings and isinstance(standings, list):
                    h_goals = sum(int(t['home_league_GF']) for t in standings)
                    a_goals = sum(int(t['away_league_GF']) for t in standings)
                    total_pj = sum(int(t['overall_league_payed']) for t in standings)

                    st.session_state['p_liga_auto'] = float((h_goals + a_goals) / (total_pj / 2)) if total_pj > 0 else 2.5
                    st.session_state['hfa_league'] = float(h_goals / a_goals) if a_goals > 0 else 1.0

                    def buscar(n):
                        nombres_equipos = [t['team_name'] for t in standings]
                        match, score = process.extractOne(n, nombres_equipos)
                        if score > 60:
                            for t in standings:
                                if t['team_name'] == match: return t
                        return None

                    dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                    if dl and dv:
                        st.session_state['form_l'] = 1.15 if int(dl['overall_league_position']) < int(dv['overall_league_position']) else 0.95
                        st.session_state['form_v'] = 1.10 if int(dv['overall_league_position']) < int(dl['overall_league_position']) else 0.90
                        pj_h, pj_a = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['lgf_auto'] = float(dl['home_league_GF'])/pj_h if pj_h>0 else 1.5
                        st.session_state['lgc_auto'] = float(dl['home_league_GA'])/pj_h if pj_h>0 else 1.0
                        st.session_state['vgf_auto'] = float(dv['away_league_GF'])/pj_a if pj_a>0 else 1.2
                        st.session_state['vgc_auto'] = float(dv['away_league_GA'])/pj_a if pj_a>0 else 1.3
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.rerun()

# =================================================================
# CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>PREDICTIVE ENGINE V3.5 PRO + FUZZY LOGIC</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-right: 2px solid var(--secondary); text-align: right; padding-right: 15px; margin-bottom: 5px;'><h6 style='color:#666; margin:0;'>EQUIPO LOCAL (EDITABLE)</h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("GF Local", 0.0, 10.0, key='lgf_auto'), lb.number_input("GC Local", 0.0, 10.0, key='lgc_auto')
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.3), lb.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("<div style='border-left: 2px solid var(--primary); text-align: left; padding-left: 15px; margin-bottom: 5px;'><h6 style='color:#666; margin:0;'>EQUIPO VISITANTE (EDITABLE)</h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Nombre Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("GF Visita", 0.0, 10.0, key='vgf_auto'), vb.number_input("GC Visita", 0.0, 10.0, key='vgc_auto')
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, 2.2), vb.number_input("Corners V", 0.0, 20.0, 4.8)

st.markdown("<br>", unsafe_allow_html=True)
p_liga = st.slider("Media de Goles de la Liga", 0.5, 5.0, key='p_liga_auto')

b_ex, b_wa = st.columns([3, 1])
with b_ex: generar = st.button("GENERAR REPORTE DE INTELIGENCIA")

if generar:
    motor = MotorMatematico(league_avg=p_liga)
    hfa, f_l, f_v = st.session_state['hfa_league'], st.session_state['form_l'], st.session_state['form_v']
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * hfa * f_l
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/hfa) * f_v
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    pool = [{"t": "Doble Oportunidad 1X", "p": res['DC'][0]}, {"t": "Doble Oportunidad X2", "p": res['DC'][1]}, {"t": "Mercado 12", "p": res['DC'][2]}, {"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]}]
    for line, p in res['GOLES'].items():
        if 1.5 <= line <= 3.5:
            pool.append({"t": f"Over {line} Goles", "p": p[0]})
            pool.append({"t": f"Under {line} Goles", "p": p[1]})
    sug = sorted([s for s in pool if 65 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:6]

    msg = f"*OR936 ELITE*\n⚽ {nl_manual} vs {nv_manual}\n\n*PICKS:*\n"
    for s in sug: msg += f"• {s['t']}: {s['p']:.1f}%\n"
    encoded_msg = urllib.parse.quote(msg + f"\n*MARCADOR:* {res['TOP'][0][0]}\n*CONFIANZA:* {res['BRIER']*100:.1f}%")
    with b_wa: st.markdown(f'<a href="https://wa.me/?text={encoded_msg}" target="_blank" class="whatsapp-btn">📲 COMPARTIR REPORTE</a>', unsafe_allow_html=True)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary);'>💎 TOP SELECCIONES (Confianza: {res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
        for s in sug:
            clase = "elite-alert" if s['p'] > 85 else ""
            st.markdown(f'<div class="verdict-item {clase}"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; text-align:center;'>🎯 MARCADOR PROBABLE</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} <span style="font-size:0.6em; color:#666;">({prob:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl_manual, "Empate", nv_manual)

    t1, t2, t3, t4, t5 = st.tabs(["🥅 GOLES", "🏆 HANDICAP", "📊 MERCADOS 1X2", "🚩 ESPECIALES", "🧩 MATRIZ"])
    with t1:
        ga, gb = st.columns(2)
        with ga:
            for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with gb: dual_bar_explicit("AMBOS ANOTAN: SÍ", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")
    with t2:
        ha, hb = st.columns(2)
        with ha:
            st.markdown(f"<h5 style='color:var(--secondary);'>{nl_manual}</h5>", unsafe_allow_html=True)
            for h, p in res['HANDICAPS']['L'].items(): dual_bar_explicit(f"Handicap {h:+}", p, "", 100-p, color="#00ffa3")
        with hb:
            st.markdown(f"<h5 style='color:var(--primary);'>{nv_manual}</h5>", unsafe_allow_html=True)
            for h, p in res['HANDICAPS']['V'].items(): dual_bar_explicit(f"Handicap {h:+}", p, "", 100-p, color="#d4af37")
    with t3:
        dual_bar_explicit(f"1X ({nl_manual} o Empate)", res['DC'][0], "2 Directo", 100-res['DC'][0], color="#00ffa3")
        dual_bar_explicit(f"X2 ({nv_manual} o Empate)", res['DC'][1], "1 Directo", 100-res['DC'][1], color="#d4af37")
        dual_bar_explicit(f"12 (Cualquiera Gana)", res['DC'][2], "Empate", 100-res['DC'][2], color="#ffffff")
    with t4:
        ta, co = st.columns(2)
        with ta:
            st.markdown("<h5 style='color:#ff4b4b; text-align:center;'>PROYECCIÓN DE TARJETAS</h5>", unsafe_allow_html=True)
            for l, p in res['TARJETAS'].items(): dual_bar_explicit(f"Tarjetas > {l}", p[0], f"< {l}", p[1], color="#ff4b4b")
        with co:
            st.markdown("<h5 style='color:#00ffa3; text-align:center;'>PROYECCIÓN DE CORNER</h5>", unsafe_allow_html=True)
            for l, p in res['CORNERS'].items(): dual_bar_explicit(f"Corners > {l}", p[0], f"< {l}", p[1], color="#00ffa3")
    with t5:
        # MAPA DE CALOR MEJORADO E INTUITIVO
        df_matriz = pd.DataFrame(res['MATRIZ'], 
                                 index=[f"{i}" for i in range(6)], 
                                 columns=[f"{j}" for j in range(6)])
        
        fig = px.imshow(df_matriz, 
                        labels=dict(x=f"Goles {nv_manual}", y=f"Goles {nl_manual}", color="% Prob."),
                        color_continuous_scale=['#05070a', '#1a332d', '#00ffa3', '#d4af37'], 
                        text_auto=".1f",
                        aspect="equal")

        fig.update_layout(
            title={'text': "MATRIZ DE PROBABILIDAD DE MARCADOR", 'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'},
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)', 
            font=dict(family="JetBrains Mono", color="#eee", size=12),
            xaxis=dict(side="bottom", title=f"GOLES VISITANTE ({nv_manual})", gridcolor="#222"),
            yaxis=dict(title=f"GOLES LOCAL ({nl_manual})", gridcolor="#222"),
            coloraxis_colorbar=dict(title="%", thickness=15)
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>SYSTEM AUTHENTICATED | FUZZY SEARCH ENABLED | OR936 ELITE v3.5</p>", unsafe_allow_html=True)
