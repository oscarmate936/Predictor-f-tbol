import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN API (apifootball.com V3)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

@st.cache_data(ttl=3600)
def api_request(action, params={}):
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except:
        return []

# =================================================================
# MOTOR MATEMÁTICO (DIXON-COLES)
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
st.set_page_config(page_title="OR936 Auto Analysis", layout="wide")

st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    .master-card { background: linear-gradient(135deg, #1e1e26 0%, #111118 100%); padding: 30px; border-radius: 20px; border: 1px solid #00ffcc; box-shadow: 0 10px 30px rgba(0,255,204,0.15); margin-bottom: 25px; }
    .verdict-item { border-left: 3px solid #00ffcc; padding-left: 15px; margin-bottom: 12px; background: rgba(255,255,255,0.02); padding: 8px 15px; border-radius: 0 8px 8px 0; }
    .share-btn { width: 100%; background-color: #25D366; color: white !important; border: none; padding: 15px; border-radius: 12px; font-weight: bold; text-align: center; display: block; text-decoration: none; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("🤖 Scouting Automático")
    
    ligas = {"La Liga (ESP)": 302, "Premier League (ENG)": 152, "Serie A (ITA)": 207, "Bundesliga (GER)": 175, "Ligue 1 (FRA)": 168}
    nombre_liga = st.selectbox("1. Selecciona Liga", list(ligas.keys()))
    league_id = ligas[nombre_liga]
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    eventos = api_request("get_events", {"from": hoy, "to": hoy, "league_id": league_id})
    
    if eventos and isinstance(eventos, list):
        opciones_partidos = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        seleccion = st.selectbox("2. Selecciona Partido", list(opciones_partidos.keys()))
        partido_data = opciones_partidos[seleccion]
        
        if st.button("⚡ SINCRONIZAR DATOS"):
            with st.spinner('Extrayendo estadísticas...'):
                standings = api_request("get_standings", {"league_id": league_id})
                
                # Función para buscar equipo de forma flexible
                def buscar_en_tabla(nombre, tabla):
                    for t in tabla:
                        if nombre.lower() in t['team_name'].lower() or t['team_name'].lower() in nombre.lower():
                            return t
                    return None

                data_l = buscar_en_tabla(partido_data['match_hometeam_name'], standings)
                data_v = buscar_en_tabla(partido_data['match_awayteam_name'], standings)
                
                if data_l and data_v:
                    pj_l = max(1, int(data_l.get('overall_league_payed', 1)))
                    pj_v = max(1, int(data_v.get('overall_league_payed', 1)))
                    
                    # Guardamos en session_state y forzamos float
                    st.session_state['lgf'] = float(data_l.get('overall_league_GF', 0)) / pj_l
                    st.session_state['lgc'] = float(data_l.get('overall_league_GA', 0)) / pj_l
                    st.session_state['vgf'] = float(data_v.get('overall_league_GF', 0)) / pj_v
                    st.session_state['vgc'] = float(data_v.get('overall_league_GA', 0)) / pj_v
                    st.session_state['l_name'] = partido_data['match_hometeam_name']
                    st.session_state['v_name'] = partido_data['match_awayteam_name']
                    st.success("✅ ¡Estadísticas cargadas!")
                else:
                    st.error("No se encontraron estadísticas para estos equipos en la tabla.")
    else:
        st.info("No hay partidos hoy en esta liga.")

    st.divider()
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, 2.5)
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 AUTO-ELITE</h1>", unsafe_allow_html=True)

# PANEL PRINCIPAL
col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Equipo L", st.session_state.get('l_name', 'Local'))
    c1, c2 = st.columns(2)
    # Importante: value=st.session_state.get(...) asegura que el input se llene
    lgf = c1.number_input("Goles Favor L", 0.0, 10.0, st.session_state.get('lgf', 0.0))
    lgc = c2.number_input("Goles Contra L", 0.0, 10.0, st.session_state.get('lgc', 0.0))
    ltj, lco = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3), c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Equipo V", st.session_state.get('v_name', 'Visitante'))
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles Favor V", 0.0, 10.0, st.session_state.get('vgf', 0.0))
    vgc = c4.number_input("Goles Contra V", 0.0, 10.0, st.session_state.get('vgc', 0.0))
    vtj, vco = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2), c4.number_input("Corners V", 0.0, 20.0, 4.8)

if st.button("🚀 REALIZAR ANÁLISIS COMPLETO", use_container_width=True):
    if lgf == 0 and vgf == 0:
        st.warning("⚠️ Los promedios de goles están en 0. Asegúrate de sincronizar o meter datos manuales.")
    
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # ... (El resto del código de visualización de resultados es idéntico al anterior)
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    # (Poner aquí las pestañas y gráficos que ya tienes)
    st.write(f"Probabilidad de Victoria Local: {res['1X2'][0]:.1f}%")
