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
# 1. CONFIGURACIÓN API & ESTADO
# =================================================================
# Usando la clave de RapidAPI que proporcionaste
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b8"
API_HOST = "api-football-v1.p.rapidapi.com"
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Inicialización de estados
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.15, 'lgf_auto': 1.5, 'lgc_auto': 1.2, 
    'vgf_auto': 1.3, 'vgc_auto': 1.4
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE CONEXIÓN (CON DEBUGGING)
# =================================================================

def api_request_live(endpoint, params=None):
    if params is None: params = {}
    url = f"{BASE_URL}/{endpoint}"
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=12)
        data = res.json()
        
        # Mostrar errores críticos de la API en el sidebar para diagnóstico
        if data.get('errors'):
            st.sidebar.error(f"Error API: {data['errors']}")
            return []
            
        return data.get('response', [])
    except Exception as e:
        st.sidebar.error(f"Error de conexión: {str(e)}")
        return []

@st.cache_data(ttl=600)
def get_fixtures(league_id, date_obj):
    # Intentar primero con temporada 2025 y luego 2026 (ajuste para marzo 2026)
    for season in [2025, 2026]:
        params = {
            "league": league_id,
            "season": season,
            "from": (date_obj - timedelta(days=3)).strftime('%Y-%m-%d'),
            "to": (date_obj + timedelta(days=3)).strftime('%Y-%m-%d')
        }
        res = api_request_live("fixtures", params)
        if res: return res, season
    return [], 2025

