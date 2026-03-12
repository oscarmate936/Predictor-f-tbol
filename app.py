import streamlit as st
import math
import pandas as pd
import numpy as np  # MEJORA: Vectorización
import plotly.express as px
import requests
from datetime import datetime
import urllib.parse

# =================================================================
# CONFIGURACIÓN API
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.0
if 'form_l' not in st.session_state: st.session_state['form_l'] = 1.0
if 'form_v' not in st.session_state: st.session_state['form_v'] = 1.0
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.7
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.2
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.5
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.1

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except: return []

# =================================================================
# MOTOR MATEMÁTICO ELITE (Upgrade Interno)
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        # Ajuste dinámico de Rho basado en la tendencia de la liga
        if league_avg > 3.0: self.rho = -0.10
        elif league_avg < 2.2: self.rho = -0.18
        else: self.rho = -0.15

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
        # 1. MATRIZ BASE (Dixon-Coles)
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

        # 2. SIMULACIÓN MONTECARLO VECTORIZADA (MEJORA: NumPy)
        # Reemplaza el loop por operaciones matriciales rápidas
        iteraciones = 15000
        sim_tj = np.random.poisson(tj_total, iteraciones)
        sim_co = np.random.poisson(co_total, iteraciones)

        tj_probs = {t: (np.sum(sim_tj > t)/iteraciones*100, np.sum(sim_tj <= t)/iteraciones*100) for t in [2.5, 3.5, 4.5, 5.5, 6.5]}
        co_probs = {t: (np.sum(sim_co > t)/iteraciones*100, np.sum(sim_co <= t)/iteraciones*100) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]}

        total = max(0.0001, p1 + px + p2)
        # Índice de Estabilidad (Confianza)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": tj_probs,
            "CORNERS": co_probs,
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz,
            "BRIER": confianza
        }

