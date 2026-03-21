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
from scipy.optimize import minimize 

# =================================================================
# 1. NÚCLEO OPERATIVO (ESTADO & CONFIGURACIÓN)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Persistencia de estados
for key, default in {
    'nl_auto': "Local", 'nv_auto': "Visitante", 'elo_bias': (1.0, 1.0),
    'h2h_bias': (1.0, 1.0), 'audit_results': [], 'fatiga_l': 1.0, 'fatiga_v': 1.0,
    'market_bias': None, 'hfa_specific': (1.1, 0.9), 'draw_freq': 0.25,
    'corner_bias': (1.0, 1.0), 'proxy_xg_l': 1.5, 'proxy_xg_v': 1.2,
    'luck_factor': (1.0, 1.0), 'conv_factor': (1.0, 1.0), 'tempo_factor': (1.0, 1.0),
    'stake_l': 1.0, 'stake_v': 1.0, 'tag_l': "Estándar", 'tag_v': "Estándar",
    'mle_rho': None, 'p_liga_auto': 2.5, 'hfa_league': 1.0, 'lgf_auto': 1.7,
    'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1, 'ltj_auto': 2.3, 'lco_auto': 5.5,
    'vtj_auto': 2.2, 'vco_auto': 4.8
}.items():
    if key not in st.session_state: st.session_state[key] = default

# =================================================================
# 2. MOTOR LÓGICO (SIN ALTERACIONES MATEMÁTICAS)
# =================================================================

def analyze_competition_stakes(standings, team_id, league_id):
    ligas_top = [152, 302, 207, 175, 168, 307, 322, 266]
    copas = [3, 4, 683, 13, 145, 146, 300, 209, 177, 169, 603]
    if league_id in copas: return 1.25, "CRÍTICO: ELIMINATORIA"
    if not standings or not isinstance(standings, list): return 1.0, "Estándar"
    try:
        team_data = next((t for t in standings if t['team_id'] == team_id), None)
        if not team_data: return 1.0, "Estándar"
        pos = int(team_data.get('overall_league_position', 10))
        pj = int(team_data.get('overall_league_payed', 0))
        restantes = ((len(standings)-1)*2) - pj
        urgencia = 1.20 if restantes <= 3 else (1.10 if restantes <= 7 else 1.0)
        if league_id in ligas_top and restantes <= 12:
            if pos == 1: return 1.15 * urgencia, "LIDERATO"
            if pos >= len(standings)-3: return 1.25 * urgencia, "DESCENSO"
        return 1.0, "Estándar"
    except: return 1.0, "Estándar"

def api_request_live(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY, "_ts": time.time()})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if isinstance(res.json(), list) else []
    except: return []

@st.cache_data(ttl=300)
def api_request_cached(league_id):
    return api_request_live("get_standings", {"league_id": league_id})

def rho_correction(x, y, lam, mu, rho):
    if x == 0 and y == 0: return 1 - (lam * mu * rho)
    elif x == 0 and y == 1: return 1 + (lam * rho)
    elif x == 1 and y == 0: return 1 + (mu * rho)
    elif x == 1 and y == 1: return 1 - rho
    return 1.0

def dc_log_likelihood(params, df, teams):
    n_teams = len(teams)
    alphas, betas = params[:n_teams], params[n_teams:2*n_teams]
    rho, gamma = params[-2], params[-1]
    attack_dict, defense_dict = dict(zip(teams, alphas)), dict(zip(teams, betas))
    log_like = 0.0
    for _, row in df.iterrows():
        x, y = row['home_goals'], row['away_goals']
        lam = attack_dict[row['home_team']] * defense_dict[row['away_team']] * gamma
        mu = attack_dict[row['away_team']] * defense_dict[row['home_team']]
        tau = rho_correction(x, y, lam, mu, rho)
        if tau <= 0 or lam <= 0 or mu <= 0: return 1e6  
        log_like += math.log(tau) - lam + x * math.log(lam) - mu + y * math.log(mu) - math.lgamma(x+1) - math.lgamma(y+1)
    return -log_like 

