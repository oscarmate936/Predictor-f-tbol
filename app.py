import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from fuzzywuzzy import process
import time

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO (DISEÑO ORIGINAL)
# =================================================================
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf081e5e5b62"
API_HOST = "free-api-live-football-data.p.rapidapi.com"
BASE_URL = "https://free-api-live-football-data.p.rapidapi.com"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Inicialización de estados
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2

# =================================================================
# 2. MOTOR DE EXTRACCIÓN INTELIGENTE (EL CORAZÓN DEL FIX)
# =================================================================

def api_request_rapid(endpoint, params=None):
    """Petición maestra con detección de estructura."""
    url = f"{BASE_URL}/{endpoint}"
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # La API puede devolver la lista en 'data', 'response' o directamente
            if isinstance(data, dict):
                for k in ['data', 'response', 'results']:
                    if k in data and data[k]: return data[k]
            return data if isinstance(data, list) else []
        return []
    except: return []

def smart_get(obj, *keys, default=0):
    """Busca un valor incluso si está anidado (ej: score.home)."""
    if not isinstance(obj, dict): return default
    for k in keys:
        # Intento de búsqueda directa o anidada
        if "." in k:
            parts = k.split(".")
            val = obj
            for p in parts:
                val = val.get(p, {}) if isinstance(val, dict) else {}
            if val != {}: return val
        elif k in obj and obj[k] is not None:
            return obj[k]
    return default

@st.cache_data(ttl=600)
def fetch_leagues():
    """Carga de ligas con mapeo de nombres."""
    res = api_request_rapid("football-get-all-leagues")
    return {l['league_name']: l['league_id'] for l in res if isinstance(l, dict) and 'league_id' in l}

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM (SIN CAMBIOS)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.12 # Calibración estándar

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def procesar(self, xg_l, xg_v):
        p1, px, p2, btts = 0.0, 0.0, 0.0, 0.0
        scores = {}
        for i in range(7):
            for j in range(7):
                p = self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts += p
                if i < 5 and j < 5: scores[f"{i}-{j}"] = p * 100
        total = p1 + px + p2
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "BTTS": (btts/total*100),
            "TOP": sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        }

# =================================================================
# 4. SIDEBAR & SINCRONIZACIÓN (DISEÑO ORIGINAL)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    .stApp { background: #05070a; color: #e0e0e0; }
    .master-card { background: #141923; padding: 25px; border-radius: 15px; border: 1px solid #d4af3744; margin-bottom: 20px; }
    .whatsapp-btn { background: #25D366; color: white !important; padding: 10px 20px; border-radius: 10px; text-decoration: none; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    # Botón de Status
    if st.button("📡 VERIFICAR API"):
        check = api_request_rapid("football-get-all-leagues")
        if check: st.success("CONECTADO: Datos recibidos")
        else: st.error("ERROR: No hay respuesta de la API")

    # Selectores
    leagues = fetch_leagues()
    if leagues:
        league_name = st.selectbox("🏆 Competición", list(leagues.keys()))
        league_id = leagues[league_name]
        date_sel = st.date_input("📅 Jornada", value=ahora_sv.date())

        # Partidos
        matches = api_request_rapid("football-get-matches-by-date", {"date": date_sel.strftime('%Y-%m-%d'), "league_id": league_id})
        
        if matches:
            match_labels = {}
            for m in matches:
                h = smart_get(m, 'match_hometeam_name', 'home_team', 'home.name')
                v = smart_get(m, 'match_awayteam_name', 'away_team', 'away.name')
                time = smart_get(m, 'match_time', 'time', 'status.type')
                match_labels[f"{time} | {h} vs {v}"] = m
            
            p_sel = st.selectbox("📍 Seleccionar Partido", list(match_labels.keys()))

            if st.button("SYNC DATA"):
                with st.spinner("Sincronizando..."):
                    m_data = match_labels[p_sel]
                    # Obtenemos tabla de posiciones para promedios
                    standings = api_request_rapid("football-get-standings-all", {"league_id": league_id})
                    
                    if standings:
                        def find_team(name):
                            names = [smart_get(t, 'team_name', 'team.name') for t in standings]
                            best, score = process.extractOne(name, names)
                            return next((t for t in standings if smart_get(t, 'team_name', 'team.name') == best), None)

                        h_name = smart_get(m_data, 'match_hometeam_name', 'home_team')
                        v_name = smart_get(m_data, 'match_awayteam_name', 'away_team')
                        
                        team_l = find_team(h_name)
                        team_v = find_team(v_name)

                        if team_l and team_v:
                            # Extraer goles y partidos jugados
                            pj_l = max(1, smart_get(team_l, 'home_league_payed', 'home.played', default=1))
                            pj_v = max(1, smart_get(team_v, 'away_league_payed', 'away.played', default=1))
                            
                            st.session_state['nl_auto'] = h_name
                            st.session_state['nv_auto'] = v_name
                            st.session_state['lgf_auto'] = smart_get(team_l, 'home_league_GF', 'home.goals_for') / pj_l
                            st.session_state['vgf_auto'] = smart_get(team_v, 'away_league_GF', 'away.goals_for') / pj_v
                            st.rerun()
        else:
            st.info("No hay partidos para esta fecha.")
    else:
        st.warning("No se pudieron cargar las ligas.")

# =================================================================
# 5. REPORTE PRINCIPAL (DISEÑO ORIGINAL)
# =================================================================
st.markdown("<h1 style='text-align: center; color: white;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    local = st.text_input("Local", value=st.session_state['nl_auto'])
    xg_l = st.number_input("xG Local", 0.0, 10.0, value=float(st.session_state['lgf_auto']))
with c2:
    visitante = st.text_input("Visitante", value=st.session_state['nv_auto'])
    xg_v = st.number_input("xG Visita", 0.0, 10.0, value=float(st.session_state['vgf_auto']))

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    engine = MotorMatematico()
    res = engine.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    res_l, res_r = st.columns(2)
    with res_l:
        st.markdown(f"### 💎 Picks Sugeridos")
        st.write(f"• Victoria {local}: **{res['1X2'][0]:.1f}%**")
        st.write(f"• Empate: **{res['1X2'][1]:.1f}%**")
        st.write(f"• Ambos Anotan (SÍ): **{res['BTTS']:.1f}%**")
    with res_r:
        st.markdown("### 🎯 Marcadores Probables")
        for sc, pr in res['TOP']:
            st.code(f"{sc} — Probabilidad: {pr:.1f}%")
    st.markdown('</div>', unsafe_allow_html=True)

    # Botón WhatsApp
    msg = f"OR936 ELITE: {local} vs {visitante}\nPredicción: {res['TOP'][0][0]}"
    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" class="whatsapp-btn">📲 COMPARTIR REPORTE</a>', unsafe_allow_html=True)
