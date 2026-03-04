import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO (ORIGINAL - SIN CAMBIOS)
# =================================================================
class MotorMatematico:
    def __init__(self):
        self.rho = -0.15

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
        marcadores = {}
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}

        for i in range(10): 
            for j in range(10):
                p_base = self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)
                p = max(0, p_base * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100

        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3]
        }

# =================================================================
# INTERFAZ PROFESIONAL (OR936 CUSTOM UI)
# =================================================================
st.set_page_config(page_title="OR936 Analysis", layout="centered")

# CSS Personalizado de Alto Nivel
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    
    .main { background-color: #0e1117; }
    
    /* Título principal */
    .title-main { color: #ffffff; font-weight: 900; text-align: center; letter-spacing: -1px; margin-bottom: 5px; }
    .subtitle-main { color: #00ffcc; text-align: center; font-size: 0.8em; font-weight: bold; margin-bottom: 30px; }
    
    /* Contenedores de mercado */
    .market-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
    }
    
    .score-box {
        background: #1e1e1e;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        border: 1px solid #00ffcc;
    }

    .percentage-label { font-size: 0.8em; font-weight: 600; color: #aaa; margin-bottom: 2px; display: flex; justify-content: space-between; }
    .percentage-value { color: #00ffcc; font-weight: bold; }
    
    /* Estilo para las métricas */
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800 !important; color: #ffffff !important; }
    
    /* Botón */
    .stButton>button {
        background: linear-gradient(90deg, #00ffcc 0%, #007bff 100%);
        color: #000 !important;
        font-weight: 800;
        border: none;
        border-radius: 10px;
        transition: 0.3s;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='title-main'>ANÁLISIS DE POSIBLES RESULTADOS</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle-main'>(OR936) PROFESSIONAL ENGINE</p>", unsafe_allow_html=True)

# CONFIGURACIÓN
with st.expander("⚙️ CONFIGURACIÓN DE LIGA Y CUOTAS", expanded=False):
    c_p1, c_p2 = st.columns(2)
    p_liga = c_p1.number_input("Goles Promedio Liga", 2.5, step=0.1)
    st.divider()
    c1, cx, c2 = st.columns(3)
    o1 = c1.number_input("Cuota Local", 1.0, value=2.0)
    ox = cx.number_input("Cuota Empate", 1.0, value=3.4)
    o2 = c2.number_input("Cuota Visita", 1.0, value=3.8)

# INPUTS DE EQUIPOS
col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Nombre L", "LOCAL", label_visibility="collapsed")
    lgf = st.number_input("Goles Favor L", 1.7)
    lgc = st.number_input("Goles Contra L", 1.2)
    ltj = st.number_input("Tarjetas L", 2.3)
    lco = st.number_input("Corners L", 5.5)

with col_v:
    st.markdown("### 🚀 Visita")
    nv = st.text_input("Nombre V", "VISITANTE", label_visibility="collapsed")
    vgf = st.number_input("Goles Favor V", 1.5)
    vgc = st.number_input("Goles Contra V", 1.1)
    vtj = st.number_input("Tarjetas V", 2.2)
    vco = st.number_input("Corners V", 4.8)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("EJECUTAR ANÁLISIS PREDICTIVO"):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    # 1. TOP MARCADORES
    st.markdown("#### ⚽ Marcadores más probables")
    cols_score = st.columns(3)
    for idx, (score, prob) in enumerate(res['TOP']):
        with cols_score[idx]:
            st.markdown(f"""
            <div class="score-box">
                <div style="font-size: 1.2em; font-weight: 900; color: #00ffcc;">{score}</div>
                <div style="font-size: 0.8em; color: white;">{prob:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 2. PROBABILIDADES 1X2 CON VALUE
    st.markdown("<br>#### 🏆 Mercado Ganador (1X2)", unsafe_allow_html=True)
    m1, mx, m2 = st.columns(3)
    def val(p, o): return "🔥 VALUE" if (p/100*o) > 1.10 else ""
    m1.metric(nl, f"{res['1X2'][0]:.1f}%", delta=val(res['1X2'][0], o1), delta_color="normal")
    mx.metric("Empate", f"{res['1X2'][1]:.1f}%", delta=val(res['1X2'][1], ox), delta_color="normal")
    m2.metric(nv, f"{res['1X2'][2]:.1f}%", delta=val(res['1X2'][2], o2), delta_color="normal")

    # 3. DOBLE OPORTUNIDAD Y BTTS
    col_dc, col_btts = st.columns(2)
    with col_dc:
        st.markdown("<div class='market-card'><b>🎯 Doble Oportunidad</b>", unsafe_allow_html=True)
        markets_dc = [("1X", res['DC'][0]), ("X2", res['DC'][1]), ("12", res['DC'][2])]
        for label, val_p in markets_dc:
            st.markdown(f"<div class='percentage-label'><span>{label}</span><span class='percentage-value'>{val_p:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(val_p/100)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_btts:
        st.markdown("<div class='market-card'><b>⚽ Ambos Anotan</b>", unsafe_allow_html=True)
        st.markdown(f"<div class='percentage-label'><span>SÍ</span><span class='percentage-value'>{res['BTTS'][0]:.1f}%</span></div>", unsafe_allow_html=True)
        st.progress(res['BTTS'][0]/100)
        st.markdown(f"<div class='percentage-label'><span>NO</span><span class='percentage-value'>{res['BTTS'][1]:.1f}%</span></div>", unsafe_allow_html=True)
        st.progress(res['BTTS'][1]/100)
        st.markdown("</div>", unsafe_allow_html=True)

    # 4. TABS PARA MERCADOS ESPECIALES
    st.markdown("#### 📊 Mercados Over / Under")
    tab_g, tab_c, tab_t = st.tabs(["🥅 GOLES", "🚩 CORNERS", "🎴 TARJETAS"])

    def draw_bar_group(data, title):
        for k, v in data.items():
            st.markdown(f"<div style='margin-bottom: 15px;'><b>{title} {k}</b>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<div class='percentage-label'><span>Over</span><span class='percentage-value'>{v[0]:.1f}%</span></div>", unsafe_allow_html=True)
                st.progress(v[0]/100)
            with c2:
                st.markdown(f"<div class='percentage-label'><span>Under</span><span class='percentage-value'>{v[1]:.1f}%</span></div>", unsafe_allow_html=True)
                st.progress(v[1]/100)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_g: draw_bar_group(res['GOLES'], "Total Goles")
    with tab_c: draw_bar_group(res['CORNERS'], "Total Corners")
    with tab_t: draw_bar_group(res['TARJETAS'], "Total Tarjetas")

st.markdown("<p style='text-align: center; color: #555; font-size: 0.7em; margin-top: 50px;'>OR936 ANALYTICS SYSTEM - POWERED BY POISSON ENGINE</p>", unsafe_allow_html=True)
