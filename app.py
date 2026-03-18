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
from collections import Counter

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO (v7.0 - LIVE MODE READY)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Estados de sesión originales y nuevos de contexto
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

# NUEVOS ESTADOS v7.0 LIVE
if 'is_live' not in st.session_state: st.session_state['is_live'] = False
if 'live_min' not in st.session_state: st.session_state['live_min'] = 0
if 'live_score' not in st.session_state: st.session_state['live_score'] = (0, 0)

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE LÓGICA ELITE (PRESERVADAS)
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
        shots_total = int(data.get('shots_total', 12))
        match_played = int(data.get('match_played', 1))
        shots_on_goal = int(data.get('shots_on_goal', 4))
        pxg_per_game = ((shots_on_goal * 0.33) + ((shots_total-shots_on_goal) * 0.10)) / match_played
        possession = int(data.get('possession', 50).replace('%',''))
        tempo = shots_total / (match_played * 12)
        ia = (1 + (int(data.get('shots_blocked', 0)) / match_played / 5)) * (possession / 50)
        return max(0.8, min(1.4, ia)), pxg_per_game, max(0.85, min(1.25, tempo))
    except: return 1.0, 1.0, 1.0

def get_fatigue_factor(team_id, match_date_str):
    last_matches = api_request_live("get_events", {
        "from": (datetime.strptime(match_date_str, '%Y-%m-%d') - timedelta(days=10)).strftime('%Y-%m-%d'),
        "to": (datetime.strptime(match_date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d'),
        "team_id": team_id
    })
    if not last_matches: return 1.0
    try:
        last_date = datetime.strptime(last_matches[-1]['match_date'], '%Y-%m-%d')
        target_date = datetime.strptime(match_date_str, '%Y-%m-%d')
        days_off = (target_date - last_date).days
        return 0.92 if days_off <= 3 else (1.05 if days_off >= 7 else 1.0)
    except: return 1.0

def get_market_consensus(match_id):
    odds = api_request_live("get_odds", {"match_id": match_id})
    if not odds: return None
    try:
        o = odds[0]; o1, ox, o2 = float(o['odd_1']), float(o['odd_x']), float(o['odd_2'])
        margin = (1/o1) + (1/ox) + (1/o2)
        return ((1/o1)/margin, (1/ox)/margin, (1/o2)/margin)
    except: return None

@st.cache_data(ttl=300)
def get_advanced_metrics(team_id, league_id, position, pxg_val):
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
            weight = math.exp(-0.04 * days_diff)
            is_home = m['match_hometeam_id'] == team_id
            gf = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            momentum_gf += (gf * weight); goles_reales += gf; total_w += weight
        except: continue
    expected = pxg_val * len(finished[-5:])
    conv_rate = (goles_reales / expected) if expected > 0 else 1.0
    momentum_adj = (momentum_gf / total_w) if total_w > 0 else 1.0
    elo = 1.15 if int(position) <= 4 else (1.05 if int(position) <= 8 else 0.95)
    return elo, momentum_adj, 1.0, max(0.75, min(1.35, conv_rate))

@st.cache_data(ttl=300)
def get_h2h_data(team_id_l, team_id_v):
    res = api_request_live("get_H2H", {"firstTeamId": team_id_l, "secondTeamId": team_id_v})
    if not res or 'firstTeam' not in res: return 1.0, 1.0
    matches = res.get('firstTeam', []) + res.get('secondTeam', [])
    if not matches: return 1.0, 1.0
    l_pts, v_pts = 0, 0
    for m in matches[:6]:
        try:
            h_s, a_s = int(m.get('match_hometeam_score', 0)), int(m.get('match_awayteam_score', 0))
            if h_s > a_s:
                if m['match_hometeam_id'] == team_id_l: l_pts += 3
                else: v_pts += 3
            elif h_s < a_s:
                if m['match_hometeam_id'] == team_id_l: v_pts += 3
                else: l_pts += 3
            else: l_pts += 1; v_pts += 1
        except: continue
    total = l_pts + v_pts if (l_pts + v_pts) > 0 else 1
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 3. MOTOR MATEMÁTICO (QUANTUM PULSE v7.0)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5, draw_freq=0.25): 
        self.rho = -0.12 if league_avg > 2.6 else -0.16
        if draw_freq > 0.30: self.rho -= 0.05

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def procesar(self, xg_l, xg_v, tj_total, co_total, live_score=(0,0)):
        p1_d, px_d, p2_d, btts_d = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]; h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        g_probs_d = {t: [0.0, 0.0] for t in g_lines}
        h_probs_l_d = {h: 0.0 for h in h_lines}; h_probs_v_d = {h: 0.0 for h in h_lines}
        cur_h, cur_v = live_score

        for i in range(10): 
            fila = []
            for j in range(10):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                final_h, final_v = i + cur_h, j + cur_v
                if final_h > final_v: p1_d += p
                elif final_h == final_v: px_d += p
                else: p2_d += p
                if final_h > 0 and final_v > 0: btts_d += p
                for t in g_lines:
                    if (final_h + final_v) > t: g_probs_d[t][0] += p
                    else: g_probs_d[t][1] += p
                for h in h_lines:
                    if (final_h + h) > final_v: h_probs_l_d[h] += p
                    if (final_v + h) > final_h: h_probs_v_d[h] += p
                if i <= 4 and j <= 4: marcadores[f"{final_h}-{final_v}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        total_d = max(0.0001, p1_d + px_d + p2_d)
        sim_h = np.random.poisson(xg_l, 10000) + cur_h
        sim_v = np.random.poisson(xg_v, 10000) + cur_v
        tot_g_sim = sim_h + sim_v; p1_mc = (sim_h > sim_v).mean()
        px_mc = (sim_h == sim_v).mean(); p2_mc = (sim_v > sim_h).mean()
        
        W_D, W_MC = 0.70, 0.30
        p1_f = (p1_d/total_d * W_D) + (p1_mc * W_MC)
        px_f = (px_d/total_d * W_D) + (px_mc * W_MC)
        p2_f = (p2_d/total_d * W_D) + (p2_mc * W_MC)
        total_f = p1_f + px_f + p2_f

        mc_data = {
            "L": p1_f*100, "X": px_f*100, "V": p2_f*100, "SIM_H": sim_h, "SIM_V": sim_v,
            "VOLATILITY": np.std(tot_g_sim), "RAW_TOTALS": tot_g_sim
        }
        return {
            "1X2": (p1_f/total_f*100, px_f/total_f*100, p2_f/total_f*100), 
            "DC": ((p1_f+px_f)/total_f*100, (p2_f+px_f)/total_f*100, (p1_f+p2_f)/total_f*100),
            "BTTS": (btts_d/total_d*100, (1 - btts_d/total_d)*100), 
            "GOLES": {t: ((g_probs_d[t][0]/total_d * W_D + (tot_g_sim > t).mean() * W_MC)*100, (g_probs_d[t][1]/total_d * W_D + (tot_g_sim <= t).mean() * W_MC)*100) for t in g_lines},
            "HANDICAPS": {"L": {h: (h_probs_l_d[h]/total_d*100*W_D + (sim_h + h > sim_v).mean()*100*W_MC) for h in h_lines}, 
                          "V": {h: (h_probs_v_d[h]/total_d*100*W_D + (sim_v + h > sim_h).mean()*100*W_MC) for h in h_lines}},
            "TARJETAS": {t: (np.sum(np.random.poisson(tj_total, 10000) > t)/100, 0) for t in [2.5, 3.5, 4.5]},
            "CORNERS": {t: (np.sum(np.random.poisson(co_total, 10000) > t)/100, 0) for t in [8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": 1-(abs(xg_l-xg_v)/(xg_l+xg_v+2)), "MONTECARLO": mc_data
        }

# =================================================================
# 4. DISEÑO UI/UX (DORADO/NEGRO PRESERVADO)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE v7.0", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; }
    .elite-alert { background: linear-gradient(90deg, rgba(212,175,55,0.15), rgba(0,255,163,0.05)); border: 1px solid var(--primary); }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; font-family: 'JetBrains Mono', monospace; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; text-transform: uppercase; letter-spacing: 3px; transition: 0.4s; width: 100%; }
    .mc-container { background: #080a0e; border: 1px solid #1a1e26; border-radius: 20px; padding: 30px; }
    .mc-stat-box { background: linear-gradient(180deg, #11151c 0%, #0a0c10 100%); border: 1px solid #222; padding: 20px; border-radius: 16px; text-align: center; }
    .mc-val { font-size: 1.8em; font-weight: 900; color: #d4af37; font-family: 'JetBrains Mono'; display: block; }
    .mc-lab { font-size: 0.75em; color: #666; text-transform: uppercase; letter-spacing: 2px; }
    .ref-box { background: linear-gradient(90deg, rgba(212, 175, 55, 0.08), rgba(0,0,0,0)); border-left: 4px solid var(--primary); padding: 20px; border-radius: 0 15px 15px 0; margin-bottom: 25px; border: 1px solid rgba(212,175,55,0.1); }
    .motivation-tag { background: rgba(212, 175, 55, 0.1); color: var(--primary); padding: 2px 8px; border-radius: 4px; font-size: 0.7em; font-weight: 700; border: 1px solid var(--primary); }
    .live-badge { background: #ff4b4b; color: white; padding: 2px 10px; border-radius: 20px; font-size: 0.7em; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
    </style>
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

# =================================================================
# 5. SIDEBAR (ACTUALIZADO CON MODO LIVE)
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL v7.0</h2>", unsafe_allow_html=True)
    
    # SECCIÓN LIVE
    with st.expander("🔴 PANEL LIVE PULSE", expanded=st.session_state['is_live']):
        st.session_state['is_live'] = st.checkbox("ACTIVAR MODO LIVE", value=st.session_state['is_live'])
        st.session_state['live_min'] = st.number_input("Minuto Actual", 0, 95, value=st.session_state['live_min'])
        l1, l2 = st.columns(2)
        score_l = l1.number_input("Goles L", 0, 10, value=st.session_state['live_score'][0])
        score_v = l2.number_input("Goles V", 0, 10, value=st.session_state['live_score'][1])
        st.session_state['live_score'] = (score_l, score_v)
    
    ligas_api = {
        "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168,
        "Saudi Pro League": 307, "Liga Mayor (SV)": 601, "Champions League": 3
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA", value=ahora_sv.date())
    
    if st.button("SYNC DATA"):
        st.cache_data.clear()
        with st.spinner("QUANTUM DEEP SYNC..."):
            standings = api_request_cached(ligas_api[nombre_liga])
            f_desde = (fecha_analisis - timedelta(days=2)).strftime('%Y-%m-%d')
            f_hasta = (fecha_analisis + timedelta(days=2)).strftime('%Y-%m-%d')
            events = api_request_live("get_events", {"from": f_desde, "to": f_hasta, "league_id": ligas_api[nombre_liga]})
            if events and standings:
                m_info = events[0] # Simplificado para demo
                def buscar(n):
                    names = [t['team_name'] for t in standings]; m, s = process.extractOne(n, names); return next((t for t in standings if t['team_name'] == m), None) if s > 65 else None
                dl, dv = buscar(m_info['match_hometeam_name']), buscar(m_info['match_awayteam_name'])
                if dl and dv:
                    sl, tl = analyze_competition_stakes(standings, dl['team_id']); sv, tv = analyze_competition_stakes(standings, dv['team_id'])
                    st.session_state['stake_l'], st.session_state['tag_l'] = sl, tl
                    st.session_state['stake_v'], st.session_state['tag_v'] = sv, tv
                    cb_l, pxg_l, tempo_l = get_team_tactical_stats(dl['team_id'], ligas_api[nombre_liga])
                    cb_v, pxg_v, tempo_v = get_team_tactical_stats(dv['team_id'], ligas_api[nombre_liga])
                    st.session_state['tempo_factor'] = (tempo_l, tempo_v)
                    elo_l, mom_l, luck_l, conv_l = get_advanced_metrics(dl['team_id'], ligas_api[nombre_liga], dl['overall_league_position'], pxg_l)
                    elo_v, mom_v, luck_v, conv_v = get_advanced_metrics(dv['team_id'], ligas_api[nombre_liga], dv['overall_league_position'], pxg_v)
                    st.session_state['conv_factor'] = (conv_l, conv_v); st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.session_state['h2h_bias'] = get_h2h_data(dl['team_id'], dv['team_id'])
                    st.session_state['elo_bias'] = (elo_l, elo_v); st.session_state['proxy_xg_l'], st.session_state['proxy_xg_v'] = pxg_l, pxg_v
                    st.session_state['fatiga_l'] = get_fatigue_factor(dl['team_id'], m_info['match_date'])
                    st.session_state['fatiga_v'] = get_fatigue_factor(dv['team_id'], m_info['match_date'])
                    st.rerun()

# =================================================================
# 6. CONTENIDO PRINCIPAL (OR936 ELITE v7.0 LIVE)
# =================================================================
st.markdown(f"<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span> {'<span class="live-badge">LIVE</span>' if st.session_state['is_live'] else ''}</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>PREDICTIVE ENGINE V7.0 | QUANTUM LIVE PULSE</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown(f"<div style='border-right: 2px solid var(--secondary); text-align: right; padding-right: 15px; margin-bottom: 5px;'><h6 style='color:var(--secondary); margin:0; font-weight:900;'>LOCAL <span class='motivation-tag'>{st.session_state['tag_l']}</span></h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("GF Local", 0.0, 10.0, key='lgf_auto'), lb.number_input("GC Local", 0.0, 10.0, key='lgc_auto')
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, key='ltj_auto'), lb.number_input("Corners L", 0.0, 20.0, key='lco_auto')

with col_v:
    st.markdown(f"<div style='border-left: 2px solid var(--primary); text-align: left; padding-left: 15px; margin-bottom: 5px;'><h6 style='color:var(--primary); margin:0; font-weight:900;'>VISITANTE <span class='motivation-tag'>{st.session_state['tag_v']}</span></h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Nombre Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("GF Visita", 0.0, 10.0, key='vgf_auto'), vb.number_input("GC Visita", 0.0, 10.0, key='vgc_auto')
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, key='vtj_auto'), vb.number_input("Corners V", 0.0, 20.0, key='vco_auto')

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(league_avg=st.session_state['p_liga_auto'], draw_freq=st.session_state['draw_freq'])
    
    # LOGICA DE CALCULO BASE
    diff_mot = st.session_state['stake_l'] / st.session_state['stake_v']
    xg_l_base = ( (lgf * 0.4) + (st.session_state['proxy_xg_l'] * 0.6) ) * st.session_state['elo_bias'][0] * st.session_state['conv_factor'][0] * st.session_state['tempo_factor'][0] * diff_mot
    xg_v_base = ( (vgf * 0.4) + (st.session_state['proxy_xg_v'] * 0.6) ) * st.session_state['elo_bias'][1] * st.session_state['conv_factor'][1] * st.session_state['tempo_factor'][1] * (1/diff_mot)
    
    # AJUSTE LIVE: Escalamiento por tiempo restante
    if st.session_state['is_live']:
        rem_time = max(0, (90 - st.session_state['live_min']) / 90)
        xg_l_final = xg_l_base * rem_time
        xg_v_final = xg_v_base * rem_time
        cur_score = st.session_state['live_score']
    else:
        xg_l_final, xg_v_final, cur_score = xg_l_base, xg_v_base, (0, 0)
    
    res = motor.procesar(xg_l_final, xg_v_final, ltj+vtj, lco+vco, live_score=cur_score)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary);'>💎 TOP SELECCIONES ({'LIVE' if st.session_state['is_live'] else 'PRE-MATCH'})</h4>", unsafe_allow_html=True)
        pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "BTTS: SÍ", "p": res['BTTS'][0]}]
        for line, p in res['GOLES'].items(): 
            if 0.5 <= line <= 3.5: pool.append({"t": f"Over {line}", "p": p[0]})
        for s in sorted([x for x in pool if x['p'] > 75], key=lambda x: x['p'], reverse=True)[:5]:
            st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; text-align:center;'>🎯 MARCADOR FINAL</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} <span style="font-size:0.6em; color:#666;">({prob:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl_manual, "Empate", nv_manual)

    tabs = st.tabs(["🥅 GOLES", "📊 1X2", "🎲 MONTE CARLO", "🧩 MATRIZ", "🔴 LIVE PULSE"])
    
    with tabs[4]:
        if st.session_state['is_live']:
            c1, c2, c3 = st.columns(3)
            c1.metric("Tiempo Restante", f"{90-st.session_state['live_min']} min")
            c2.metric("xG Restante L", f"{xg_l_final:.2f}")
            c3.metric("xG Restante V", f"{xg_v_final:.2f}")
            st.info(f"Probabilidad de que el marcador actual **({cur_score[0]}-{cur_score[1]})** NO cambie: **{((res['MATRIZ'][0][0])):.1f}%**")
        else: st.warning("Activa el Modo Live en el Sidebar para ver este análisis.")

    with tabs[0]:
        ga, gb = st.columns(2)
        with ga:
            for l in [1.5, 2.5, 3.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with gb: dual_bar_explicit("AMBOS ANOTAN: SÍ", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>OR936 ELITE v7.0 | QUANTUM LIVE PULSE MODE ACTIVE</p>", unsafe_allow_html=True)
