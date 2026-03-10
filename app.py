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
# COMPONENTES VISUALES (ESTILO ELITE)
# =================================================================
def triple_bar(p1, px, p2, n1, nx, n2):
    """Barra segmentada única para 1X2"""
    st.markdown(f"""
        <div style="margin-bottom: 25px; background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d;">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 10px; color: #eee;">
                <span>{n1}: <b>{p1:.1f}%</b></span>
                <span>{nx}: <b>{px:.1f}%</b></span>
                <span>{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 18px; border-radius: 9px; overflow: hidden; background: #333;">
                <div style="width: {p1}%; background: #00ffcc; box-shadow: 0 0 10px #00ffcc55;"></div>
                <div style="width: {px}%; background: #444;"></div>
                <div style="width: {p2}%; background: #3498db;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffcc"):
    """Barra comparativa para Doble Oportunidad, Goles, Tarjetas y Corners"""
    st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #eee; margin-bottom: 4px;">
                <span><b>{label_over}:</b> {prob_over:.1f}%</span>
                <span><b>{label_under}:</b> {prob_under:.1f}%</span>
            </div>
            <div style="display: flex; background: #222; height: 10px; border-radius: 5px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
                <div style="width: {prob_over}%; background: {color};"></div>
                <div style="width: {prob_under}%; background: rgba(255,255,255,0.05);"></div>
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
# INTERFAZ Y SIDEBAR
# =================================================================
st.set_page_config(page_title="OR936 Elite v3.2", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .master-card { background: #161b22; padding: 25px; border-radius: 15px; border: 1px solid #30363d; margin-bottom: 20px; }
    .verdict-item { border-left: 4px solid #00ffcc; background: rgba(255,255,255,0.03); padding: 10px; margin-bottom: 8px; border-radius: 0 8px 8px 0; }
    .score-badge { background: #1c2128; padding: 8px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 5px; text-align: center; }
    .stButton>button { background: linear-gradient(90deg, #00ffcc 0%, #008577 100%); color: black !important; font-weight: bold; border: none; padding: 12px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ PANEL CONTROL API")
    ligas_api = {
        "La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, 
        "UEFA Champions": 3, "Copa Libertadores": 13, "Brasileirão Serie A": 99, 
        "Liga Mayor SLV": 601, "Copa Presidente SLV": 603, "FA Cup": 145
    }
    nombre_liga = st.selectbox("Selecciona Liga", list(ligas_api.keys()))
    fecha_analisis = st.date_input("Fecha", datetime.now())
    
    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})
    if eventos and isinstance(eventos, list):
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("Partidos Detectados", list(op_p.keys()))
        if st.button("⚡ SINCRONIZAR DATOS"):
            standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
            if standings:
                # --- ACTUALIZACIÓN AUTOMÁTICA PROMEDIO GOLES LIGA ---
                total_g = sum(int(t['overall_league_GF']) for t in standings)
                total_pj = sum(int(t['overall_league_payed']) for t in standings)
                st.session_state['p_liga_auto'] = total_g / (total_pj / 2) if total_pj > 0 else 2.5
                
                def buscar(n):
                    for t in standings: 
                        if n.lower() in t['team_name'].lower() or t['team_name'].lower() in n.lower(): return t
                    return None
                dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                if dl and dv:
                    st.session_state['lgf_auto'], st.session_state['lgc_auto'] = float(dl['overall_league_GF'])/int(dl['overall_league_payed']), float(dl['overall_league_GA'])/int(dl['overall_league_payed'])
                    st.session_state['vgf_auto'], st.session_state['vgc_auto'] = float(dv['overall_league_GF'])/int(dv['overall_league_payed']), float(dv['overall_league_GA'])/int(dv['overall_league_payed'])
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 ELITE ANALYSIS v3.2</h1>", unsafe_allow_html=True)

# ENTRADA DE DATOS
col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Local", st.session_state.get('nl_auto', "Local"), label_visibility="collapsed")
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Favor L", 0.0, 10.0, st.session_state.get('lgf_auto', 1.7))
    lgc = c2.number_input("Contra L", 0.0, 10.0, st.session_state.get('lgc_auto', 1.2))
    ltj, lco = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3), c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Visitante", st.session_state.get('nv_auto', "Visitante"), label_visibility="collapsed")
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Favor V", 0.0, 10.0, st.session_state.get('vgf_auto', 1.5))
    vgc = c4.number_input("Contra V", 0.0, 10.0, st.session_state.get('vgc_auto', 1.1))
    vtj, vco = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2), c4.number_input("Corners V", 0.0, 20.0, 4.8)

# Promedio dinámico
p_liga = st.slider("Media Goles Liga (API Sync)", 0.5, 5.0, st.session_state.get('p_liga_auto', 2.5))

if st.button("🚀 PROCESAR ANÁLISIS ELITE", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # 1X2 BARRA ÚNICA
    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "X", nv)
    
    # --- SUGERENCIAS EXPANDIDAS (6 OPCIONES) ---
    pool = []
    pool.append({"t": "Doble Oportunidad 1X", "p": res['DC'][0]})
    pool.append({"t": "Doble Oportunidad X2", "p": res['DC'][1]})
    pool.append({"t": "Doble Oportunidad 12", "p": res['DC'][2]})
    pool.append({"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]})
    pool.append({"t": "Ambos Anotan: NO", "p": res['BTTS'][1]})
    for line, p in res['GOLES'].items():
        if 1.5 <= line <= 3.5:
            pool.append({"t": f"Over {line} Goles", "p": p[0]})
            pool.append({"t": f"Under {line} Goles", "p": p[1]})
    sug = sorted([s for s in pool if 65 < s['p'] < 96], key=lambda x: x['p'], reverse=True)[:6]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.2, 1])
    with v1:
        st.markdown("#### 💎 Top 6 Sugerencias Maestras")
        for s in sug: st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> | {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("#### ⚽ Marcadores")
        for i, (score, prob) in enumerate(res['TOP']):
            st.markdown(f'<div class="score-badge"><b>{score}</b> — {prob:.1f}%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- PESTAÑAS ---
    tab_dc, tab_g, tab_spec, tab_m = st.tabs(["🏆 Doble Oportunidad", "🥅 Goles / BTTS", "🚩 Especiales", "📊 Matriz"])
    
    with tab_dc:
        st.write("##### Mercados de Doble Oportunidad")
        dual_bar_explicit(f"1X (Local o Empate)", res['DC'][0], "2 (Visitante Directo)", 100-res['DC'][0], color="#9b59b6")
        dual_bar_explicit(f"X2 (Visitante o Empate)", res['DC'][1], "1 (Local Directo)", 100-res['DC'][1], color="#f39c12")
        dual_bar_explicit(f"12 (Local o Visitante)", res['DC'][2], "X (Empate Directo)", 100-res['DC'][2], color="#e74c3c")

    with tab_g:
        ga, gb = st.columns(2)
        with ga:
            st.write("##### Over/Under Goles")
            for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
                p = res['GOLES'][line]
                dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1])
        with gb:
            st.write("##### Ambos Anotan")
            dual_bar_explicit("BTTS SÍ", res['BTTS'][0], "BTTS NO", res['BTTS'][1], color="#f1c40f")

    with tab_spec:
        tj, co = st.columns(2)
        with tj:
            st.write("🎴 **Tarjetas**")
            for line, p in res['TARJETAS'].items(): dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color="#e74c3c")
        with co:
            st.write("🚩 **Corners**")
            for line, p in res['CORNERS'].items(): dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color="#2ecc71")

    with tab_m:
        st.plotly_chart(px.imshow(pd.DataFrame(res['MATRIZ']), color_continuous_scale='Viridis', text_auto=".1f"), use_container_width=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8em; margin-top: 30px;'>OR936 Elite v3.2 | Motor Auto-Sincronizado</p>", unsafe_allow_html=True)
