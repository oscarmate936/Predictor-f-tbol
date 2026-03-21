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
from scipy.optimize import minimize  # <--- Motor de optimización Dixon-Coles

# =================================================================
# 1. CONFIGURACIÓN API & ESTADO (v6.9.2 - QUANTUM MLE INTEGRATED)
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
if 'mle_rho' not in st.session_state: st.session_state['mle_rho'] = None 

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. FUNCIONES DE LÓGICA ELITE (ACTUALIZADAS CON MLE)
# =================================================================

def analyze_competition_stakes(standings, team_id, league_id):
    ligas_top = [152, 302, 207, 175, 168, 307, 322, 266] # <--- ID 266 AÑADIDO
    ligas_playoffs = [601, 99, 100, 103]
    copas = [3, 4, 683, 13, 145, 146, 300, 209, 177, 169, 603]

    if league_id in copas:
        return 1.25, "CRÍTICO: ELIMINATORIA / COPA"

    if not standings or not isinstance(standings, list): 
        return 1.0, "Estándar: Sin Datos"
        
    try:
        total_teams = len(standings)
        team_data = next((t for t in standings if t['team_id'] == team_id), None)
        if not team_data: return 1.0, "Estándar"
        
        pos = int(team_data.get('overall_league_position', 10))
        pj = int(team_data.get('overall_league_payed', 0))
        
        total_jornadas = (total_teams - 1) * 2
        restantes = total_jornadas - pj
        
        urgencia = 1.0
        if restantes <= 3: urgencia = 1.20
        elif restantes <= 7: urgencia = 1.10
        elif restantes <= 12: urgencia = 1.05

        if league_id in ligas_top:
            if restantes <= 12:
                if pos == 1: return 1.15 * urgencia, "CRÍTICO: LIDERATO"
                elif 2 <= pos <= 4: return 1.10 * urgencia, "ALTA: ZONA CHAMPIONS"
                elif 5 <= pos <= 7: return 1.08 * urgencia, "ALTA: ZONA EUROPA"
                elif pos >= total_teams - 3: return 1.25 * urgencia, "CRÍTICO: PELIGRO DESCENSO"
                elif pos >= total_teams - 5: return 1.05 * urgencia, "MEDIA: RIESGO DESCENSO"
                else: return 0.85, "BAJA: MITAD DE TABLA"
            return 1.0, "Estándar: Fase Regular"

        elif league_id in ligas_playoffs:
            zona_corte = 8 if total_teams >= 12 else 4
            if restantes <= 8:
                if pos <= 2: return 1.08 * urgencia, "ALTA: VENTAJA PLAYOFFS"
                elif pos == zona_corte or pos == zona_corte + 1: return 1.25 * urgencia, "CRÍTICO: PASE LIGUILLA"
                elif pos < zona_corte: return 1.05 * urgencia, "MEDIA: DENTRO LIGUILLA"
                elif pos >= total_teams - 1: return 1.20 * urgencia, "CRÍTICO: DESCENSO"
                else: return 0.85, "BAJA: ELIMINADO"
            return 1.0, "Estándar: Fase Regular"

        else:
            if restantes <= 6:
                if pos <= 3: return 1.15 * urgencia, "CRÍTICO: TÍTULO"
                if pos >= total_teams - 3: return 1.20 * urgencia, "CRÍTICO: DESCENSO"
                if 4 <= pos <= 7: return 1.10 * urgencia, "ALTA: COPAS"
                if 8 <= pos <= total_teams - 4: return 0.85, "BAJA: SIN OBJETIVOS"
            return 1.0, "Estándar"

    except Exception: 
        return 1.0, "Estándar"

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

def rho_correction(x, y, lam, mu, rho):
    if x == 0 and y == 0: return 1 - (lam * mu * rho)
    elif x == 0 and y == 1: return 1 + (lam * rho)
    elif x == 1 and y == 0: return 1 + (mu * rho)
    elif x == 1 and y == 1: return 1 - rho
    return 1.0

