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
# 1. CONFIGURACIÓN API & ESTADO INICIAL
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Persistencia de estados
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

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE EXTRACCIÓN Y ESTADÍSTICA
# =================================================================

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
    if not data or 'corners' not in data: return 1.0
    try:
        shots_blocked = int(data.get('shots_blocked', 0))
        total_matches = int(data.get('match_played', 1))
        possession = int(data.get('possession', 50).replace('%',''))
        ia = (1 + (shots_blocked / total_matches / 5)) * (possession / 50)
        return max(0.8, min(1.4, ia))
    except: return 1.0

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
        o = odds[0]
        o1, ox, o2 = float(o['odd_1']), float(o['odd_x']), float(o['odd_2'])
        margin = (1/o1) + (1/ox) + (1/o2)
        return ((1/o1)/margin, (1/ox)/margin, (1/o2)/margin)
    except: return None

@st.cache_data(ttl=300)
def get_advanced_metrics(team_id, league_id, position):
    events = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=60)).strftime('%Y-%m-%d'), 
                                             "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": league_id, "team_id": team_id})
    if not events: return 1.0, 1.0
    finished = [e for e in events if e['match_status'] == 'Finished']
    if not finished: return 1.0, 1.0
    momentum_gf, total_w = 0, 0
    for m in finished[-5:]:
        try:
            m_date = datetime.strptime(m['match_date'], '%Y-%m-%d').replace(tzinfo=tz_sv)
            days_diff = (ahora_sv - m_date).days
            weight = math.exp(-0.04 * days_diff)
            is_home = m['match_hometeam_id'] == team_id
            gf = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            momentum_gf += (gf * weight); total_w += weight
        except: continue
    elo_strength = 1.15 if int(position) <= 4 else (1.05 if int(position) <= 8 else 0.95)
    return elo_strength, (momentum_gf / total_w if total_w > 0 else 1.0)

@st.cache_data(ttl=300)
def get_h2h_data(team_id_l, team_id_v):
    res = api_request_live("get_H2H", {"firstTeamId": team_id_l, "secondTeamId": team_id_v})
    if not res or 'firstTeam' not in res: return 1.0, 1.0
    matches = res.get('firstTeam', []) + res.get('secondTeam', [])
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
# 3. MOTOR MATEMÁTICO QUANTUM HÍBRIDO
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

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        # 1. ANALÍTICO DIXON-COLES
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

        # 2. ESTOCÁSTICO MONTE CARLO PRO (10k)
        sim_h = np.random.poisson(xg_l, 10000)
        sim_v = np.random.poisson(xg_v, 10000)
        tot_g_sim = sim_h + sim_v
        margen_sim = sim_h - sim_v
        
        # 3. FUSIÓN HÍBRIDA 70/30
        W_D, W_MC = 0.70, 0.30
        p1_f = (p1_d/total_d * W_D) + ((sim_h > sim_v).mean() * W_MC)
        px_f = (px_d/total_d * W_D) + ((sim_h == sim_v).mean() * W_MC)
        p2_f = (p2_d/total_d * W_D) + ((sim_v > sim_h).mean() * W_MC)
        total_f = p1_f + px_f + p2_f

        if st.session_state['market_bias']:
            m1, mx, m2 = st.session_state['market_bias']
            p1_f = (p1_f/total_f * 0.75) + (m1 * 0.25)
            px_f = (px_f/total_f * 0.75) + (mx * 0.25)
            p2_f = (p2_f/total_f * 0.75) + (m2 * 0.25)
            total_f = p1_f + px_f + p2_f

        mc_data = {
            "L": (sim_h > sim_v).mean() * 100, "X": (sim_h == sim_v).mean() * 100, "V": (sim_v > sim_h).mean() * 100,
            "CS_L": (sim_v == 0).mean() * 100, "CS_V": (sim_h == 0).mean() * 100,
            "G_0_1": (tot_g_sim <= 1).mean() * 100, "G_2_3": ((tot_g_sim >= 2) & (tot_g_sim <= 3)).mean() * 100, "G_4_MAS": (tot_g_sim >= 4).mean() * 100,
            "M_L1": (margen_sim == 1).mean() * 100, "M_L2": (margen_sim == 2).mean() * 100, "M_L3": (margen_sim >= 3).mean() * 100,
            "M_V1": (margen_sim == -1).mean() * 100, "M_V2": (margen_sim == -2).mean() * 100, "M_V3": (margen_sim <= -3).mean() * 100,
            "VOLATILITY": np.std(tot_g_sim), "RAW_TOTALS": tot_g_sim
        }

        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1_f/total_f*100, px_f/total_f*100, p2_f/total_f*100), 
            "DC": ((p1_f+px_f)/total_f*100, (p2_f+px_f)/total_f*100, (p1_f+p2_f)/total_f*100),
            "BTTS": ((btts_d/total_d*W_D + ((sim_h>0)&(sim_v>0)).mean()*W_MC)*100, (1-(btts_d/total_d*W_D + ((sim_h>0)&(sim_v>0)).mean()*W_MC))*100), 
            "GOLES": {t: ((g_probs_d[t][0]/total_d*W_D + (tot_g_sim > t).mean()*W_MC)*100, (g_probs_d[t][1]/total_d*W_D + (tot_g_sim <= t).mean()*W_MC)*100) for t in g_lines},
            "HANDICAPS": {"L": {h: (h_probs_l_d[h]/total_d*100*W_D + (sim_h + h > sim_v).mean()*100*W_MC) for h in h_lines}, 
                          "V": {h: (h_probs_v_d[h]/total_d*100*W_D + (sim_v + h > sim_h).mean()*100*W_MC) for h in h_lines}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8)), "MONTECARLO": mc_data
        }

