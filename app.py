import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO ORIGINAL (SÍNTESIS PRO)
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

        for i in range(12): 
            for j in range(12):
                p_base = self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)
                p = max(0, p_base * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                if i <= 5 and j <= 5: marcadores[f"{i}-{j}"] = p * 100

        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:5]
        }

# =================================================================
# INTERFAZ DE USUARIO ULTIMATE WEB v6.0
# =================================================================
st.set_page_config(page_title="Ultimate Stats Predictor", layout="wide", page_icon="⚽")

# Estilo personalizado para barras y diseño
st.markdown("""
    <style>
    .main { background-color: #f1f5f9; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; background-color: #0f172a; color: white; font-weight: bold; }
    .reportview-container .main .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 DASHBOARD DE ANÁLISIS PREDICTIVO")

# --- SECCIÓN 1: PARÁMETROS DE MERCADO ---
with st.container():
    st.subheader("⚙️ Configuración y Cuotas")
    c_cfg1, c_cfg2, c_cfg3, c_cfg4 = st.columns([1, 1, 1, 1])
    with c_cfg1:
        p_liga = st.number_input("Goles Prom. Liga", value=2.5, step=0.1)
    with c_cfg2:
        o1 = st.number_input("Cuota Local (1)", value=1.00, step=0.01)
    with c_cfg3:
        ox = st.number_input("Cuota Empate (X)", value=1.00, step=0.01)
    with c_cfg4:
        o2 = st.number_input("Cuota Visita (2)", value=1.00, step=0.01)

st.divider()

# --- SECCIÓN 2: ENTRADA DE DATOS DE EQUIPOS ---
col_l, col_v = st.columns(2)

with col_l:
    st.markdown("### 🏠 EQUIPO LOCAL")
    nl = st.text_input("Nombre", "LOCAL", key="nl")
    lgf = st.number_input("Goles Favor (L)", value=1.7, key="lgf")
    lgc = st.number_input("Goles Contra (L)", value=1.2, key="lgc")
    ltj = st.number_input("Tarjetas (L)", value=2.3, key="ltj")
    lco = st.number_input("Corners (L)", value=5.5, key="lco")

with col_v:
    st.markdown("### 🚀 EQUIPO VISITANTE")
    nv = st.text_input("Nombre", "VISITANTE", key="nv")
    vgf = st.number_input("Goles Favor (V)", value=1.5, key="vgf")
    vgc = st.number_input("Goles Contra (V)", value=1.1, key="vgc")
    vtj = st.number_input("Tarjetas (V)", value=2.2, key="vtj")
    vco = st.number_input("Corners (V)", value=4.8, key="vco")

st.write("")
if st.button("CALCULAR TODOS LOS MERCADOS"):
    motor = MotorMatematico()
    # xG dinámico
    xg_l = (lgf/p_liga) * (vgc/p_liga) * p_liga
    xg_v = (vgf/p_liga) * (lgc/p_liga) * p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    # --- MOSTRAR RESULTADOS ---
    st.divider()
    
    # 1. SUGERENCIAS (Alert box)
    picks = []
    if res['DC'][0] > 78: picks.append(f"1X {nl}")
    if res['DC'][1] > 78: picks.append(f"X2 {nv}")
    for l, p in res['GOLES'].items():
        if p[0] > 78: picks.append(f"Over {l}")
        if p[1] > 78: picks.append(f"Under {l}")
    
    if picks:
        st.warning(f"⚡ **SUGERENCIAS CLAVE (>78%):** {' | '.join(picks[:5])}")

    # 2. PROBABILIDADES PRINCIPALES (Con barras)
    st.header("📊 Probabilidades Principales")
    c1, c2 = st.columns(2)
    
    with c1:
        st.write(f"**Ganador 1X2**")
        def show_prob(label, p, odd=1.0):
            value_fire = " 🔥" if (p/100 * odd) > 1.10 else ""
            st.write(f"{label}: **{p:.1f}%**{value_fire}")
            st.progress(p/100)
            
        show_prob(f"Victoria {nl}", res['1X2'][0], o1)
        show_prob("Empate (X)", res['1X2'][1], ox)
        show_prob(f"Victoria {nv}", res['1X2'][2], o2)

    with c2:
        st.write(f"**Doble Oportunidad y BTTS**")
        show_prob("1X (Local o Empate)", res['DC'][0])
        show_prob("X2 (Visitante o Empate)", res['DC'][1])
        show_prob("12 (No Empate)", res['DC'][2])
        st.write("---")
        show_prob("Ambos Anotan (SÍ)", res['BTTS'][0])

    st.divider()

    # 3. TABLAS DE GOLES, TARJETAS Y CORNERS
    st.header("🥅 Mercados de Over / Under")
    tg1, tg2, tg3 = st.columns(3)

    with tg1:
        st.subheader("Goles")
        for l, p in res['GOLES'].items():
            st.write(f"Línea {l}")
            st.progress(p[0]/100)
            st.caption(f"Over: {p[0]:.1f}% | Under: {p[1]:.1f}%")

    with tg2:
        st.subheader("Tarjetas")
        for l, p in res['TARJETAS'].items():
            st.write(f"Línea {l}")
            st.progress(p[0]/100)
            st.caption(f"Over: {p[0]:.0f}% | Under: {p[1]:.0f}%")

    with tg3:
        st.subheader("Corners")
        for l, p in res['CORNERS'].items():
            st.write(f"Línea {l}")
            st.progress(p[0]/100)
            st.caption(f"Over: {p[0]:.0f}% | Under: {p[1]:.0f}%")

    st.divider()

    # 4. TOP MARCADORES (Sección especial)
    st.header("🎯 Marcadores Más Probables")
    cols_score = st.columns(5)
    for idx, (score, prob) in enumerate(res['TOP']):
        cols_score[idx].metric(f"Top {idx+1}", score, f"{prob:.1f}%")