def dc_log_likelihood(params, df, teams):
    n_teams = len(teams)
    alphas = params[:n_teams]
    betas = params[n_teams:2*n_teams]
    rho = params[-2]
    gamma = params[-1] 
    
    attack_dict = dict(zip(teams, alphas))
    defense_dict = dict(zip(teams, betas))
    
    log_like = 0.0
    for _, row in df.iterrows():
        x = row['home_goals']; y = row['away_goals']
        lam = attack_dict[row['home_team']] * defense_dict[row['away_team']] * gamma
        mu = attack_dict[row['away_team']] * defense_dict[row['home_team']]
        tau = rho_correction(x, y, lam, mu, rho)
        if tau <= 0 or lam <= 0 or mu <= 0: return 1e6  
        ll_match = math.log(tau) - lam + x * math.log(lam) - mu + y * math.log(mu) - math.lgamma(x + 1) - math.lgamma(y + 1)
        log_like += ll_match
    return -log_like 

def train_dixon_coles(df):
    teams = np.unique(df[['home_team', 'away_team']].values)
    n_teams = len(teams)
    init_params = np.concatenate((np.ones(n_teams), np.ones(n_teams), [0.0], [1.1]))
    def constraint_func(params): return np.mean(params[:n_teams]) - 1.0
    constraints = [{'type': 'eq', 'fun': constraint_func}]
    bounds = [(0.01, 3.0)] * (2 * n_teams) + [(-0.2, 0.2), (0.5, 2.0)]
    
    res = minimize(dc_log_likelihood, init_params, args=(df, teams), method='SLSQP', bounds=bounds, constraints=constraints, options={'maxiter': 100})
    model_params = {'attack': dict(zip(teams, res.x[:n_teams])), 'defense': dict(zip(teams, res.x[n_teams:2*n_teams])), 'rho': res.x[-2], 'gamma': res.x[-1]}
    return model_params, res.success