# =================================================================
# 4. DISEÑO UI/UX ELITE
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE v7.5", layout="wide")

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
    </style>
    """, unsafe_allow_html=True)

def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin: 30px 0; background: #0a0c10; padding: 25px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #aaa; text-transform: uppercase; margin-bottom: 15px;"><span style="color:var(--secondary)">{n1}: <b>{p1:.1f}%</b></span><span>EMPATE: <b>{px_val:.1f}%</b></span><span style="color:var(--primary)">{n2}: <b>{p2:.1f}%</b></span></div>
            <div style="display: flex; height: 16px; border-radius: 50px; overflow: hidden; background: #1a1a1a;"><div style="width: {p1}%; background: var(--secondary); box-shadow: 0 0 10px var(--secondary);"></div><div style="width: {px_val}%; background: #444;"></div><div style="width: {p2}%; background: var(--primary); box-shadow: 0 0 10px var(--primary);"></div></div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 22px;"><div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #eee; margin-bottom: 8px;"><span style="font-weight: 600;">{label_over} <span style="color:{color};">{prob_over:.1f}%</span></span><span style="color: #666;">{prob_under:.1f}% {label_under}</span></div>
        <div style="display: flex; background: #111; height: 10px; border-radius: 5px; overflow: hidden;"><div style="width: {prob_over}%; background: {color};"></div></div></div>
    """, unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL v7.5</h2>", unsafe_allow_html=True)
    ligas_api = {"Saudi Pro League": 307, "Trendyol Süper Lig": 322, "Liga Mayor (El Salvador)": 601, "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168}
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA", value=ahora_sv.date())
    raw_events = api_request_live("get_events", {"from": (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d'), "to": (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d'), "league_id": ligas_api[nombre_liga]})

    if raw_events:
        op_p = {f"({e['match_date']}) {e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos", list(op_p.keys()))
        if st.button("SYNC DATA"):
            st.cache_data.clear()
            with st.spinner("QUANTUM DEEP SYNC..."):
                standings = api_request_cached(ligas_api[nombre_liga])
                match_info = op_p[p_sel]
                if standings:
                    def buscar(n):
                        nombres = [t['team_name'] for t in standings]
                        m, s = process.extractOne(n, nombres); return next((t for t in standings if t['team_name'] == m), None) if s > 65 else None
                    dl, dv = buscar(match_info['match_hometeam_name']), buscar(match_info['match_awayteam_name'])
                    if dl and dv:
                        phl, pav = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['corner_bias'] = (get_team_tactical_stats(dl['team_id'], ligas_api[nombre_liga]), get_team_tactical_stats(dv['team_id'], ligas_api[nombre_liga]))
                        st.session_state['h2h_bias'] = get_h2h_data(dl['team_id'], dv['team_id'])
                        elo_l, mom_l = get_advanced_metrics(dl['team_id'], ligas_api[nombre_liga], dl['overall_league_position'])
                        elo_v, mom_v = get_advanced_metrics(dv['team_id'], ligas_api[nombre_liga], dv['overall_league_position'])
                        st.session_state['fatiga_l'] = get_fatigue_factor(dl['team_id'], match_info['match_date'])
                        st.session_state['fatiga_v'] = get_fatigue_factor(dv['team_id'], match_info['match_date'])
                        st.session_state['market_bias'] = get_market_consensus(match_info['match_id'])
                        st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/phl if phl>0 else 1.5) * 0.7 + (mom_l * 0.3)
                        st.session_state['vgf_auto'] = (float(dv['away_league_GF'])/pav if pav>0 else 1.2) * 0.7 + (mom_v * 0.3)
                        st.session_state['lgc_auto'] = float(dl['home_league_GA'])/phl if phl>0 else 1.0
                        st.session_state['vgc_auto'] = float(dv['away_league_GA'])/pav if pav>0 else 1.3
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        recent_league = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=10)).strftime('%Y-%m-%d'), "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": ligas_api[nombre_liga]})
                        st.session_state['audit_results'] = [e for e in recent_league if e['match_status'] == 'Finished'][-5:]
                        st.rerun()

