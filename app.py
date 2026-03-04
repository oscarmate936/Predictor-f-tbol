import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Predicciones de Fútbol Pro", layout="wide")

# --- LÓGICA MATEMÁTICA ---
def calcular_probabilidades(l_home, l_away):
    """Calcula todas las métricas basadas en Poisson."""
    
    # 1. Matriz de Resultados (para 1X2 y Marcadores)
    max_goles = 10
    prob_matrix = np.outer(poisson.pmf(range(max_goles), l_home), 
                           poisson.pmf(range(max_goles), l_away))
    
    prob_home = np.sum(np.tril(prob_matrix, -1))
    prob_draw = np.sum(np.diag(prob_matrix))
    prob_away = np.sum(np.triu(prob_matrix, 1))
    
    # 2. Ambos Anotan (BTTS)
    prob_home_0 = poisson.pmf(0, l_home)
    prob_away_0 = poisson.pmf(0, l_away)
    prob_btts_no = prob_home_0 + prob_away_0 - (prob_home_0 * prob_away_0)
    prob_btts_yes = 1 - prob_btts_no

    # 3. Top 3 Marcadores
    resultados = []
    for h in range(6):
        for a in range(6):
            resultados.append({
                'Marcador': f"{h} - {a}",
                'Probabilidad': prob_matrix[h, a] * 100
            })
    top_3 = pd.DataFrame(resultados).sort_values(by='Probabilidad', ascending=False).head(3)

    # 4. Mercado de Goles Completo (0.5 a 5.5)
    l_total = l_home + l_away
    lineas_goles = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
    mercado_goles = []
    for linea in lineas_goles:
        prob_under = poisson.cdf(int(linea), l_total)
        mercado_goles.append({
            'Línea': f"{linea} Goles",
            'Over (%)': round((1 - prob_under) * 100, 2),
            'Under (%)': round(prob_under * 100, 2)
        })

    return {
        "1X2": [prob_home, prob_draw, prob_away],
        "BTTS": [prob_btts_yes, prob_btts_no],
        "Top3": top_3,
        "Goles": pd.DataFrame(mercado_goles)
    }

# --- INTERFAZ DE USUARIO ---
st.title("⚽ Analizador de Partidos Poisson")
st.markdown("Introduce los goles esperados (xG) para obtener el análisis completo.")

with st.sidebar:
    st.header("Entrada de Datos")
    xg_home = st.number_input("xG Local", min_value=0.0, value=1.5, step=0.1)
    xg_away = st.number_input("xG Visitante", min_value=0.0, value=1.2, step=0.1)
    
    st.divider()
    st.info("Este modelo utiliza la distribución de Poisson para proyectar resultados.")

if xg_home or xg_away:
    res = calcular_probabilidades(xg_home, xg_away)

    # SECCIÓN 1: MARCADORES PROBABLES (CORRECCIÓN DE VISIBILIDAD)
    st.subheader("🎯 Top 3 Marcadores más Probables")
    m_cols = st.columns(3)
    for i, (idx, row) in enumerate(res["Top3"].iterrows()):
        with m_cols[i]:
            st.metric(label=f"Opción {i+1}", value=row['Marcador'], delta=f"{row['Probabilidad']:.2f}%")

    st.divider()

    # SECCIÓN 2: MERCADOS PRINCIPALES
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Mercado de Goles (Over/Under)")
        st.table(res["Goles"])

    with col2:
        st.subheader("🏆 Probabilidades 1X2")
        p1, px, p2 = res["1X2"]
        st.write(f"**Local (1):** {p1*100:.2f}%")
        st.write(f"**Empate (X):** {px*100:.2f}%")
        st.write(f"**Visitante (2):** {p2*100:.2f}%")
        
        st.subheader("🥪 Ambos Anotan (BTTS)")
        st.write(f"**Sí:** {res['BTTS'][0]*100:.2f}%")
        st.write(f"**No:** {res['BTTS'][1]*100:.2f}%")

# --- NOTA TÉCNICA ---
with st.expander("Ver detalle matemático"):
    st.write("""
    La probabilidad de que un equipo anote exactamente $k$ goles se calcula mediante:
    """)
    st.latex(r"P(X=k) = \frac{\lambda^k e^{-\lambda}}{k!}")
    st.write("Donde $\lambda$ es el promedio de goles esperados.")





