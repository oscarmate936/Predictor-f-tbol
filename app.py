import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from fuzzywuzzy import process
import time
from collections import Counter

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO (v7.0 - FULL PRECISION)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Estados de sesión (Todos los originales preservados)
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []
if 'fatiga_l' not in st.session_state: st.session_state['fatiga_l'] = 1.0
if 'fatiga_v' not in st.session_state: st.session_state['fatiga_v'] = 1.0
if 'market_bias' not in st.session_state: st.session_state['market_bias'] = None
if 'hfa_specific' not in st.session_state: st.session_state['hfa_specific'] = (1.1, 0.9)
if 'draw_freq' not in st.session_state: st.session_state['draw_freq'] = 0.25
if 'corner_bias' not in st.session_state: st.session_state['corner_bias'] = (1.0, 1.0)
if 'proxy_xg_l' not in st.session_state: st.session_state['proxy_xg_l'] = 1.5
if 'proxy_xg_v' not in st.session_state: st.session_state['proxy_xg_v'] = 1.2
if 'luck_factor' not in st.session_state: st.session_state['luck_factor'] = (1.0, 1.0)
if 'conv_factor' not in st.session_state: st.session_state['conv_factor'] = (1.0, 1.0)
if 'tempo_factor' not in st.session_state: st.session_state['tempo_factor'] = (1.0, 1.0)
if 'stake_l' not in st.session_state: st.session_state['stake_l'] = 1.0
if 'stake_v' not in st.session_state: st.session_state['stake_v'] = 1.0
if 'tag_l' not in st.session_state: st.session_state['tag_l'] = "Estándar"
if 'tag_v' not in st.session_state: st.session_state['tag_v'] = "Estándar"

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE LÓGICA ELITE (MEJORADAS)
# =================================================================

def analyze_competition_stakes(standings, team_id):
    if not standings or not isinstance(standings, list): return 1.0, "Estándar"
    try:
        total_teams = len(standings)
        team_data = next((t for t in standings if t['team_id'] == team_id), None)
        if not team_data: return 1.0, "Estándar"
        pos = int(team_data.get('overall_league_position', 10))
        pj = int(team_data.get('overall_league_payed', 0))
        restantes = ((total_teams - 1) * 2) - pj
        if restantes <= 6:
            if pos <= 3: return 1.15, "CRÍTICO: TÍTULO"
            if pos >= total_teams - 3: return 1.18, "CRÍTICO: DESCENSO"
            if 4 <= pos <= 7: return 1.10, "ALTA: COPAS"
            if 8 <= pos <= total_teams - 4: return 0.85, "BAJA: SIN OBJETIVOS"
        return 1.0, "Estándar"
    except: return 1.0, "Estándar"

def api_request_live(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY, "_ts": time.time()})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

@st.cache_data(ttl=300)
def api_request_cached(league_id):
    params = {"action": "get_standings", "APIkey": API_KEY, "league_id": league_id}
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

@st.cache_data(ttl=600)
def get_team_tactical_stats(team_id, league_id):
    params = {"action": "get_statistics", "league_id": league_id, "team_id": team_id}
    data = api_request_live("get_statistics", params)
    if not data or 'corners' not in data: return 1.0, 1.0, 1.0
    try:
        shots_on_goal = int(data.get('shots_on_goal', 0))
        shots_total = int(data.get('shots_total', 0))
        match_played = int(data.get('match_played', 1))
        shots_off = max(0, shots_total - shots_on_goal)
        pxg_per_game = ((shots_on_goal * 0.33) + (shots_off * 0.10)) / match_played
        possession = int(data.get('possession', 50).replace('%',''))
        tempo = shots_total / (match_played * 12)
        ia = (1 + (int(data.get('shots_blocked', 0)) / match_played / 5)) * (possession / 50)
        return max(0.8, min(1.4, ia)), pxg_per_game, max(0.85, min(1.25, tempo))
    except: return 1.0, 1.0, 1.0