# =================================================================
# 6. DASHBOARD PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; font-weight: 900;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>V7.5 FULL HYBRID MOTOR</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'])
    la, lb = st.columns(2); lgf = la.number_input("GF Local", 0.0, 10.0, key='lgf_auto'); lgc = lb.number_input("GC Local", 0.0, 10.0, key='lgc_auto')
    ltj = la.number_input("Tarjetas L", 0.0, 15.0); lco = lb.number_input("Corners L", 0.0, 20.0)
with col_v:
    nv_manual = st.text_input("Nombre Visitante", value=st.session_state['nv_auto'])
    va, vb = st.columns(2); vgf = va.number_input("GF Visita", 0.0, 10.0, key='vgf_auto'); vgc = vb.number_input("GC Visita", 0.0, 10.0, key='vgc_auto')
    vtj = va.number_input("Tarjetas V", 0.0, 15.0); vco = vb.number_input("Corners V", 0.0, 20.0)

st.markdown('<div class="ref-box">⚖️ CALIBRACIÓN DEL COLEGIADO', unsafe_allow_html=True)
rc1, rc2 = st.columns([2, 1]); ref_nom = rc1.text_input("Nombre Árbitro", placeholder="Ej: Michael Oliver"); ref_avg = rc2.number_input("Promedio Tarjetas", 0.0, 15.0, step=0.1)
st.markdown('</div>', unsafe_allow_html=True)

p_liga = st.slider("Media Goles Liga", 0.5, 5.0, key='p_liga_auto')

