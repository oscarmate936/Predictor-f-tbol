import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests

# =================================================================
# CONFIGURACIÓN DE API
# =================================================================
# Asegúrate de que esta clave sea la que aparece en tu panel de RapidAPI
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf13c6d701e5"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

@st.cache_data(ttl=3600)
def buscar_equipo_api(query):
    if not query or len(query) < 3: return []
    url = "https://api-football-v1.p.rapidapi.com/v3/teams"
    try:
        res = requests.get(url, headers=HEADERS, params={"search": query}, timeout=10)
        data = res.json()
        if res.status_code != 200:
            st.error(f"Error API: {data.get('message', 'Desconocido')}")
            return []
        return data.get('response', [])
    except Exception as e:
        st.error(f"Fallo de conexión: {e}")
        return []

@st.cache_data(ttl=86400)
def obtener_stats_api(team_id, league_id, season=2025):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams/statistics"
    params = {"league": league_id, "season": season, "team": team_id}
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = res.json()
        
        # DEBUG: Si quieres ver qué responde la API exactamente, descomenta la siguiente línea:
        # st.write(data) 

        if not data.get('response'):
            st.warning(f"No hay datos para el equipo {team_id} en la liga {league_id} temporada {season}")
            return None
            
        stats_data = data['response']
        played = stats_data.get('fixtures', {}).get('played', {}).get('total', 0)
        
        if played == 0:
            st.warning("El equipo seleccionado no tiene partidos jugados en esta temporada/liga.")
            return None

        return {
            "gf": stats_data.get('goals', {}).get('for', {}).get('average', {}).get('total', 0),
            "gc": stats_data.get('goals', {}).get('against', {}).get('average', {}).get('total', 0),
            "tj": (stats_data.get('cards', {}).get('yellow', {}).get('total', 0) or 0) / played
        }
    except Exception as e:
        st.error(f"Error al obtener estadísticas: {e}")
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
# INTERFAZ (UI)
# =================================================================
st.set_page_config(page_title="OR936 Analysis Pro", layout="wide")

with st.sidebar:
    st.title("🔌 API Smart Search")
    # Añadimos selector de temporada para evitar que quede obsoleta
    temp_act = st.selectbox("Temporada", [2025, 2024, 2023], index=0)
    liga_id = st.number_input("ID Liga (LaLiga=140, PL=39)", 1, 1000, 140)
    
    st.divider()
    search_l = st.text_input("🔍 Buscar Local", "Real Madrid")
    equipos_l = buscar_equipo_api(search_l)
    equipo_l_obj = st.selectbox("Confirmar Local", equipos_l, format_func=lambda x: x['team']['name']) if equipos_l else None

    search_v = st.text_input("🔍 Buscar Visitante", "Barcelona")
    equipos_v = buscar_equipo_api(search_v)
    equipo_v_obj = st.selectbox("Confirmar Visitante", equipos_v, format_func=lambda x: x['team']['name']) if equipos_v else None

    if st.button("📥 CARGAR DATOS DE API"):
        if equipo_l_obj and equipo_v_obj:
            with st.spinner('Obteniendo datos...'):
                s_l = obtener_stats_api(equipo_l_obj['team']['id'], liga_id, temp_act)
                s_v = obtener_stats_api(equipo_v_obj['team']['id'], liga_id, temp_act)
                
                if s_l and s_v:
                    st.session_state['lgf'] = float(s_l['gf'])
                    st.session_state['lgc'] = float(s_l['gc'])
                    st.session_state['vgf'] = float(s_v['gf'])
                    st.session_state['vgc'] = float(s_v['gc'])
                    st.session_state['ltj'] = float(s_l['tj'])
                    st.session_state['vtj'] = float(s_v['tj'])
                    st.session_state['l_name'] = equipo_l_obj['team']['name']
                    st.session_state['v_name'] = equipo_v_obj['team']['name']
                    st.success("✅ Datos sincronizados")
                else:
                    st.error("❌ No se pudieron obtener las estadísticas. Verifica la ID de la Liga y la Temporada.")

    st.divider()
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, 2.5)
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

# El resto del código de la interfaz (visualización de resultados) sigue igual que el anterior...
# (Omito la parte visual repetida para que el mensaje no sea eterno, pero debes mantenerla debajo)

# RECUERDA: Al final del código va la lógica del botón "🚀 PROCESAR ANÁLISIS COMPLETO" 
# que ya tienes en el mensaje anterior.
