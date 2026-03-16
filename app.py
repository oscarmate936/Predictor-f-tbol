import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import urllib.parse

# =================================================================
# 1. CONFIGURACIÓN API (THESPORTSDB FREE) & ESTADO
# =================================================================
# La clave '123' es solo para pruebas y tiene muchas restricciones.
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

# Inicializar estados de sesión para evitar errores de carga
for key, val in {
    'nl_auto': "Local", 'nv_auto': "Visitante",
    'lgf_auto': 1.5, 'lgc_auto': 1.0, 
    'vgf_auto': 1.2, 'vgc_auto': 1.3,
    'p_liga_auto': 2.5
}.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE BÚSQUEDA (BLINDADAS PARA VERSIÓN FREE)
# =================================================================

def fetch_team_data(name):
    """Busca un equipo y trata de obtener sus estadísticas básicas"""
    if not name or name in ["Local", "Visitante", ""]: return None
    try:
        # 1. Buscar el equipo para obtener su ID y Liga
        search_url = f"{BASE_URL}searchteams.php?t={name}"
        r = requests.get(search_url, timeout=5).json()
        if not r or not r.get('teams'): return None
        
        team = r['teams'][0]
        t_id = team['idTeam']
        l_id = team['idLeague']
        
        # 2. Intentar obtener la tabla de posiciones (esto falla mucho en la versión free)
        table_url = f"{BASE_URL}lookuptable.php?l={l_id}&s=2024-2025"
        tr = requests.get(table_url, timeout=5).json()
        
        if tr and tr.get('table'):
            stats = next((t for t in tr['table'] if t['idTeam'] == t_id), None)
            if stats:
                pj = max(1, int(stats['intPlayed']))
                return {
                    'name': stats['strTeam'],
                    'gf': float(stats['intGoalsFor']) / pj,
                    'gc': float(stats['intGoalsAgainst']) / pj
                }
        
        # Si la tabla está bloqueada, devolvemos solo el nombre encontrado
        return {'name': team['strTeam'], 'gf': 1.5, 'gc': 1.0}
    except:
        return None

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
# 4. DISEÑO UI/UX
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 12px; height: 50px; }
</style>""", unsafe_allow_html=True)

# SIDEBAR: BUSCADOR
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    st.write("---")
    st.subheader("🔍 BUSCADOR POR NOMBRE")
    query_l = st.text_input("Equipo Local", placeholder="Ej: Real Madrid")
    query_v = st.text_input("Equipo Visitante", placeholder="Ej: Liverpool")
    
    if st.button("⚡ SINCRONIZAR"):
        with st.spinner("Buscando equipos..."):
            data_l = fetch_team_data(query_l)
            data_v = fetch_team_data(query_v)
            
            if data_l and data_v:
                st.session_state['nl_auto'] = data_l['name']
                st.session_state['nv_auto'] = data_v['name']
                st.session_state['lgf_auto'] = data_l['gf']
                st.session_state['lgc_auto'] = data_l['gc']
                st.session_state['vgf_auto'] = data_v['gf']
                st.session_state['vgc_auto'] = data_v['gc']
                st.success("Sincronización Exitosa")
                st.rerun()
            else:
                st.error("No se encontraron los equipos. Intenta con nombres conocidos.")

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Promedio Goles Favor L", value=st.session_state['lgf_auto'], step=0.1)
    lgc = st.number_input("Promedio Goles Contra L", value=st.session_state['lgc_auto'], step=0.1)
with c2:
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("Promedio Goles Favor V", value=st.session_state['vgf_auto'], step=0.1)
    vgc = st.number_input("Promedio Goles Contra V", value=st.session_state['vgc_auto'], step=0.1)

media_liga = st.slider("Media Goles Liga", 1.0, 4.5, value=st.session_state['p_liga_auto'])

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(media_liga)
    # Cálculo de XG
    xg_l = (lgf/media_liga)*(vgc/media_liga)*media_liga * 1.1 
    xg_v = (vgf/media_liga)*(lgc/media_liga)*media_liga * 0.9 
    
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 PICKS SUGERIDOS")
        st.write(f"✅ **Doble Oportunidad 1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **Doble Oportunidad X2**: {res['DC'][1]:.1f}%")
        st.write(f"✅ **Ambos Anotan (SÍ)**: {res['BTTS'][0]:.1f}%")
        st.markdown(f"**Probabilidades 1X2:** L: {res['1X2'][0]:.1f}% | E: {res['1X2'][1]:.1f}% | V: {res['1X2'][2]:.1f}%")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div><br>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Matriz
    fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Portland', labels=dict(x="Goles Visita", y="Goles Local"))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5</p>", unsafe_allow_html=True)
