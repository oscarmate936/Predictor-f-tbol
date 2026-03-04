import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO (ORIGINAL - MANTENIDO INTACTO)
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
# INTERFAZ PROFESIONAL REDISEÑADA (OR936)
# =================================================================
st.set_page_config(page_title="OR936 Analysis System", layout="wide")

# CSS Personalizado de Alto Nivel para Tema Oscuro Profesional
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; }
    
    /* Título principal y subtítulo, sin superposiciones */
    .title-main { color: #ffffff; font-weight: 900; text-align: center; letter-spacing: -1px; margin-bottom: 5px; font-size: 2.5em; }
    .subtitle-main { color: #00ffcc; text-align: center; font-size: 1.1em; font-weight: bold; margin-bottom: 30px; }
    
    /* Contenedores de mercado con efecto 'Glassmorphism' */
    .market-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        color: white;
    }
    
    /* Barra de Configuración Limpia */
    .conf-header { color: #aaa; font-size: 0.85em; font-weight: bold; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; }
    .conf-header-icon { font-size: 1.1em; margin-right: 5px; color: #aaa; }

    .percentage-label { font-size: 0.8em; font-weight: 600; color: #aaa; margin-bottom: 2px; display: flex; justify-content: space-between; }
    .percentage-value { color: #00ffcc; font-weight: bold; font-size: 1.1em; }
    
    /* Estilo para las métricas */
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800 !important; color: #ffffff !important; }
    
    /* Botón Profesional con Degradado */
    .stButton>button {
        background: linear-gradient(90deg, #00ffcc 0%, #007bff 100%);
        color: #000 !important;
        font-weight: 800;
        border: none;
        border-radius: 10px;
        transition: 0.3s;
        height: 3.5em;
        width: 100%;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); }
    </style>
    """, unsafe_allow_html=True)

# Encabezado Limpio y Profesional
st.markdown("<h1 class='title-main'>ANÁLISIS DE POSIBLES RESULTADOS</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle-main'>(OR936) PROFESSIONAL ENGINE</p>", unsafe_allow_html=True)
st.write("---")

# CONFIGURACIÓN (Sección limpia en lugar de expander problemático)
with st.container():
    col_conf1, col_conf2 = st.columns([1, 1])
    with col_conf1:
        st.markdown("<div class='conf-header'><span class='conf-header-icon'>⚙️</span>Configuración General</div>", unsafe_allow_html=True)
        p_liga = st.number_input("Goles Promedio Liga", min_value=0.1, max_value=10.0, value=2.5, step=0.1, help="Total promedio de goles por partido en la liga actual.")
    with col_conf2:
        st.write("") # Spacer
        col_c1, col_cx, col_c2 = st.columns(3)
        o1 = col_c1.number_input("Cuota Local", min_value=1.01, value=2.10, step=0.01)
        ox = col_cx.number_input("Cuota Empate", min_value=1.01, value=3.20, step=0.01)
        o2 = col_c2.number_input("Cuota Visita", min_value=1.01, value=3.50, step=0.01)

st.write("---")

# ENTRADA DE DATOS DE EQUIPOS (En Columnas para Móvil)
st.subheader("🏟️ Datos del Encuentro")
col_l, col_v = st.columns(2)

with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Equipo L", "Local", label_visibility="collapsed")
    lgf = st.number_input("Goles a Favor L", min_value=0.0, value=1.70, step=0.1, key="lgf")
    lgc = st.number_input("Goles en Contra L", min_value=0.0, value=1.20, step=0.1, key="lgc")
    ltj = st.number_input("Tarjetas L", min_value=0.0, value=2.30, step=0.1, key="ltj")
    lco = st.number_input("Corners L", min_value=0.0, value=5.50, step=0.1, key="lco")

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Equipo V", "Visitante", label_visibility="collapsed")
    vgf = st.number_input("Goles a Favor V", min_value=0.0, value=1.50, step=0.1, key="vgf")
    vgc = st.number_input("Goles en Contra V", min_value=0.0, value=1.10, step=0.1, key="vgc")
    vtj = st.number_input("Tarjetas V", min_value=0.0, value=2.20, step=0.1, key="vtj")
    vco = st.number_input("Corners V", min_value=0.0, value=4.80, step=0.1, key="vco")

st.markdown("<br>", unsafe_allow_html=True)
analizar_btn = st.button("🚀 EJECUTAR ANÁLISIS DE POSIBLES RESULTADOS (OR936)", use_container_width=True)

if analizar_btn:
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    st.write("---")
    st.markdown("## 📊 Resultados del Análisis")

    # 1. Top 3 Marcadores Más Probables (Tarjetas de métrica)
    st.markdown("### ⚽ Marcadores Más Probables")
    cols_score = st.columns(3)
    for idx, (score, prob) in enumerate(res['TOP']):
        with cols_score[idx]:
            st.metric(label=f"Puesto {idx+1}", value=f"{score}", delta=f"{prob:.1f}% de prob.")

    st.write("---")

    # 2. Ganador del Partido (1X2) y Doble Oportunidad con BARRAS DE PROGRESO
    st.markdown("### 🏆 Ganador del Partido (1X2) y Valor")
    col_1x2_m, col_dc_m = st.columns([2, 1])

    with col_1x2_m:
        st.markdown("<div class='market-card'><b>Probabilidades y Value Check</b>", unsafe_allow_html=True)
        def val(p, o): return " (🔥 Value)" if (p/100*o) > 1.10 else ""
        
        c_l, c_x, c_v = st.columns(3)
        with c_l:
            st.markdown(f"<div class='percentage-label'><span>{nl}</span><span class='percentage-value'>{res['1X2'][0]:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(res['1X2'][0]/100)
            st.write(f"Value Check:{val(res['1X2'][0], o1)}")
        with c_x:
            st.markdown(f"<div class='percentage-label'><span>Empate</span><span class='percentage-value'>{res['1X2'][1]:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(res['1X2'][1]/100)
            st.write(f"Value Check:{val(res['1X2'][1], ox)}")
        with c_v:
            st.markdown(f"<div class='percentage-label'><span>{nv}</span><span class='percentage-value'>{res['1X2'][2]:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(res['1X2'][2]/100)
            st.write(f"Value Check:{val(res['1X2'][2], o2)}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_dc_m:
        st.markdown("<div class='market-card'><b>🎯 Doble Oportunidad</b>", unsafe_allow_html=True)
        markets_dc = [("1X", res['DC'][0]), ("X2", res['DC'][1]), ("12", res['DC'][2])]
        for label, val_p in markets_dc:
            st.markdown(f"<div class='percentage-label'><span>{label}</span><span class='percentage-value'>{val_p:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(val_p/100)
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("---")

    # 3. GOLES OVER/UNDER con BARRAS DUALES (Mostrando Porcentajes Numéricos exactos)
    st.markdown("### 🥅 Mercado de Goles (Over/Under)")
    
    for k, v in res['GOLES'].items():
        st.markdown(f"<div style='margin-bottom: 15px;'><b>Total Goles {k}</b>", unsafe_allow_html=True)
        c_o, c_u = st.columns(2)
        with c_o:
            st.markdown(f"<div class='percentage-label'><span>Over</span><span class='percentage-value'>{v[0]:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(v[0]/100)
        with c_u:
            st.markdown(f"<div class='percentage-label'><span>Under</span><span class='percentage-value'>{v[1]:.1f}%</span></div>", unsafe_allow_html=True)
            st.progress(v[1]/100)
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("---")

    # 4. Mercados Especiales: TARJETAS y CORNERS
    col_tj_d, col_co_d = st.columns(2)
    
    with col_tj_d:
        st.markdown("### 🎴 Mercado de Tarjetas")
        for k, v in res['TARJETAS'].items():
            st.markdown(f"<div style='margin-bottom: 15px;'><b>Línea {k}</b>", unsafe_allow_html=True)
            c_tj_o, c_tj_u = st.columns(2)
            with c_tj_o:
                st.markdown(f"<div class='percentage-label'><span>Over</span><span class='percentage-value'>{v[0]:.1f}%</span></div>", unsafe_allow_html=True)
                st.progress(v[0]/100)
            with c_tj_u:
                st.markdown(f"<div class='percentage-label'><span>Under</span><span class='percentage-value'>{v[1]:.1f}%</span></div>", unsafe_allow_html=True)
                st.progress(v[1]/100)
            st.markdown("</div>", unsafe_allow_html=True)

    with col_co_d:
        st.markdown("### 🚩 Mercado de Corners")
        for k, v in res['CORNERS'].items():
            st.markdown(f"<div style='margin-bottom: 15px;'><b>Línea {k}</b>", unsafe_allow_html=True)
            c_co_o, c_co_u = st.columns(2)
            with c_co_o:
                st.markdown(f"<div class='percentage-label'><span>Over</span><span class='percentage-value'>{v[0]:.1f}%</span></div>", unsafe_allow_html=True)
                st.progress(v[0]/100)
            with c_co_u:
                st.markdown(f"<div class='percentage-label'><span>Under</span><span class='percentage-value'>{v[1]:.1f}%</span></div>", unsafe_allow_html=True)
                st.progress(v[1]/100)
            st.markdown("</div>", unsafe_allow_html=True)
    
    st.write("---")
    # 5. BTTS
    col_btts_lbl_m, col_btts_p_m = st.columns([1, 2])
    with col_btts_lbl_m:
        st.markdown("### ⚽ Ambos Anotan")
    with col_btts_p_m:
        st.write(f"SÍ: **{res['BTTS'][0]:.1f}%**")
        st.progress(res['BTTS'][0]/100)
        st.write(f"NO: **{res['BTTS'][1]:.1f}%**")
        st.progress(res['BTTS'][1]/100)

# Pie de página Limpio
st.markdown("<p style='text-align: center; color: gray; font-size: 0.8em; margin-top: 50px;'>ProStats Engine OR936 v1.0 - Usar con responsabilidad. Datos meramente estadísticos.</p>", unsafe_allow_html=True)
