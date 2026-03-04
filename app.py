import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO (SÍNTESIS PRO - DIXON COLES)
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
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), # SI y NO
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3] # Solo los 3 más probables
        }

# =================================================================
# INTERFAZ PROFESIONAL (UX/UI)
# =================================================================
st.set_page_config(page_title="Ultimate Stats Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stMetric { background-color: white; border-radius: 12px; border: 1px solid #e2e8f0; padding: 15px; }
    .stProgress > div > div > div > div { background-color: #2563eb; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚽ Ultimate Stats Predictor v6.0")

# --- SECCIÓN 1: CONFIGURACIÓN GLOBAL Y CUOTAS ---
with st.container():
    st.markdown("#### 🌍 Parámetros de Liga y Mercado")
    c_p1, c_p2, c_p3, c_p4 = st.columns(4)
    with c_p1: p_liga = st.number_input("Goles Prom. Liga", 2.5, help="Promedio de goles de la liga actual")
    with c_p2: o1 = st.number_input("Cuota Local (1)", 1.0, step=0.01)
    with c_p3: ox = st.number_input("Cuota Empate (X)", 1.0, step=0.01)
    with c_p4: o2 = st.number_input("Cuota Visita (2)", 1.0, step=0.01)

st.divider()

# --- SECCIÓN 2: ENTRADA DE EQUIPOS ---
col_l, col_v = st.columns(2)

with col_l:
    st.subheader("🏠 DATOS LOCAL")
    nl = st.text_input("Equipo Local", "LOCAL")
    lgf = st.number_input("Goles Favor (L)", 1.7)
    lgc = st.number_input("Goles Contra (L)", 1.2)
    ltj = st.number_input("Tarjetas Prom. (L)", 2.3)
    lco = st.number_input("Corners Prom. (L)", 5.5)

with col_v:
    st.subheader("🚀 DATOS VISITANTE")
    nv = st.text_input("Equipo Visitante", "VISITANTE")
    vgf = st.number_input("Goles Favor (V)", 1.5)
    vgc = st.number_input("Goles Contra (V)", 1.1)
    vtj = st.number_input("Tarjetas Prom. (V)", 2.2)
    vco = st.number_input("Corners Prom. (V)", 4.8)

if st.button("🚀 GENERAR ANÁLISIS COMPLETO", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga) * (vgc/p_liga) * p_liga
    xg_v = (vgf/p_liga) * (lgc/p_liga) * p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    # --- SECCIÓN 3: RESULTADOS ---
    st.divider()
    
    # Marcadores Exactos (TOP 3)
    st.markdown("### 🎯 Top 3 Marcadores Probables")
    cols_top = st.columns(3)
    for idx, (score, prob) in enumerate(res['TOP']):
        cols_top[idx].metric(f"Probabilidad #{idx+1}", score, f"{prob:.1f}%")

    st.write("")
    
    # Gráficos de Probabilidad con Barras
    col_res1, col_res2 = st.columns(2)

    with col_res1:
        st.markdown("#### 📊 Ganador del Partido (1X2)")
        def bar_prog(label, p, odd=1.0):
            value_check = " 🔥" if (p/100 * odd) > 1.10 else ""
            st.write(f"{label}: **{p:.1f}%**{value_check}")
            st.progress(p/100)
            
        bar_prog(f"Victoria {nl}", res['1X2'][0], o1)
        bar_prog("Empate (X)", res['1X2'][1], ox)
        bar_prog(f"Victoria {nv}", res['1X2'][2], o2)

        st.markdown("#### 🎯 Doble Oportunidad")
        bar_prog("1X (Local o Empate)", res['DC'][0])
        bar_prog("X2 (Visitante o Empate)", res['DC'][1])
        bar_prog("12 (No Empate)", res['DC'][2])

    with col_res2:
        st.markdown("#### ⚽ Ambos Equipos Anotan")
        bar_prog("Ambos Anotan: SÍ", res['BTTS'][0])
        bar_prog("Ambos Anotan: NO", res['BTTS'][1]) # Añadido mercado NO

        st.markdown("#### 🥅 Líneas de Goles (Over)")
        for line, p in res['GOLES'].items():
            if line in [1.5, 2.5, 3.5]: # Mostramos las líneas más comunes para no saturar
                st.write(f"Over {line}: **{p[0]:.1f}%**")
                st.progress(p[0]/100)

    st.divider()

    # Especiales con separación clara
    st.markdown("### 🎴 Especiales: Tarjetas y Corners")
    c_tj, c_co = st.columns(2)

    with c_tj:
        st.info("**Mercado de Tarjetas**")
        tj_data = [{"Línea": f"O/U {l}", "Over %": f"{p[0]:.0f}%", "Under %": f"{p[1]:.0f}%"} for l, p in res['TARJETAS'].items()]
        st.table(pd.DataFrame(tj_data))

    with c_co:
        st.success("**Mercado de Corners**")
        co_data = [{"Línea": f"O/U {l}", "Over %": f"{p[0]:.0f}%", "Under %": f"{p[1]:.0f}%"} for l, p in res['CORNERS'].items()]
        st.table(pd.DataFrame(co_data))
