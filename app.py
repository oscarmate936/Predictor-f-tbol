import streamlit as st
import math
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN Y ESTILO CSS ULTRA-PREMIUM
# =================================================================
st.set_page_config(page_title="OR936 Elite v3.2", layout="wide")

def inject_full_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
        
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #e1e1e1; }
        .stApp { background-color: #0b0e11; }
        
        /* Dashboard de Entrada Profesional */
        .input-panel {
            background: #161b22;
            border-radius: 15px;
            padding: 25px;
            border: 1px solid #30363d;
            margin-bottom: 25px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }
        
        .panel-header {
            color: #00ffcc;
            font-size: 0.9rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 20px;
            border-bottom: 1px solid #30363d;
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Marquesina VS */
        .match-marquee {
            text-align: center;
            padding: 40px 0;
            background: radial-gradient(circle, #1c2128 0%, #0b0e11 100%);
            border-radius: 20px;
            margin-bottom: 30px;
            border: 1px solid #30363d;
        }

        /* Tarjetas de Resultado */
        .premium-card {
            background: #161b22;
            border-radius: 20px;
            padding: 20px;
            border: 1px solid #30363d;
            margin-bottom: 20px;
        }

        .section-title {
            color: #8b949e;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 15px;
            display: block;
        }

        /* Barras Duales */
        .stat-container { margin-bottom: 18px; }
        .stat-info { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.85rem; }
        .stat-bar-bg { height: 6px; background: #30363d; border-radius: 10px; display: flex; overflow: hidden; }
        .bar-l { background: #00ffcc; }
        .bar-v { background: #3498db; }

        /* Estilo de Inputs */
        .stNumberInput div[data-baseweb="input"] {
            background-color: #0b0e11 !important;
            border: 1px solid #30363d !important;
            border-radius: 8px !important;
            color: #00ffcc !important;
        }
        
        .suggestion-item {
            background: rgba(0, 255, 204, 0.03);
            border-left: 3px solid #00ffcc;
            padding: 12px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }

        .stButton>button {
            background: linear-gradient(90deg, #00ffcc 0%, #008577 100%);
            color: #000 !important;
            font-weight: 800;
            border-radius: 12px;
            height: 50px;
        }
        </style>
    """, unsafe_allow_html=True)

inject_full_css()

# =================================================================
# MOTOR MATEMÁTICO (DIXON-COLES)
# =================================================================
class MotorMatematico:
    def __init__(self): self.rho = -0.15
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
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1-btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz
        }

# =================================================================
# LÓGICA DE API Y ESTADOS
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "HOME TEAM"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "AWAY TEAM"

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except: return []

# =================================================================
# SIDEBAR (SYNC)
# =================================================================
with st.sidebar:
    st.markdown("<h3 style='color:#00ffcc;'>📡 API Control</h3>", unsafe_allow_html=True)
    ligas_api = {"La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168}
    nombre_liga = st.selectbox("League", list(ligas_api.keys()))
    fecha_analisis = st.date_input("Date", datetime.now())
    
    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})
    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("Detected Matches", list(op_p.keys()))
        if st.button("⚡ AUTO-SYNC TEAM DATA"):
            standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
            if standings:
                total_g = sum(int(t['overall_league_GF']) for t in standings)
                total_pj = sum(int(t['overall_league_payed']) for t in standings)
                st.session_state['p_liga_auto'] = float(total_g / (total_pj / 2)) if total_pj > 0 else 2.5
                def buscar(n):
                    for t in standings: 
                        if n.lower() in t['team_name'].lower() or t['team_name'].lower() in n.lower(): return t
                    return None
                dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                if dl and dv:
                    st.session_state['lgf_auto'] = float(dl['overall_league_GF'])/int(dl['overall_league_payed'])
                    st.session_state['lgc_auto'] = float(dl['overall_league_GA'])/int(dl['overall_league_payed'])
                    st.session_state['vgf_auto'] = float(dv['overall_league_GF'])/int(dv['overall_league_payed'])
                    st.session_state['vgc_auto'] = float(dv['overall_league_GA'])/int(dv['overall_league_payed'])
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.rerun()

# =================================================================
# 1. HEADER VISUAL (EL "VS")
# =================================================================
st.markdown(f"""
    <div class="match-marquee">
        <span style="color:#8b949e; font-size:0.8rem; font-weight:700; text-transform:uppercase; letter-spacing:3px;">{nombre_liga} Analysis</span>
        <div style="display:flex; justify-content:center; align-items:center; gap:50px; margin-top:20px;">
            <div style="text-align:right;">
                <h1 style="margin:0; font-weight:800; font-size:2.5rem; color:white;">{st.session_state['nl_auto']}</h1>
                <span style="color:#00ffcc; font-family:'JetBrains Mono';">HOME SQUAD</span>
            </div>
            <div style="background:#00ffcc; color:#000; padding:10px 25px; border-radius:12px; font-weight:900; font-size:1.8rem;">VS</div>
            <div style="text-align:left;">
                <h1 style="margin:0; font-weight:800; font-size:2.5rem; color:white;">{st.session_state['nv_auto']}</h1>
                <span style="color:#3498db; font-family:'JetBrains Mono';">AWAY SQUAD</span>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# =================================================================
# 2. DASHBOARD DE ENTRADA (CONTROL PANEL)
# =================================================================
st.markdown('<div class="input-panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-header">🛠️ Tactic Control Dashboard</div>', unsafe_allow_html=True)

d_col1, d_col2, d_col3 = st.columns(3)

with d_col1:
    st.markdown("<span class='section-title' style='color:#00ffcc;'>🏠 Home Statistics</span>", unsafe_allow_html=True)
    lgf = st.number_input("Avg Goals Scored", 0.0, 5.0, st.session_state.get('lgf_auto', 1.5), step=0.1)
    lgc = st.number_input("Avg Goals Conceded", 0.0, 5.0, st.session_state.get('lgc_auto', 1.2), step=0.1)

with d_col2:
    st.markdown("<span class='section-title' style='color:#3498db;'>🚀 Away Statistics</span>", unsafe_allow_html=True)
    vgf = st.number_input("Avg Goals Scored ", 0.0, 5.0, st.session_state.get('vgf_auto', 1.3), step=0.1)
    vgc = st.number_input("Avg Goals Conceded ", 0.0, 5.0, st.session_state.get('vgc_auto', 1.4), step=0.1)

with d_col3:
    st.markdown("<span class='section-title'>📍 Match Conditions</span>", unsafe_allow_html=True)
    ltj = st.number_input("Exp. Total Cards", 0.0, 15.0, 4.5, step=0.5)
    lco = st.number_input("Exp. Total Corners", 0.0, 20.0, 9.5, step=0.5)
    p_liga = st.slider("League Goal Avg", 0.5, 4.5, st.session_state['p_liga_auto'])

run_analysis = st.button("🚀 EXECUTE ELITE PROJECTION", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# =================================================================
# 3. RESULTADOS (DASHBOARD PRINCIPAL)
# =================================================================
if run_analysis:
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj, lco)
    
    # RENDERIZADO DE RESULTADOS
    c_res_main, c_res_side = st.columns([1.6, 1])
    
    with c_res_main:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<span class="section-title">💎 Master Betting Insights</span>', unsafe_allow_html=True)
        pool = []
        pool.append({"t": "Doble Oportunidad 1X", "p": res['DC'][0]})
        pool.append({"t": "Doble Oportunidad X2", "p": res['DC'][1]})
        pool.append({"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]})
        for line, p in res['GOLES'].items():
            if 1.5 <= line <= 3.5:
                pool.append({"t": f"Over {line} Goals", "p": p[0]})
                pool.append({"t": f"Under {line} Goals", "p": p[1]})
        
        sugerencias = sorted([s for s in pool if 68 < s['p'] < 96], key=lambda x: x['p'], reverse=True)[:5]
        for s in sugerencias:
            st.markdown(f"<div class='suggestion-item'><span>{s['t']}</span><b style='color:#00ffcc;'>{s['p']:.1f}%</b></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c_res_side:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<span class="section-title">⚽ Top 3 Scores</span>', unsafe_allow_html=True)
        for score, prob in res['TOP']:
            st.markdown(f"<div style='background:#0b0e11; padding:12px; border-radius:10px; margin-bottom:10px; display:flex; justify-content:space-between; border:1px solid #30363d;'><b style='font-size:1.2rem; color:#00ffcc;'>{score}</b><span>{prob:.1f}%</span></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Tabs de Mercados
    t1, t2, t3, t4 = st.tabs(["📊 Main", "🥅 Goals 0.5-5.5", "🚩 Special", "📈 Matrix"])
    
    def render_bar(label, p_l, p_v):
        total = p_l + p_v if (p_l + p_v) > 0 else 1
        st.markdown(f"""
            <div class="stat-container">
                <div class="stat-info"><span>{p_l:.1f}%</span><span style='color:#8b949e;'>{label}</span><span>{p_v:.1f}%</span></div>
                <div class="stat-bar-bg"><div style="width:{p_l/total*100}%;" class="bar-l"></div><div style="width:{(1-p_l/total)*100}%;" class="bar-v"></div></div>
            </div>
        """, unsafe_allow_html=True)

    with t1:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        render_bar("Double Chance 1X / 2", res['DC'][0], 100-res['DC'][0])
        render_bar("Double Chance X2 / 1", res['DC'][1], 100-res['DC'][1])
        render_bar("Both Teams to Score", res['BTTS'][0], res['BTTS'][1])
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            p = res['GOLES'][line]
            render_bar(f"OVER / UNDER {line}", p[0], p[1])
        st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        ca, cb = st.columns(2)
        with ca:
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            for line, p in res['CORNERS'].items(): render_bar(f"Corners Over {line}", p[0], p[1])
            st.markdown('</div>', unsafe_allow_html=True)
        with cb:
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            for line, p in res['TARJETAS'].items(): render_bar(f"Cards Over {line}", p[0], p[1])
            st.markdown('</div>', unsafe_allow_html=True)

    with t4:
        st.plotly_chart(px.imshow(pd.DataFrame(res['MATRIZ']), text_auto=".1f", color_continuous_scale='Viridis'), use_container_width=True)
