import streamlit as st
import math
import pandas as pd
import plotly.express as px

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
# INTERFAZ PROFESIONAL REDISEÑADA (OR936 PRO)
# =================================================================
st.set_page_config(page_title="ProStats OR936 Engine", layout="wide", initial_sidebar_state="expanded")

# CSS Avanzado para Estilo "Fintech/Dark Mode"
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    
    .main { background-color: #0e1117; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(255,255,255,0.05);
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
        color: white;
    }
    .stTabs [aria-selected="true"] { background-color: #00ffcc !important; color: black !important; }
    
    .value-badge {
        background: linear-gradient(90deg, #00f260, #0575e6);
        color: white;
        padding: 2px 8px;
        border-radius: 5px;
        font-size: 0.7em;
        font-weight: bold;
        margin-left: 10px;
    }
    
    .card {
        background: #1a1c24;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #2d2e38;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# SIDEBAR: CONFIGURACIÓN
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3408/3408591.png", width=80)
    st.title("Configuración")
    p_liga = st.number_input("Goles Promedio Liga", 0.1, 10.0, 2.5, help="Promedio de la liga actual (ej. Premier 2.8, Serie A 2.6)")
    
    st.divider()
    st.subheader("Cuotas (Bookie)")
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)
    
    st.divider()
    st.caption("ProStats Engine v2.1 • Dixon-Coles Matrix Active")

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 PRO ANALYSIS</h1>", unsafe_allow_html=True)

# Entrada de Datos en un contenedor elegante
with st.container():
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏠 Local")
        nl = st.text_input("Nombre", "Local", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        lgf = c1.number_input("Goles Favor", 0.0, 10.0, 1.7, key="lgf", help="Goles anotados por el local en casa")
        lgc = c2.number_input("Goles Contra", 0.0, 10.0, 1.2, key="lgc")
        ltj = c1.number_input("Tarjetas Prom.", 0.0, 15.0, 2.3, key="ltj")
        lco = c2.number_input("Corners Prom.", 0.0, 20.0, 5.5, key="lco")

    with col2:
        st.markdown("### 🚀 Visitante")
        nv = st.text_input("Nombre ", "Visitante", label_visibility="collapsed")
        c3, c4 = st.columns(2)
        vgf = c3.number_input("Goles Favor ", 0.0, 10.0, 1.5, key="vgf")
        vgc = c4.number_input("Goles Contra ", 0.0, 10.0, 1.1, key="vgc")
        vtj = c3.number_input("Tarjetas Prom. ", 0.0, 15.0, 2.2, key="vtj")
        vco = c4.number_input("Corners Prom. ", 0.0, 20.0, 4.8, key="vco")

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 INICIAR PROCESAMIENTO ESTADÍSTICO", use_container_width=True):
    with st.spinner('Ejecutando simulación de Monte Carlo y Dixon-Coles...'):
        motor = MotorMatematico()
        xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
        xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
        res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
        
        # --- SECCIÓN DE RESULTADOS ---
        st.divider()
        
        # Pestañas para organizar mercados
        tab1, tab2, tab3, tab4 = st.tabs(["🏆 Principal (1X2)", "⚽ Goles (O/U)", "🚩 Especiales", "📊 Matriz"])

        with tab1:
            # Marcadores Top
            st.markdown("#### Marcadores más probables")
            m1, m2, m3 = st.columns(3)
            for i, (score, prob) in enumerate(res['TOP']):
                with [m1, m2, m3][i]:
                    st.metric(f"Top {i+1}", score, f"{prob:.1f}%")

            # 1X2 con Barras y Value
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            def check_val(p, o): return "<span class='value-badge'>🔥 VALUE</span>" if (p/100*o) > 1.10 else ""
            
            for label, prob, cuota, name in zip(["1", "X", "2"], res['1X2'], [o1, ox, o2], [nl, "Empate", nv]):
                col_n, col_p, col_b = st.columns([1, 4, 1])
                col_n.write(f"**{name}**")
                col_p.progress(prob/100)
                col_b.write(f"{prob:.1f}% {check_val(prob, cuota)}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("#### Over / Under Goles")
            col_g1, col_g2 = st.columns(2)
            for i, (line, probs) in enumerate(res['GOLES'].items()):
                target_col = col_g1 if i < 3 else col_g2
                with target_col:
                    st.write(f"**Línea {line}**")
                    st.write(f"Over: {probs[0]:.1f}% | Under: {probs[1]:.1f}%")
                    st.progress(probs[0]/100)

            st.divider()
            st.markdown(f"**Ambos Anotan (BTTS):** SÍ {res['BTTS'][0]:.1f}% | NO {res['BTTS'][1]:.1f}%")
            st.progress(res['BTTS'][0]/100)

        with tab3:
            st.markdown("#### Córners y Tarjetas")
            c_tj, c_co = st.columns(2)
            with c_tj:
                st.write("🎴 **Tarjetas**")
                for k, v in res['TARJETAS'].items():
                    st.write(f"Línea {k}: Over {v[0]:.1f}%")
                    st.progress(v[0]/100)
            with c_co:
                st.write("🚩 **Corners**")
                for k, v in res['CORNERS'].items():
                    st.write(f"Línea {k}: Over {v[0]:.1f}%")
                    st.progress(v[0]/100)

        with tab4:
            st.markdown("#### Matriz de Probabilidades (Heatmap)")
            # Generar heatmap con Plotly para hacerlo pro
            df_matriz = pd.DataFrame(res['MATRIZ'])
            fig = px.imshow(df_matriz, 
                            labels=dict(x=f"Goles {nv}", y=f"Goles {nl}", color="% Prob"),
                            x=[0,1,2,3,4,5], y=[0,1,2,3,4,5],
                            color_continuous_scale='Viridis',
                            text_auto=".1f")
            st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #555;'>ProStats OR936 v2.1 | © 2026 Professional Analysis System</p>", unsafe_allow_html=True)