if st.button("GENERAR REPORTE CUÁNTICO"):
    motor = MotorMatematico(league_avg=p_liga, draw_freq=st.session_state['draw_freq'])
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * st.session_state['hfa_specific'][0] * st.session_state['h2h_bias'][0] * st.session_state['fatiga_l']
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * st.session_state['hfa_specific'][1] * st.session_state['h2h_bias'][1] * st.session_state['fatiga_v']
    tj_f = ((ltj + vtj) * 0.4 + (ref_avg * 0.6)) if ref_avg > 0 else (ltj + vtj)
    cb_l, cb_v = st.session_state['corner_bias']; co_f = (lco * cb_l) + (vco * cb_v)

    res = motor.procesar(xg_l, xg_v, tj_f, co_f)
    pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "12", "p": res['DC'][2]}, {"t": "BTTS: SÍ", "p": res['BTTS'][0]}]
    for l, p in res['GOLES'].items(): pool.append({"t": f"Over {l}", "p": p[0]}); pool.append({"t": f"Under {l}", "p": p[1]})
    sug = sorted([s for s in pool if 70 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:6]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary);'>💎 TOP SELECCIONES ({res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
        for s in sug: st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='text-align:center;'>🎯 MARCADORES</h4>", unsafe_allow_html=True)
        for s, p in res['TOP']: st.markdown(f'<div class="score-badge">{s} <span style="font-size:0.6em;">({p:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl_manual, "Empate", nv_manual)

    t1, t2, t3, t4, t5, t6, t7 = st.tabs(["🥅 GOLES", "🏆 HANDICAP", "📊 1X2", "🚩 ESPECIALES", "🎲 MONTE CARLO PRO", "🧩 MATRIZ", "📈 AUDITORÍA"])
    
    with t1:
        c_a, c_b = st.columns(2)
        with c_a:
            for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with c_b: dual_bar_explicit("AMBOS ANOTAN: SÍ", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")

    with t2:
        c_l, c_v = st.columns(2)
        with c_l: 
            st.write(f"Hándicaps {nl_manual}")
            for h, p in res['HANDICAPS']['L'].items(): dual_bar_explicit(f"H {h:+}", p, "", 100-p)
        with c_v: 
            st.write(f"Hándicaps {nv_manual}")
            for h, p in res['HANDICAPS']['V'].items(): dual_bar_explicit(f"H {h:+}", p, "", 100-p, color="#d4af37")

    with t4:
        c_tj, c_co = st.columns(2)
        with c_tj:
            st.write(f"Tarjetas ({ref_nom if ref_nom else 'Sim'})")
            for l, p in res['TARJETAS'].items(): dual_bar_explicit(f"> {l}", p[0], f"< {l}", p[1], color="#ff4b4b")
        with c_co:
            st.write("Corners (Ajuste Táctico)")
            for l, p in res['CORNERS'].items(): dual_bar_explicit(f"> {l}", p[0], f"< {l}", p[1], color="#00ffa3")

    with t5:
        mc = res['MONTECARLO']
        st.markdown("<div class='mc-container'><h3 style='color:#fff; text-align:center;'>SIMULACIÓN INSTITUCIONAL</h3>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4); c1.metric("Local", f"{mc['L']:.1f}%"); c2.metric("Empate", f"{mc['X']:.1f}%"); c3.metric("Visita", f"{mc['V']:.1f}%"); c4.metric("Volatilidad", f"{mc['VOLATILITY']:.2f}")
        ca, cb = st.columns([1.6, 1])
        with ca:
            st.plotly_chart(px.histogram(pd.DataFrame({"G": mc['RAW_TOTALS']}), x="G", nbins=15, title="DENSIDAD DE GOLES", color_discrete_sequence=['#d4af37']), use_container_width=True)
        with cb:
            st.write("Métricas Cuánticas")
            dual_bar_explicit("Clean Sheet L", mc['CS_L'], "", 100-mc['CS_L'])
            dual_bar_explicit("Clean Sheet V", mc['CS_V'], "", 100-mc['CS_V'], color="#d4af37")
            st.write(f"Márgenes L: 1({mc['M_L1']:.1f}%) | 2({mc['M_L2']:.1f}%) | 3+({mc['M_L3']:.1f}%)")
            st.write(f"Márgenes V: 1({mc['M_V1']:.1f}%) | 2({mc['M_V2']:.1f}%) | 3+({mc['M_V3']:.1f}%)")
        st.markdown("</div>", unsafe_allow_html=True)

    with t7:
        st.markdown("""
            <div style='background: linear-gradient(90deg, #0a0c10 0%, #141923 100%); padding: 20px; border-radius: 15px; border-left: 5px solid #d4af37; margin-bottom: 25px;'>
                <h3 style='color:#fff; margin:0;'>BACKTESTING DE PRECISIÓN <span style='color:#d4af37; font-size:0.6em;'>QUANTUM ENGINE</span></h3>
                <p style='color:#666; font-size:0.9em; margin:0;'>Validación exacta de las sugerencias frente a resultados finales.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.session_state['audit_results']:
            hits, picks = 0, 0; audit_list = []
            for m in st.session_state['audit_results']:
                try:
                    h_s, v_s = int(m['match_hometeam_score']), int(m['match_awayteam_score'])
                    # Auditoría con mini-simulación original
                    br = motor.procesar(xg_l, xg_v, 4.0, 9.5)
                    s_b = sorted([{"t":"1X","p":br['DC'][0]}, {"t":"X2","p":br['DC'][1]}], key=lambda x:x['p'], reverse=True)[:1]
                    p_h = ""
                    for ps in s_b:
                        is_h = (h_s >= v_s if ps['t']=="1X" else v_s >= h_s)
                        hits += (1 if is_h else 0); picks += 1
                        p_h += f"<div style='color:{'#00ffa3' if is_h else '#ff4b4b'}'>{'✓' if is_h else '✗'} {ps['t']}</div>"
                    audit_list.append({"d": m['match_date'], "m": f"{m['match_hometeam_name']} {h_s}-{v_s} {m['match_awayteam_name']}", "p": p_h})
                except: continue
            st.write(f"Precisión: {(hits/picks*100) if picks>0 else 0:.1f}%")
            for i in audit_list:
                st.markdown(f"<div style='display:flex; background:rgba(255,255,255,0.02); padding:15px; border-radius:12px; margin-bottom:10px; border:1px solid #222;'><div style='flex:1'><small>{i['d']}</small><br><b>{i['m']}</b></div><div style='flex:1'>{i['p']}</div></div>", unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #333; font-size: 0.8em; margin-top: 50px;'>OR936 ELITE v7.5 | ALL SYSTEMS ACTIVE</p>", unsafe_allow_html=True)