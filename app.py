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
# 1. CONFIGURACIÓN API (CORRECCIÓN DE RUTA 404)
# =================================================================
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf081e5e5b62"
API_HOST = "free-api-live-football-data.p.rapidapi.com"
# Esta API no acepta rutas. Se usa la URL base y se envía la acción por parámetro.
BASE_URL = "https://free-api-live-football-data.p.rapidapi.com/"

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# =================================================================
# 2. INICIALIZACIÓN DE ESTADO (SOLUCIÓN AL KEYERROR)
# =================================================================
# Definimos todos los valores iniciales para que la app no falle al cargar
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.0
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.3
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.0
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)

# =================================================================
# 3. FUNCIONES DE CONEXIÓN (BRIDGE)
# =================================================================

def safe_api_request(action, params=None):
    """Corregido: Envía la acción como parámetro para evitar error 404"""
    if params is None: params = {}
    params["action"] = action  # Aquí es donde la API recibe la orden
    try:
        res = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json()
            # Esta API devuelve una lista directa o un objeto con los datos
            return data if isinstance(data, list) else []
        else:
            st.sidebar.error(f"Error {res.status_code}")
            return []
    except Exception as e:
        return []

@st.cache_data(ttl=600)
def get_events(league_id, date_str):
    return safe_api_request("get_events", {"from": date_str, "to": date_str, "league_id": league_id})

@st.cache_data(ttl=600)
def get_standings(league_id):
    return safe_api_request("get_standings", {"league_id": league_id})

@st.cache_data(ttl=600)
def get_h2h(id_l, id_v):
    res = safe_api_request("get_H2H", {"firstTeamId": id_l, "secondTeamId": id_v})
    if not res or 'firstTeam' not in str(res): return 1.0, 1.0
    # Lógica simplificada de puntos para H2H
    return 1.05, 0.95 

# =================================================================
# 4. MOTOR MATEMÁTICO (TU LÓGICA ORIGINAL)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.12

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def procesar(self, xg_l, xg_v):
        p1, px, p2 = 0.0, 0.0, 0.0
        marcadores = {}
        for i in range(6): 
            for j in range(6):
                p = self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
        
        total = p1 + px + p2
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3]
        }

# =================================================================
# 5. INTERFAZ (SIDEBAR)
# =================================================================
st.set_page_config(page_title="OR936 GOLD", layout="wide")

with st.sidebar:
    st.title("OR936 GOLD")
    ligas_dict = {
        "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175,
        "Ligue 1": 168, "Saudi Pro": 307, "Champions League": 3, "Liga Mayor SLV": 601
    }
    liga_sel = st.selectbox("Liga", list(ligas_dict.keys()))
    fecha = st.date_input("Fecha", value=ahora_sv.date())
    
    eventos = get_events(ligas_dict[liga_sel], fecha.strftime('%Y-%m-%d'))
    
    if eventos and isinstance(eventos, list):
        partidos_op = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        sel_match = st.selectbox("Partido", list(partidos_op.keys()))
        
        if st.button("SYNC DATA"):
            with st.spinner("Sincronizando..."):
                match_data = partidos_op[sel_match]
                tabla = get_standings(ligas_dict[liga_sel])
                
                if tabla and isinstance(tabla, list):
                    def buscar(n):
                        nombres = [t['team_name'] for t in tabla]
                        m, s = process.extractOne(n, nombres)
                        return next(t for t in tabla if t['team_name'] == m) if s > 65 else None

                    tl = buscar(match_data['match_hometeam_name'])
                    tv = buscar(match_data['match_awayteam_name'])
                    
                    if tl and tv:
                        st.session_state['nl_auto'] = tl['team_name']
                        st.session_state['nv_auto'] = tv['team_name']
                        st.session_state['lgf_auto'] = float(tl['home_league_GF']) / max(1, int(tl['home_league_payed']))
                        st.session_state['lgc_auto'] = float(tl['home_league_GA']) / max(1, int(tl['home_league_payed']))
                        st.session_state['vgf_auto'] = float(tv['away_league_GF']) / max(1, int(tv['away_league_payed']))
                        st.session_state['vgc_auto'] = float(tv['away_league_GA']) / max(1, int(tv['away_league_payed']))
                        st.success("Datos listos")
                        st.rerun()
    else:
        st.info("No hay partidos en esta fecha.")

# =================================================================
# 6. CUERPO PRINCIPAL (CORREGIDO)
# =================================================================
st.header("OR936 QUANTUM ELITE")

col1, col2 = st.columns(2)
with col1:
    l_name = st.text_input("Local", value=st.session_state['nl_auto'])
    # Ahora 'lgf_auto' siempre existe, evitando el KeyError
    lgf_val = st.number_input("GF Promedio L", value=float(st.session_state['lgf_auto']))

with col2:
    v_name = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf_val = st.number_input("GF Promedio V", value=float(st.session_state['vgf_auto']))

p_liga = st.slider("Media Goles Liga", 0.5, 5.0, value=st.session_state['p_liga_auto'])

if st.button("GENERAR PREDICCIÓN"):
    motor = MotorMatematico(league_avg=p_liga)
    # Cálculo simple de xG basado en tus inputs
    xg_l = (lgf_val / p_liga) * (st.session_state['vgc_auto'] / p_liga) * p_liga
    xg_v = (vgf_val / p_liga) * (st.session_state['lgc_auto'] / p_liga) * p_liga
    
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric(l_name, f"{res['1X2'][0]:.1f}%")
    c2.metric("Empate", f"{res['1X2'][1]:.1f}%")
    c3.metric(v_name, f"{res['1X2'][2]:.1f}%")
    
    st.subheader("Marcadores Probables")
    for m, p in res['TOP']:
        st.write(f"🎯 **{m}** — Probabilidad: {p:.1f}%")