# =================================================================
# DISEÑO UI/UX (IDÉNTICO AL ORIGINAL)
# =================================================================
st.set_page_config(page_title="OR936 PRO ELITE", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: radial-gradient(circle at top right, #1a1f25, #0a0c10); }
    .master-card { background: rgba(22, 27, 34, 0.7); padding: 30px; border-radius: 20px; border: 1px solid rgba(212, 175, 55, 0.2); box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 25px; backdrop-filter: blur(10px); }
    .verdict-item { background: linear-gradient(90deg, rgba(0, 255, 163, 0.1) 0%, rgba(0,0,0,0) 100%); border-left: 3px solid #00ffa3; padding: 12px 15px; margin-bottom: 10px; border-radius: 4px 12px 12px 4px; color: #e0e0e0; font-size: 0.95em; }
    .elite-alert { background: linear-gradient(90deg, rgba(0, 255, 163, 0.2) 0%, rgba(212, 175, 55, 0.1) 100%); border: 1px solid #00ffa3; box-shadow: 0 0 15px rgba(0, 255, 163, 0.3); font-weight: 700; }
    .score-badge { background: #000; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 8px; text-align: center; color: #d4af37; font-weight: 900; font-size: 1.1em; letter-spacing: 1px; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #aa8a2e 100%); color: #000 !important; font-weight: 800; border: none; padding: 15px; border-radius: 12px; text-transform: uppercase; letter-spacing: 2px; transition: all 0.3s ease; width: 100%; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background-color: #25D366; color: white !important; padding: 12px; border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 0.9em; margin-top: 10px; text-align: center; }
    [data-testid="stSidebar"] { background-color: #0a0c10; border-right: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin: 25px 0; background: #000; padding: 20px; border-radius: 15px; border: 1px solid #222;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #888; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 1px;">
                <span style="color:#00ffa3">{n1}: <b>{p1:.1f}%</b></span>
                <span>{nx}: <b>{px_val:.1f}%</b></span>
                <span style="color:#d4af37">{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: #111;">
                <div style="width: {p1}%; background: #00ffa3; box-shadow: 0 0 15px rgba(0,255,163,0.4);"></div>
                <div style="width: {px_val}%; background: #333;"></div>
                <div style="width: {p2}%; background: #d4af37; box-shadow: 0 0 15px rgba(212,175,55,0.4);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 18px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #bbb; margin-bottom: 6px;">
                <span>{label_over}: <b>{prob_over:.1f}%</b></span>
                <span style="opacity: 0.6;">{prob_under:.1f}% : {label_under}</span>
            </div>
            <div style="display: flex; background: #000; height: 8px; border-radius: 4px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color}; box-shadow: 0 0 8px {color}66;"></div>
                <div style="width: {prob_under}%; background: #1a1a1a;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Brasileirão Betano (Série A)": 99, "Brasileirão Série B": 100, "Brasileirão Série C": 103, "Copa de Brasil": 101,
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207, "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, 
        "UEFA Champions League": 3, "UEFA Europa League": 4, "UEFA Conference League": 683, "Copa Libertadores": 13,
        "FA Cup (Inglaterra)": 145, "EFL Cup (Inglaterra)": 146, "Copa del Rey (España)": 300, "Coppa Italia (Italia)": 209, "DFB Pokal (Alemania)": 177, "Coupe de France (Francia)": 169,
        "Liga Mayor (El Salvador)": 601, "Copa Presidente (El Salvador)": 603
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha de Jornada", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Eventos en Vivo", list(op_p.keys()))

        if st.button("SYNC DATA"):
            # MEJORA: Feedback de carga
            with st.spinner("Analizando métricas de competición..."):
                standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
                if standings and isinstance(standings, list):
                    h_goals = sum(int(t['home_league_GF']) for t in standings)
                    a_goals = sum(int(t['away_league_GF']) for t in standings)
                    total_pj = sum(int(t['overall_league_payed']) for t in standings)
                    
                    st.session_state['p_liga_auto'] = float((h_goals + a_goals) / (total_pj / 2)) if total_pj > 0 else 2.5
                    st.session_state['hfa_league'] = float(h_goals / a_goals) if a_goals > 0 else 1.0

                    def buscar(n):
                        for t in standings: 
                            if n.lower() in t['team_name'].lower() or t['team_name'].lower() in n.lower(): return t
                        return None

                    dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                    if dl and dv:
                        st.session_state['form_l'] = 1.15 if int(dl['overall_league_position']) < int(dv['overall_league_position']) else 0.95
                        st.session_state['form_v'] = 1.10 if int(dv['overall_league_position']) < int(dl['overall_league_position']) else 0.90
                        pj_h, pj_a = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['lgf_auto'] = float(dl['home_league_GF'])/pj_h if pj_h>0 else 0.0
                        st.session_state['lgc_auto'] = float(dl['home_league_GA'])/pj_h if pj_h>0 else 0.0
                        st.session_state['vgf_auto'] = float(dv['away_league_GF'])/pj_a if pj_a>0 else 0.0
                        st.session_state['vgc_auto'] = float(dv['away_league_GA'])/pj_a if pj_a>0 else 0.0
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.rerun()

# CONTENIDO PRINCIPAL (IDÉNTICO)
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666; font-size: 0.9em; margin-bottom: 40px;'>PREDICTIVE INTELLIGENCE ENGINE V3.5 PRO + NUMPY MONTE CARLO</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-left: 2px solid #00ffa3; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🏠 LOCAL</h3></div>", unsafe_allow_html=True)
    nl = st.text_input("Nombre", key='nl_auto', label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("Goles Favor L", 0.0, 10.0, step=0.1, key='lgf_auto'), lb.number_input("Goles Contra L", 0.0, 10.0, step=0.1, key='lgc_auto')
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.3, step=0.1), lb.number_input("Corners L", 0.0, 20.0, 5.5, step=0.1)

with col_v:
    st.markdown("<div style='border-left: 2px solid #d4af37; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🚀 VISITANTE</h3></div>", unsafe_allow_html=True)
    nv = st.text_input("Nombre", key='nv_auto', label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("Goles Favor V", 0.
