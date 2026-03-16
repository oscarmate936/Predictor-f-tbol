import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import urllib.parse
from fuzzywuzzy import process

# =================================================================
# 1. CONFIGURACIÓN API (THESPORTSDB FREE) & ESTADO
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

# Inicialización de estados para evitar errores de Streamlit
state_keys = {
    'nl_auto': "Local", 'nv_auto': "Visitante",
    'lgf_auto': 1.5, 'lgc_auto': 1.0, 
    'vgf_auto': 1.2, 'vgc_auto': 1.3,
    'p_liga_auto': 2.5, 'hfa_league': 1.1,
    'elo_bias': (1.0, 1.0), 'h2h_bias': (1.0, 1.0)
}
for key, val in state_keys.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE EXTRACCIÓN (MÉTODO COMPATIBLE FREE)
# =================================================================

def get_team_data(name):
    try:
        # Paso 1: Buscar ID del equipo (Este método es libre en la API 123)
        r = requests.get(f"{BASE_URL}searchteams.php?t={name}", timeout=5).json()
        if not r or not r.get('teams'): return None
        team = r['teams'][0]
        t_id = team['idTeam']
        l_id = team['idLeague']
        
        # Paso 2: Intentar traer stats de la tabla
        table_r = requests.get(f"{BASE_URL}lookuptable.php?l={l_id}&s=2024-2025", timeout=5).json()
        if table_r and table_r.get('table'):
            stats = next((t for t in table_r['table'] if t['idTeam'] == t_id), None)
            if stats:
                pj = max(1, int(stats['intPlayed']))
                return {
                    'name': stats['strTeam'],
                    'gf': float(stats['intGoalsFor']) / pj,
                    'gc': float(stats['intGoalsAgainst']) / pj
                }
        return {'name': team['strTeam'], 'gf': 1.5, 'gc': 1.0} # Fallback si la tabla está bloqueada
    except: return None

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM (DIXON-COLES V4.5)
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

    def procesar(self, xg_l, xg_v):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [1.5, 2.5, 3.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}

        for i in range(7): 
            fila = []
            for j in range(7):
                p = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            matriz.append(fila)

        total = p1 + px + p2
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz[:6]
        }

# =================================================================
# 4. DISEÑO UI/UX (ESTILOS)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")
st.markdown("""
    <style>
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    .stApp { background: var(--bg); color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid rgba(212, 175, 55, 0.2); margin-bottom: 20px; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid var(--primary); text-align: center; color: var(--primary); font-weight: 800; margin-bottom: 5px; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR - BUSCADOR DE EQUIPOS
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    st.write("---")
    st.subheader("🔍 BUSCADOR DE EQUIPOS")
    search_l = st.text_input("Equipo Local (Ej: Real Madrid)")
    search_v = st.text_input("Equipo Visita (Ej: Liverpool)")

    if st.button("⚡ SINCRONIZAR DATOS"):
        with st.spinner("Buscando en la base de datos..."):
            res_l = get_team_data(search_l)
            res_v = get_team_data(search_v)
            if res_l and res_v:
                st.session_state['nl_auto'] = res_l['name']
                st.session_state['nv_auto'] = res_v['name']
                st.session_state['lgf_auto'] = res_l['gf']
                st.session_state['lgc_auto'] = res_l['gc']
                st.session_state['vgf_auto'] = res_v['gf']
                st.session_state['vgc_auto'] = res_v['gc']
                st.success("Sincronización lista")
                st.rerun()
            else:
                st.error("No se encontraron resultados. Intenta con nombres en inglés.")

# =================================================================
# 6. CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Promedio Goles Favor L", value=st.session_state['lgf_auto'])
    lgc = st.number_input("Promedio Goles Contra L", value=st.session_state['lgc_auto'])
with col2:
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("Promedio Goles Favor V", value=st.session_state['vgf_auto'])
    vgc = st.number_input("Promedio Goles Contra V", value=st.session_state['vgc_auto'])

p_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, value=st.session_state['p_liga_auto'])

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(p_liga)
    # Cálculo de XG basado en fortalezas y debilidades
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * st.session_state['hfa_league']
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/st.session_state['hfa_league'])
    
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 PICKS SUGERIDOS")
        pool = [{"t": "1X (Local o Empate)", "p": res['DC'][0]}, {"t": "X2 (Visita o Empate)", "p": res['DC'][1]}, {"t": "Ambos Anotan", "p": res['BTTS'][0]}]
        for s in sorted(pool, key=lambda x: x['p'], reverse=True):
            st.markdown(f"🔹 **{s['t']}**: {s['p']:.1f}%")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📊 Probabilidades", "🧩 Matriz de Goles"])
    with t1:
        st.write(f"**Resultado 1X2:** L: {res['1X2'][0]:.1f}% | E: {res['1X2'][1]:.1f}% | V: {res['1X2'][2]:.1f}%")
        for l in [1.5, 2.5, 3.5]:
            st.write(f"**Línea {l}:** Over {res['GOLES'][l][0]:.1f}% | Under {res['GOLES'][l][1]:.1f}%")
    with t2:
        fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Viridis', labels=dict(x="Goles Visita", y="Goles Local"))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #333;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5</p>", unsafe_allow_html=True)