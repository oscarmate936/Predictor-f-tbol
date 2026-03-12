import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime
import urllib.parse
from fuzzywuzzy import fuzz, process

# =================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILO ELITE V2
# =================================================================
st.set_page_config(page_title="OR936 PRO ELITE", layout="wide", initial_sidebar_state="expanded")

# Inyección de CSS Avanzado
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');

    :root {
        --primary: #00ffa3;
        --secondary: #d4af37;
        --bg-dark: #0f1117;
        --card-bg: rgba(23, 28, 40, 0.8);
        --text-main: #e2e8f0;
    }

    /* Contenedor Principal */
    .stApp {
        background-color: var(--bg-dark);
        background-image: 
            radial-gradient(at 0% 0%, rgba(0, 255, 163, 0.05) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(212, 175, 55, 0.05) 0px, transparent 50%);
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Cards Estilo Glassmorphism */
    .glass-card {
        background: var(--card-bg);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 25px;
        margin-bottom: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }

    .metric-title {
        color: #64748b;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 1.5px;
        font-weight: 700;
        margin-bottom: 10px;
    }

    /* Botones Pro */
    .stButton>button {
        background: linear-gradient(135deg, var(--primary) 0%, #00d48a 100%) !important;
        color: #000 !important;
        border: none !important;
        padding: 12px 24px !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        width: 100%;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 255, 163, 0.3);
    }

    /* Inputs Estilizados */
    .stTextInput>div>div>input {
        background: rgba(0,0,0,0.2) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: white !important;
        border-radius: 10px !important;
    }

    /* Tabs Personalizados */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: rgba(255,255,255,0.03);
        border-radius: 10px 10px 0 0;
        color: #94a3b8;
        border: none;
        padding: 0 20px;
    }

    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 255, 163, 0.1) !important;
        color: var(--primary) !important;
        border-bottom: 2px solid var(--primary) !important;
    }

    /* Badges */
    .badge-elite {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 800;
        background: rgba(212, 175, 55, 0.1);
        color: var(--secondary);
        border: 1px solid var(--secondary);
    }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# LÓGICA DE NEGOCIO (MANTENIDA)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.0
if 'form_l' not in st.session_state: st.session_state['form_l'] = 1.0
if 'form_v' not in st.session_state: st.session_state['form_v'] = 1.0
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.7
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.2
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.5
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.1

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.15 if 2.2 <= league_avg <= 3.0 else (-0.10 if league_avg > 3.0 else -0.18)

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
        h_lines = [-1.5, -0.5, 0.5, 1.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}
        h_probs = {t: 0.0 for t in h_lines}

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
                    if (i + h) > j: h_probs[h] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        it = 10000
        sim_tj = np.random.poisson(tj_total, it)
        sim_co = np.random.poisson(co_total, it)
        
        return {
            "1X2": (p1*100, px*100, p2*100), 
            "DC": ((p1+px)*100, (p2+px)*100, (p1+p2)*100),
            "BTTS": (btts_si*100, (1-btts_si)*100), 
            "GOLES": {t: (p[0]*100, p[1]*100) for t, p in g_probs.items()},
            "HANDICAP": {t: p*100 for t, p in h_probs.items()},
            "TARJETAS": {t: (np.sum(sim_tj > t)/it*100, np.sum(sim_tj <= t)/it*100) for t in [3.5, 4.5, 5.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/it*100, np.sum(sim_co <= t)/it*100) for t in [7.5, 8.5, 9.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, 
            "CONFIANZA": 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))
        }

