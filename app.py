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

# Inicialización de estados para evitar errores de carga
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.0
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.3
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.1

# =================================================================
# 2. FUNCIONES DE CONEXIÓN ROBUSTAS
# =================================================================

def api_request_rapid(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # Esta API anida los datos en 'data' o 'response'
            if isinstance(data, dict):
                for k in ['data', 'response', 'results']:
                    if k in data and data[k]: return data[k]
            return data if isinstance(data, list) else []
        return []
    except:
        return []

def smart_get(obj, *keys, default=0):
    """Busca valores en diccionarios anidados de forma segura."""
    if not isinstance(obj, dict): return default
    for k in keys:
        if "." in k:
            parts = k.split(".")
            val = obj
            for p in parts:
                val = val.get(p, {}) if isinstance(val, dict) else {}
            if val != {} and val is not None: return val
        elif k in obj and obj[k] is not None:
            return obj[k]
    return default

@st.cache_data(ttl=600)
def fetch_leagues():
    res = api_request_rapid("football-get-all-leagues")
    if not res: return {"Premier League": "152"}
    return {l['league_name']: l['league_id'] for l in res if isinstance(l, dict) and 'league_id' in l}

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM (RESTAURADO)
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
        marcadores = {}
        for i in range(10): 
            for j in range(10):
                p = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
        
        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3],
            "BRIER": confianza
        }

# =================================================================
# 4. SIDEBAR & LÓGICA DE SYNC (CORREGIDA)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    .stApp { background: #05070a; color: #e0e0e0; }
    .master-card { background: #141923; padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; }
    .whatsapp-btn { background: #25D366; color: white !important; padding: 10px; border-radius: 10px; text-decoration: none; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    if st.button("📡 VERIFICAR API"):
        check = api_request_rapid("football-get-all-leagues")
        if check: st.success(f"ONLINE: {len(check)} Ligas")
        else: st.error("SIN RESPUESTA")

    leagues = fetch_leagues()
    league_name = st.selectbox("🏆 Competición", list(leagues.keys()))
    l_id = leagues[league_name]
    f_sel = st.date_input("📅 Jornada", value=ahora_sv.date())
    
    matches = api_request_rapid("football-get-matches-by-date", {"date": f_sel.strftime('%Y-%m-%d'), "league_id": l_id})

    if matches and isinstance(matches, list):
        op_p = {}
        for m in matches:
            h = smart_get(m, 'match_hometeam_name', 'home_team', 'home.name')
            v = smart_get(m, 'match_awayteam_name', 'away_team', 'away.name')
            op_p[f"{h} vs {v}"] = m
        
        p_sel = st.selectbox("📍 Partidos", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Sincronizando..."):
                standings = api_request_rapid("football-get-standings-all", {"league_id": l_id})
                m_info = op_p[p_sel]
                
                if standings and isinstance(standings, list):
                    # Promedios de liga
                    hg = sum(smart_get(t, 'home_league_GF', 'home.goals_for') for t in standings if isinstance(t, dict))
                    ag = sum(smart_get(t, 'away_league_GF', 'away.goals_for') for t in standings if isinstance(t, dict))
                    pj = sum(smart_get(t, 'overall_league_payed', 'played') for t in standings if isinstance(t, dict))
                    st.session_state['p_liga_auto'] = (hg + ag) / (max(1, pj) / 2)
                    st.session_state['hfa_league'] = hg / ag if ag > 0 else 1.1

                    def find_team(name):
                        names = [smart_get(t, 'team_name', 'team.name') for t in standings if isinstance(t, dict)]
                        if not names: return None
                        best, score = process.extractOne(name, names)
                        return next((t for t in standings if smart_get(t, 'team_name', 'team.name') == best), None)

                    dl, dv = find_team(smart_get(m_info, 'match_hometeam_name', 'home_team')), find_team(smart_get(m_info, 'match_awayteam_name', 'away_team'))
                    
                    if dl and dv:
                        ph = max(1, smart_get(dl, 'home_league_payed', 'home.played'))
                        pa = max(1, smart_get(dv, 'away_league_payed', 'away.played'))
                        st.session_state['lgf_auto'] = smart_get(dl, 'home_league_GF', 'home.goals_for') / ph
                        st.session_state['lgc_auto'] = smart_get(dl, 'home_league_GA', 'home.goals_against') / ph
                        st.session_state['vgf_auto'] = smart_get(dv, 'away_league_GF', 'away.goals_for') / pa
                        st.session_state['vgc_auto'] = smart_get(dv, 'away_league_GA', 'away.goals_against') / pa
                        st.session_state['nl_auto'] = smart_get(dl, 'team_name', 'team.name')
                        st.session_state['nv_auto'] = smart_get(dv, 'team_name', 'team.name')
                        st.rerun()
    else:
        st.info("No hay partidos hoy.")

# =================================================================
# 5. MAIN CONTENT (MANTENIDO)
# =================================================================
st.markdown("<h1 style='text-align: center; color: white;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF Local", 0.0, 10.0, value=float(st.session_state['lgf_auto']))
with c2:
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF Visita", 0.0, 10.0, value=float(st.session_state['vgf_auto']))

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(st.session_state['p_liga_auto'])
    res = motor.procesar(lgf, vgf, 4.0, 9.0)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    res_l, res_r = st.columns(2)
    with res_l:
        st.markdown(f"### 💎 Picks (Confianza: {res['BRIER']*100:.1f}%)")
        st.write(f"• Victoria {nl}: **{res['1X2'][0]:.1f}%**")
        st.write(f"• Ambos Anotan (SÍ): **{res['BTTS'][0]:.1f}%**")
    with res_r:
        st.markdown("### 🎯 Marcador Probable")
        st.success(f"PREDOMINANTE: {res['TOP'][0][0]}")
    st.markdown('</div>', unsafe_allow_html=True)

    msg = f"OR936 ELITE: {nl} vs {nv}\nMarcador: {res['TOP'][0][0]}"
    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" class="whatsapp-btn">📲 COMPARTIR</a>', unsafe_allow_html=True)
