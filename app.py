import streamlit as st
import math
import pandas as pd
import plotly.express as px

# =================================================================
# MOTOR MATEMÁTICO (OPTIMIZADO)
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
        matriz_calor = []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}

        for i in range(10): 
            fila = []
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
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz_calor.append(fila)

        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3],
            "MATRIZ": matriz_calor
        }

# =================================================================
# INTERFAZ PROFESIONAL REDISEÑADA
# =================================================================
st.set_page_config(page_title="ProStats OR936 Engine", layout="wide")

st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    .card { background: #1a1c24; padding: 20px; border-radius: 15px; border: 1px solid #2d2e38; margin-bottom: 20px; }
    .value-badge { background: linear-gradient(90deg, #00f260, #0575e6); color: white; padding: 2px 8px; border-radius: 5px; font-size: 0.75em; font-weight: bold; }
    .stat-label { font-size: 0.9em; color: #aaa; }
    .stat-value { font-weight: bold; color: #fff; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚽ Panel de Control")
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, 2.5)
    st.divider()
    st.subheader("Cuotas del Mercado")
    o1 = st.number_input("Cuota Local (1)", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate (X)", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita (2)", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>ANÁLISIS DE POSIBLES RESULTADOS (OR936)</h1>", unsafe_allow_html=True)

# ENTRADA DE DATOS
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Equipo Local", "Local")
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Goles Favor (Local)", 0.0, 10.0, 1.7)
    lgc = c2.number_input("Goles Contra (Local)", 0.0, 10.0, 1.2)
    ltj = c1.number_input("Media Tarjetas (L)", 0.0, 15.0, 2.3)
    lco = c2.number_input("Media Corners (L)", 0.0, 20.0, 5.5)

with col_b:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Equipo Visitante", "Visitante")
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles Favor (Visita)", 0.0, 10.0, 1.5)
    vgc = c4.number_input("Goles Contra (Visita)", 0.0, 10.0, 1.1)
    vtj = c3.number_input("Media Tarjetas (V)", 0.0, 15.0, 2.2)
    vco = c4.number_input("Media Corners (V)", 0.0, 20.0, 4.8)

if st.button("🚀 EJECUTAR ANÁLISIS PROFESIONAL", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🏆 Resultados 1X2 & DC", "🥅 Goles Over/Under", "🚩 Tarjetas y Córners", "📊 Matriz de Probabilidad"])

    with tab1:
        st.markdown("#### Marcadores Exactos Más Probables")
        m1, m2, m3 = st.columns(3)
        for i, (score, prob) in enumerate(res['TOP']):
            with [m1, m2, m3][i]:
                st.metric(f"Probabilidad #{i+1}", score, f"{prob:.1f}%")

        st.divider()
        col_1x2, col_dc = st.columns(2)
        
        with col_1x2:
            st.markdown("##### Mercado 1X2")
            def get_val(p, o): return " <span class='value-badge'>VALUE</span>" if (p/100*o) > 1.10 else ""
            st.write(f"**{nl} (1):** {res['1X2'][0]:.1f}% {get_val(res['1X2'][0], o1)}", unsafe_allow_html=True)
            st.progress(res['1X2'][0]/100)
            st.write(f"**Empate (X):** {res['1X2'][1]:.1f}% {get_val(res['1X2'][1], ox)}", unsafe_allow_html=True)
            st.progress(res['1X2'][1]/100)
            st.write(f"**{nv} (2):** {res['1X2'][2]:.1f}% {get_val(res['1X2'][2], o2)}", unsafe_allow_html=True)
            st.progress(res['1X2'][2]/100)

        with col_dc:
            st.markdown("##### Doble Oportunidad")
            st.write(f"**1X (Local o Empate):** {res['DC'][0]:.1f}%")
            st.progress(res['DC'][0]/100)
            st.write(f"**X2 (Visitante o Empate):** {res['DC'][1]:.1f}%")
            st.progress(res['DC'][1]/100)
            st.write(f"**12 (Cualquiera gana):** {res['DC'][2]:.1f}%")
            st.progress(res['DC'][2]/100)

    with tab2:
        st.markdown("#### Goles Totales (Over / Under)")
        g1, g2 = st.columns(2)
        for i, (line, probs) in enumerate(res['GOLES'].items()):
            with (g1 if i < 3 else g2):
                st.write(f"**Línea {line}**")
                st.write(f"O {line}: {probs[0]:.1f}% | U {line}: {probs[1]:.1f}%")
                st.progress(probs[0]/100)
        st.divider()
        st.markdown(f"**Ambos Anotan (BTTS):** SÍ {res['BTTS'][0]:.1f}% | NO {res['BTTS'][1]:.1f}%")

    with tab3:
        st.markdown("#### Mercados Especiales (Over y Under)")
        tj, co = st.columns(2)
        with tj:
            st.markdown("##### 🎴 Tarjetas Totales")
            for k, v in res['TARJETAS'].items():
                st.markdown(f"**Línea {k}**")
                st.write(f"Over: {v[0]:.1f}% | <span style='color:#ff4b4b'>Under: {v[1]:.1f}%</span>", unsafe_allow_html=True)
                st.progress(v[0]/100)
        with co:
            st.markdown("##### 🚩 Córners Totales")
            for k, v in res['CORNERS'].items():
                st.markdown(f"**Línea {k}**")
                st.write(f"Over: {v[0]:.1f}% | <span style='color:#ff4b4b'>Under: {v[1]:.1f}%</span>", unsafe_allow_html=True)
                st.progress(v[0]/100)

    with tab4:
        st.markdown("#### Matriz de Probabilidades (Mapa de Calor)")
        df_matriz = pd.DataFrame(res['MATRIZ'], 
                                 index=[f"{i} Goles {nl}" for i in range(6)],
                                 columns=[f"{j} Goles {nv}" for j in range(6)])
        
        fig = px.imshow(df_matriz,
                        labels=dict(x="Goles Visitante", y="Goles Local", color="% Prob"),
                        color_continuous_scale='Viridis',
                        text_auto=".1f",
                        aspect="auto")
        
        fig.update_layout(title_text='Distribución de Probabilidad de Marcadores', title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: gray; font-size: 0.8em;'>ProStats OR936 v2.2 - Datos estadísticos basados en Dixon-Coles</p>", unsafe_allow_html=True)
