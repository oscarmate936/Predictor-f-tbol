import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import time

# =================================================================
# 1. CONFIGURACIÓN API & IDENTIDAD
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# Estados de sesión
state_keys = ['nl_auto', 'nv_auto', 'lgf_auto', 'lgc_auto', 'vgf_auto', 'vgc_auto', 'l_badge', 'v_badge']
defaults = ["Local", "Visitante", 1.5, 1.0, 1.2, 1.3, None, None]
for key, val in zip(state_keys, defaults):
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. DIAGNÓSTICO DE SALUD (ACTUALIZADO)
# =================================================================
def run_api_diagnostic():
    test_url = f"{BASE_URL}searchteams.php?t=Arsenal"
    start_time = time.time()
    try:
        res = requests.get(test_url, headers=HEADERS, timeout=7)
        latency = round((time.time() - start_time) * 1000, 2)
        if res.status_code == 200:
            return "✅ ONLINE", f"Status 200 | {latency}ms | Datos: OK"
        return "❌ OFFLINE", f"Error {res.status_code}"
    except: return "🚨 ERROR RED", "Fallo de conexión"

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM
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
# 4. UI Y SIDEBAR
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; margin-bottom: 20px; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.title("TERMINAL DE ORO")
    
    st.markdown("### 🛠 MÓDULO DE SALUD API")
    if st.button("EJECUTAR DIAGNÓSTICO"):
        status, detail = run_api_diagnostic()
        st.markdown(f"**Sistema:** {status}")
        st.info(detail)
    
    st.write("---")
    st.subheader("🔍 BUSCADOR DE EQUIPOS")
    t1_q = st.text_input("Local", placeholder="Ej: Real Madrid")
    t2_q = st.text_input("Visita", placeholder="Ej: Liverpool")

    if st.button("⚡ SINCRONIZAR"):
        with st.spinner("Buscando..."):
            def fetch(name):
                try:
                    r = requests.get(f"{BASE_URL}searchteams.php?t={name}", headers=HEADERS).json()
                    if r and r.get('teams'):
                        team = r['teams'][0]
                        data = {'n': team['strTeam'], 'b': team['strBadge'], 'gf': 1.5, 'gc': 1.0}
                        
                        # Intento de tabla (Solo para ligas destacadas)
                        try:
                            t_url = f"{BASE_URL}lookuptable.php?l={team['idLeague']}&s=2024-2025"
                            table = requests.get(t_url, headers=HEADERS).json()
                            if table and table.get('table'):
                                s = next((x for x in table['table'] if x['idTeam'] == team['idTeam']), None)
                                if s:
                                    pj = max(1, int(s['intPlayed']))
                                    data['gf'] = int(s['intGoalsFor'])/pj
                                    data['gc'] = int(s['intGoalsAgainst'])/pj
                        except: pass 
                        return data
                except: return None

            d1, d2 = fetch(t1_q), fetch(t2_q)
            if d1: st.session_state.update({'nl_auto': d1['n'], 'lgf_auto': d1['gf'], 'lgc_auto': d1['gc'], 'l_badge': d1['b']})
            if d2: st.session_state.update({'nv_auto': d2['n'], 'vgf_auto': d2['gf'], 'vgc_auto': d2['gc'], 'v_badge': d2['b']})
            st.rerun()

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

# Sección de Escudos
b1, b2, b3 = st.columns([1, 2, 1])
with b1:
    if st.session_state['l_badge']: st.image(st.session_state['l_badge'], width=100)
with b3:
    if st.session_state['v_badge']: st.image(st.session_state['v_badge'], width=100)

st.write("---")

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Goles Favor L", value=float(st.session_state['lgf_auto']), step=0.1)
    lgc = st.number_input("Goles Contra L", value=float(st.session_state['lgc_auto']), step=0.1)
with col2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("Goles Favor V", value=float(st.session_state['vgf_auto']), step=0.1)
    vgc = st.number_input("Goles Contra V", value=float(st.session_state['vgc_auto']), step=0.1)

media_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR PREDICCIÓN"):
    motor = MotorMatematico(media_liga)
    xg_l = (lgf/media_liga)*(vgc/media_liga)*media_liga * 1.1 
    xg_v = (vgf/media_liga)*(lgc/media_liga)*media_liga * 0.9 
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 PICKS SUGERIDOS")
        st.write(f"✅ **Doble Oportunidad 1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **Ambos Anotan**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **Probabilidades 1X2**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for sc, pr in res['TOP']: 
            st.markdown(f'<div class="score-badge">{sc} ({pr:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Turbo'), use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>SYSTEM AUTHENTICATED | MOMENTUM WEIGHTING ACTIVE</p>", unsafe_allow_html=True)
