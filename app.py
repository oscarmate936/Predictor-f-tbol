import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analizador de Goles", layout="wide")

def calcular_analisis(l_home, l_away):
    # 1. Matriz de Probabilidades (Poisson)
    # Calculamos hasta 10 goles para asegurar precisión, aunque el top sea 0-5
    goles_rango = np.arange(0, 11)
    prob_h = poisson.pmf(goles_rango, l_home)
    prob_a = poisson.pmf(goles_rango, l_away)
    
    # Matriz de resultados exactos (Home x Away)
    matriz = np.outer(prob_h, prob_a)
    
    # 2. Top 3 Marcadores Exactos
    resultados = []
    # Solo revisamos de 0 a 5 goles para los marcadores más comunes
    for h in range(6):
        for a in range(6):
            prob = matriz[h, a] * 100
            resultados.append({"Marcador": f"{h} - {a}", "Probabilidad": prob})
    
    df_marcadores = pd.DataFrame(resultados)
    top_3 = df_marcadores.sort_values(by="Probabilidad", ascending=False).head(3)
    
    # 3. Mercado Over/Under Completo (0.5 a 5.5)
    l_total = l_home + l_away
    lineas = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
    data_goles = []
    
    for linea in lineas:
        # Under es la suma de probabilidades de goles <= linea
        # Ejemplo: Under 2.5 es P(0)+P(1)+P(2)
        prob_under = poisson.cdf(int(np.floor(linea)), l_total) * 100
        prob_over = 100 - prob_under
        data_goles.append({
            "Línea": f"{linea} Goles",
            "Over (%)": f"{prob_over:.2f}%",
            "Under (%)": f"{prob_under:.2f}%"
        })
    
    df_goles = pd.DataFrame(data_goles)
    
    # 4. Probabilidades 1X2
    p_home = np.sum(np.tril(matriz, -1)) * 100
    p_draw = np.sum(np.diag(matriz)) * 100
    p_away = np.sum(np.triu(matriz, 1)) * 100
    
    return top_3, df_goles, (p_home, p_draw, p_away)

# --- INTERFAZ ---
st.title("⚽ Predicciones de Fútbol")

col_in1, col_in2 = st.columns(2)
with col_in1:
    home_xg = st.number_input("Goles Esperados Local (xG)", min_value=0.0, value=1.5, step=0.1)
with col_in2:
    away_xg = st.number_input("Goles Esperados Visitante (xG)", min_value=0.0, value=1.0, step=0.1)

if st.button("Calcular Análisis"):
    top3, goles_completos, cuotas = calcular_analisis(home_xg, away_xg)
    
    st.markdown("---")
    
    # SECCIÓN: MARCADORES
    st.subheader("🎯 Los 3 Marcadores más Probables")
    # Mostramos como tabla para asegurar que SIEMPRE se vea
    st.table(top3.assign(Probabilidad=top3['Probabilidad'].map('{:.2f}%'.format)))
    
    st.markdown("---")
    
    # SECCIÓN: MERCADOS
    col_res1, col_res2 = st.columns(2)
    
    with col_res1:
        st.subheader("📊 Mercado de Goles (Completo)")
        st.table(goles_completos)
        
    with col_res2:
        st.subheader("🏆 Probabilidad 1X2")
        st.write(f"🏠 **Local:** {cuotas[0]:.2f}%")
        st.write(f"🤝 **Empate:** {cuotas[1]:.2f}%")
        st.write(f"🚀 **Visitante:** {cuotas[2]:.2f}%")
        
        # Ambos Anotan (Cálculo rápido)
        p_h0 = poisson.pmf(0, home_xg)
        p_a0 = poisson.pmf(0, away_xg)
        btts_no = (p_h0 + p_a0 - (p_h0 * p_a0)) * 100
        st.write(f"🥪 **Ambos Anotan (Sí):** {100 - btts_no:.2f}%")