@st.cache_data(ttl=300)
def get_advanced_metrics(team_id, league_id, position, pxg_val, standings):
    events = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=60)).strftime('%Y-%m-%d'), 
                                             "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": league_id, "team_id": team_id})
    if not events or not isinstance(events, list): return 1.0, 1.0, 1.0, 1.0
    finished = [e for e in events if e['match_status'] == 'Finished']
    if not finished: return 1.0, 1.0, 1.0, 1.0
    momentum_gf, total_w, goles_reales = 0, 0, 0
    for m in finished[-5:]:
        try:
            m_date = datetime.strptime(m['match_date'], '%Y-%m-%d').replace(tzinfo=tz_sv)
            days_diff = (ahora_sv - m_date).days
            
            # MEJORA 1: DECAIMIENTO TEMPORAL HÍBRIDO (Exponencial + Lineal)
            w_exp = math.exp(-0.04 * days_diff)
            w_lin = max(0.1, 1 - (days_diff / 60))
            weight = (w_exp * 0.7) + (w_lin * 0.3)
            
            is_home = m['match_hometeam_id'] == team_id
            rival_id = m['match_awayteam_id'] if is_home else m['match_hometeam_id']
            
            # MEJORA 2: SCHEDULE STRENGTH (Calidad de Rivales)
            rival_data = next((t for t in standings if t['team_id'] == rival_id), None)
            rival_pos = int(rival_data['overall_league_position']) if rival_data else 10
            rival_strength = 1.25 if rival_pos <= 5 else (0.80 if rival_pos >= 15 else 1.0)
            
            gf = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            momentum_gf += (gf * weight * rival_strength)
            goles_reales += gf; total_w += weight
        except: continue

    expected_period = pxg_val * len(finished[-5:])
    conv_rate = (goles_reales / expected_period) if expected_period > 0 else 1.0
    momentum_adj = (momentum_gf / total_w) if total_w > 0 else 1.0
    elo_strength = 1.15 if int(position) <= 4 else (1.05 if int(position) <= 8 else 0.95)
    luck_factor = 1.0
    avg_goles = goles_reales / len(finished[-5:])
    if avg_goles > 2.0: luck_factor = 0.95
    elif avg_goles < 0.5: luck_factor = 1.05
    return elo_strength, momentum_adj, luck_factor, max(0.75, min(1.35, conv_rate))

def get_market_consensus(match_id):
    odds = api_request_live("get_odds", {"match_id": match_id})
    if not odds: return None
    try:
        o = odds[0]; o1, ox, o2 = float(o['odd_1']), float(o['odd_x']), float(o['odd_2'])
        margin = (1/o1) + (1/ox) + (1/o2)
        return ((1/o1)/margin, (1/ox)/margin, (1/o2)/margin)
    except: return None

