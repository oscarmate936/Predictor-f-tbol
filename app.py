import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO (Lógica Original Preservada)
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
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3] # Solo los 3 mejores
        }

# =================================================================
# DISEÑO VISUAL MEJORADO (CSS PROFESIONAL)
# =================================================================
st.set_page_config(page_title="Ultimate Predictor Pro", layout="wide")

st.markdown("""
    <style>
    /* Fondo de la aplicación */
    .stApp { background-color: #f0f2f6; }
    
    /* Estilo de las tarjetas de resultados */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Color de las barras de progreso */
    .stProgress > div > div > div > div { background-color: #2563eb; }
    
    /* Títulos con mejor contraste */
    h1, h2, h3 { color: #0f172a !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* Estilo para los bloques de entrada */
    .stNumberInput, .stTextInput { background-color: white; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Ultimate Stats Predictor Pro")
st.write("---")

# --- ENTRADA DE DATOS PRINCIPALES ---
with st.container():
    col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns(4)
    with col_cfg1: p_liga = st.number_input("Promedio Goles Liga", 2.5)
    with col_cfg2: o1 = st.number_input("Cuota Local", 1.0)
    with col_cfg3: ox = st.number_input("Cuota Empate", 1.0)
    with col_cfg4: o2 = st.number_input("Cuota Visita", 1.0)

st.write("")

col_l, col_v = st.columns(2)
with col_l:
    st.subheader("🏠 Datos Local")
    nl = st.text_input("Nombre Local", "LOCAL")
    lgf = st.number_input("Goles Favor (L)", 1.7)
    lgc = st.number_input("Goles Contra (L)", 1.2)
    ltj = st.number_input("Tarjetas (L)", 2.3)
    lco = st.number_input("Corners (L)", 5.5)

with col_v:
    st.subheader("🚀 Datos Visitante")
    nv = st.text_input("Nombre Visitante", "VISITANTE")
    vgf = st.number_input("Goles Favor (V)", 1.5)
    vgc = st.number_input("Goles Contra (V)", 1.1)
    vtj = st.number_input("Tarjetas (V)", 2.2)
    vco = st.number_input("Corners (V)", 4.8)

if st.button("🚀 GENERAR ANÁLISIS DETALLADO", use_container_width=True):
    motor = MotorMatematico()
    res = motor.procesar((lgf/p_liga)*(vgc/p_liga)*p_liga, (vgf/p_liga)*(lgc/p_liga)*p_liga, ltj+vtj, lco+vco)

    st.divider()

    # 1. TOP 3 MARCADORES (Diseño Limpio)
    st.subheader("🎯 Top 3 Marcadores Más Probables")
    m1, m2, m3 = st.columns(3)
    cols = [m1, m2, m3]
    for i, (score, prob) in enumerate(res['TOP']):
        cols[i].metric(f"Posición {i+1}", score, f"{prob:.1f}%")

    st.divider()

    # 2. MERCADOS CON BARRAS
    col_res1, col_res2 = st.columns(2)

    with col_res1:
        st.subheader("📊 Probabilidades 1X2")
        def draw_bar(label, p, odd=1.0):
            val_fire = " 🔥" if (p/100*odd) > 1.10 else ""
            st.write(f"{label}: **{p:.1f}%**{val_fire}")
            st.progress(p/100)
        
        draw_bar(f"Gana {nl}", res['1X2'][0], o1)
        draw_bar("Empate (X)", res['1X2'][1], ox)
        draw_bar(f"Gana {nv}", res['1X2'][2], o2)

        st.write("")
        st.subheader("🎯 Doble Oportunidad")
        draw_bar("1X (Local o Empate)", res['DC'][0])
        draw_bar("X2 (Visita o Empate)", res['DC'][1])
        draw_bar("12 (No Empate)", res['DC'][2])

    with col_res2:
        st.subheader("⚽ Ambos Anotan")
        draw_bar("SÍ Anotan", res['BTTS'][0])
        draw_bar("NO Anotan", res['BTTS'][1])

        st.write("")
        st.subheader("🥅 Líneas de Goles (Over)")
        for l, p in res['GOLES'].items():
            if l in [1.5, 2.5, 3.5]: # Mostramos las principales
                draw_bar(f"Más de {l}", p[0])

    st.divider()

    # 3. ESPECIALES (Tablas limpias)
    st.subheader("🎴 Especiales: Tarjetas y Corners")
    ct, cc = st.columns(2)
    
    with ct:
        st.info("**Probabilidades de Tarjetas**")
        st.table(pd.DataFrame([{"Línea": f"{l}", "Over %": f"{p[0]:.0f}%", "Under %": f"{p[1]:.0f}%"} for l, p in res['TARJETAS'].items()]))

    with cc:
        st.success("**Probabilidades de Corners**")
        st.table(pd.DataFrame([{"Línea": f"{l}", "Over %": f"{p[0]:.0f}%", "Under %": f"{p[1]:.0f}%"} for l, p in res['CORNERS'].items()]))



