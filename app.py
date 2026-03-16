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
# 1. CONFIGURACIÓN API (RAPIDAPI BRIDGE)
# =================================================================
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf081e5e5b62"
API_HOST = "free-api-live-football-data.p.rapidapi.com"
# Eliminamos la barra final para evitar errores de doble barra //
BASE_URL = "https://free-api-live-football-data.p.rapidapi.com"

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

# La mayoría de ligas operan bajo la temporada 2025 actualmente
SEASON_ACTUAL = "2025" 

# Estados de sesión
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.0
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)

# =================================================================
# 2. MOTOR DE DIAGNÓSTICO Y SOLICITUDES
# =================================================================

def safe_api_request(endpoint, params=None):
    """Función maestra para peticiones seguras"""
    try:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            return res.json().get("response", [])
        else:
            st.error(f"Error API {res.status_code}: {res.text}")
            return []
    except Exception as e:
        st.error(f"Fallo de conexión: {str(e)}")
        return []

def run_diagnostic():
    st.write("### 🛠 Verificación de Sistema")
    with st.spinner("Consultando estado de suscripción..."):
        # Probamos el endpoint más ligero
        test = safe_api_request("leagues", {"id": 39}) # Premier League
        if test:
            st.success("✅ Conexión Exitosa. La API está respondiendo correctamente.")
            st.json(test[0].get('league', {}))
        else:
            st.warning("⚠️ La conexión responde pero no devolvió datos. Revisa si tu suscripción en RapidAPI está activa (Plan Free).")

# =================================================================
# 3. LÓGICA DE DATOS (ADAPTADA A LA NUEVA ESTRUCTURA)
# =================================================================

@st.cache_data(ttl=600)
def get_events(league_id, date_str):
    return safe_api_request("fixtures", {"league": league_id, "date": date_str, "season": SEASON_ACTUAL})

@st.cache_data(ttl=600)
def get_standings(league_id):
    return safe_api_request("standings", {"league": league_id, "season": SEASON_ACTUAL})

@st.cache_data(ttl=600)
def get_h2h(id_l, id_v):
    res = safe_api_request("fixtures/headtohead", {"h2h": f"{id_l}-{id_v}"})
    if not res: return 1.0, 1.0
    l_pts, v_pts = 0, 0
    for m in res[:6]:
        g = m.get('goals', {})
        h_s, a_s = (g.get('home') or 0), (g.get('away') or 0)
        is_l_home = str(m['teams']['home']['id']) == str(id_l)
        if h_s > a_s:
            if is_l_home: l_pts += 3
            else: v_pts += 3
        elif h_s < a_s:
            if is_l_home: v_pts += 3
            else: l_pts += 3
        else:
            l_pts += 1; v_pts += 1
    total = max(1, l_pts + v_pts)
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 4. INTERFAZ Y SIDEBAR
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

with st.sidebar:
    st.title("OR936 GOLD")
    if st.button("🔍 CORRER DIAGNÓSTICO"):
        run_diagnostic()
    
    st.divider()
    
    ligas_dict = {
        "Premier League (ING)": 39, "La Liga (ESP)": 140, "Serie A (ITA)": 135,
        "Bundesliga (ALE)": 78, "Ligue 1 (FRA)": 61, "Saudi Pro (SAU)": 307,
        "Liga Mayor (SLV)": 251, "Champions League": 2
    }
    liga_sel = st.selectbox("Liga", list(ligas_dict.keys()))
    fecha = st.date_input("Fecha de Partido")
    
    eventos = get_events(ligas_dict[liga_sel], fecha.strftime('%Y-%m-%d'))
    
    if eventos:
        partidos_op = {f"{e['teams']['home']['name']} vs {e['teams']['away']['name']}": e for e in eventos}
        sel_match = st.selectbox("Selecciona Partido", list(partidos_op.keys()))
        
        if st.button("SYNC DATA"):
            with st.spinner("Extrayendo métricas..."):
                match_data = partidos_op[sel_match]
                res_stand = get_standings(ligas_dict[liga_sel])
                
                if res_stand:
                    # En RapidAPI: response -> [ { league: { standings: [ [TEAM_DATA] ] } } ]
                    tabla = res_stand[0]['league'].get('standings', [[]])[0]
                    
                    def find_team(name):
                        names = [t['team']['name'] for t in tabla]
                        m, s = process.extractOne(name, names)
                        return next(t for t in tabla if t['team']['name'] == m) if s > 70 else None

                    tl = find_team(match_data['teams']['home']['name'])
                    tv = find_team(match_data['teams']['away']['name'])
                    
                    if tl and tv:
                        st.session_state['nl_auto'] = tl['team']['name']
                        st.session_state['nv_auto'] = tv['team']['name']
                        st.session_state['lgf_auto'] = tl['all']['goals']['for'] / max(1, tl['all']['played'])
                        st.session_state['lgc_auto'] = tl['all']['goals']['against'] / max(1, tl['all']['played'])
                        st.session_state['vgf_auto'] = tv['all']['goals']['for'] / max(1, tv['all']['played'])
                        st.session_state['vgc_auto'] = tv['all']['goals']['against'] / max(1, tv['all']['played'])
                        st.session_state['h2h_bias'] = get_h2h(tl['team']['id'], tv['team']['id'])
                        st.success("Sincronización completa.")
                        st.rerun()
    else:
        st.info("No se hallaron partidos. Prueba otra fecha o liga.")

# =================================================================
# 5. MOTOR Y REPORTE (TU LÓGICA ORIGINAL)
# =================================================================
st.header("OR936 QUANTUM ELITE")

c1, c2 = st.columns(2)
with c1:
    l_name = st.text_input("Local", st.session_state['nl_auto'])
    lgf = st.number_input("GF Promedio L", value=st.session_state['lgf_auto'])
with c2:
    v_name = st.text_input("Visita", st.session_state['nv_auto'])
    vgf = st.number_input("GF Promedio V", value=st.session_state['vgf_auto'])

# Botón generar... (Aquí iría tu MotorMatematico definido anteriormente)
# [Se mantiene igual a tu código original para no alterar los cálculos]
