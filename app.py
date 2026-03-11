import streamlit as st
import math
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN Y ESTILO CSS PREMIUM
# =================================================================
st.set_page_config(page_title="OR936 Elite v3.2", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
        
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #e1e1e1; }
        .stApp { background-color: #0b0e11; }
        
        /* Contenedores Tipo Card */
        .premium-card {
            background: #161b22;
            border-radius: 20px;
            padding: 20px;
            border: 1px solid #30363d;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
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

        /* Marcador y Equipos */
        .match-header {
            text-align: center;
            padding: 30px 0;
            background: linear-gradient(180deg, #161b22 0%, #0b0e11 100%);
            border-radius: 0 0 30px 30px;
            margin-bottom: 25px;
            border-bottom: 1px solid #30363d;
        }

        /* Barras de comparación dual */
        .stat-container { margin-bottom: 18px; }
        .stat-info { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.9rem; font-weight: 600; }
        .stat-bar-bg { height: 8px; background: #30363d; border-radius: 10px; display: flex; overflow: hidden; }
        .bar-l { background: #00ffcc; box-shadow: 0 0 10px rgba(0,255,204,0.3); }
        .bar-v { background: #3498db; }

        /* Sugerencias Maestras */
        .suggestion-item {
            background: rgba(0, 255, 204, 0.05);
            border-left: 3px solid #00ffcc;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 0 10px 10px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Estilo para los botones */
        .stButton>button {
            background: linear-gradient(90deg, #00ffcc 0%, #008577 100%);
            color: #000 !important;
            font-weight: 800;
            border-radius: 12px;
            border: none;
            padding: 15px;
            transition: all 0.3s;
        }
        .stButton>button:hover { transform: scale(1.02); box-shadow: 0 0 20px rgba(0,255,204,0.4); }

        /* Tabs personalizadas */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
        .stTabs [data-baseweb="tab"] {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 8px 16px;
            color: #8b949e;
        }
        .stTabs [aria-selected="true"] { background-color: #00ffcc !important; color: #000 !important; }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# =================================================================
# COMPONENTES VISUALES PERSONALIZADOS
# =================================================================
def render_dual_bar(label, p_l, p_v, color_l="#00ffcc", color_v="#3498db"):
    total = p_l + p_v if (p_l + p_v) > 0 else 1
    w_l = (p_l / total) * 100
    st.markdown(f"""
        <div class="stat-container">
            <div class="stat-info">
                <span>{p_l:.1f}%</span>
                <span style="color:#8b949e; font-size:0.75rem;">{label.upper()}</span>
                <span>{p_v:.1f}%</span>
            </div>
            <div class="stat-bar-bg">
                <div style="width: {w_l}%;" class="bar-l"></div>
                <div style="width: {100-w_l}%;" class="bar-v"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_triple_bar(p1, px, p2, n1, nv):
    st.markdown(f"""
        <div class="premium-card">
            <span class="section-title">Probabilidades Directas (1X2)</span>
            <div style="display:flex; justify-content: space-between; margin-bottom:10px; font-weight:bold;">
                <span style="color:#00ffcc;">{n1}: {p1:.1f}%</span>
                <span style="color:#8b949e;">Empate: {px:.1f}%</span>
                <span style="color:#3498db;">{nv}: {p2:.1f}%</span>
            </div>
            <div class="stat-bar-bg" style="height:12px;">
                <div style="width: {p1}%; background:#00ffcc;"></div>
                <div style="width: {px}%; background:#444;"></div>
                <div style="width: {p2}%; background:#3498db;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# MOTOR MATEMÁTICO (SIN CAMBIOS)
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

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except: return []

# =================================================================
# SIDEBAR (CONTROL)
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#00ffcc;'>Configuración</h2>", unsafe_allow_html=True)
    ligas_api = {"La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, "Champions": 3}
    nombre_liga = st.selectbox("Liga", list(ligas_api.keys()))
    fecha_analisis = st.date_input("Fecha del Partido", datetime.now())
    
    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})
    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("Seleccionar Partido", list(op_p.keys()))
        if st.button("⚡ SINCRONIZAR DATOS"):
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
# INTERFAZ PRINCIPAL
# =================================================================
nl = st.session_state.get('nl_auto', "Local")
nv = st.session_state.get('nv_auto', "Visitante")

st.markdown(f"""
    <div class="match-header">
        <span style="color:#8b949e; font-size:0.8rem; font-weight:700; text-transform:uppercase;">{nombre_liga}</span>
        <div style="display:flex; justify-content:center; align-items:center; gap:40px; margin-top:15px;">
            <div style="text-align:right; width:200px;">
                <h2 style="margin:0; font-weight:800; color:#00ffcc;">{nl}</h2>
            </div>
            <div style="background:#1c2127; padding:10px 20px; border-radius:15px; border:1px solid #30363d;">
                <h1 style="margin:0; letter-spacing:5px; color:#ffffff;">VS</h1>
            </div>
            <div style="text-align:left; width:200px;">
                <h2 style="margin:0; font-weight:800; color:#3498db;">{nv}</h2>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Inputs de Ajuste Fino (Regreso al diseño original dentro de expander)
with st.expander("🛠️ Ajuste Manual de Datos"):
    c1, c2, c3 = st.columns(3)
    lgf = c1.number_input("Promedio Goles Local (Favor)", 0.0, 5.0, st.session_state.get('lgf_auto', 1.5))
    lgc = c1.number_input("Promedio Goles Local (Contra)", 0.0, 5.0, st.session_state.get('lgc_auto', 1.2))
    vgf = c2.number_input("Promedio Goles Visitante (Favor)", 0.0, 5.0, st.session_state.get('vgf_auto', 1.3))
    vgc = c2.number_input("Promedio Goles Visitante (Contra)", 0.0, 5.0, st.session_state.get('vgc_auto', 1.4))
    ltj = c3.number_input("Línea de Tarjetas Total", 0.0, 10.0, 4.5)
    lco = c3.number_input("Línea de Córners Total", 0.0, 15.0, 9.5)
    p_liga = st.slider("Media de Goles de la Liga", 0.5, 4.0, st.session_state['p_liga_auto'])

if st.button("🔥 EJECUTAR ANÁLISIS IA ELITE", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj, lco)
    
    # --- COLUMNAS DE RESULTADOS ---
    col_main, col_side = st.columns([1.5, 1])
    
    with col_main:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<span class="section-title">💎 Recomendaciones Maetras</span>', unsafe_allow_html=True)
        
        pool = []
        pool.append({"t": "Doble Oportunidad 1X", "p": res['DC'][0]})
        pool.append({"t": "Doble Oportunidad X2", "p": res['DC'][1]})
        pool.append({"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]})
        for line, p in res['GOLES'].items():
            if 1.5 <= line <= 3.5:
                pool.append({"t": f"Más de {line} Goles", "p": p[0]})
                pool.append({"t": f"Menos de {line} Goles", "p": p[1]})
        
        sugerencias = sorted([s for s in pool if 68 < s['p'] < 96], key=lambda x: x['p'], reverse=True)[:5]
        for s in sugerencias:
            st.markdown(f"""
                <div class="suggestion-item">
                    <span>{s['t']}</span>
                    <span style="font-weight:800; color:#00ffcc;">{s['p']:.1f}%</span>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        render_triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, nv)

    with col_side:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<span class="section-title">🎯 Marcador Exacto</span>', unsafe_allow_html=True)
        for score, prob in res['TOP']:
            st.markdown(f"""
                <div style="display:flex; justify-content:space-between; padding:15px; background:#1c2127; border-radius:12px; margin-bottom:10px; border: 1px solid #30363d;">
                    <span style="font-size:1.2rem; font-weight:800; color:#00ffcc;">{score}</span>
                    <span style="color:#8b949e;">{prob:.1f}%</span>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- PESTAÑAS DETALLADAS ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Mercados Principales", "⚽ Goles (Rango Completo)", "🚩 Córners y Tarjetas", "📈 Matriz"])
    
    with tab1:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        render_dual_bar("Doble Oportunidad 1X", res['DC'][0], 100-res['DC'][0])
        render_dual_bar("Doble Oportunidad X2", res['DC'][1], 100-res['DC'][1])
        render_dual_bar("Doble Oportunidad 12", res['DC'][2], 100-res['DC'][2], color_l="#e74c3c")
        render_dual_bar("Ambos Anotan (BTTS)", res['BTTS'][0], res['BTTS'][1], color_l="#f1c40f")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            p = res['GOLES'][line]
            render_dual_bar(f"Más/Menos {line} Goles", p[0], p[1])
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<span class="section-title">Probabilidades Córners</span>', unsafe_allow_html=True)
            for line, p in res['CORNERS'].items():
                render_dual_bar(f"Más de {line}", p[0], p[1], color_l="#2ecc71")
            st.markdown('</div>', unsafe_allow_html=True)
        with c_b:
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<span class="section-title">Probabilidades Tarjetas</span>', unsafe_allow_html=True)
            for line, p in res['TARJETAS'].items():
                render_dual_bar(f"Más de {line}", p[0], p[1], color_l="#e74c3c")
            st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        fig = px.imshow(pd.DataFrame(res['MATRIZ']), text_auto=".1f", color_continuous_scale='Viridis',
                        labels=dict(x="Visitante", y="Local", color="%"))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<p style='text-align:center; color:#555; font-size:0.7rem; margin-top:50px;'>Motor OR936 Elite v3.2 | Diseñado para Análisis de Alto Rendimiento</p>", unsafe_allow_html=True)
