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
# CONFIGURACIÓN API (RAPIDAPI - API-FOOTBALL V3)
# =================================================================
# Clave corregida según tu imagen de RapidAPI
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf8f81aec6"
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3/"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

# Sincronización horaria El Salvador
tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# Función de Fixtures (Partidos) con reintento de temporada automático
def api_request_live(params):
    endpoint = "fixtures"
    league_id = params.get("league_id")
    target_date = params.get("from")
    year_search = int(target_date[:4])
    
    # Intentamos con el año actual y el anterior (Marzo 2026 suele ser season 2025)
    for s in [year_search - 1, year_search]:
        url_params = {
            "league": league_id,
            "season": s,
            "from": params.get("from"),
            "to": params.get("to")
        }
        try:
            res = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=url_params, timeout=10)
            data_json = res.json()
            
            if data_json.get("errors"):
                if "subscription" in str(data_json["errors"]):
                    st.error("⚠️ Error: No estás suscrito al plan (incluso el gratuito) en RapidAPI.")
                return []
                
            resp = data_json.get('response', [])
            if resp:
                return [{'match_date': f['fixture']['date'][:10], 
                         'match_hometeam_name': f['teams']['home']['name'], 
                         'match_awayteam_name': f['teams']['away']['name']} for f in resp]
        except: continue
    return []

# Función de Standings (Posiciones) con soporte para ligas con grupos
@st.cache_data(ttl=600)
def api_request_cached(league_id):
    endpoint = "standings"
    year_search = ahora_sv.year
    
    for s in [year_search - 1, year_search]:
        try:
            res = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params={"league": league_id, "season": s}, timeout=10)
            resp = res.json().get('response', [])
            if resp:
                # API-Football puede devolver varios grupos (Apertura/Clausura o Grupos A,B,C)
                standings_nested = resp[0]['league']['standings']
                normalized = []
                # Aplanamos todos los grupos en una sola lista para la búsqueda
                for group in standings_nested:
                    for t in group:
                        normalized.append({
                            'team_name': t['team']['name'],
                            'overall_league_position': t['rank'],
                            'overall_league_payed': t['all']['played'],
                            'home_league_payed': t['home']['played'],
                            'home_league_GF': t['home']['goals']['for'],
                            'home_league_GA': t['home']['goals']['against'],
                            'away_league_payed': t['away']['played'],
                            'away_league_GF': t['away']['goals']['for'],
                            'away_league_GA': t['away']['goals']['against']
                        })
                if normalized: return normalized
        except: continue
    return []

# =================================================================
# MOTOR MATEMÁTICO (Sin cambios)
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.15 if 2.2 <= league_avg <= 3.0 else (-0.10 if league_avg > 3.0 else -0.18)

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
        h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        h_probs_l = {h: 0.0 for h in h_lines}
        h_probs_v = {h: 0.0 for h in h_lines}

        for i in range(10): 
            fila = []
            for j in range(10):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                for h in h_lines:
                    if (i + h) > j: h_probs_l[h] += p
                    if (j + h) > i: h_probs_v[h] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))
        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# UI STREAMLIT
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid var(--primary); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 14px; padding: 15px; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background: #25D366; color: white !important; padding: 14px; border-radius: 14px; text-decoration: none; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Premier League (Inglaterra)": 39, "La Liga (España)": 140, "Serie A (Italia)": 135, 
        "Bundesliga (Alemania)": 78, "Ligue 1 (Francia)": 61, "UEFA Champions League": 2, 
        "Brasileirão Série A": 71, "Liga Mayor (El Salvador)": 242, "Saudi Pro League": 307
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 FECHA", value=ahora_sv.date())
    
    f_desde = (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d')
    f_hasta = (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d')

    raw_events = api_request_live({"from": f_desde, "to": f_hasta, "league_id": ligas_api[nombre_liga]})

    if raw_events:
        op_p = {f"({e['match_date']}) {e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos Encontrados", list(op_p.keys()))

        if st.button("SYNC DATA"):
            st.cache_data.clear()
            with st.spinner("CONECTANDO..."):
                standings = api_request_cached(ligas_api[nombre_liga])
                if standings:
                    def buscar(n):
                        match, score = process.extractOne(n, [t['team_name'] for t in standings])
                        return next(t for t in standings if t['team_name'] == match) if score > 60 else None

                    dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                    if dl and dv:
                        pj_h, pj_v = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['lgf_auto'] = float(dl['home_league_GF'])/pj_h if pj_h>0 else 1.5
                        st.session_state['lgc_auto'] = float(dl['home_league_GA'])/pj_h if pj_h>0 else 1.0
                        st.session_state['vgf_auto'] = float(dv['away_league_GF'])/pj_v if pj_v>0 else 1.2
                        st.session_state['vgc_auto'] = float(dv['away_league_GA'])/pj_v if pj_v>0 else 1.3
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.rerun()
    else:
        st.warning("No hay partidos programados. Intenta otra fecha.")

# CONTENIDO
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF Home", 0.0, 10.0, key='lgf_auto')
    lgc = st.number_input("GC Home", 0.0, 10.0, key='lgc_auto')
with col_v:
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF Away", 0.0, 10.0, key='vgf_auto')
    vgc = st.number_input("GC Away", 0.0, 10.0, key='vgc_auto')

p_liga = st.slider("Media Liga", 0.5, 5.0, value=2.5)

if st.button("GENERAR REPORTE"):
    motor = MotorMatematico(p_liga)
    # Cálculo XG simplificado para el reporte
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * 1.1 # HFA 1.1
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * 0.9
    res = motor.procesar(xg_l, xg_v, 4.5, 9.5)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([2,1])
    with c1:
        st.subheader("💎 TOP PICKS")
        pool = [("1X", res['DC'][0]), ("X2", res['DC'][1]), ("Ambos Anotan", res['BTTS'][0]), ("Over 2.5", res['GOLES'][2.5][0])]
        for t, p in sorted(pool, key=lambda x: x[1], reverse=True):
            st.markdown(f'<div class="verdict-item"><b>{p:.1f}%</b> — {t}</div>', unsafe_allow_html=True)
    with c2:
        st.subheader("🎯 SCORES")
        for s, p in res['TOP']: st.markdown(f'<div class="score-badge">{s} ({p:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.plotly_chart(px.imshow(res['MATRIZ'], labels=dict(x=nv, y=nl, color="%"), text_auto=".1f", color_continuous_scale='Greens'))
