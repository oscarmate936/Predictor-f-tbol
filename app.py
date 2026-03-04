import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO INTEGRAL (SÍNTESIS PRO - Dixon-Coles)
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
                if i <= 5 and j <= 5: marcadores[f"{i} - {j}"] = p * 100

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
# INTERFAZ DE USUARIO PROFESIONAL
# =================================================================
st.set_page_config(page_title="Ultimate Predictor Pro", layout="wide")

# Estilo para las barras y diseño
st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #1E3A8A; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Ultimate Stats Predictor Pro")
st.write("---")

# --- BLOQUE 1: INTRODUCCIÓN DE DATOS ---
with st.sidebar:
    st.header("⚙️ Configuración Global")
    prom_liga = st.number_input("Goles Promedio Liga", value=2.5, step=0.1)
    st.divider()
    st.header("💰 Cuotas de Mercado")
    c_o1 = st.number_input("Cuota Local", value=1.0)
    c_ox = st.number_input("Cuota Empate", value=1.0)
    c_o2 = st.number_input("Cuota Visita", value=1.0)

col_local, col_visit = st.columns(2)

with col_local:
    st.subheader("🏠 Datos Local")
    nl = st.text_input("Nombre del Equipo", "LOCAL")
    lgf = st.number_input("Goles Favor (L)", value=1.7)
    lgc = st.number_input("Goles Contra (L)", value=1.2)
    ltj = st.number_input("Tarjetas Promedio (L)", value=2.3)
    lco = st.number_input("Corners Promedio (L)", value=5.5)

with col_visit:
    st.subheader("🚀 Datos Visitante")
    nv = st.text_input("Nombre del Equipo", "VISITANTE")
    vgf = st.number_input("Goles Favor (V)", value=1.5)
    vgc = st.number_input("Goles Contra (V)", value=1.1)
    vtj = st.number_input("Tarjetas Promedio (V)", value=2.2)
    vco = st.number_input("Corners Promedio (V)", value=4.8)

# --- BLOQUE 2: PROCESAMIENTO ---
if st.button("🚀 GENERAR ANÁLISIS DETALLADO", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/prom_liga) * (vgc/prom_liga) * prom_liga
    xg_v = (vgf/prom_liga) * (lgc/prom_liga) * prom_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    # --- BLOQUE 3: RESULTADOS VISUALES ---
    st.divider()
    
    # Marcadores Exactos (TOP 5) - ¡Nuevo!
    st.subheader("🎯 Marcadores Exactos Más Probables")
    cols_top = st.columns(5)
    for idx, (score, prob) in enumerate(res['TOP']):
        cols_top[idx].metric(f"Top {idx+1}", score, f"{prob:.1f}%")

    st.divider()

    # 1X2 y Doble Oportunidad con Barras
    st.subheader("📊 Mercados Principales")
    c1, c2 = st.columns(2)

    with c1:
        st.write("**Ganador del Partido (1X2)**")
        # Función para dibujar barra
        def draw_bar(label, value, color="#1D4ED8"):
            st.write(f"{label}: {value:.1f}%")
            st.progress(value/100)

        draw_bar(f"Victoria {nl}", res['1X2'][0])
        draw_bar("Empate (X)", res['1X2'][1])
        draw_bar(f"Victoria {nv}", res['1X2'][2])

    with c2:
        st.write("**Doble Oportunidad**")
        draw_bar("1X (Local o Empate)", res['DC'][0])
        draw_bar("X2 (Visitante o Empate)", res['DC'][1])
        draw_bar("12 (Local o Visitante)", res['DC'][2])

    st.divider()

    # BTTS y Goles
    st.subheader("🥅 Mercado de Goles")
    col_btts, col_goles = st.columns([1, 2])
    
    with col_btts:
        st.write("**Ambos Anotan (BTTS)**")
        draw_bar("SÍ", res['BTTS'][0])
        draw_bar("NO", res['BTTS'][1])

    with col_goles:
        st.write("**Líneas Over / Under**")
        tabs_g = st.tabs([f"{l}" for l in res['GOLES'].keys()])
        for i, (line, p) in enumerate(res['GOLES'].items()):
            with tabs_g[i]:
                st.write(f"Probabilidades para {line} goles:")
                st.write(f"Over {line}: {p[0]:.1f}%")
                st.progress(p[0]/100)
                st.write(f"Under {line}: {p[1]:.1f}%")
                st.progress(p[1]/100)

    st.divider()

    # Especiales: Tarjetas y Corners
    st.subheader("🎴 Especiales (Totales)")
    col_t, col_c = st.columns(2)

    with col_t:
        st.markdown("##### Tarjetas")
        for l, p in res['TARJETAS'].items():
            with st.expander(f"Línea {l}"):
                st.write(f"Over: {p[0]:.1f}% | Under: {p[1]:.1f}%")
                st.progress(p[0]/100)

    with col_c:
        st.markdown("##### Corners")
        for l, p in res['CORNERS'].items():
            with st.expander(f"Línea {l}"):
                st.write(f"Over: {p[0]:.1f}% | Under: {p[1]:.1f}%")
                st.progress(p[0]/100)
