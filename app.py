import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests

# =================================================================
# 1. CONFIGURACIÓN API (IDS ACTUALIZADOS A THESPORTSDB)
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

# Mapeo de IDs reales de TheSportsDB para evitar errores
LIGAS_IDS = {
    "Premier League (UK)": "4328",
    "La Liga (ES)": "4335",
    "Serie A (IT)": "4332",
    "Bundesliga (DE)": "4331",
    "Ligue 1 (FR)": "4334",
    "Brasileirão (BR)": "4351",
    "Liga Mayor (ES)": "4645",
    "Saudi Pro League": "4622"
}

# Inicialización de estados
for key, val in {'nl_auto': "Local", 'nv_auto': "Visitante", 'lgf_auto': 1.5, 'lgc_auto': 1.0, 'vgf_auto': 1.2, 'vgc_auto': 1.3}.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. MOTOR MATEMÁTICO QUANTUM (SIN CAMBIOS EN LÓGICA)
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
# 3. INTERFAZ Y SYNC DE DATOS
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 12px; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.title("GOLD TERMINAL")
    liga_nombre = st.selectbox("Seleccionar Liga", list(LIGAS_IDS.keys()))
    l_id = LIGAS_IDS[liga_nombre]
    
    st.write("---")
    t1_q = st.text_input("Equipo Local", placeholder="Ej: Real Madrid")
    t2_q = st.text_input("Equipo Visitante", placeholder="Ej: Barcelona")

    if st.button("⚡ SYNC QUANTUM"):
        with st.spinner("Buscando IDs y Estadísticas..."):
            # 1. Traer la tabla de la liga seleccionada
            res = requests.get(f"{BASE_URL}lookuptable.php?l={l_id}&s=2024-2025").json()
            if res and res.get('table'):
                table = res['table']
                # Buscar equipos en la tabla (case insensitive)
                stats_l = next((t for t in table if t1_q.lower() in t['strTeam'].lower()), None)
                stats_v = next((t for t in table if t2_q.lower() in t['strTeam'].lower()), None)

                if stats_l and stats_v:
                    pj_l, pj_v = max(1, int(stats_l['intPlayed'])), max(1, int(stats_v['intPlayed']))
                    st.session_state.update({
                        'nl_auto': stats_l['strTeam'], 'nv_auto': stats_v['strTeam'],
                        'lgf_auto': int(stats_l['intGoalsFor'])/pj_l, 'lgc_auto': int(stats_l['intGoalsAgainst'])/pj_l,
                        'vgf_auto': int(stats_v['intGoalsFor'])/pj_v, 'vgc_auto': int(stats_v['intGoalsAgainst'])/pj_v
                    })
                    st.success("Sincronización Exitosa")
                    st.rerun()
                else:
                    st.error("No se encontraron los equipos en esta liga. Revisa el nombre.")
            else:
                st.error("La API no devolvió datos para esta liga (Límite Free).")

# PANTALLA PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Promedio Goles L", value=st.session_state['lgf_auto'])
with col2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("Promedio Goles V", value=st.session_state['vgf_auto'])

media_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR REPORTE"):
    motor = MotorMatematico(media_liga)
    # xg_l y xg_v simplificados para el reporte
    xg_l = (lgf / media_liga) * media_liga * 1.1
    xg_v = (vgf / media_liga) * media_liga * 0.9
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
    
    st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Inferno'), use_container_width=True)
