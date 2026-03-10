import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN API (apiv3.apifootball.com)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

@st.cache_data(ttl=3600)
def api_request(action, params={}):
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except:
        return []

# =================================================================
# ESTILOS CSS PROFESIONALES (ELITE UI)
# =================================================================
st.set_page_config(page_title="OR936 Elite v3.1", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .input-card {
        background: #161b22; padding: 20px; border-radius: 12px;
        border-top: 4px solid #00ffcc; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .stButton>button {
        width: 100%; background: linear-gradient(90deg, #00ffcc 0%, #008577 100%);
        color: black !important; font-weight: bold; border: none;
        padding: 12px; border-radius: 10px;
    }
    .market-label { font-size: 0.85em; color: #888; margin-bottom: 2px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# COMPONENTES VISUALES AVANZADOS
# =================================================================
def triple_bar(p1, px, p2, n1, nx, n2):
    """Barra segmentada única para 1X2"""
    st.markdown(f"""
        <div style="margin-bottom: 25px; background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d;">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 8px; color: #eee;">
                <span>{n1}: <b>{p1:.1f}%</b></span>
                <span>Empate: <b>{px:.1f}%</b></span>
                <span>{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 20px; border-radius: 10px; overflow: hidden; border: 1px solid #444;">
                <div style="width: {p1}%; background: #00ffcc;"></div>
                <div style="width: {px}%; background: #555;"></div>
                <div style="width: {p2}%; background: #3498db;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color_over="#00ffcc", color_under="#ff4b4b"):
    """Barra doble explícita para Over/Under y BTTS"""
    st.markdown(f"""
        <div style="margin-bottom: 18px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #eee; margin-bottom: 4px;">
                <span><b>{label_over}:</b> {prob_over:.1f}%</span>
                <span><b>{label_under}:</b> {prob_under:.1f}%</span>
            </div>
            <div style="display: flex; background: #222; height: 12px; border-radius: 6px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
                <div style="width: {prob_over}%; background: {color_over}; box-shadow: 0 0 10px {color_over}44;"></div>
                <div style="width: {prob_under}%; background: {color_under}66; border-left: 1px solid rgba(255,255,255,0.1);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# MOTOR MATEMÁTICO (PRO STATS ENGINE)
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
        return {"1X2": (p1/total*100, px/total*100, p2/total*100), "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
                "BTTS": (btts_si/total*100, (1-btts_si/total)*100), "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
                "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
                "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
                "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], "MATRIZ": matriz}

# =================================================================
# INTERFAZ (SIDEBAR Y DASHBOARD)
# =================================================================
with st.sidebar:
    st.markdown("### 🌐 DATA CONSOLE")
    ligas_api = {"La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, 
                 "UCL": 3, "Libertadores": 13, "Brasileirão": 99, "Liga Mayor SLV": 601, "Copa Presidente SLV": 603}
    nombre_liga = st.selectbox("Liga", list(ligas_api.keys()))
    fecha_analisis = st.date_input("Fecha Partido", datetime.now())
    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})
    if eventos and isinstance(eventos, list):
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("Partidos Disponibles", list(op_p.keys()))
        if st.button("⚡ SINCRONIZAR API"):
            standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
            if standings:
                st.session_state['p_liga_auto'] = sum(int(t['overall_league_GF']) for t in standings) / (sum(int(t['overall_league_payed']) for t in standings)/2)
                def buscar(n):
                    for t in standings: 
                        if n.lower() in t['team_name'].lower() or t['team_name'].lower() in n.lower(): return t
                    return None
                dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                if dl and dv:
                    st.session_state['lgf_auto'], st.session_state['lgc_auto'] = float(dl['overall_league_GF'])/int(dl['overall_league_payed']), float(dl['overall_league_GA'])/int(dl['overall_league_payed'])
                    st.session_state['vgf_auto'], st.session_state['vgc_auto'] = float(dv['overall_league_GF'])/int(dv['overall_league_payed']), float(dv['overall_league_GA'])/int(dv['overall_league_payed'])
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']

st.markdown("<h1 style='text-align: center; color: #00ffcc; font-size: 2.2em;'>OR936 ELITE CONTROL PANEL</h1>", unsafe_allow_html=True)

with st.container():
    c1, spacer, c2 = st.columns([1, 0.1, 1])
    with c1:
        st.markdown("<div class='input-card'>", unsafe_allow_html=True)
        nl = st.text_input("LOCAL", st.session_state.get('nl_auto', "Local"))
        la, lb = st.columns(2)
        lgf, lgc = la.number_input("Goles Favor L", 0.0, 10.0, st.session_state.get('lgf_auto', 1.5)), lb.number_input("Goles Contra L", 0.0, 10.0, st.session_state.get('lgc_auto', 1.0))
        ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.0), lb.number_input("Corners L", 0.0, 20.0, 5.0)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='input-card' style='border-top-color: #3498db;'>", unsafe_allow_html=True)
        nv = st.text_input("VISITANTE", st.session_state.get('nv_auto', "Visitante"))
        va, vb = st.columns(2)
        vgf, vgc = va.number_input("Goles Favor V", 0.0, 10.0, st.session_state.get('vgf_auto', 1.3)), vb.number_input("Goles Contra V", 0.0, 10.0, st.session_state.get('vgc_auto', 1.2))
        vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, 2.5), vb.number_input("Corners V", 0.0, 20.0, 4.5)
        st.markdown("</div>", unsafe_allow_html=True)

p_liga = st.slider("Media de Goles de la Liga", 0.5, 5.0, st.session_state.get('p_liga_auto', 2.5))

if st.button("🚀 EJECUTAR ANÁLISIS"):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "X", nv)
    
    t1, t2, t3, t4, t5 = st.tabs(["💎 VERDICTO", "🥅 GOLES", "🎴 TARJETAS", "🚩 CORNERS", "📊 MATRIZ"])
    
    with t1:
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.markdown("#### Top Sugerencias")
            pool = [{"t": "Doble Op. 1X", "p": res['DC'][0]}, {"t": "Doble Op. X2", "p": res['DC'][1]}, {"t": "Ambos Anotan", "p": res['BTTS'][0]}]
            for line, p in res['GOLES'].items():
                if 1.5 <= line <= 3.5: pool.append({"t": f"Over {line}", "p": p[0]})
            sug = sorted([s for s in pool if 65 < s['p'] < 95], key=lambda x: x['p'], reverse=True)[:4]
            for s in sug: st.success(f"✅ {s['t']} ({s['p']:.1f}%)")
        with col_v2:
            st.markdown("#### Marcadores Exactos")
            for i, (score, prob) in enumerate(res['TOP']):
                st.info(f"📍 {score} — Probabilidad: {prob:.1f}%")

    with t2:
        ga, gb = st.columns(2)
        with ga:
            st.write("##### Líneas de Goles (Over vs Under)")
            for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
                p = res['GOLES'][line]
                dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1])
        with gb:
            st.write("##### Ambos Anotan")
            dual_bar_explicit("BTTS SÍ", res['BTTS'][0], "BTTS NO", res['BTTS'][1], color_over="#f1c40f", color_under="#444")

    with t3:
        st.write("##### Mercado de Tarjetas (Over vs Under)")
        tj_a, tj_b = st.columns(2)
        for i, (line, p) in enumerate(res['TARJETAS'].items()):
            with (tj_a if i < 3 else tj_b):
                dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color_over="#e74c3c", color_under="#444")

    with t4:
        st.write("##### Mercado de Corners (Over vs Under)")
        co_a, co_b = st.columns(2)
        for i, (line, p) in enumerate(res['CORNERS'].items()):
            with (co_a if i < 3 else co_b):
                dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color_over="#2ecc71", color_under="#444")

    with t5:
        df_m = pd.DataFrame(res['MATRIZ'])
        fig = px.imshow(df_m, color_continuous_scale='Viridis', text_auto=".1f", labels=dict(x=f"Goles {nv}", y=f"Goles {nl}"))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8em; margin-top: 50px;'>OR936 ELITE v3.1 | Sistema de Análisis Bidimensional</p>", unsafe_allow_html=True)
