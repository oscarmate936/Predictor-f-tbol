import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests

# =================================================================
# 1. CONFIGURACIÓN API (TOTALMENTE AJUSTADA A KEY 123)
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

# IDs correctos de TheSportsDB
LIGAS_IDS = {
    "Premier League (Inglaterra)": "4328",
    "La Liga (España)": "4335",
    "Serie A (Italia)": "4332",
    "Bundesliga (Alemania)": "4331",
    "Ligue 1 (Francia)": "4334",
    "Liga Mayor (El Salvador)": "4645",
    "Brasileirão (Brasil)": "4351"
}

# Inicializar memoria del programa
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.0
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.3

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
# 3. INTERFAZ Y LÓGICA DE SINCRONIZACIÓN
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 12px; height: 50px; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    st.write("---")
    
    liga_sel = st.selectbox("1. Elige la Competición", list(LIGAS_IDS.keys()))
    id_liga = LIGAS_IDS[liga_sel]
    
    st.write("---")
    st.subheader("2. Busca los Equipos")
    nombre_l = st.text_input("Equipo Local", placeholder="Ej: Real Madrid o Alianza")
    nombre_v = st.text_input("Equipo Visita", placeholder="Ej: Barcelona o FAS")

    if st.button("⚡ SYNC DATA"):
        with st.spinner("Conectando con TheSportsDB..."):
            try:
                # Paso A: Intentar buscar equipos por nombre (Método más estable en la llave 123)
                def buscar_equipo(q):
                    r = requests.get(f"{BASE_URL}searchteams.php?t={q}").json()
                    return r['teams'][0] if r and r.get('teams') else None

                t1, t2 = buscar_equipo(nombre_l), buscar_equipo(nombre_v)

                if t1 and t2:
                    st.session_state['nl_auto'] = t1['strTeam']
                    st.session_state['nv_auto'] = t2['strTeam']
                    
                    # Paso B: Intentar traer la tabla para los goles (Si la llave 123 lo permite)
                    # Temporada 2024-2025 es la más estable ahora
                    tabla_res = requests.get(f"{BASE_URL}lookuptable.php?l={id_liga}&s=2024-2025").json()
                    
                    if tabla_res and tabla_res.get('table'):
                        def extract(tid, table):
                            s = next((x for x in table if x['idTeam'] == tid), None)
                            if s:
                                pj = max(1, int(s['intPlayed']))
                                return int(s['intGoalsFor'])/pj, int(s['intGoalsAgainst'])/pj
                            return 1.5, 1.0
                        
                        l_gf, l_gc = extract(t1['idTeam'], tabla_res['table'])
                        v_gf, v_gc = extract(t2['idTeam'], tabla_res['table'])
                        
                        st.session_state['lgf_auto'] = l_gf
                        st.session_state['lgc_auto'] = l_gc
                        st.session_state['vgf_auto'] = v_gf
                        st.session_state['vgc_auto'] = v_gc
                        st.success("Sincronización Completa: Nombres y Goles.")
                    else:
                        st.warning("Nombres encontrados, pero la tabla de goles está bloqueada por la API gratuita. Por favor, ingresa los promedios manualmente.")
                    st.rerun()
                else:
                    st.error("No se encontraron los equipos. Prueba escribiendo el nombre exacto.")
            except Exception as e:
                st.error("Error de conexión con la API.")

# PANTALLA PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Promedio Goles L", value=st.session_state['lgf_auto'], step=0.1)
    lgc = st.number_input("Promedio Goles Contra L", value=st.session_state['lgc_auto'], step=0.1)
with col2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("Promedio Goles V", value=st.session_state['vgf_auto'], step=0.1)
    vgc = st.number_input("Promedio Goles Contra V", value=st.session_state['vgc_auto'], step=0.1)

media_liga = st.slider("Media Goles Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(media_liga)
    xg_l = (lgf / media_liga) * (vgc / media_liga) * media_liga * 1.1 
    xg_v = (vgf / media_liga) * (lgc / media_liga) * media_liga * 0.9 
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 PREVISIÓN")
        st.write(f"✅ **Doble Oportunidad 1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **Ambos Anotan**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **1X2**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='YlGnBu'), use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5 | KEY: 123 MODE</p>", unsafe_allow_html=True)