# =================================================================
# COMPONENTES VISUALES REDISEÑADOS
# =================================================================
def draw_probability_bar(label, prob, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 0.85rem; color: #94a3b8; font-weight: 600;">{label}</span>
                <span style="font-size: 0.85rem; color: white; font-weight: 800;">{prob:.1f}%</span>
            </div>
            <div style="background: rgba(255,255,255,0.05); height: 8px; border-radius: 10px; overflow: hidden;">
                <div style="width: {prob}%; background: {color}; height: 100%; box-shadow: 0 0 10px {color}44;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# ESTRUCTURA PRINCIPAL (LAYOUT)
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#00ffa3; font-weight:800;'>OR936 ENGINE</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748b; font-size:0.8rem;'>V3.5 PRO TERMINAL</p>", unsafe_allow_html=True)
    st.divider()
    
    ligas_api = {
        "Brasileirão Betano (Série A)": 99, "La Liga (España)": 302, "Premier League": 152, 
        "Serie A (Italia)": 207, "Bundesliga": 175, "Champions League": 3
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Seleccionar Partido", list(op_p.keys()))
        
        if st.button("SINCRONIZAR DATOS"):
            with st.spinner("Actualizando Smart Data..."):
                standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
                if standings:
                    def buscar_fuzzy(n, lista):
                        nombres = [t['team_name'] for t in lista]
                        match, score = process.extractOne(n, nombres, scorer=fuzz.token_set_ratio)
                        return next((t for t in lista if t['team_name'] == match), None) if score > 65 else None

                    dl = buscar_fuzzy(op_p[p_sel]['match_hometeam_name'], standings)
                    dv = buscar_fuzzy(op_p[p_sel]['match_awayteam_name'], standings)

                    if dl and dv:
                        st.session_state['nl_auto'] = dl['team_name']
                        st.session_state['nv_auto'] = dv['team_name']
                        pj_h = int(dl.get('home_league_played', 1))
                        pj_v = int(dv.get('away_league_played', 1))
                        st.session_state['lgf_auto'] = float(dl.get('home_league_GF', 0)) / pj_h
                        st.session_state['lgc_auto'] = float(dl.get('home_league_GA', 0)) / pj_h
                        st.session_state['vgf_auto'] = float(dv.get('away_league_GF', 0)) / pj_v
                        st.session_state['vgc_auto'] = float(dv.get('away_league_GA', 0)) / pj_v
                        st.rerun()

# --- HEADER PRINCIPAL ---
st.markdown("<h1 style='text-align: center; color: white; font-weight: 800; letter-spacing: -1px;'>Análisis <span style='color:#00ffa3'>Predictivo</span> Elite</h1>", unsafe_allow_html=True)

# --- ENTRADA DE DATOS (REDISEÑADA) ---
c1, c2, c3 = st.columns([1, 0.1, 1])

with c1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="badge-elite">LOCAL</div>', unsafe_allow_html=True)
    nl = st.text_input("Equipo", key='nl_auto', label_visibility="collapsed")
    i1, i2 = st.columns(2)
    lgf = i1.number_input("Goles Favor", 0.0, 5.0, step=0.1, key='lgf_auto')
    lgc = i2.number_input("Goles Contra", 0.0, 5.0, step=0.1, key='lgc_auto')
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="badge-elite" style="color:#d4af37; border-color:#d4af37;">VISITANTE</div>', unsafe_allow_html=True)
    nv = st.text_input("Equipo ", key='nv_auto', label_visibility="collapsed")
    i3, i4 = st.columns(2)
    vgf = i3.number_input("Goles Favor ", 0.0, 5.0, step=0.1, key='vgf_auto')
    vgc = i4.number_input("Goles Contra ", 0.0, 5.0, step=0.1, key='vgc_auto')
    st.markdown('</div>', unsafe_allow_html=True)

p_liga = st.slider("Media de la Liga", 1.0, 4.0, st.session_state['p_liga_auto'])

# --- GENERACIÓN ---
if st.button("REALIZAR CÁLCULO ESTADÍSTICO"):
    motor = MotorMatematico(p_liga)
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * st.session_state['hfa_league']
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, 4.5, 9.5)

    # --- RESULTADOS TOP ---
    st.markdown("### 💎 Smart Picks")
    col_res1, col_res2, col_res3 = st.columns(3)
    
    picks = [
        {"t": "Doble Oportunidad 1X", "p": res['DC'][0]},
        {"t": "Ambos Anotan", "p": res['BTTS'][0]},
        {"t": "Over 1.5 Goles", "p": res['GOLES'][1.5][0]}
    ]
    
    for i, p in enumerate(picks):
        with [col_res1, col_res2, col_res3][i]:
            st.markdown(f"""
                <div class="glass-card" style="text-align:center; border-top: 3px solid #00ffa3;">
                    <div class="metric-title">{p['t']}</div>
                    <div style="font-size: 2rem; font-weight: 800; color: white;">{p['p']:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)

    # --- DASHBOARD DE MERCADOS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Probabilidades 1X2", "🥅 Goles & BTTS", "🚩 Especiales", "📈 Matriz"])

    with tab1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        draw_probability_bar(f"Victoria {nl}", res['1X2'][0])
        draw_probability_bar("Empate", res['1X2'][1], "#94a3b8")
        draw_probability_bar(f"Victoria {nv}", res['1X2'][2], "#d4af37")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            for g in [1.5, 2.5, 3.5]:
                draw_probability_bar(f"Over {g}", res['GOLES'][g][0])
            st.markdown('</div>', unsafe_allow_html=True)
        with c_g2:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            draw_probability_bar("Ambos Anotan: SÍ", res['BTTS'][0])
            draw_probability_bar("Ambos Anotan: NO", res['BTTS'][1], "#ff4b4b")
            st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        c_e1, c_e2 = st.columns(2)
        with c_e1:
            st.markdown("<div class='metric-title'>Córners (Línea 8.5)</div>", unsafe_allow_html=True)
            draw_probability_bar("Over 8.5", res['CORNERS'][8.5][0])
        with c_e2:
            st.markdown("<div class='metric-title'>Tarjetas (Línea 4.5)</div>", unsafe_allow_html=True)
            draw_probability_bar("Over 4.5", res['TARJETAS'][4.5][0], "#ff4b4b")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        fig = px.imshow(res['MATRIZ'], 
                        labels=dict(x="Visitante", y="Local", color="Prob %"),
                        x=[str(i) for i in range(6)], y=[str(i) for i in range(6)],
                        color_continuous_scale='Viridis')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<p style='text-align:center; color:#475569; font-size:0.7rem; margin-top:50px;'>OR936 ELITE V3.5 - SISTEMA DE ALTA PRECISIÓN</p>", unsafe_allow_html=True) 