@st.cache_data(ttl=86400) 
def extraer_historial_mle(league_id):
    f_hasta = ahora_sv.strftime('%Y-%m-%d')
    f_desde = (ahora_sv - timedelta(days=240)).strftime('%Y-%m-%d')
    params = {"action": "get_events", "from": f_desde, "to": f_hasta, "league_id": league_id}
    eventos_brutos = api_request_live("get_events", params)
    datos_mle = []
    for m in eventos_brutos:
        if m.get('match_status') == 'Finished':
            try:
                datos_mle.append({
                    'home_team': m['match_hometeam_name'],
                    'away_team': m['match_awayteam_name'],
                    'home_goals': int(m['match_hometeam_score']),
                    'away_goals': int(m['match_awayteam_score'])
                })
            except: continue
    return pd.DataFrame(datos_mle)

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
        if days_off <= 3: return 0.92
        if days_off >= 7: return 1.05
        return 1.0
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

            decay_exp = math.exp(-0.04 * days_diff)
            decay_lin = max(0.1, 1 - (days_diff / 60))
            weight = (decay_exp * 0.6) + (decay_lin * 0.4) 

            is_home = m['match_hometeam_id'] == team_id
            gf = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            gc = int(m['match_awayteam_score']) if is_home else int(m['match_hometeam_score'])

            calidad_rival_adj = 1.0
            if not is_home and gc == 0: calidad_rival_adj = 1.15
            elif is_home and gc > 2: calidad_rival_adj = 0.90

            momentum_gf += (gf * weight * calidad_rival_adj)
            goles_reales += gf
            total_w += weight
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
# 3. MOTOR MATEMÁTICO (QUANTUM DIXON-COLES)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5, draw_freq=0.25, custom_rho=None):
        if custom_rho is not None:
            self.rho = custom_rho
        else:
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
        sim_tj = np.random.poisson(tj_total, 15000); sim_co = np.random.poisson(co_total, 15000)
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
# 4. DISEÑO UI/UX
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE v6.9.1", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Outfit:wght@300;400;600;900&display=swap');
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; --panel-bg: rgba(15, 20, 25, 0.7); }
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); box-shadow: 0 20px 40px rgba(0,0,0,0.6); margin-bottom: 30px; }
    .premium-card { background: var(--panel-bg); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 20px; padding: 25px; margin-bottom: 25px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); backdrop-filter: blur(10px); }
    .tab-header { border-bottom: 1px solid rgba(212, 175, 55, 0.2); padding-bottom: 12px; margin-bottom: 20px; color: var(--primary); font-weight: 800; font-size: 1.1em; text-transform: uppercase; letter-spacing: 2px; display:flex; align-items:center; gap: 8px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.05em; display:flex; justify-content:space-between; align-items:center; transition: all 0.3s ease; }
    .verdict-item:hover { transform: translateX(5px); background: rgba(0, 255, 163, 0.08); }
    .score-badge { background: linear-gradient(145deg, #111, #0a0a0a); padding: 15px; border-radius: 16px; border: 1px solid rgba(212, 175, 55, 0.4); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.3em; font-family: 'JetBrains Mono', monospace; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; border: none; padding: 20px; border-radius: 14px; text-transform: uppercase; letter-spacing: 3px; width: 100%; }
    .wa-btn { background: #25D366; color: white !important; text-decoration: none; padding: 12px 25px; border-radius: 12px; font-weight: 800; display: inline-flex; align-items: center; gap: 10px; width: 100%; justify-content: center; }
    .mc-stat-box { background: linear-gradient(180deg, rgba(20,25,30,0.8) 0%, rgba(10,12,15,0.8) 100%); border: 1px solid rgba(255,255,255,0.05); padding: 25px 20px; border-radius: 16px; text-align: center; }
    .mc-val { font-size: 2em; font-weight: 900; color: #d4af37; font-family: 'JetBrains Mono'; }
    .mc-lab { font-size: 0.75em; color: #888; text-transform: uppercase; letter-spacing: 2px; }
    .audit-card { background: rgba(15,20,25,0.8); border: 1px solid rgba(255,255,255,0.05); padding: 25px; border-radius: 16px; margin-bottom: 20px; }
    .hit { color: var(--secondary); font-weight: 900; }
    .miss { color: #ff4b4b; font-weight: 900; }
    .motivation-tag { background: rgba(212, 175, 55, 0.1); color: var(--primary); padding: 2px 8px; border-radius: 4px; font-size: 0.7em; font-weight: 700; border: 1px solid var(--primary); }
    </style>
    """, unsafe_allow_html=True)

def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin: 30px 0; background: rgba(15,20,25,0.8); padding: 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; justify-content: space-between; font-size: 0.95em; color: #bbb; text-transform: uppercase; margin-bottom: 20px; font-weight: 600;">
                <span style="color:var(--secondary)">{n1}: <b style="font-family:'JetBrains Mono';">{p1:.1f}%</b></span>
                <span>{nx}: <b style="font-family:'JetBrains Mono';">{px_val:.1f}%</b></span>
                <span style="color:var(--primary)">{n2}: <b style="font-family:'JetBrains Mono';">{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 18px; border-radius: 50px; overflow: hidden; background: #0a0c10;">
                <div style="width: {p1}%; background: linear-gradient(90deg, #00b372, var(--secondary));"></div>
                <div style="width: {px_val}%; background: #333;"></div>
                <div style="width: {p2}%; background: linear-gradient(90deg, #8a6d1d, var(--primary));"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="background: rgba(10,12,15,0.6); padding: 16px 20px; border-radius: 12px; margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-weight: 700; color: #fff;">{label_over} <span style="color:{color};">{prob_over:.1f}%</span></span>
                <span style="color: #777;">{prob_under:.1f}% <span>{label_under}</span></span>
            </div>
            <div style="display: flex; background: #05070a; height: 10px; border-radius: 5px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color};"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# 5. SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center; font-weight:900;'>GOLD TERMINAL v6.9.1</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Saudi Pro League": 307, "Trendyol Süper Lig": 322, "Liga Mayor (El Salvador)": 601, "Copa Presidente (El Salvador)": 603,
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207, "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, 
        "Liga Portugal Betclic": 266, # <--- PORTUGAL AGREGADA
        "UEFA Champions League": 3, "UEFA Europa League": 4, "UEFA Conference League": 683, "Copa Libertadores": 13,
        "Brasileirão Betano (Série A)": 99, "Brasileirão Série B": 100, "Brasileirão Série C": 103, "Copa de Brasil": 101,
        "FA Cup (Inglaterra)": 145, "EFL Cup (Inglaterra)": 146, "Copa del Rey (España)": 300, "Coppa Italia (Italia)": 209, "DFB Pokal (Alemania)": 177, "Coupe de France (Francia)": 169
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 JORNADA CENTRAL", value=ahora_sv.date())
    f_desde = (fecha_analisis - timedelta(days=3)).strftime('%Y-%m-%d'); f_hasta = (fecha_analisis + timedelta(days=3)).strftime('%Y-%m-%d')
    raw_events = api_request_live("get_events", {"from": f_desde, "to": f_hasta, "league_id": ligas_api[nombre_liga]})
    if raw_events:
        op_p = {f"({e['match_date']}) {e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        p_sel = st.selectbox("📍 Partidos Encontrados", list(op_p.keys()))
        if st.button("SYNC DATA"):
            st.cache_data.clear()
            with st.spinner("QUANTUM DEEP SYNC & MLE TRAINING..."):
                standings = api_request_cached(ligas_api[nombre_liga]); match_info = op_p[p_sel]
                if standings:
                    h_goals = sum(int(t['home_league_GF']) for t in standings); a_goals = sum(int(t['away_league_GF']) for t in standings)
                    draws = sum(int(t['overall_league_D']) for t in standings); total_pj = sum(int(t['overall_league_payed']) for t in standings)
                    st.session_state['draw_freq'] = draws / total_pj if total_pj > 0 else 0.25; st.session_state['p_liga_auto'] = (h_goals + a_goals) / (total_pj / 2) if total_pj > 0 else 2.5
                    st.session_state['hfa_league'] = float(h_goals / a_goals) if a_goals > 0 else 1.1
                    def buscar(n):
                        nombres = [t['team_name'] for t in standings]; m, s = process.extractOne(n, nombres); return next((t for t in standings if t['team_name'] == m), None) if s > 65 else None
                    dl, dv = buscar(match_info['match_hometeam_name']), buscar(match_info['match_awayteam_name'])
                    if dl and dv:
                        sl, tl = analyze_competition_stakes(standings, dl['team_id'], ligas_api[nombre_liga])
                        sv, tv = analyze_competition_stakes(standings, dv['team_id'], ligas_api[nombre_liga])
                        st.session_state['stake_l'], st.session_state['tag_l'] = sl, tl
                        st.session_state['stake_v'], st.session_state['tag_v'] = sv, tv
                        phl, pav = int(dl['home_league_payed']), int(dv['away_league_payed'])
                        cb_l, pxg_l, tempo_l = get_team_tactical_stats(dl['team_id'], ligas_api[nombre_liga])
                        cb_v, pxg_v, tempo_v = get_team_tactical_stats(dv['team_id'], ligas_api[nombre_liga])
                        st.session_state['tempo_factor'] = (tempo_l, tempo_v)
                        st.session_state['corner_bias'] = (cb_l, cb_v); st.session_state['proxy_xg_l'] = pxg_l; st.session_state['proxy_xg_v'] = pxg_v
                        st.session_state['h2h_bias'] = get_h2h_data(dl['team_id'], dv['team_id'])
                        elo_l, mom_l, luck_l, conv_l = get_advanced_metrics(dl['team_id'], ligas_api[nombre_liga], dl['overall_league_position'], pxg_l)
                        elo_v, mom_v, luck_v, conv_v = get_advanced_metrics(dv['team_id'], ligas_api[nombre_liga], dv['overall_league_position'], pxg_v)
                        df_historial = extraer_historial_mle(ligas_api[nombre_liga])
                        if not df_historial.empty:
                            params_mle, success = train_dixon_coles(df_historial)
                            if success:
                                st.session_state['mle_rho'] = params_mle['rho']
                                alpha_l = params_mle['attack'].get(dl['team_name'], 1.0); beta_l = params_mle['defense'].get(dl['team_name'], 1.0)
                                alpha_v = params_mle['attack'].get(dv['team_name'], 1.0); beta_v = params_mle['defense'].get(dv['team_name'], 1.0)
                                mle_elo_l = alpha_l / max(0.1, beta_l); mle_elo_v = alpha_v / max(0.1, beta_v)
                                elo_l = max(0.75, min(1.4, mle_elo_l)); elo_v = max(0.75, min(1.4, mle_elo_v))
                                st.session_state['hfa_specific'] = (params_mle['gamma'], 1/params_mle['gamma'] if params_mle['gamma']>0 else 0.9)
                        st.session_state['conv_factor'] = (conv_l, conv_v); st.session_state['luck_factor'] = (luck_l, luck_v)
                        st.session_state['fatiga_l'] = get_fatigue_factor(dl['team_id'], match_info['match_date'])
                        st.session_state['fatiga_v'] = get_fatigue_factor(dv['team_id'], match_info['match_date'])
                        st.session_state['market_bias'] = get_market_consensus(match_info['match_id'])
                        st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/phl if phl>0 else 1.5) * 0.6 + (mom_l * 0.4)
                        st.session_state['lgc_auto'] = (float(dl['home_league_GA'])/phl if phl>0 else 1.0)
                        st.session_state['vgf_auto'] = (float(dv['away_league_GF'])/pav if pav>0 else 1.2) * 0.6 + (mom_v * 0.4)
                        st.session_state['vgc_auto'] = (float(dv['away_league_GA'])/pav if pav>0 else 1.3)
                        st.session_state['lco_auto'] = float(dl.get('home_league_corners', 5.5)); st.session_state['vco_auto'] = float(dv.get('away_league_corners', 4.8))
                        st.session_state['elo_bias'] = (elo_l, elo_v); st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        recent_league = api_request_live("get_events", {"from": (ahora_sv - timedelta(days=10)).strftime('%Y-%m-%d'), "to": ahora_sv.strftime('%Y-%m-%d'), "league_id": ligas_api[nombre_liga]})
                        st.session_state['audit_results'] = [e for e in recent_league if e['match_status'] == 'Finished'][-10:]; st.rerun()

# =================================================================
# 6. CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555; letter-spacing: 5px; margin-bottom: 40px;'>PREDICTIVE ENGINE V6.9.1 QUANTUM + PULSE MODE</p>", unsafe_allow_html=True)

importancia_global = max(st.session_state['stake_l'], st.session_state['stake_v'])
color_imp = "#00ffa3" if importancia_global < 1.1 else ("#d4af37" if importancia_global < 1.2 else "#ff4b4b")
txt_imp = "Fase Regular / Normal" if importancia_global < 1.1 else ("Alta Importancia / Tensión" if importancia_global < 1.2 else "CRÍTICO / A MUERTE")

st.markdown(f"<div style='text-align: center; margin-bottom: 30px;'><div style='display: inline-block; background: rgba(255,255,255,0.03); padding: 12px 30px; border-radius: 16px; border: 1px solid {color_imp};'><div style='color: {color_imp}; font-weight: 900;'>{txt_imp}</div></div></div>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown(f"<div><h6 style='color:var(--secondary); font-weight:900;'>LOCAL <span class='motivation-tag'>{st.session_state['tag_l']}</span></h6></div>", unsafe_allow_html=True)
    nl_manual = st.text_input("Nombre Local", value=st.session_state['nl_auto'], label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf = la.number_input("GF Local", 0.0, 10.0, key='lgf_auto'); lgc = lb.number_input("GC Local", 0.0, 10.0, key='lgc_auto')
    ltj = la.number_input("Tarjetas L", 0.0, 15.0, key='ltj_auto'); lco = lb.number_input("Corners L", 0.0, 20.0, key='lco_auto')

with col_v:
    st.markdown(f"<div><h6 style='color:var(--primary); font-weight:900;'>VISITANTE <span class='motivation-tag'>{st.session_state['tag_v']}</span></h6></div>", unsafe_allow_html=True)
    nv_manual = st.text_input("Nombre Visita", value=st.session_state['nv_auto'], label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf = va.number_input("GF Visita", 0.0, 10.0, key='vgf_auto'); vgc = vb.number_input("GC Visita", 0.0, 10.0, key='vgc_auto')
    vtj = va.number_input("Tarjetas V", 0.0, 15.0, key='vtj_auto'); vco = vb.number_input("Corners V", 0.0, 20.0, key='vco_auto')

p_liga = st.slider("Media de Goles de la Liga", 0.5, 5.0, key='p_liga_auto')

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico(league_avg=p_liga, draw_freq=st.session_state['draw_freq'], custom_rho=st.session_state.get('mle_rho'))
    hfa_base = st.session_state['hfa_league']; hfa_l_spec, hfa_v_spec = st.session_state['hfa_specific']
    luck_l, luck_v = st.session_state['luck_factor']; conv_l, conv_v = st.session_state['conv_factor']; tempo_l, tempo_v = st.session_state['tempo_factor']
    stake_l, stake_v = st.session_state['stake_l'], st.session_state['stake_v']; diff_motivation = stake_l / stake_v
    ataque_l = (lgf * 0.4) + (st.session_state['proxy_xg_l'] * 0.6); ataque_v = (vgf * 0.4) + (st.session_state['proxy_xg_v'] * 0.6)
    xg_l = (ataque_l/p_liga)*(vgc/p_liga)*p_liga * (hfa_base * hfa_l_spec) * st.session_state['h2h_bias'][0] * st.session_state['elo_bias'][0] * st.session_state['fatiga_l'] * luck_l * diff_motivation * conv_l * tempo_l
    xg_v = (ataque_v/p_liga)*(lgc/p_liga)*p_liga * (1/(hfa_base * (1/hfa_v_spec))) * st.session_state['h2h_bias'][1] * st.session_state['elo_bias'][1] * st.session_state['fatiga_v'] * luck_v * (1/diff_motivation) * conv_v * tempo_v
    tj_final = ( (ltj + vtj) * 0.4 + (ref_avg * 0.6) ) if 'ref_avg' in locals() and ref_avg > 0 else (ltj + vtj)
    cb_l, cb_v = st.session_state['corner_bias']; co_final = (lco * cb_l) + (vco * cb_v)
    res = motor.procesar(xg_l, xg_v, tj_final, co_final)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:var(--primary); font-weight: 800;'>💎 TOP SELECCIONES</h4>", unsafe_allow_html=True)
        pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "BTTS: SÍ", "p": res['BTTS'][0]}]
        for line, p in res['GOLES'].items():
            if 0.5 <= line <= 2.5: pool.append({"t": f"Over {line}", "p": p[0]})
        sug = sorted([s for s in pool if s['p'] > 72], key=lambda x: x['p'], reverse=True)[:5]
        for s in sug: st.markdown(f'<div class="verdict-item"><span><b>{s["p"]:.1f}%</b> — {s["t"]}</span></div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; text-align:center;'>🎯 MARCADORES</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} <br><small>Prob: {prob:.1f}%</small></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl_manual, "Empate", nv_manual)
    
    # El resto de tabs (Goles, Handicap, etc.) continúan con la misma lógica visual.
    st.tabs(["🥅 GOLES", "🏆 HANDICAP", "📊 1X2", "🎲 MONTE CARLO", "🧩 MATRIZ", "📈 AUDITORÍA", "🕸️ RADAR"])

st.markdown("<p style='text-align: center; color: #444; font-size: 0.8em;'>OR936 ELITE v6.9.2 | QUANTUM MLE PORTUGAL READY</p>", unsafe_allow_html=True)
