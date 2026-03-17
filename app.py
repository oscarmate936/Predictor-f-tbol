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

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []
if 'fatiga_l' not in st.session_state: st.session_state['fatiga_l'] = 1.0
if 'fatiga_v' not in st.session_state: st.session_state['fatiga_v'] = 1.0
if 'market_bias' not in st.session_state: st.session_state['market_bias'] = None
if 'form_l_icons' not in st.session_state: st.session_state['form_l_icons'] = ""
if 'form_v_icons' not in st.session_state: st.session_state['form_v_icons'] = ""

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE LÓGICA ELITE
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

def get_fatigue_factor(team_id, match_date_str):
    last_matches = api_request_live("get_events", {
        "from": (datetime.strptime(match_date_str, '%Y-%m-%d') - timedelta(days=12)).strftime('%Y-%m-%d'),
        "to": (datetime.strptime(match_date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d'),
        "team_id": team_id
    })
    if not last_matches: return 1.0
    try:
        last_date = datetime.strptime(last_matches[-1]['match_date'], '%Y-%m-%d')
        target_date = datetime.strptime(match_date_str, '%Y-%m-%d')
        days_off = (target_date - last_date).days
        return 0.90 if days_off <= 3 else (1.06 if days_off >= 7 else 1.0)
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
def get_advanced_metrics_v2(team_id, league_id):
    events = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=60)).strftime('%Y-%m-%d'), 
                                             "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": league_id, "team_id": team_id})
    if not events: return 1.0, 1.0, ""
    finished = [e for e in events if e['match_status'] == 'Finished']
    icons = []
    momentum = 0
    for i, m in enumerate(finished[-5:][::-1]):
        is_home = m['match_hometeam_id'] == team_id
        gs, gc = (int(m['match_hometeam_score']), int(m['match_awayteam_score'])) if is_home else (int(m['match_awayteam_score']), int(m['match_hometeam_score']))
        if gs > gc: icons.append("🟢")
        elif gs < gc: icons.append("🔴")
        else: icons.append("🟡")
        if i < 3: momentum += gs * [0.5, 0.3, 0.2][i]
    return 1.10 if "🟢🟢" in "".join(icons) else 1.0, momentum, "".join(icons)

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
    total = max(1, l_pts + v_pts)
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 3. MOTOR MATEMÁTICO (DIXON-COLES V4.8)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.18 if league_avg < 2.3 else (-0.12 if league_avg > 2.8 else -0.15)

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
        h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
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
        if st.session_state['market_bias']:
            m1, mx, m2 = st.session_state['market_bias']
            p1 = (p1/total * 0.75) + (m1 * 0.25)
            px = (px/total * 0.75) + (mx * 0.25)
            p2 = (p2/total * 0.75) + (m2 * 0.25)
            total = p1 + px + p2

        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        }

# =================================================================
# 4. DISEÑO UI/UX ORIGINAL
# =================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; font-family: 'JetBrains Mono', monospace; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; text-transform: uppercase; letter-spacing: 3px; transition: 0.4s; width: 100%; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background: #25D366; color: white !important; padding: 14px; border-radius: 14px; text-decoration: none; font-weight: 700; margin-top: 5px; }
    .form-pill { font-size: 0.8em; letter-spacing: 2px; margin-top: 5px; opacity: 0.8; }
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
# 5. SIDEBAR & SYNC (RESTABLECIMIENTO AUDITORÍA)
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Saudi Pro League": 307, "Trendyol Süper Lig": 322, "Liga Mayor (SV)": 601,
        "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, 
        "Champions League": 3, "Libertadores": 13, "Brasileirão Série A": 99
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA CENTRAL", value=ahora_sv.date())
    raw_events = api_request_live("get_events", {"from": (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d'), "to": (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d'), "league_id": ligas_api[nombre_liga]})

    if raw_events:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos", list(op_p.keys()))

        if st.button("SYNC QUANTUM DATA"):
            with st.spinner("QUANTUM DEEP SYNC..."):
                standings = api_request_cached(ligas_api[nombre_liga])
                match_info = op_p[p_sel]
                if standings:
                    def buscar(n):
                        nombres = [t['team_name'] for t in standings]
                        m, s = process.extractOne(n, nombres)
                        return next((t for t in standings if t['team_name'] == m), None) if s > 65 else None
                    dl, dv = buscar(match_info['match_hometeam_name']), buscar(match_info['match_awayteam_name'])
                    if dl and dv:
                        elo_l, mom_l, icons_l = get_advanced_metrics_v2(dl['team_id'], ligas_api[nombre_liga])
                        elo_v, mom_v, icons_v = get_advanced_metrics_v2(dv['team_id'], ligas_api[nombre_liga])
                        st.session_state['form_l_icons'], st.session_state['form_v_icons'] = icons_l, icons_v
                        st.session_state['fatiga_l'] = get_fatigue_factor(dl['team_id'], match_info['match_date'])
                        st.session_state['fatiga_v'] = get_fatigue_factor(dv['team_id'], match_info['match_date'])
                        st.session_state['market_bias'] = get_market_consensus(match_info['match_id'])
                        st.session_state['h2h_bias'] = get_h2h_data(dl['team_id'], dv['team_id'])
                        ph, pa = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/ph if ph>0 else 1.5) + (mom
