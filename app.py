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
# CONFIGURACIÓN API & ESTADO
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

# Sincronización horaria absoluta para El Salvador (UTC-6)
tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Inicialización de estados
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

def api_request_direct(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY, "_cache": time.time()})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

@st.cache_data(ttl=300)
def get_standings_cached(league_id):
    return api_request_direct("get_standings", {"league_id": league_id})

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

        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))
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

# =================================================================
# SIDEBAR - SINCRONIZACIÓN MAESTRA
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
    
    fecha_sel = st.date_input("📅 JORNADA", value=ahora_sv.date())
    f_str = fecha_sel.strftime('%Y-%m-%d')

    # RANGO DE SEGURIDAD: Traer ayer, hoy y mañana para evitar desfases de la API
    f_inicio = (fecha_sel - timedelta(days=1)).strftime('%Y-%m-%d')
    f_fin = (fecha_sel + timedelta(days=1)).strftime('%Y-%m-%d')

    raw_events = api_request_direct("get_events", {"from": f_inicio, "to": f_fin, "league_id": ligas_api[nombre_liga]})
    
    # FILTRO ESTRICTO: Solo lo que coincide con el calendario visual
    eventos_hoy = [e for e in raw_events if e.get('match_date') == f_str]

    if eventos_hoy:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos_hoy}
        p_sel = st.selectbox("📍 Partidos Disponibles", list(op_p.keys()))
        
        # Sincronización automática de nombres al seleccionar
        match_data = op_p[p_sel]
        st.session_state['nl_auto'] = match_data['match_hometeam_name']
        st.session_state['nv_auto'] = match_data['match_awayteam_name']

        if st.button("CALIBRAR ESTADÍSTICAS"):
            with st.spinner("BUSCANDO DATOS..."):
                standings = get_standings_cached(ligas_api[nombre_liga])
                if standings:
                    def buscar_elite(n):
                        nombres = [t['team_name'] for t in standings]
                        match, score = process.extractOne(n, nombres)
                        return next((t for t in standings if t['team_name'] == match), None) if score > 60 else None

                    dl, dv = buscar_elite(st.session_state['nl_auto']), buscar_elite(st.session_state['nv_auto'])
                    if dl and dv:
                        pj_h, pj_a = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['lgf_auto'] = float(dl['home_league_GF'])/pj_h if pj_h>0 else 1.5
                        st.session_state['lgc_auto'] = float(dl['home_league_GA'])/pj_h if pj_h>0 else 1.0
                        st.session_state['vgf_auto'] = float(dv['away_league_GF'])/pj_a if pj_a>0 else 1.2
                        st.session_state['vgc_auto'] = float(dv['away_league_GA'])/pj_a if pj_a>0 else 1.3
                        st.rerun()
    else:
        st.error("No se encontraron partidos para hoy.")

# =================================================================
# CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>PREDICTIVE ENGINE V3.5 PRO • QUANTUM SYNC</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-right: 2px solid var(--secondary); text-align: right; padding-right: 15px; margin-bottom: 5px;'><h6 style='color:var(--secondary); margin:0; font-weight:900;'>LOCAL</h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("GF L", 0.0, 10.0, key='lgf_auto'), lb.number_input("GC L", 0.0, 10.0, key='lgc_auto')
    ltj, lco = la.number_input("Tj L", 0.0, 15.0, 2.3), lb.number_input("Co L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("<div style='border-left: 2px solid var(--primary); text-align: left; padding-left: 15px; margin-bottom: 5px;'><h6 style='color:var(--primary); margin:0; font-weight:900;'>VISITANTE</h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Nombre Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("GF V", 0.0, 10.0, key='vgf_auto'), vb.number_input("GC V", 0.0, 10.0, key='vgc_auto')
    vtj, vco = va.number_input("Tj V", 0.0, 15.0, 2.2), vb.number_input("Co V", 0.0, 20.0, 4.8)

p_liga = st.slider("Media de Goles de la Liga", 0.5, 5.0, key='p_liga_auto')
if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(league_avg=p_liga)
    res = motor.procesar(lgf, vgf, ltj+vtj, lco+vco)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    st.markdown(f"<h4 style='color:var(--primary); text-align:center;'>PROYECCIÓN: {res['TOP'][0][0]} (Confianza: {res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    t1, t2, t3, t4, t5 = st.tabs(["🥅 GOLES", "🏆 HANDICAP", "📊 1X2", "🚩 ESPECIALES", "🧩 MATRIZ"])
    with t4:
        c1, c2 = st.columns(2)
        c1.markdown("<h5 style='color:#ff4b4b; text-align:center;'>PROYECCIÓN DE TARJETAS</h5>", unsafe_allow_html=True)
        c2.markdown("<h5 style='color:#00ffa3; text-align:center;'>PROYECCIÓN DE CORNER</h5>", unsafe_allow_html=True)
    with t5:
        df_matriz = pd.DataFrame(res['MATRIZ'], index=[f"{i}" for i in range(6)], columns=[f"{j}" for j in range(6)])
        st.plotly_chart(px.imshow(df_matriz, color_continuous_scale=['#05070a', '#00ffa3', '#d4af37'], text_auto=".1f"), use_container_width=True)

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>OR936 ELITE v3.5 | SYNCED</p>", unsafe_allow_html=True)