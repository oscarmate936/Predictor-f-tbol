import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import urllib.parse

# =================================================================
# 1. CONFIGURACIÓN API (SEGÚN DOCUMENTACIÓN THE SPORTS DB V1)
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

# Inicialización de estados de sesión (Persistencia de datos)
states = {
    'nl_auto': "Local", 'nv_auto': "Visitante",
    'lgf_auto': 1.5, 'lgc_auto': 1.0, 
    'vgf_auto': 1.2, 'vgc_auto': 1.3,
    'l_badge': None, 'v_badge': None
}
for key, val in states.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. MOTOR MATEMÁTICO QUANTUM (DIXON-COLES V4.5)
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
        for i in range(7): 
            fila = []
            for j in range(7):
                p = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            matriz.append(fila)
        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz[:6]
        }

# =================================================================
# 3. INTERFAZ Y LÓGICA DE DATOS
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; margin-bottom: 20px; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 12px; height: 50px; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    st.write("---")
    st.subheader("🔍 BUSCADOR DE EQUIPOS")
    local_q = st.text_input("Equipo Local (Ej: Arsenal)")
    visita_q = st.text_input("Equipo Visita (Ej: Liverpool)")

    if st.button("⚡ SINCRONIZAR"):
        with st.spinner("Conectando con la API..."):
            def fetch_team_logic(name):
                try:
                    # Búsqueda por nombre (V1)
                    r = requests.get(f"{BASE_URL}searchteams.php?t={name}").json()
                    if r and r.get('teams'):
                        team = r['teams'][0]
                        # Obtener URL del escudo (Badge)
                        badge_url = team.get('strBadge')
                        if badge_url: badge_url += "/preview" # Cambiado /small por /preview para mejor compatibilidad
                        
                        # Obtener tabla para GF/GC
                        table_res = requests.get(f"{BASE_URL}lookuptable.php?l={team['idLeague']}&s=2024-2025").json()
                        if table_res and table_res.get('table'):
                            s = next((x for x in table_res['table'] if x['idTeam'] == team['idTeam']), None)
                            if s:
                                pj = max(1, int(s['intPlayed']))
                                return {'n': team['strTeam'], 'gf': int(s['intGoalsFor'])/pj, 'gc': int(s['intGoalsAgainst'])/pj, 'b': badge_url}
                        return {'n': team['strTeam'], 'gf': 1.5, 'gc': 1.0, 'b': badge_url}
                except: return None
                return None

            d1, d2 = fetch_team_logic(local_q), fetch_team_logic(visita_q)
            if d1 or d2:
                if d1:
                    st.session_state['nl_auto'], st.session_state['lgf_auto'], st.session_state['lgc_auto'], st.session_state['l_badge'] = d1['n'], d1['gf'], d1['gc'], d1['b']
                if d2:
                    st.session_state['nv_auto'], st.session_state['vgf_auto'], st.session_state['vgc_auto'], st.session_state['v_badge'] = d2['n'], d2['gf'], d2['gc'], d2['b']
                st.success("Sincronización terminada")
                st.rerun()
            else: st.error("No se encontraron datos.")

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

# Sección de Escudos (Independiente)
badge_col1, badge_col2, badge_col3 = st.columns([1, 2, 1])
with badge_col1:
    if st.session_state['l_badge']: st.image(st.session_state['l_badge'], width=100)
with badge_col3:
    if st.session_state['v_badge']: st.image(st.session_state['v_badge'], width=100)

st.write("---")

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Promedio Goles L", value=st.session_state['lgf_auto'], step=0.1)
    lgc = st.number_input("Promedio GC L", value=st.session_state['lgc_auto'], step=0.1)
with col2:
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("Promedio Goles V", value=st.session_state['vgf_auto'], step=0.1)
    vgc = st.number_input("Promedio GC V", value=st.session_state['vgc_auto'], step=0.1)

media_liga = st.slider("Media Goles Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(media_liga)
    xg_l = (lgf/media_liga)*(vgc/media_liga)*media_liga * 1.1 
    xg_v = (vgf/media_liga)*(lgc/media_liga)*media_liga * 0.9 
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 PICKS")
        st.write(f"✅ **Doble Oportunidad 1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **Ambos Anotan (SÍ)**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **Probabilidades**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Magma')
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5</p>", unsafe_allow_html=True)
