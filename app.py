import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests

# =================================================================
# CONFIGURACIÓN DE API (Tu clave de la imagen)
# =================================================================
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf13c6d701e5"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

# =================================================================
# FUNCIONES DE DATOS (API CONNECTORS)
# =================================================================
@st.cache_data(ttl=3600)
def buscar_equipo_api(query):
    if len(query) < 3: return []
    url = "https://api-football-v1.p.rapidapi.com/v3/teams"
    res = requests.get(url, headers=HEADERS, params={"search": query})
    return res.json().get('response', []) if res.status_code == 200 else []

@st.cache_data(ttl=86400)
def obtener_stats_api(team_id, league_id, season=2023):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    res = requests.get(url, headers=HEADERS, params=params)
    if res.status_code == 200:
        data = res.json().get('response', {})
        # Procesamiento de promedios
        played = data.get('fixtures', {}).get('played', {}).get('total', 1)
        stats = {
            "gf": data.get('goals', {}).get('for', {}).get('average', {}).get('total', 1.5),
            "gc": data.get('goals', {}).get('against', {}).get('average', {}).get('total', 1.2),
            "tj": (data.get('cards', {}).get('yellow', {}).get('total', 0) or 0) / (played or 1),
            "co": 5.0 # Estimado base si la API no devuelve corners directos
        }
        return stats
    return None

# =================================================================
# MOTOR MATEMÁTICO (PRO STATS ENGINE) - INTACTO
# =================================================================
class MotorMatematico:
    def __init__(self):
        self.rho = -0.15

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        try: return (lam**k * math.exp(-lam)) / math.factorial(k)
        except: return 0.0

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def calcular_ou_prob(self, valor_esperado, threshold):
        prob_under = sum(self.poisson_prob(k, valor_esperado) for k in range(int(math.floor(threshold)) + 1))
        return (1 - prob_under) * 100, prob_under * 100

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz_calor = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}

        for i in range(10): 
            fila = []
            for j in range(10):
                p_base = self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)
                p = max(0, p_base * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz_calor.append(fila)

        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3],
            "MATRIZ": matriz_calor
        }

# =================================================================
# INTERFAZ PROFESIONAL (MASTER DASHBOARD)
# =================================================================
st.set_page_config(page_title="OR936 API Analysis", layout="wide")

# Estilos CSS (Iguales a los tuyos)
st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    .master-card { background: linear-gradient(135deg, #1e1e26 0%, #111118 100%); padding: 30px; border-radius: 20px; border: 1px solid #00ffcc; box-shadow: 0 10px 30px rgba(0,255,204,0.15); margin-bottom: 25px; }
    .score-badge { background: rgba(255,255,255,0.05); padding: 10px; border-radius: 10px; border: 1px solid rgba(0,255,204,0.3); text-align: center; }
    .verdict-item { border-left: 3px solid #00ffcc; padding-left: 15px; margin-bottom: 12px; background: rgba(255,255,255,0.02); padding: 8px 15px; border-radius: 0 8px 8px 0; }
    .btts-card { background: rgba(0, 255, 204, 0.05); padding: 10px; border-radius: 10px; text-align: center; border: 1px dashed #00ffcc; margin-bottom: 15px; }
    .share-btn { width: 100%; background-color: #25D366; color: white !important; border: none; padding: 15px; border-radius: 12px; font-weight: bold; text-align: center; display: block; text-decoration: none; margin-top: 20px; }
    .value-tag { background: #00ffcc; color: black; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("🔌 API Smart Search")
    liga_id = st.number_input("ID Liga (LaLiga=140, PL=39)", 1, 1000, 140)
    
    st.divider()
    search_l = st.text_input("🔍 Buscar Local", "Real Madrid")
    res_l = buscar_equipo_api(search_l)
    equipo_l_obj = st.selectbox("Confirmar Local", res_l, format_func=lambda x: x['team']['name']) if res_l else None

    search_v = st.text_input("🔍 Buscar Visitante", "Barcelona")
    res_v = buscar_equipo_api(search_v)
    equipo_v_obj = st.selectbox("Confirmar Visitante", res_v, format_func=lambda x: x['team']['name']) if res_v else None

    if st.button("📥 CARGAR DATOS DE API"):
        if equipo_l_obj and equipo_v_obj:
            s_l = obtener_stats_api(equipo_l_obj['team']['id'], liga_id)
            s_v = obtener_stats_api(equipo_v_obj['team']['id'], liga_id)
            if s_l and s_v:
                st.session_state.lgf, st.session_state.lgc = float(s_l['gf']), float(s_l['gc'])
                st.session_state.vgf, st.session_state.
