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

# Inicialización de estados
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'form_l_list' not in st.session_state: st.session_state['form_l_list'] = []
if 'form_v_list' not in st.session_state: st.session_state['form_v_list'] = []
if 'market_bias' not in st.session_state: st.session_state['market_bias'] = None
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.15, 'elo_bias': (1.0, 1.0),
    'h2h_bias': (1.0, 1.0), 'fatiga_l': 1.0, 'fatiga_v': 1.0,
    'lgf_auto': 1.5, 'lgc_auto': 1.0, 'vgf_auto': 1.2, 'vgc_auto': 1.3,
    'ltj_auto': 2.3, 'lco_auto': 5.5, 'vtj_auto': 2.2, 'vco_auto': 4.8
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. LÓGICA ELITE MEJORADA
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
def get_advanced_metrics_v2(team_id, league_id):
    events = api_request_live("get_events", {
        "from": (ahora_sv - timedelta(days=60)).strftime('%Y-%m-%d'), 
        "to": ahora_sv.strftime('%Y-%m-%d'), 
        "league_id": league_id, 
        "team_id": team_id
    })
    if not events: return 1.0, 0, []
    
    finished = [e for e in events if e['match_status'] == 'Finished']
    form_icons = []
    momentum_score = 0
    weights = [0.5, 0.3, 0.2] # Recientes pesan más
    
    for i, m in enumerate(finished[-5:][::-1]):
        is_home = m['match_hometeam_id'] == team_id
        try:
            gs = int(m['match_hometeam_score']) if is_home else int(m['match_awayteam_score'])
            gc = int(m['match_awayteam_score']) if is_home else int(m['match_hometeam_score'])
            
            if gs > gc: 
                form_icons.append("🟢")
                if i < 3: momentum_score += 1.2 * weights[i]
            elif gs < gc: 
                form_icons.append("🔴")
            else: 
                form_icons.append("🟡")
                if i < 3: momentum_score += 1.0 * weights[i]
        except: continue
        
    return 1.0 + momentum_score, momentum_score, form_icons

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
        if days_off <= 3: return 0.88 
        if days_off >= 7: return 1.08
        return 1.0
    except: return 1.0

# =================================================================
# 3. MOTOR QUANTUM (DIXON-COLES V4.8 + DYNAMIC RHO)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5, draw_prob=0.25): 
        # Rho dinámica basada en la tendencia de empates de la liga
        self.rho = -0.18 if draw_prob > 0.30 else (-0.12 if draw_prob < 0.22 else -0.15)

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def procesar(self, xg_l, xg_v, tj_total, co_total, market_odds=None):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5]
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
        
        # Guardar probabilidades originales para cálculo de valor
        raw_probs = (p1/total, px/total, p2/total)

        if market_odds:
            m1, mx, m2 = market_odds
            p1 = (p1/total * 0.70) + (m1 * 0.30)
            px = (px/total * 0.70) + (mx * 0.30)
            p2 = (p2/total * 0.70) + (m2 * 0.30)
            total = p1 + px + p2

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "RAW_PROBS": raw_probs,
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, 
            "BRIER": 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 2.0))
        }

# =================================================================
# 4. COMPONENTES VISUALES ELITE
# =================================================================

def draw_radar(stats_l, stats_v, names):
    categories = ['Ataque', 'Defensa', 'ELO', 'Fatiga', 'Momentum']
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=stats_l, theta=categories, fill='toself', name=names[0], line_color='#00ffa3'))
    fig.add_trace(go.Scatterpolar(r=stats_v, theta=categories, fill='toself', name=names[1], line_color='#d4af37'))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=False), bgcolor='rgba(0,0,0,0)'),
        showlegend=True, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="#fff")
    )
    return fig

