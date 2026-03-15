import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from bs4 import BeautifulSoup
from fuzzywuzzy import process
import time
import json
import google.generativeai as genai

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO
# =================================================================
API_KEY_FOOTBALL = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
# API KEY INTEGRADA
GEMINI_API_KEY = "AIzaSyDxmkDZKvPT6qHHEEU21a6SZzrAmak6l64"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

BASE_URL = "https://apiv3.apifootball.com/"
tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Inicialización de estados
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []
if 'historial_analisis' not in st.session_state: st.session_state['historial_analisis'] = []
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)

defaults = {
    'p_liga_auto': 2.5, 'lgf_auto': 1.7, 'vgf_auto': 1.5, 'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. INTELIGENCIA ARTIFICIAL (AGENTIC NEWS & STATS SEARCH)
# =================================================================

def extract_stats_with_gemini(home_team, away_team, league_name):
    """
    Agente de IA que busca estadísticas, noticias de lesionados y bajas 
    para ajustar el xG de forma dinámica.
    """
    # Buscamos estadísticas puras y noticias de última hora
    query = f"stats and injuries {home_team} vs {away_team} football match {league_name} latest news"
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    try:
        res = requests.get(search_url, headers=headers, timeout=12)
        soup = BeautifulSoup(res.text, 'html.parser')
        snippets = [div.text for div in soup.find_all('div') if len(div.text) > 45][:10]
        context = "\n".join(snippets)
        
        prompt = f"""
        Como analista de fútbol profesional, extrae datos para el partido: {home_team} (Local) vs {away_team} (Visitante).
        
        INSTRUCCIONES:
        1. Analiza el xG (Goles Esperados) considerando:
           - Rendimiento del LOCAL únicamente en casa.
           - Rendimiento del VISITANTE únicamente fuera.
        2. ANALIZADOR DE BAJAS: Busca noticias de lesionados o suspendidos. 
           - Si el goleador o portero titular de un equipo no juega, reduce su xG en un 15-20%.
        3. Extrae promedios de tarjetas y corners.

        Texto de búsqueda: {context}

        Responde ESTRICTAMENTE con este formato JSON:
        {{
            "xg_home": float, 
            "xg_away": float, 
            "league_avg": float, 
            "corners_home": float, 
            "corners_away": float, 
            "cards_home": float, 
            "cards_away": float,
            "news_summary": "resumen breve de bajas encontradas"
        }}
        """
        
        response = model.generate_content(prompt)
        clean_res = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_res)
    except Exception as e:
        st.error(f"Error en el Agente IA: {e}")
        return None

# =================================================================
# 3. MOTOR MATEMÁTICO (DIXON-COLES ORIGINAL)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.12

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
        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz,
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [3.5, 4.5, 5.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [7.5, 8.5, 9.5]}
        }

# =================================================================
# 4. UI/UX (IDENTICA A TU ORIGINAL)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; text-transform: uppercase; letter-spacing: 3px; }
    .news-box { background: rgba(212, 175, 55, 0.05); border: 1px solid var(--primary); padding: 15px; border-radius: 12px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207,
        "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, "Primeira Liga (Portugal)": 262,
        "Liga Mayor (El Salvador)": 601, "Brasileirão (Série A)": 99
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA", value=ahora_sv.date())
    
    # Discovery via API (Backup)
    try:
        raw_events = requests.get(BASE_URL, params={"action": "get_events", "from": fecha_analisis, "to": fecha_analisis, "league_id": ligas_api[nombre_liga], "APIkey": API_KEY_FOOTBALL}).json()
    except: raw_events = []

    if isinstance(raw_events, list) and raw_events:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partido", list(op_p.keys()))

        if st.button("🚀 SYNC QUANTUM IA"):
            with st.spinner("IA ANALIZANDO NOTICIAS Y STATS..."):
                m_info = op_p[p_sel]
                ai_res = extract_stats_with_gemini(m_info['match_hometeam_name'], m_info['match_awayteam_name'], nombre_liga)
                
                if ai_res:
                    st.session_state['nl_auto'] = m_info['match_hometeam_name']
                    st.session_state['nv_auto'] = m_info['match_awayteam_name']
                    st.session_state['lgf_auto'] = ai_res['xg_home']
                    st.session_state['vgf_auto'] = ai_res['xg_away']
                    st.session_state['p_liga_auto'] = ai_res['league_avg']
                    st.session_state['ltj_auto'] = ai_res['cards_home']
                    st.session_state['lco_auto'] = ai_res['corners_home']
                    st.session_state['vtj_auto'] = ai_res['cards_away']
                    st.session_state['vco_auto'] = ai_res['corners_away']
                    st.session_state['news_current'] = ai_res['news_summary']
                    st.rerun()

# --- INPUTS PRINCIPALES ---
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE IA</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>AGENTIC INTELLIGENCE V4.6</p>", unsafe_allow_html=True)

if 'news_current' in st.session_state:
    st.markdown(f'<div class="news-box"><b>📰 REPORTE DE BAJAS IA:</b><br>{st.session_state["news_current"]}</div>', unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-right: 2px solid var(--secondary); text-align: right; padding-right: 15px;'><h6 style='color:var(--secondary); margin:0; font-weight:900;'>LOCAL</h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf = la.number_input("xG Local (Home Only)", 0.0, 10.0, key='lgf_auto')
    ltj = la.number_input("Tarjetas L", 0.0, 15.0, key='ltj_auto')
    lco = lb.number_input("Corners L", 0.0, 20.0, key='lco_auto')

with col_v:
    st.markdown("<div style='border-left: 2px solid var(--primary); text-align: left; padding-left: 15px;'><h6 style='color:var(--primary); margin:0; font-weight:900;'>VISITANTE</h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf = va.number_input("xG Visita (Away Only)", 0.0, 10.0, key='vgf_auto')
    vtj = va.number_input("Tarjetas V", 0.0, 15.0, key='vtj_auto')
    vco = vb.number_input("Corners V", 0.0, 20.0, key='vco_auto')

p_liga = st.slider("Media Goles Liga", 0.5, 5.0, key='p_liga_auto')

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(p_liga)
    res = motor.procesar(lgf, vgf, ltj+vtj, lco+vco)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary);'>💎 TOP SELECCIONES IA</h4>", unsafe_allow_html=True)
        st.write(f"Prob. {nl_manual}: {res['1X2'][0]:.1f}%")
        st.write(f"Empate: {res['1X2'][1]:.1f}%")
        st.write(f"Prob. {nv_manual}: {res['1X2'][2]:.1f}%")
        st.write(f"Ambos Anotan: {'SÍ' if res['BTTS'][0] > 52 else 'NO'} ({res['BTTS'][0]:.1f}%)")
    with v2:
        st.markdown("<h4 style='color:#fff; text-align:center;'>🎯 MARCADORES</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>AGENTE GEMINI 1.5 FLASH ACTIVO | BRIER CALIBRATION | OR936 v4.6</p>", unsafe_allow_html=True)
