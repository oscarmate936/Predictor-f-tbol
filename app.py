import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime
import urllib.parse
from fuzzywuzzy import fuzz, process

# =================================================================
# CONFIGURACIÓN API
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

# Inicialización de estados
for key, val in {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'nl_auto': "Local", 'nv_auto': "Visitante", 'lgf_auto': 1.7, 'lgc_auto': 1.2,
    'vgf_auto': 1.5, 'vgc_auto': 1.1
}.items():
    if key not in st.session_state: st.session_state[key] = val

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

# =================================================================
# MOTOR MATEMÁTICO ELITE
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.10 if league_avg > 3.0 else (-0.18 if league_avg < 2.2 else -0.15)

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

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines, h_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5], [-1.5, -0.5, 0.5, 1.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}
        h_probs = {t: 0.0 for t in h_lines}

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
                    if (i + h) > j: h_probs[h] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        iteraciones = 15000
        sim_tj = np.random.poisson(tj_total, iteraciones)
        sim_co = np.random.poisson(co_total, iteraciones)
        tj_probs = {t: (np.sum(sim_tj > t)/iteraciones*100, np.sum(sim_tj <= t)/iteraciones*100) for t in [2.5, 3.5, 4.5, 5.5, 6.5]}
        co_probs = {t: (np.sum(sim_co > t)/iteraciones*100, np.sum(sim_co <= t)/iteraciones*100) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]}
        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAP": {t: p/total*100 for t, p in h_probs.items()},
            "TARJETAS": tj_probs, "CORNERS": co_probs,
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# UI Y LÓGICA DE SINCRONIZACIÓN
# =================================================================
st.set_page_config(page_title="OR936 PRO ELITE", layout="wide")

# Estilos (omitidos para brevedad, mantener los mismos que tienes)
st.markdown("<style>...</style>", unsafe_allow_html=True) # (Tu CSS original aquí)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168,
        "Brasileirão A": 99, "Libertadores": 13, "Champions League": 3, "Liga Mayor El Salvador": 601
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha", datetime.now())
    
    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Evento", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Procesando..."):
                standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
                if standings:
                    # 1. Promedios de Liga (Robustez en llaves)
                    g_h = sum(int(t.get('home_league_GF', 0)) for t in standings)
                    g_a = sum(int(t.get('away_league_GF', 0)) for t in standings)
                    # La API a veces usa 'payed' y otras 'played'
                    pj = sum(int(t.get('overall_league_payed', t.get('overall_league_played', 0))) for t in standings)
                    
                    if pj > 0:
                        st.session_state['p_liga_auto'] = float((g_h + g_a) / (pj / 2))
                        st.session_state['hfa_league'] = float(g_h / g_a) if g_a > 0 else 1.0

                    # 2. Búsqueda de Equipos (Fuzzy)
                    def buscar_equipo(nombre, lista):
                        nombres_tabla = [t['team_name'] for t in lista]
                        mejor_match, score = process.extractOne(nombre, nombres_tabla, scorer=fuzz.token_set_ratio)
                        return next((t for t in lista if t['team_name'] == mejor_match), None) if score > 60 else None

                    dl = buscar_equipo(op_p[p_sel]['match_hometeam_name'], standings)
                    dv = buscar_equipo(op_p[p_sel]['match_awayteam_name'], standings)

                    if dl and dv:
                        pj_h = int(dl.get('home_league_payed', dl.get('home_league_played', 1)))
                        pj_a = int(dv.get('away_league_payed', dv.get('away_league_played', 1)))
                        
                        st.session_state['lgf_auto'] = float(dl.get('home_league_GF', 0)) / (pj_h if pj_h > 0 else 1)
                        st.session_state['lgc_auto'] = float(dl.get('home_league_GA', 0)) / (pj_h if pj_h > 0 else 1)
                        st.session_state['vgf_auto'] = float(dv.get('away_league_GF', 0)) / (pj_a if pj_a > 0 else 1)
                        st.session_state['vgc_auto'] = float(dv.get('away_league_GA', 0)) / (pj_a if pj_a > 0 else 1)
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.rerun()
                    else:
                        st.sidebar.warning("⚠️ No se encontró uno de los equipos en la tabla de esta liga.")
                else:
                    st.sidebar.error("❌ La API no devolvió tabla para esta liga.")

# (El resto del código de visualización de pestañas se mantiene igual al anterior)
# ... [Contenido Principal, Tabs, Gráficos] ...
