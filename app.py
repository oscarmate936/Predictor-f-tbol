import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from fuzzywuzzy import process

# =================================================================
# 1. CONFIGURACIÓN API (THESPORTSDB) & ESTADO
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = ""
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = ""

# Defaults del motor matemático
for key, val in {'lgf_auto': 1.5, 'lgc_auto': 1.0, 'vgf_auto': 1.2, 'vgc_auto': 1.3, 'p_liga_auto': 2.5, 'hfa_league': 1.1}.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE BÚSQUEDA (BYPASS PARA API GRATUITA)
# =================================================================

def search_team_stats(team_name):
    # Paso 1: Buscar el ID del equipo por nombre
    search = requests.get(f"{BASE_URL}searchteams.php?t={team_name}").json()
    if not search or not search.get('teams'): return None
    
    team = search['teams'][0]
    t_id = team['idTeam']
    
    # Paso 2: Buscar su liga y posición para sacar goles
    # Nota: Usamos la tabla de la liga principal del equipo (ej. Premier League)
    l_id = team['idLeague']
    table = requests.get(f"{BASE_URL}lookuptable.php?l={l_id}&s=2024-2025").json() # Temporada actual
    
    if table and table.get('table'):
        stats = next((t for t in table['table'] if t['idTeam'] == t_id), None)
        return stats
    return None

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM (SIN TOCAR LÓGICA)
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

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}

        for i in range(8): 
            fila = []
            for j in range(8):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
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

        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz[:6]
        }

# =================================================================
# 4. DISEÑO UI/UX (ESTILOS ELITE)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")
st.markdown("""<style>
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    .stApp { background: var(--bg); color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: rgba(20,25,35,0.9); padding: 30px; border-radius: 20px; border: 1px solid rgba(212, 175, 55, 0.2); }
    .score-badge { background: #000; padding: 12px; border-radius: 12px; border: 1px solid var(--primary); text-align: center; color: var(--primary); font-weight: 800; margin-bottom: 8px;}
</style>""", unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR - BUSCADOR INTELIGENTE
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    st.info("Escribe el nombre del equipo y presiona 'SYNC'")
    
    t_local = st.text_input("Buscar Local (Ej: Real Madrid)")
    t_visita = st.text_input("Buscar Visita (Ej: Barcelona)")

    if st.button("🚀 SYNC DATA"):
        with st.spinner("Buscando estadísticas..."):
            sl = search_team_stats(t_local)
            sv = search_team_stats(t_visita)
            
            if sl and sv:
                st.session_state['nl_auto'], st.session_state['nv_auto'] = sl['strTeam'], sv['strTeam']
                pj_l, pj_v = max(1, int(sl['intPlayed'])), max(1, int(sv['intPlayed']))
                st.session_state['lgf_auto'] = float(sl['intGoalsFor']) / pj_l
                st.session_state['lgc_auto'] = float(sl['intGoalsAgainst']) / pj_l
                st.session_state['vgf_auto'] = float(sv['intGoalsFor']) / pj_v
                st.session_state['vgc_auto'] = float(sv['intGoalsAgainst']) / pj_v
                st.success("Equipos sincronizados con éxito.")
                st.rerun()
            else:
                st.error("No se encontró alguno de los equipos. Revisa la ortografía.")

# =================================================================
# 6. CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("Goles Favor L", value=st.session_state['lgf_auto'])
    lgc = st.number_input("Goles Contra L", value=st.session_state['lgc_auto'])
with c2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("Goles Favor V", value=st.session_state['vgf_auto'])
    vgc = st.number_input("Goles Contra V", value=st.session_state['vgc_auto'])

p_liga = st.slider("Media Goles Liga", 1.0, 4.0, value=st.session_state['p_liga_auto'])

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(p_liga)
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * st.session_state['hfa_league']
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/st.session_state['hfa_league'])
    res = motor.procesar(xg_l, xg_v, 4.5, 9.5)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 TOP SELECCIONES")
        pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "Ambos Anotan", "p": res['BTTS'][0]}]
        for s in sorted(pool, key=lambda x: x['p'], reverse=True):
            st.markdown(f"✅ **{s['t']}**: {s['p']:.1f}%")
    with v2:
        st.subheader("🎯 MARCADORES")
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Matriz y Gráficos
    t1, t2 = st.tabs(["📊 Probabilidades", "🧩 Matriz Quantum"])
    with t1:
        st.write(f"Probabilidad 1X2: **L: {res['1X2'][0]:.1f}% | E: {res['1X2'][1]:.1f}% | V: {res['1X2'][2]:.1f}%**")
        for l in [1.5, 2.5, 3.5]:
            st.write(f"Over {l}: {res['GOLES'][l][0]:.1f}% | Under {l}: {res['GOLES'][l][1]:.1f}%")
    with t2:
        fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Viridis')
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #333;'>SYSTEM AUTHENTICATED | THESPORTSDB ENGINE v4.5</p>", unsafe_allow_html=True)