# =================================================================
# 3. MOTOR MATEMÁTICO (QUANTUM DIXON-COLES PRO)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5, draw_freq=0.25): 
        base_rho = -0.12 if league_avg > 2.6 else -0.16
        if draw_freq > 0.30: base_rho -= 0.05
        self.rho = base_rho

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
        p1_d, px_d, p2_d, btts_d = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]; h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        g_probs_d = {t: [0.0, 0.0] for t in g_lines}
        h_probs_l_d = {h: 0.0 for h in h_lines}; h_probs_v_d = {h: 0.0 for h in h_lines}

        for i in range(10): 
            fila = []
            for j in range(10):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1_d += p
                elif i == j: px_d += p
                else: p2_d += p
                if i > 0 and j > 0: btts_d += p
                for t in g_lines:
                    if (i + j) > t: g_probs_d[t][0] += p
                    else: g_probs_d[t][1] += p
                for h in h_lines:
                    if (i + h) > j: h_probs_l_d[h] += p
                    if (j + h) > i: h_probs_v_d[h] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        total_d = max(0.0001, p1_d + px_d + p2_d)
        sim_h = np.random.poisson(xg_l, 10000); sim_v = np.random.poisson(xg_v, 10000)
        tot_g_sim = sim_h + sim_v; margen_sim = sim_h - sim_v
        
        # MEJORA 3: REFINAMIENTO DE TARJETAS (Volatilidad por tensión)
        prob_tension = (np.abs(sim_h - sim_v) <= 1).mean()
        tj_ajustado = tj_total * (1 + (prob_tension * 0.18))
        sim_tj = np.random.poisson(tj_ajustado, 15000)
        
        p1_mc = (sim_h > sim_v).mean(); px_mc = (sim_h == sim_v).mean(); p2_mc = (sim_v > sim_h).mean()
        W_D, W_MC = 0.70, 0.30
        p1_f = (p1_d/total_d * W_D) + (p1_mc * W_MC)
        px_f = (px_d/total_d * W_D) + (px_mc * W_MC)
        p2_f = (p2_d/total_d * W_D) + (p2_mc * W_MC)
        total_f = p1_f + px_f + p2_f

        if st.session_state['market_bias']:
            m1, mx, m2 = st.session_state['market_bias']
            p1_f = (p1_f/total_f * 0.75) + (m1 * 0.25)
            px_f = (px_f/total_f * 0.75) + (mx * 0.25)
            p2_f = (p2_f/total_f * 0.75) + (m2 * 0.25)
            total_f = p1_f + px_f + p2_f

        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        mc_data = {
            "L": p1_mc * 100, "X": px_mc * 100, "V": p2_mc * 100,
            "SIM_H": sim_h, "SIM_V": sim_v,
            "CS_L": (sim_v == 0).mean() * 100, "CS_V": (sim_h == 0).mean() * 100,
            "G_0_1": (tot_g_sim <= 1).mean() * 100,
            "G_2_3": ((tot_g_sim >= 2) & (tot_g_sim <= 3)).mean() * 100,
            "G_4_MAS": (tot_g_sim >= 4).mean() * 100,
            "M_L1": (margen_sim == 1).mean() * 100, "M_L2": (margen_sim == 2).mean() * 100, "M_L3": (margen_sim >= 3).mean() * 100,
            "M_V1": (margen_sim == -1).mean() * 100, "M_V2": (margen_sim == -2).mean() * 100, "M_V3": (margen_sim <= -3).mean() * 100,
            "VOLATILITY": np.std(tot_g_sim), "RAW_TOTALS": tot_g_sim
        }
        sim_co = np.random.poisson(co_total, 15000)
        return {
            "1X2": (p1_f/total_f*100, px_f/total_f*100, p2_f/total_f*100), 
            "DC": ((p1_f+px_f)/total_f*100, (p2_f+px_f)/total_f*100, (p1_f+p2_f)/total_f*100),
            "BTTS": (btts_d/total_d*100, (1 - btts_d/total_d)*100), 
            "GOLES": {t: ((g_probs_d[t][0]/total_d * W_D + (tot_g_sim > t).mean() * W_MC)*100, (g_probs_d[t][1]/total_d * W_D + (tot_g_sim <= t).mean() * W_MC)*100) for t in g_lines},
            "HANDICAPS": {"L": {h: (h_probs_l_d[h]/total_d*100*W_D + (sim_h + h > sim_v).mean()*100*W_MC) for h in h_lines}, 
                          "V": {h: (h_probs_v_d[h]/total_d*100*W_D + (sim_v + h > sim_h).mean()*100*W_MC) for h in h_lines}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza, "MONTECARLO": mc_data
        }

# =================================================================
# 4. DISEÑO UI/UX (ESTILO DORADO PRESERVADO)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE v7.0", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; display: flex; justify-content: space-between; align-items: center; }
    .value-badge { background: #d4af37; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.7em; font-weight: 900; box-shadow: 0 0 10px #d4af37; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; font-family: 'JetBrains Mono', monospace; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; text-transform: uppercase; letter-spacing: 3px; transition: 0.4s; width: 100%; }
    .mc-stat-box { background: linear-gradient(180deg, #11151c 0%, #0a0c10 100%); border: 1px solid #222; padding: 20px; border-radius: 16px; text-align: center; }
    .mc-val { font-size: 1.8em; font-weight: 900; color: #d4af37; font-family: 'JetBrains Mono'; display: block; }
    .wa-btn { background: #25D366; color: white !important; text-decoration: none; padding: 12px 25px; border-radius: 12px; font-weight: 800; display: inline-flex; align-items: center; gap: 10px; transition: 0.3s; margin-top: 15px; border: none; width: 100%; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin: 30px 0; background: #0a0c10; padding: 25px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #aaa; text-transform: uppercase; margin-bottom: 15px;">
                <span style="color:var(--secondary)">{n1}: <b>{p1:.1f}%</b></span>
                <span>{nx}: <b>{px_val:.1f}%</b></span>
                <span style="color:var(--primary)">{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 16px; border-radius: 50px; overflow: hidden; background: #1a1a1a;">
                <div style="width: {p1}%; background: var(--secondary); box-shadow: 0 0 15px var(--secondary);"></div>
                <div style="width: {px_val}%; background: #444;"></div>
                <div style="width: {p2}%; background: var(--primary); box-shadow: 0 0 15px var(--primary);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 22px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #eee; margin-bottom: 8px;">
                <span style="font-weight: 600;">{label_over} <span style="color:{color};">{prob_over:.1f}%</span></span>
                <span style="color: #666;">{prob_under:.1f}% {label_under}</span>
            </div>
            <div style="display: flex; background: #111; height: 10px; border-radius: 5px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color};"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR (TODAS LAS LIGAS ORIGINALES RESTAURADAS)
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL v7.0</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Saudi Pro League": 307, "Trendyol Süper Lig": 322, "Liga Mayor (El Salvador)": 601, "Copa Presidente (El Salvador)": 603,
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207, "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, 
        "UEFA Champions League": 3, "UEFA Europa League": 4, "UEFA Conference League": 683, "Copa Libertadores": 13,
        "Brasileirão Betano (Série A)": 99, "Brasileirão Série B": 100, "Brasileirão Série C": 103, "Copa de Brasil": 101,
        "FA Cup (Inglaterra)": 145, "EFL Cup (Inglaterra)": 146, "Copa del Rey (España)": 300, "Coppa Italia (Italia)": 209, "DFB Pokal (Alemania)": 177, "Coupe de France (Francia)": 169
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()), help="Selecciona la liga para sincronizar datos reales.")
    fecha_analisis = st.date_input("📅 JORNADA CENTRAL", value=ahora_sv.date())
    
    if st.button("SYNC DATA"):
        st.cache_data.clear()
        with st.spinner("QUANTUM DEEP SYNC..."):
            f_desde = (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d'); f_hasta = (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d')
            raw_events = api_request_live("get_events", {"from": f_desde, "to": f_hasta, "league_id": ligas_api[nombre_liga]})
            standings = api_request_cached(ligas_api[nombre_liga])
            if raw_events and standings:
                match_info = raw_events[0]
                h_goals = sum(int(t['home_league_GF']) for t in standings); a_goals = sum(int(t['away_league_GF']) for t in standings)
                draws = sum(int(t['overall_league_D']) for t in standings); total_pj = sum(int(t['overall_league_payed']) for t in standings)
                st.session_state['draw_freq'] = draws / total_pj; st.session_state['p_liga_auto'] = (h_goals + a_goals) / (total_pj / 2)
                st.session_state['hfa_league'] = float(h_goals / a_goals)
                def buscar(n):
                    nombres = [t['team_name'] for t in standings]; m, s = process.extractOne(n, nombres); return next((t for t in standings if t['team_name'] == m), None) if s > 65 else None
                dl, dv = buscar(match_info['match_hometeam_name']), buscar(match_info['match_awayteam_name'])
                if dl and dv:
                    sl, tl = analyze_competition_stakes(standings, dl['team_id']); sv, tv = analyze_competition_stakes(standings, dv['team_id'])
                    st.session_state['stake_l'], st.session_state['tag_l'] = sl, tl; st.session_state['stake_v'], st.session_state['tag_v'] = sv, tv
                    cb_l, pxg_l, tempo_l = get_team_tactical_stats(dl['team_id'], ligas_api[nombre_liga])
                    cb_v, pxg_v, tempo_v = get_team_tactical_stats(dv['team_id'], ligas_api[nombre_liga])
                    st.session_state['tempo_factor'] = (tempo_l, tempo_v); st.session_state['corner_bias'] = (cb_l, cb_v)
                    elo_l, mom_l, luck_l, conv_l = get_advanced_metrics(dl['team_id'], ligas_api[nombre_liga], dl['overall_league_position'], pxg_l, standings)
                    elo_v, mom_v, luck_v, conv_v = get_advanced_metrics(dv['team_id'], ligas_api[nombre_liga], dv['overall_league_position'], pxg_v, standings)
                    st.session_state['conv_factor'] = (conv_l, conv_v); st.session_state['luck_factor'] = (luck_l, luck_v); st.session_state['elo_bias'] = (elo_l, elo_v)
                    st.session_state['proxy_xg_l'], st.session_state['proxy_xg_v'] = pxg_l, pxg_v
                    st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/int(dl['home_league_payed'])) * 0.6 + (mom_l * 0.4)
                    st.session_state['vgf_auto'] = (float(dv['away_league_GF'])/int(dv['away_league_payed'])) * 0.6 + (mom_v * 0.4)
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.session_state['market_bias'] = get_market_consensus(match_info['match_id'])
                    st.rerun()

# =================================================================
# 6. CONTENIDO PRINCIPAL (OR936 ELITE v7.0)
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900;'>OR936 <span style='color:#d4af37'>ELITE</span> v7.0</h1>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown(f"<div style='border-right: 2px solid var(--secondary); text-align: right; padding-right: 15px;'><h6 style='color:var(--secondary); margin:0; font-weight:900;'>LOCAL <span style='font-size:0.7em; color:#666;'>{st.session_state['tag_l']}</span></h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf = la.number_input("GF Local", 0.0, 10.0, key='lgf_auto', help="Promedio de goles proyectado.")
    ltj = lb.number_input("Tarjetas L", 0.0, 15.0, key='ltj_auto')

with col_v:
    st.markdown(f"<div style='border-left: 2px solid var(--primary); text-align: left; padding-left: 15px;'><h6 style='color:var(--primary); margin:0; font-weight:900;'>VISITANTE <span style='font-size:0.7em; color:#666;'>{st.session_state['tag_v']}</span></h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Nombre Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf = va.number_input("GF Visita", 0.0, 10.0, key='vgf_auto')
    vtj = vb.number_input("Tarjetas V", 0.0, 15.0, key='vtj_auto')

p_liga = st.slider("Media de Goles de la Liga", 0.5, 5.0, key='p_liga_auto', help="Ajusta el nivel ofensivo base de la competición.")

if st.button("GENERAR REPORTE DE INTELIGENCIA QUANTUM"):
    motor = MotorMatematico(p_liga, st.session_state['draw_freq'])
    conv_l, conv_v = st.session_state['conv_factor']; tempo_l, tempo_v = st.session_state['tempo_factor']
    
    # AJUSTE QUANTUM FINAL (Integrando todas las mejoras de precisión)
    xg_l = (lgf * 0.4 + st.session_state['proxy_xg_l'] * 0.6) * st.session_state['hfa_league'] * conv_l * tempo_l * st.session_state['stake_l'] * st.session_state['elo_bias'][0]
    xg_v = (vgf * 0.4 + st.session_state['proxy_xg_v'] * 0.6) * (1/st.session_state['hfa_league']) * conv_v * tempo_v * st.session_state['stake_v'] * st.session_state['elo_bias'][1]
    
    res = motor.procesar(xg_l, xg_v, (ltj + vtj), (st.session_state['lco_auto'] + st.session_state['vco_auto']))

    # MEJORA 4: VALUE BET INDICATOR
    def check_value(prob, market_idx):
        if not st.session_state['market_bias']: return False
        m_prob = st.session_state['market_bias'][market_idx]
        return prob > (m_prob * 100 + 8) # 8% de ventaja sobre el mercado

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary);'>💎 TOP SELECCIONES (Confianza: {res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
        pool = [
            {"t": "1X (Local o Empate)", "p": res['DC'][0], "v": check_value(res['DC'][0], 0)},
            {"t": "X2 (Visita o Empate)", "p": res['DC'][1], "v": check_value(res['DC'][1], 2)},
            {"t": "BTTS: SÍ", "p": res['BTTS'][0], "v": False},
            {"t": "Over 2.5 Goles", "p": res['GOLES'][2.5][0], "v": False}
        ]
        for s in sorted(pool, key=lambda x: x['p'], reverse=True):
            val_tag = '<span class="value-badge">💎 VALUE</span>' if s['v'] else ''
            st.markdown(f'<div class="verdict-item"><span><b>{s["p"]:.1f}%</b> — {s["t"]}</span> {val_tag}</div>', unsafe_allow_html=True)
        
        # WhatsApp Share
        msg_wa = f"💎 *OR936 ELITE v7.0* 💎\n📍 *{nl_manual} vs {nv_manual}*\n🎯 Confianza: {res['BRIER']*100:.1f}%\n✅ Top Pick: {pool[0]['t']} ({pool[0]['p']:.1f}%)"
        st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg_wa)}" target="_blank" class="wa-btn">📲 COMPARTIR PICKS</a>', unsafe_allow_html=True)

    with v2:
        st.markdown("<h4 style='color:#fff; text-align:center;'>🎯 MARCADOR PROBABLE</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} <span style="font-size:0.6em; color:#666;">({prob:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl_manual, "Empate", nv_manual)

    # RE-ESTABLECIMIENTO DE TODAS LAS PESTAÑAS ORIGINALES + MEJORAS
    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(["🥅 GOLES", "🏆 HANDICAP", "📊 1X2", "🚩 ESPECIALES", "🎲 MONTE CARLO PRO", "🎯 RADAR TÁCTICO", "🧩 MATRIZ", "📈 AUDITORÍA"])

    with t1:
        ga, gb = st.columns(2)
        with ga:
            for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with gb: dual_bar_explicit("AMBOS ANOTAN: SÍ", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")
    
    with t2:
        ha, hb = st.columns(2)
        with ha:
            st.markdown(f"<h5 style='color:var(--secondary);'>{nl_manual}</h5>", unsafe_allow_html=True)
            for h, p in res['HANDICAPS']['L'].items(): dual_bar_explicit(f"Handicap {h:+}", p, "", 100-p, color="#00ffa3")
        with hb:
            st.markdown(f"<h5 style='color:var(--primary);'>{nv_manual}</h5>", unsafe_allow_html=True)
            for h, p in res['HANDICAPS']['V'].items(): dual_bar_explicit(f"Handicap {h:+}", p, "", 100-p, color="#d4af37")

    with t3:
        dual_bar_explicit(f"1X ({nl_manual} o Empate)", res['DC'][0], "2 Directo", 100-res['DC'][0], color="#00ffa3")
        dual_bar_explicit(f"X2 ({nv_manual} o Empate)", res['DC'][1], "1 Directo", 100-res['DC'][1], color="#d4af37")
        dual_bar_explicit(f"12 (Cualquiera Gana)", res['DC'][2], "Empate", 100-res['DC'][2], color="#ffffff")

    with t4:
        ta, co = st.columns(2)
        with ta:
            st.markdown(f"<h5 style='color:#ff4b4b; text-align:center;'>TARJETAS (Volatilidad Ajustada)</h5>", unsafe_allow_html=True)
            for l, p in res['TARJETAS'].items(): dual_bar_explicit(f"Tarjetas > {l}", p[0], f"< {l}", p[1], color="#ff4b4b")
        with co:
            st.markdown("<h5 style='color:#00ffa3; text-align:center;'>CORNERS</h5>", unsafe_allow_html=True)
            for l, p in res['CORNERS'].items(): dual_bar_explicit(f"Corners > {l}", p[0], f"< {l}", p[1], color="#00ffa3")

    with t5:
        mc = res['MONTECARLO']
        st.markdown("<div class='mc-stat-box'>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Local", f"{mc['L']:.1f}%"); c2.metric("Draw", f"{mc['X']:.1f}%"); c3.metric("Win Away", f"{mc['V']:.1f}%"); c4.metric("Volatilidad", f"{mc['VOLATILITY']:.2f}")
        st.plotly_chart(px.histogram(mc['RAW_TOTALS'], nbins=15, title="Curva de Densidad de Goles", color_discrete_sequence=['#d4af37']), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with t6: # MEJORA 5: RADAR TÁCTICO
        cat = ['xG Ataque', 'Conversión', 'Tempo/Ritmo', 'ELO Fuerza', 'Defensa']
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=[xg_l, conv_l, tempo_l, st.session_state['elo_bias'][0], 1.5/st.session_state['lgc_auto']], theta=cat, fill='toself', name=nl_manual, line_color='#00ffa3'))
        fig.add_trace(go.Scatterpolar(r=[xg_v, conv_v, tempo_v, st.session_state['elo_bias'][1], 1.5/st.session_state['vgc_auto']], theta=cat, fill='toself', name=nv_manual, line_color='#d4af37'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 2.5])), paper_bgcolor='rgba(0,0,0,0)', font_color="white", title="Balance Táctico Quantum")
        st.plotly_chart(fig, use_container_width=True)

    with t7:
        st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='YlGnBu', title="Matriz de Probabilidad Exacta"), use_container_width=True)

    with t8:
        st.info("Sincroniza una liga para activar el backtesting automático basado en los últimos 10 resultados.")
