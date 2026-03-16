import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

# Inicializar estados de sesión para que la UI no se rompa
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.0
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.3

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
# 3. INTERFAZ Y LÓGICA DE BÚSQUEDA
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

# Estilos visuales mantenidos
st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; margin-bottom: 5px; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.title("GOLD TERMINAL")
    st.write("---")
    st.subheader("🔍 BUSCADOR")
    t1_query = st.text_input("Local", placeholder="Ej: Real Madrid")
    t2_query = st.text_input("Visita", placeholder="Ej: Liverpool")

    if st.button("SINCRONIZAR"):
        # Búsqueda simple de equipos (El método más estable de la API 123)
        def fetch_team(name):
            try:
                r = requests.get(f"{BASE_URL}searchteams.php?t={name}").json()
                return r['teams'][0] if r.get('teams') else None
            except: return None

        res1, res2 = fetch_team(t1_query), fetch_team(t2_query)
        if res1 and res2:
            st.session_state['nl_auto'], st.session_state['nv_auto'] = res1['strTeam'], res2['strTeam']
            st.success(f"Equipos encontrados: {res1['strTeam']} vs {res2['strTeam']}")
            # Nota: No buscamos tabla de posiciones aquí porque la API 123 la bloquea frecuentemente
            st.rerun()
        else:
            st.error("No se hallaron los equipos.")

# Pantalla Principal
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Nombre Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Goles Favor L", value=st.session_state['lgf_auto'], step=0.1)
    lgc = st.number_input("Goles Contra L", value=st.session_state['lgc_auto'], step=0.1)
with c2:
    nv = st.text_input("Nombre Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("Goles Favor V", value=st.session_state['vgf_auto'], step=0.1)
    vgc = st.number_input("Goles Contra V", value=st.session_state['vgc_auto'], step=0.1)

media_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR PREDICCIÓN"):
    motor = MotorMatematico(media_liga)
    # Cálculo de XG (Expected Goals)
    xg_l = (lgf/media_liga)*(vgc/media_liga)*media_liga * 1.1 # +10% ventaja local
    xg_v = (vgf/media_liga)*(lgc/media_liga)*media_liga * 0.9 # -10% desventaja visita
    
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 SUGERENCIAS")
        st.write(f"✅ **1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **X2**: {res['DC'][1]:.1f}%")
        st.write(f"✅ **Ambos Anotan**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **Probabilidades 1X2**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Magma', labels=dict(x="Goles V", y="Goles L")), use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5</p>", unsafe_allow_html=True)
