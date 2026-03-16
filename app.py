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
# 1. CONFIGURACIÓN API (RAPIDAPI BRIDGE) & ESTADO
# =================================================================
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf081e5e5b62"
API_HOST = "free-api-live-football-data.p.rapidapi.com"
BASE_URL = "https://free-api-live-football-data.p.rapidapi.com/"

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Actualizamos temporada al año actual (2026)
SEASON_ACTUAL = str(ahora_sv.year)

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'lgf_auto': 1.7, 'lgc_auto': 1.2, 
    'vgf_auto': 1.5, 'vgc_auto': 1.1, 'fatiga_l': 1.0, 'fatiga_v': 1.0
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE CONEXIÓN Y DIAGNÓSTICO
# =================================================================

def api_request_live(action, params=None):
    if params is None: params = {}
    
    # Traducción de rutas para RapidAPI
    mapping = {
        "get_events": "fixtures",
        "get_standings": "standings",
        "get_H2H": "fixtures/headtohead"
    }
    endpoint = mapping.get(action, action)
    
    # Limpieza y mapeo de parámetros
    clean_params = params.copy()
    if "league_id" in clean_params: clean_params["league"] = clean_params.pop("league_id")
    if "team_id" in clean_params: clean_params["team"] = clean_params.pop("team_id")
    
    # La mayoría de endpoints requieren temporada
    if endpoint in ["fixtures", "standings"]:
        clean_params["season"] = SEASON_ACTUAL

    try:
        url = f"{BASE_URL}{endpoint}"
        res = requests.get(url, params=clean_params, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json()
            return data.get("response", [])
        else:
            return []
    except:
        return []

@st.cache_data(ttl=300)
def api_request_cached(league_id):
    return api_request_live("get_standings", {"league_id": league_id})

# FUNCIÓN DE DIAGNÓSTICO
def run_api_diagnostic():
    st.write("### 🛠 Informe de Conexión")
    with st.spinner("Verificando API..."):
        try:
            # Prueba básica con el endpoint de ligas (suele ser el más estable)
            test_res = requests.get(f"{BASE_URL}leagues", headers=HEADERS, timeout=10)
            st.write(f"**Status Code:** {test_res.status_code}")
            
            if test_res.status_code == 200:
                st.success("✅ Conexión establecida con RapidAPI.")
                data = test_res.json()
                st.write(f"**Resultados encontrados:** {len(data.get('response', []))}")
                if data.get("errors"):
                    st.error(f"Errores reportados por la API: {data['errors']}")
            elif test_res.status_code == 403:
                st.error("❌ Error 403: Tu API Key es inválida o no tienes suscripción activa a este plan en RapidAPI.")
            elif test_res.status_code == 429:
                st.warning("⚠️ Error 429: Has superado el límite de peticiones por minuto.")
            else:
                st.error(f"❌ Error desconocido: {test_res.status_code}")
        except Exception as e:
            st.error(f"❌ Fallo de red: {str(e)}")

# =================================================================
# 3. LÓGICA DE MÉTRICAS (MANTENIDA)
# =================================================================

@st.cache_data(ttl=300)
def get_advanced_metrics(team_id, league_id, position):
    events = api_request_live("get_events", {
        "league_id": league_id, 
        "team_id": team_id,
        "last": 5 # Pedimos los últimos 5 partidos
    })
    if not events: return 1.0, 1.0
    
    finished = [e for e in events if e.get('fixture', {}).get('status', {}).get('short') == 'FT']
    if not finished: return 1.0, 1.0

    momentum_gf = 0
    weights = [0.5, 0.3, 0.2]
    for i, m in enumerate(finished[-3:][::-1]):
        goals = m.get('goals', {})
        is_home = str(m.get('teams', {}).get('home', {}).get('id')) == str(team_id)
        try:
            gf = int(goals.get('home') if is_home else goals.get('away'))
            momentum_gf += gf * weights[i]
        except: continue

    elo_strength = 1.15 if int(position) <= 4 else (1.05 if int(position) <= 8 else 0.95)
    return elo_strength, momentum_gf

@st.cache_data(ttl=300)
def get_h2h_data(team_id_l, team_id_v):
    # En esta API el H2H se consulta enviando los dos IDs separados por guion
    matches = api_request_live("fixtures/headtohead", {"h2h": f"{team_id_l}-{team_id_v}"})
    if not matches: return 1.0, 1.0
    
    l_pts, v_pts = 0, 0
    for m in matches[:6]:
        goals = m.get('goals', {})
        try:
            h_s, a_s = int(goals.get('home', 0)), int(goals.get('away', 0))
            is_l_home = str(m['teams']['home']['id']) == str(team_id_l)
            if h_s > a_s:
                if is_l_home: l_pts += 3
                else: v_pts += 3
            elif h_s < a_s:
                if is_l_home: v_pts += 3
                else: l_pts += 3
            else:
                l_pts += 1; v_pts += 1
        except: continue
    total = l_pts + v_pts if (l_pts + v_pts) > 0 else 1
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 4. MOTOR MATEMÁTICO QUANTUM (MANTENIDO)
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
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# 5. UI/UX Y SIDEBAR
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

# CSS Mantenido
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background: #25D366; color: white !important; padding: 14px; border-radius: 14px; text-decoration: none; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    # BOTÓN DE DIAGNÓSTICO
    if st.button("🔍 CORRER DIAGNÓSTICO"):
        run_api_diagnostic()
    
    st.divider()

    ligas_api = {
        "Premier League": 39, "La Liga": 140, "Serie A": 135, "Bundesliga": 78, "Ligue 1": 61,
        "Saudi Pro League": 307, "UEFA Champions": 2, "Liga Mayor SV": 251
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA", value=ahora_sv.date())
    
    # Obtener eventos
    f_str = fecha_analisis.strftime('%Y-%m-%d')
    raw_events = api_request_live("get_events", {"date": f_str, "league_id": ligas_api[nombre_liga]})

    if raw_events:
        op_p = {f"{e['teams']['home']['name']} vs {e['teams']['away']['name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Sincronizando..."):
                res_standings = api_request_cached(ligas_api[nombre_liga])
                if res_standings:
                    standings = res_standings[0]['league'].get('standings', [[]])[0]
                    match_info = op_p[p_sel]

                    def buscar(n):
                        nombres = [t['team']['name'] for t in standings]
                        m, s = process.extractOne(n, nombres)
                        return next((t for t in standings if t['team']['name'] == m), None) if s > 65 else None

                    dl, dv = buscar(match_info['teams']['home']['name']), buscar(match_info['teams']['away']['name'])

                    if dl and dv:
                        st.session_state['h2h_bias'] = get_h2h_data(dl['team']['id'], dv['team']['id'])
                        elo_l, mom_l = get_advanced_metrics(dl['team']['id'], ligas_api[nombre_liga], dl['rank'])
                        elo_v, mom_v = get_advanced_metrics(dv['team']['id'], ligas_api[nombre_liga], dv['rank'])
                        
                        st.session_state['lgf_auto'] = (dl['all']['goals']['for']/max(1, dl['all']['played'])) * 0.7 + (mom_l * 0.3)
                        st.session_state['lgc_auto'] = (dl['all']['goals']['against']/max(1, dl['all']['played']))
                        st.session_state['vgf_auto'] = (dv['all']['goals']['for']/max(1, dv['all']['played'])) * 0.7 + (mom_v * 0.3)
                        st.session_state['vgc_auto'] = (dv['all']['goals']['against']/max(1, dv['all']['played']))
                        st.session_state['elo_bias'] = (elo_l, elo_v)
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team']['name'], dv['team']['name']
                        st.success("¡Datos Sincronizados!")
                        st.rerun()
    else:
        st.info("No hay partidos para esta fecha.")

# =================================================================
# 6. CONTENIDO PRINCIPAL (MANTENIDO)
# =================================================================
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    nl_manual = st.text_input("Local", value=st.session_state['nl_auto'])
    la, lb = st.columns(2)
    lgf = la.number_input("GF L", 0.0, 10.0, key='lgf_auto')
    lgc = lb.number_input("GC L", 0.0, 10.0, key='lgc_auto')
with col_v:
    nv_manual = st.text_input("Visita", value=st.session_state['nv_auto'])
    va, vb = st.columns(2)
    vgf = va.number_input("GF V", 0.0, 10.0, key='vgf_auto')
    vgc = vb.number_input("GC V", 0.0, 10.0, key='vgc_auto')

p_liga = st.slider("Media Goles Liga", 0.5, 5.0, value=st.session_state['p_liga_auto'])

if st.button("GENERAR REPORTE"):
    motor = MotorMatematico(league_avg=p_liga)
    res = motor.procesar(lgf, vgf, 4.5, 10.5) # Valores base para tarjetas/corners
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown("<h4>💎 TOP SELECCIONES</h4>", unsafe_allow_html=True)
        st.markdown(f'<div class="verdict-item">1X2: {res["1X2"][0]:.1f}% - {res["1X2"][1]:.1f}% - {res["1X2"][2]:.1f}%</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='text-align:center;'>🎯 MARCADOR</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
