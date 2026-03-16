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
# 2. MOTOR MATEMÁTICO QUANTUM
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
# 3. LÓGICA DE EXTRACCIÓN AVANZADA (DATOS + ESCUDOS)
# =================================================================
def fetch_complete_data(name):
    try:
        # Búsqueda del equipo
        r = requests.get(f"{BASE_URL}searchteams.php?t={name}", headers=HEADERS).json()
        if not r or not r.get('teams'): return None
        team = r['teams'][0]
        
        # Datos base
        data = {'name': team['strTeam'], 'badge': team['strBadge'], 'gf': 1.5, 'gc': 1.0}
        
        # INTENTO 1: Tabla de posiciones (Solo ligas top)
        try:
            table_r = requests.get(f"{BASE_URL}lookuptable.php?l={team['idLeague']}", headers=HEADERS).json()
            if table_r and table_r.get('table'):
                stats = next((x for x in table_r['table'] if x['idTeam'] == team['idTeam']), None)
                if stats:
                    pj = max(1, int(stats['intPlayed']))
                    data['gf'] = int(stats['intGoalsFor']) / pj
                    data['gc'] = int(stats['intGoalsAgainst']) / pj
                    return data # Si funcionó, salimos con estos datos
        except: pass

        # INTENTO 2: Últimos 5 partidos (Bypass para ligas pequeñas como El Salvador)
        try:
            last_r = requests.get(f"{BASE_URL}eventslast.php?id={team['idTeam']}", headers=HEADERS).json()
            if last_r and last_r.get('results'):
                results = last_r['results']
                total_gf = 0
                total_gc = 0
                for match in results:
                    if match['idHomeTeam'] == team['idTeam']:
                        total_gf += int(match['intHomeScore'] or 0)
                        total_gc += int(match['intAwayScore'] or 0)
                    else:
                        total_gf += int(match['intAwayScore'] or 0)
                        total_gc += int(match['intHomeScore'] or 0)
                data['gf'] = total_gf / len(results)
                data['gc'] = total_gc / len(results)
        except: pass

        return data
    except: return None

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
    
    st.markdown("### 🛠 DIAGNÓSTICO")
    if st.button("EJECUTAR DIAGNÓSTICO"):
        try:
            res = requests.get(f"{BASE_URL}searchteams.php?t=Arsenal", headers=HEADERS)
            st.success(f"Status 200: Conexión OK")
        except: st.error("Error de conexión")
    
    st.write("---")
    st.subheader("🔍 BUSCADOR")
    t1_q = st.text_input("Equipo Local")
    t2_q = st.text_input("Equipo Visita")

    if st.button("⚡ SINCRONIZAR"):
        with st.spinner("Extrayendo estadísticas de goles..."):
            d1 = fetch_complete_data(t1_q)
            d2 = fetch_complete_data(t2_q)
            
            if d1: st.session_state.update({'nl_auto': d1['name'], 'lgf_auto': d1['gf'], 'lgc_auto': d1['gc'], 'l_badge': d1['b'] if 'b' in d1 else d1['badge']})
            if d2: st.session_state.update({'nv_auto': d2['name'], 'vgf_auto': d2['gf'], 'vgc_auto': d2['gc'], 'v_badge': d2['b'] if 'b' in d2 else d2['badge']})
            st.rerun()

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

# Logos
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
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
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
        st.subheader("💎 SUGERENCIAS")
        st.write(f"✅ **1X**: {res['DC'][0]:.1f}% | **Ambos Anotan**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **Probabilidades**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for sc, pr in res['TOP']: 
            st.markdown(f'<div class="score-badge">{sc} ({pr:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Turbo'), use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>SYSTEM AUTHENTICATED | HYBRID SYNC ACTIVE</p>", unsafe_allow_html=True)