def train_dixon_coles(df):
    teams = np.unique(df[['home_team', 'away_team']].values)
    n_teams = len(teams)
    init_params = np.concatenate((np.ones(n_teams), np.ones(n_teams), [0.0], [1.1]))
    constraints = [{'type': 'eq', 'fun': lambda p: np.mean(p[:n_teams]) - 1.0}]
    bounds = [(0.01, 3.0)] * (2*n_teams) + [(-0.2, 0.2), (0.5, 2.0)]
    res = minimize(dc_log_likelihood, init_params, args=(df, teams), method='SLSQP', bounds=bounds, constraints=constraints)
    return {'attack': dict(zip(teams, res.x[:n_teams])), 'defense': dict(zip(teams, res.x[n_teams:2*n_teams])), 'rho': res.x[-2], 'gamma': res.x[-1]}, res.success

@st.cache_data(ttl=600)
def get_team_tactical_stats(team_id, league_id):
    data = api_request_live("get_statistics", {"league_id": league_id, "team_id": team_id})
    if not data or 'corners' not in data: return 1.0, 1.0, 1.0
    try:
        sog, st = int(data.get('shots_on_goal', 0)), int(data.get('shots_total', 0))
        mp = int(data.get('match_played', 1))
        pxg = ((sog * 0.33) + ((st-sog) * 0.10)) / mp
        pos = int(data.get('possession', 50).replace('%',''))
        ia = (1 + (int(data.get('shots_blocked', 0)) / mp / 5)) * (pos / 50)
        return max(0.8, min(1.4, ia)), pxg, max(0.85, min(1.25, st/(mp*12)))
    except: return 1.0, 1.0, 1.0

@st.cache_data(ttl=300)
def get_h2h_data(t_l, t_v):
    res = api_request_live("get_H2H", {"firstTeamId": t_l, "secondTeamId": t_v})
    if not res or 'firstTeam' not in res: return 1.0, 1.0
    m = res.get('firstTeam', []) + res.get('secondTeam', [])
    l_p, v_p = 0, 0
    for i in m[:6]:
        try:
            h, a = int(i['match_hometeam_score']), int(i['match_awayteam_score'])
            # CORRECCIÓN DE SINTAXIS AQUÍ:
            if h > a:
                if i['match_hometeam_id'] == t_l: l_p += 3
                else: v_p += 3
            elif h < a:
                if i['match_hometeam_id'] == t_l: v_p += 3
                else: l_p += 3
            else:
                l_p += 1; v_p += 1
        except: continue
    tot = max(1, l_p + v_p)
    return 0.95 + (l_p/tot * 0.1), 0.95 + (v_p/tot * 0.1)

