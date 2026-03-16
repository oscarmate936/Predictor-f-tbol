import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests

# =================================================================
# 1. CONFIGURACIÓN API (CON IDENTIDAD DE NAVEGADOR)
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"
# Engañamos a la API para que piense que somos un navegador Chrome
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.0
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.3
if 'l_badge' not in st.session_state: st.session_state['l_badge'] = None
if 'v_badge' not in st.session_state: st.session_state['v_badge'] = None

# =================================================================
# 2. MOTOR MATEMÁTICO QUANTUM (DIXON-COLES)
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
    .stApp { background: #05070a; color: #e0e0e0; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; margin-bottom: 20px; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 12px; height: 50px; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    st.write("---")
    st.subheader("🔍 BUSCADOR DE EQUIPOS")
    t1_q = st.text_input("Equipo Local (Ej: Real Madrid)")
    t2_q = st.text_input("Equipo Visita (Ej: Liverpool)")

    if st.button("⚡ SINCRONIZAR"):
        with st.spinner("Cargando datos deportivos..."):
            def get_team_info(name):
                try:
                    # Búsqueda de equipo (Método estable de la V1)
                    res = requests.get(f"{BASE_URL}searchteams.php?t={name}", headers=HEADERS).json()
                    if not res or not res.get('teams'): return None
                    
                    team = res['teams'][0]
                    data = {
                        'name': team['strTeam'],
                        'badge': team['strBadge'],
                        'gf': 1.5, 'gc': 1.0 # Valores base si la tabla falla
                    }
                    
                    # Intentamos sacar goles de la tabla (Solo ligas principales en cuenta free)
                    table_res = requests.get(f"{BASE_URL}lookuptable.php?l={team['idLeague']}&s=2024-2025", headers=HEADERS).json()
                    if table_res and table_res.get('table'):
                        stats = next((x for x in table_res['table'] if x['idTeam'] == team['idTeam']), None)
                        if stats:
                            pj = max(1, int(stats['intPlayed']))
                            data['gf'] = int(stats['intGoalsFor']) / pj
                            data['gc'] = int(stats['intGoalsAgainst']) / pj
                    return data
                except: return None

            d1, d2 = get_team_info(t1_q), get_team_info(t2_q)
            if d1:
                st.session_state.update({'nl_auto': d1['name'], 'lgf_auto': d1['gf'], 'lgc_auto': d1['gc'], 'l_badge': d1['badge']})
            if d2:
                st.session_state.update({'nv_auto': d2['name'], 'vgf_auto': d2['gf'], 'vgc_auto': d2['gc'], 'v_badge': d2['badge']})
            
            if d1 or d2:
                st.success("Sincronización terminada")
                st.rerun()
            else:
                st.error("No se encontraron equipos.")

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

# Sección de Escudos Optimizada
b_col1, b_col2, b_col3 = st.columns([1, 2, 1])
with b_col1:
    if st.session_state['l_badge']: st.image(st.session_state['l_badge'], width=120)
with b_col3:
    if st.session_state['v_badge']: st.image(st.session_state['v_badge'], width=120)

st.write("---")

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Equipo Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF Local", value=st.session_state['lgf_auto'])
    lgc = st.number_input("GC Local", value=st.session_state['lgc_auto'])
with col2:
    nv = st.text_input("Equipo Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF Visita", value=st.session_state['vgf_auto'])
    vgc = st.number_input("GC Visita", value=st.session_state['vgc_auto'])

p_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(p_liga)
    # xg_l y xg_v con factor de localía (1.1)
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * 1.1 
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * 0.9 
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 PICKS SUGERIDOS")
        st.write(f"✅ **Doble Oportunidad 1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **Ambos Anotan (SÍ)**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **Probabilidades**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Turbo', labels=dict(x="Goles V", y="Goles L"))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5</p>", unsafe_allow_html=True)