# =================================================================
# 5. SIDEBAR & SYNC
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168,
        "Saudi Pro League": 307, "Liga Mayor (SV)": 601, "Champions League": 3, "Libertadores": 13
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Jornada", value=ahora_sv.date())
    
    events = api_request_live("get_events", {
        "from": (fecha_analisis - timedelta(days=2)).strftime('%Y-%m-%d'),
        "to": (fecha_analisis + timedelta(days=2)).strftime('%Y-%m-%d'),
        "league_id": ligas_api[nombre_liga]
    })

    if events:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in events}
        p_sel = st.selectbox("📍 Partido", list(op_p.keys()))

        if st.button("SYNC QUANTUM DATA"):
            with st.spinner("Calibrando..."):
                m = op_p[p_sel]
                standings = api_request_live("get_standings", {"league_id": ligas_api[nombre_liga]})
                
                def find_t(n):
                    names = [x['team_name'] for x in standings]
                    res = process.extractOne(n, names)
                    return next(t for t in standings if t['team_name'] == res[0]) if res[1] > 70 else None

                dl, dv = find_t(m['match_hometeam_name']), find_t(m['match_awayteam_name'])
                if dl and dv:
                    # Datos Forma
                    _, ml, fl = get_advanced_metrics_v2(dl['team_id'], ligas_api[nombre_liga])
                    _, mv, fv = get_advanced_metrics_v2(dv['team_id'], ligas_api[nombre_liga])
                    st.session_state['form_l_list'], st.session_state['form_v_list'] = fl, fv
                    
                    # Fatiga
                    st.session_state['fatiga_l'] = get_fatigue_factor(dl['team_id'], m['match_date'])
                    st.session_state['fatiga_v'] = get_fatigue_factor(dv['team_id'], m['match_date'])
                    
                    # Stats Base
                    ph, pa = int(dl['home_league_payed']), int(dv['away_league_payed'])
                    st.session_state['lgf_auto'] = (float(dl['home_league_GF'])/ph if ph>0 else 1.5)
                    st.session_state['lgc_auto'] = (float(dl['home_league_GA'])/ph if ph>0 else 1.0)
                    st.session_state['vgf_auto'] = (float(dv['away_league_GF'])/pa if pa>0 else 1.2)
                    st.session_state['vgc_auto'] = (float(dv['away_league_GA'])/pa if pa>0 else 1.3)
                    
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.session_state['market_bias'] = ((1/float(m['match_hometeam_score'] or 2.0)), 0.3, 0.3) # Dummy placeholder if no odds
                    st.rerun()

# =================================================================
# 6. UI PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE V4.8</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader(f"🏠 {st.session_state['nl_auto']}")
    st.write(" ".join(st.session_state['form_l_list']))
    la, lb = st.columns(2)
    lgf = la.number_input("GF Home", value=st.session_state['lgf_auto'])
    lgc = lb.number_input("GC Home", value=st.session_state['lgc_auto'])
with c2:
    st.subheader(f"🚀 {st.session_state['nv_auto']}")
    st.write(" ".join(st.session_state['form_v_list']))
    va, vb = st.columns(2)
    vgf = va.number_input("GF Away", value=st.session_state['vgf_auto'])
    vgc = vb.number_input("GC Away", value=st.session_state['vgc_auto'])

if st.button("GENERAR INTELIGENCIA DE MERCADO"):
    # Cálculos Finales
    p_liga = st.session_state['p_liga_auto']
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * st.session_state['hfa_league'] * st.session_state['fatiga_l']
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/st.session_state['hfa_league']) * st.session_state['fatiga_v']
    
    motor = MotorMatematico(league_avg=p_liga)
    res = motor.procesar(xg_l, xg_v, 4.5, 9.5, market_odds=st.session_state['market_bias'])

    # Métricas Superiores
    m1, m2, m3 = st.columns(3)
    m1.metric(f"xG {st.session_state['nl_auto']}", f"{xg_l:.2f}", delta=f"{(st.session_state['fatiga_l']-1):.2%}")
    m2.metric("Confianza Modelo", f"{res['BRIER']*100:.1f}%")
    m3.metric(f"xG {st.session_state['nv_auto']}", f"{xg_v:.2f}", delta=f"{(st.session_state['fatiga_v']-1):.2%}")

    col_left, col_right = st.columns([1.2, 1])
    
    with col_left:
        st.markdown("### 💎 SELECCIONES DE VALOR")
        # Lógica de Value Betting
        picks = [
            ("Gana " + st.session_state['nl_auto'], res['1X2'][0], st.session_state['market_bias'][0] if st.session_state['market_bias'] else 0),
            ("Over 2.5 Goles", res['GOLES'][2.5][0], 0.5)
        ]
        for name, prob, m_prob in picks:
            is_value = prob/100 > m_prob and m_prob > 0
            color = "#00ffa3" if is_value else "#555"
            st.markdown(f"""<div style='background:rgba(255,255,255,0.05); padding:15px; border-left:5px solid {color}; border-radius:10px; margin-bottom:10px;'>
                <b style='color:{color}'>{'[VALOR] ' if is_value else ''}{name}</b> — Probabilidad: {prob:.1f}%
            </div>""", unsafe_allow_html=True)

    with col_right:
        st.markdown("### 📊 COMPARATIVA RADAR")
        s_l = [lgf*20, (3-lgc)*20, 70, st.session_state['fatiga_l']*80, 75]
        s_v = [vgf*20, (3-vgc)*20, 65, st.session_state['fatiga_v']*80, 60]
        st.plotly_chart(draw_radar(s_l, s_v, [st.session_state['nl_auto'], st.session_state['nv_auto']]), use_container_width=True)

    # Matriz y Tabs
    t1, t2 = st.tabs(["🧩 Matriz de Marcadores", "📈 Probabilidades Detalladas"])
    with t1:
        fig = px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Greens')
        st.plotly_chart(fig, use_container_width=True)
    with t2:
        st.json(res['GOLES'])

st.markdown("<p style='text-align:center; opacity:0.5;'>OR936 QUANTUM ELITE v4.8 | Basado en Dixon-Coles & Fatigue Index</p>", unsafe_allow_html=True)