class MotorMatematico:
    def __init__(self, league_avg=2.5, draw_freq=0.25, custom_rho=None):
        self.rho = custom_rho if custom_rho is not None else (-0.12 if league_avg > 2.6 else -0.16)
    def poisson_prob(self, k, lam): return (lam**k * math.exp(-lam)) / math.factorial(k) if lam > 0 else (1.0 if k == 0 else 0.0)
    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0
    def procesar(self, xg_l, xg_v, tj_t, co_t):
        p1_d, px_d, p2_d, btts_d = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_p_d = {t: [0.0, 0.0] for t in g_lines}
        for i in range(10): 
            fila = []
            for j in range(10):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1_d += p
                elif i == j: px_d += p
                else: p2_d += p
                if i > 0 and j > 0: btts_d += p
                for t in g_lines:
                    if (i+j) > t: g_p_d[t][0] += p
                    else: g_p_d[t][1] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)
        sh, sv = np.random.poisson(xg_l, 10000), np.random.poisson(xg_v, 10000)
        p1_f = (p1_d/max(0.001, (p1_d+px_d+p2_d)) * 0.7) + ((sh > sv).mean() * 0.3)
        px_f = (px_d/max(0.001, (p1_d+px_d+p2_d)) * 0.7) + ((sh == sv).mean() * 0.3)
        p2_f = (p2_d/max(0.001, (p1_d+px_d+p2_d)) * 0.7) + ((sv > sh).mean() * 0.3)
        stj, sco = np.random.poisson(tj_t, 10000), np.random.poisson(co_t, 10000)
        return {"1X2": (p1_f*100, px_f*100, p2_f*100), "BTTS": (btts_d*100, (1-btts_d)*100), "GOLES": {t: (g_p_d[t][0]*100, g_p_d[t][1]*100) for t in g_lines}, "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], "MATRIZ": matriz, "BRIER": 1-(abs(xg_l-xg_v)/(xg_l+xg_v+1.8)), "MONTECARLO": {"L": (sh > sv).mean()*100, "X": (sh == sv).mean()*100, "V": (sv > sh).mean()*100, "VOL": np.std(sh+sv)}, "TARJETAS": {t: (np.sum(stj > t)/100, np.sum(stj <= t)/100) for t in [3.5, 4.5, 5.5]}, "CORNERS": {t: (np.sum(sco > t)/100, np.sum(sco <= t)/100) for t in [8.5, 9.5, 10.5]}}

# =================================================================
# 3. INTERFAZ STRATOS NEURAL (VISUAL)
# =================================================================
st.set_page_config(page_title="STRATOS NEURAL ENGINE", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&family=Space+Mono:wght@400;700&display=swap');
    :root { --accent: #00ffa3; --bg-dark: #0a0b0d; --card-bg: rgba(23, 25, 30, 0.8); }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: var(--bg-dark); color: #edeff2; }
    .stApp { background: radial-gradient(circle at top right, #161b22, #0a0b0d); }
    .master-container { background: var(--card-bg); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.05); border-radius: 24px; padding: 40px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); margin-bottom: 30px; }
    .stat-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 20px; border-radius: 16px; transition: 0.3s; }
    .stat-card:hover { border-color: var(--accent); background: rgba(0, 255, 163, 0.02); }
    .glitch-title { font-size: 3.2rem; font-weight: 900; letter-spacing: -2px; background: linear-gradient(90deg, #fff, #888); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0; }
    .sidebar-title { color: var(--accent); font-family: 'Space Mono', monospace; font-size: 0.85rem; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 25px; }
    .stButton>button { background: #fff !important; color: #000 !important; border-radius: 12px; font-weight: 800; border: none; padding: 1rem; transition: 0.2s; width: 100%; text-transform: uppercase; letter-spacing: 1px; }
    .wa-link { background: #25D366; color: white !important; text-decoration: none; padding: 15px; border-radius: 12px; display: block; text-align: center; font-weight: 700; margin-top: 20px; }
    .bar-container { background: rgba(255,255,255,0.05); height: 8px; border-radius: 10px; overflow: hidden; margin: 10px 0; }
    .bar-fill { height: 100%; background: var(--accent); box-shadow: 0 0 10px var(--accent); }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 4. SIDEBAR REBRANDING
# =================================================================
with st.sidebar:
    st.markdown("<div class='sidebar-title'>Neural Control Interface</div>", unsafe_allow_html=True)
    ligas_api = {"Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, "Champions League": 3, "Brasileirão": 99}
    nombre_liga = st.selectbox("COMPETICIÓN", list(ligas_api.keys()))
    fecha_analisis = st.date_input("FECHA DE OPERACIÓN", value=ahora_sv.date())
    
    eventos = api_request_live("get_events", {"from": (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d'), "to": (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d'), "league_id": ligas_api[nombre_liga]})
    if eventos:
        p_sel = st.selectbox("PARTIDO DETECTADO", [f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}" for e in eventos])
        if st.button("SINCRONIZAR DATOS"):
            with st.spinner("CALIBRANDO..."):
                standings = api_request_cached(ligas_api[nombre_liga])
                m_i = next(e for e in eventos if f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}" == p_sel)
                def find_t(n): names = [t['team_name'] for t in standings]; m, s = process.extractOne(n, names); return next(t for t in standings if t['team_name'] == m) if s > 65 else None
                dl, dv = find_t(m_i['match_hometeam_name']), find_t(m_i['match_awayteam_name'])
                if dl and dv:
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.session_state['lgf_auto'] = float(dl['home_league_GF'])/max(1,int(dl['home_league_payed']))
                    st.session_state['vgf_auto'] = float(dv['away_league_GF'])/max(1,int(dv['away_league_payed']))
                    st.rerun()

# =================================================================
# 5. DASHBOARD PRINCIPAL
# =================================================================
st.markdown("<h1 class='glitch-title'>STRATOS QUANTUM</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#666; letter-spacing:4px; font-weight:300; margin-bottom:40px;'>ADVANCED STOCHASTIC PREDICTION HUB</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown(f"<div style='border-left: 3px solid var(--accent); padding-left: 15px;'><small style='color:var(--accent); font-family:Space Mono;'>PRIMARY_UNIT</small><br><h3>{st.session_state['nl_auto']}</h3></div>", unsafe_allow_html=True)
    la, lb = st.columns(2)
    lgf = la.number_input("Goles Favor", 0.0, 10.0, key='lgf_auto')
    lgc = lb.number_input("Goles Contra", 0.0, 10.0, key='lgc_auto')

with col_v:
    st.markdown(f"<div style='border-left: 3px solid #666; padding-left: 15px;'><small style='color:#666; font-family:Space Mono;'>OPPOSITION_UNIT</small><br><h3>{st.session_state['nv_auto']}</h3></div>", unsafe_allow_html=True)
    va, vb = st.columns(2)
    vgf = va.number_input("Goles Favor ", 0.0, 10.0, key='vgf_auto')
    vgc = vb.number_input("Goles Contra ", 0.0, 10.0, key='vgc_auto')

if st.button("EJECUTAR ANÁLISIS"):
    motor = MotorMatematico(league_avg=st.session_state['p_liga_auto'], draw_freq=st.session_state['draw_freq'])
    res = motor.procesar((lgf/2.5)*(vgc/2.5)*2.5*1.1, (vgf/2.5)*(lgc/2.5)*2.5*0.9, 4.5, 9.5)
    
    st.markdown("<div class='master-container'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for i, (lab, val, col) in enumerate([("LOCAL", res['1X2'][0], "var(--accent)"), ("DRAW", res['1X2'][1], "#fff"), ("AWAY", res['1X2'][2], "#666")]):
        with [c1, c2, c3][i]:
            st.markdown(f"<small style='color:#666;'>{lab} PROBABILITY</small><br><h1 style='color:{col};'>{val:.1f}%</h1>", unsafe_allow_html=True)
            st.markdown(f"<div class='bar-container'><div class='bar-fill' style='width:{val}%; background:{col};'></div></div>", unsafe_allow_html=True)
    
    st.markdown("<br><h4>INTELLIGENCE PICKS</h4>", unsafe_allow_html=True)
    picks = sorted([{"t": "Over 1.5", "p": res['GOLES'][1.5][0]}, {"t": "Over 2.5", "p": res['GOLES'][2.5][0]}, {"t": "BTTS: SI", "p": res['BTTS'][0]}, {"t": "1X", "p": res['1X2'][0]+res['1X2'][1]}], key=lambda x:x['p'], reverse=True)
    p1, p2, p3 = st.columns(3)
    for i in range(3):
        with [p1,p2,p3][i]:
            st.markdown(f"<div class='stat-card'><small style='color:var(--accent);'>PICK_0{i+1}</small><br><b style='font-size:1.1rem;'>{picks[i]['t']}</b><br><span style='color:#666;'>Conf: {picks[i]['p']:.1f}%</span></div>", unsafe_allow_html=True)
    
    st.markdown(f'<a href="https://wa.me/?text=STRATOS REPORT: {st.session_state["nl_auto"]} vs {st.session_state["nv_auto"]}" class="wa-link">EXPORTAR A MÓVIL</a>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<p style='text-align:center; color:#333; font-family:Space Mono; font-size:0.7rem; margin-top:100px;'>SYSTEM_STATUS: OPERATIONAL | CORE: DIXON-COLES MLE | NO_WATERMARK</p>", unsafe_allow_html=True)
