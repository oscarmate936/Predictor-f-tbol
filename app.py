import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO (MANTENIDO INTACTO)
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
# INTERFAZ WEB MINIMALISTA
# =================================================================
st.set_page_config(page_title="ProStats Mobile", layout="centered")

# Estilos CSS para mejorar la UI
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; background-color: #007bff; color: white; font-weight: bold; border: none; }
    .market-box { background-color: white; padding: 12px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #eee; }
    .score-badge { background-color: #1e1e1e; color: #00ffcc; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-family: monospace; }
    .percentage-text { font-size: 0.9em; color: #666; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #1e1e1e;'>🎯 Ultimate Predictor</h1>", unsafe_allow_html=True)
st.markdown("---")

# CONFIGURACIÓN INICIAL
with st.expander("⚙️ AJUSTES DE LIGA Y CUOTAS"):
    col_l1, col_l2 = st.columns([1, 1])
    p_liga = col_l1.number_input("Goles Promedio Liga", 2.5, step=0.1)
    
    st.write("**Cuotas Actuales (Value Check)**")
    c1, cx, c2 = st.columns(3)
    o1 = c1.number_input("Local", 1.0, value=2.10)
    ox = cx.number_input("Empate", 1.0, value=3.20)
    o2 = c2.number_input("Visita", 1.0, value=3.50)

# ENTRADA DE DATOS (2 COLUMNAS PARA MÓVIL)
col_team1, col_team2 = st.columns(2)

with col_team1:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Equipo L", "Local", label_visibility="collapsed")
    lgf = st.number_input("Goles Favor L", 1.7)
    lgc = st.number_input("Goles Contra L", 1.2)
    ltj = st.number_input("Tarjetas L", 2.3)
    lco = st.number_input("Corners L", 5.5)

with col_team2:
    st.markdown("### 🚀 Visita")
    nv = st.text_input("Equipo V", "Visita", label_visibility="collapsed")
    vgf = st.number_input("Goles Favor V", 1.5)
    vgc = st.number_input("Goles Contra V", 1.1)
    vtj = st.number_input("Tarjetas V", 2.2)
    vco = st.number_input("Corners V", 4.8)

st.markdown("---")

if st.button("🚀 REALIZAR ANÁLISIS"):
    motor = MotorMatematico()
    # Cálculo de xG Proyectado
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    # 1. TOP MARCADORES (NUEVO)
    st.markdown("### 📊 Top 3 Marcadores Probables")
    cols_score = st.columns(3)
    for idx, (score, prob) in enumerate(res['TOP']):
        with cols_score[idx]:
            st.markdown(f"""
            <div style="text-align: center;" class="market-box">
                <span class="score-badge">{score}</span><br>
                <span style="font-size: 1.1em; font-weight: bold;">{prob:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)

    # 2. SUGERENCIAS INTELIGENTES
    picks = []
    if res['DC'][0] > 78: picks.append(f"✅ 1X {nl}")
    if res['DC'][1] > 78: picks.append(f"✅ X2 {nv}")
    for l, p in res['GOLES'].items():
        if p[0] > 78: picks.append(f"⚽ Over {l}")
        if p[1] > 78: picks.append(f"🔒 Under {l}")
    
    if picks:
        st.info(f"💡 **Recomendaciones Pro:** {' | '.join(picks[:3])}")

    # 3. PROBABILIDADES PRINCIPALES (CON VALOR)
    st.markdown("### 🏆 Ganador del Partido (1X2)")
    m1, mx, m2 = st.columns(3)
    
    def get_value_tag(p, o):
        return " (Value 🔥)" if (p/100*o) > 1.10 else ""

    m1.metric(nl, f"{res['1X2'][0]:.1f}%", delta=get_value_tag(res['1X2'][0], o1), delta_color="normal")
    mx.metric("Empate", f"{res['1X2'][1]:.1f}%", delta=get_value_tag(res['1X2'][1], ox), delta_color="normal")
    m2.metric(nv, f"{res['1X2'][2]:.1f}%", delta=get_value_tag(res['1X2'][2], o2), delta_color="normal")

    # 4. MERCADOS SECUNDARIOS CON BARRAS
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**🎯 Doble Oportunidad**")
        st.write(f"1X: {res['DC'][0]:.1f}%")
        st.progress(res['DC'][0]/100)
        st.write(f"X2: {res['DC'][1]:.1f}%")
        st.progress(res['DC'][1]/100)
        
    with col_b:
        st.markdown("**⚽ Ambos Anotan (BTTS)**")
        st.write(f"SÍ: {res['BTTS'][0]:.1f}%")
        st.progress(res['BTTS'][0]/100)
        st.write(f"NO: {res['BTTS'][1]:.1f}%")
        st.progress(res['BTTS'][1]/100)

    # 5. GOLES / CORNERS / TARJETAS (MERCADOS ORDENADOS)
    st.markdown("---")
    tab_g, tab_c, tab_t = st.tabs(["🥅 GOLES", "🚩 CORNERS", "🎴 TARJETAS"])

    with tab_g:
        for k, v in res['GOLES'].items():
            col1, col2 = st.columns([1, 4])
            col1.markdown(f"**+{k}**")
            col2.progress(v[0]/100)

    with tab_c:
        for k, v in res['CORNERS'].items():
            col1, col2 = st.columns([1, 4])
            col1.markdown(f"**+{k}**")
            col2.progress(v[0]/100)

    with tab_t:
        for k, v in res['TARJETAS'].items():
            col1, col2 = st.columns([1, 4])
            col1.markdown(f"**+{k}**")
            col2.progress(v[0]/100)

st.markdown("<p style='text-align: center; color: gray; font-size: 0.8em;'>ProStats Engine v2.0 - Análisis basado en Distribución de Poisson</p>", unsafe_allow_html=True)