@st.cache_data(ttl=600)
def get_h2h_data(team_id_l, team_id_v):
    params = {"h2h": f"{team_id_l}-{team_id_v}", "last": 6}
    matches = api_request_live("fixtures/headtohead", params)
    if not matches: return 1.0, 1.0
    l_pts, v_pts = 0, 0
    for m in matches:
        try:
            h_s = m['goals']['home']
            a_s = m['goals']['away']
            if h_s is None or a_s is None: continue
            if h_s > a_s:
                if m['teams']['home']['id'] == team_id_l: l_pts += 3
                else: v_pts += 3
            elif h_s < a_s:
                if m['teams']['home']['id'] == team_id_l: v_pts += 3
                else: l_pts += 3
            else: l_pts += 1; v_pts += 1
        except: continue
    total = l_pts + v_pts if (l_pts + v_pts) > 0 else 1
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 3. MOTOR MATEMÁTICO (DIXON-COLES)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.14

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
        h_lines = [-1.5, -0.5, 0.5, 1.5]
        h_probs_l = {h: 0.0 for h in h_lines}; h_probs_v = {h: 0.0 for h in h_lines}

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
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        sim_tj = np.random.poisson(tj_total, 10000)
        sim_co = np.random.poisson(co_total, 10000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/100, np.sum(sim_tj <= t)/100) for t in [3.5, 4.5, 5.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/100, np.sum(sim_co <= t)/100) for t in [7.5, 8.5, 9.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# 4. SIDEBAR - CONTROL DE DATOS
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    # IDs de ligas verificados para API-Football
    ligas_api = {
        "Premier League (Inglaterra)": 39, "La Liga (España)": 140, "Serie A (Italia)": 135, 
        "Bundesliga (Alemania)": 78, "Ligue 1 (Francia)": 61, "Liga Mayor (El Salvador)": 321,
        "Brasileirão (Série A)": 71, "Liga MX (México)": 262, "Saudi Pro League": 307
    }
    
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA", value=ahora_sv.date())
    
    # Intento de obtener partidos
    raw_events, season_detectada = get_fixtures(ligas_api[nombre_liga], fecha_analisis)

    if raw_events:
        op_p = {f"({e['fixture']['date'][5:10]}) {e['teams']['home']['name']} vs {e['teams']['away']['name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos Disponibles", list(op_p.keys()))

        if st.button("SYNC DATA"):
            st.cache_data.clear()
            with st.spinner("Sincronizando con API-Sports..."):
                match_info = op_p[p_sel]
                standings_res = api_request_live("standings", {"league": ligas_api[nombre_liga], "season": season_detectada})
                
                if standings_res:
                    tabla = standings_res[0]['league']['standings'][0]
                    
                    # Media de liga
                    gf_tot = sum(int(t['all']['goals']['for']) for t in tabla)
                    pj_tot = sum(int(t['all']['played']) for t in tabla)
                    st.session_state['p_liga_auto'] = (gf_tot / pj_tot) if pj_tot > 0 else 2.5
                    
                    # Buscar equipos
                    def find_t(name):
                        names = [t['team']['name'] for t in tabla]
                        m, s = process.extractOne(name, names)
                        return next(t for t in tabla if t['team']['name'] == m) if s > 60 else None

                    dl = find_t(match_info['teams']['home']['name'])
                    dv = find_t(match_info['teams']['away']['name'])

                    if dl and dv:
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team']['name'], dv['team']['name']
                        st.session_state['lgf_auto'] = float(dl['home']['goals']['for'] / dl['home']['played']) if dl['home']['played'] > 0 else 1.5
                        st.session_state['lgc_auto'] = float(dl['home']['goals']['against'] / dl['home']['played']) if dl['home']['played'] > 0 else 1.0
                        st.session_state['vgf_auto'] = float(dv['away']['goals']['for'] / dv['away']['played']) if dv['away']['played'] > 0 else 1.2
                        st.session_state['vgc_auto'] = float(dv['away']['goals']['against'] / dv['away']['played']) if dv['away']['played'] > 0 else 1.4
                        st.session_state['h2h_bias'] = get_h2h_data(dl['team']['id'], dv['team']['id'])
                        st.session_state['audit_results'] = raw_events[:5]
                        st.success("¡Datos Sincronizados!")
                        st.rerun()
    else:
        st.warning("No se encontraron partidos para esta fecha/liga. Intenta otra fecha.")

# =================================================================
# 5. UI PRINCIPAL Y CÁLCULOS
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

# Layout de inputs (pueden ser manuales o auto-rellenados)
c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF Local", 0.0, 5.0, key='lgf_auto')
    lgc = st.number_input("GC Local", 0.0, 5.0, key='lgc_auto')
with c2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF Visita", 0.0, 5.0, key='vgf_auto')
    vgc = st.number_input("GC Visita", 0.0, 5.0, key='vgc_auto')

p_liga = st.slider("Media Liga", 0.5, 4.0, value=st.session_state['p_liga_auto'])

if st.button("GENERAR PREDICCIÓN QUANTUM"):
    motor = MotorMatematico(p_liga)
    h2h_l, h2h_v = st.session_state['h2h_bias']
    
    # Cálculo de xG Proyectado
    xg_l = (lgf / p_liga) * (vgc / p_liga) * p_liga * 1.15 * h2h_l
    xg_v = (vgf / p_liga) * (lgc / p_liga) * p_liga * 0.85 * h2h_v
    
    res = motor.procesar(xg_l, xg_v, 4.5, 9.5)
    
    # Visualización de Resultados (Resumen de tu código original)
    st.markdown(f"### Análisis: {nl} vs {nv}")
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.write("**Probabilidades 1X2**")
        p1, px, p2 = res['1X2']
        st.info(f"{nl}: {p1:.1f}% | Empate: {px:.1f}% | {nv}: {p2:.1f}%")
        
        st.write("**Sugerencias de Valor**")
        pool = [
            ("Over 2.5 Goles", res['GOLES'][2.5][0]),
            ("Ambos Anotan: SÍ", res['BTTS'][0]),
            (f"Doble Oportunidad {nl}/X", res['DC'][0]),
            (f"Doble Oportunidad {nv}/X", res['DC'][1])
        ]
        for t, p in sorted(pool, key=lambda x: x[1], reverse=True):
            if p > 65: st.success(f"💎 {t}: {p:.1f}%")

    with col_b:
        st.write("**Marcadores Probables**")
        for m, p in res['TOP']:
            st.markdown(f"<div style='background:#000; color:#d4af37; padding:10px; border-radius:5px; margin-bottom:5px; border:1px solid #d4af37; text-align:center;'><b>{m}</b> ({p:.1f}%)</div>", unsafe_allow_html=True)

    # Tabs con detalles (simplificado para brevedad)
    t1, t2 = st.tabs(["📊 Matriz", "📈 Auditoría"])
    with t1:
        fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Viridis')
        st.plotly_chart(fig)
    with t2:
        if st.session_state['audit_results']:
            for m in st.session_state['audit_results']:
                st.write(f"{m['fixture']['date'][:10]} - {m['teams']['home']['name']} {m['goals']['home']} vs {m['goals']['away']} {m['teams']['away']['name']}")

st.markdown("<p style='text-align:center; color:gray;'>OR936 ELITE v4.5 | API-SPORTS SYNC</p>", unsafe_allow_html=True)
