import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse

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
# INTERFAZ PROFESIONAL (PRO VERDICT EDITION)
# =================================================================
st.set_page_config(page_title="OR936 Analysis System", layout="wide")

st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    .card { background: #1a1c24; padding: 25px; border-radius: 15px; border: 1px solid #2d2e38; margin-bottom: 20px; }
    .verdict-card { 
        background: linear-gradient(135deg, rgba(0,255,204,0.1) 0%, rgba(0,123,255,0.1) 100%); 
        border: 1px solid #00ffcc; padding: 15px; border-radius: 12px; text-align: center;
        box-shadow: 0 4px 15px rgba(0,255,204,0.1);
    }
    .value-badge { background: linear-gradient(90deg, #00f260, #0575e6); color: white; padding: 2px 8px; border-radius: 5px; font-size: 0.75em; font-weight: bold; }
    .share-btn { width: 100%; background-color: #25D366; color: white !important; border: none; padding: 12px; border-radius: 10px; font-weight: bold; text-align: center; display: block; text-decoration: none; transition: 0.3s; }
    .share-btn:hover { background-color: #128C7E; transform: translateY(-2px); }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ Configuración")
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, 2.5)
    st.divider()
    st.subheader("Cuotas (Value Check)")
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>SISTEMA DE ANÁLISIS PROFESIONAL OR936</h1>", unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Nombre Local", "Local")
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Goles Favor L", 0.0, 10.0, 1.7)
    lgc = c2.number_input("Goles Contra L", 0.0, 10.0, 1.2)
    ltj = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3)
    lco = c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_b:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Nombre Visitante", "Visitante")
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles Favor V", 0.0, 10.0, 1.5)
    vgc = c4.number_input("Goles Contra V", 0.0, 10.0, 1.1)
    vtj = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2)
    vco = c4.number_input("Corners V", 0.0, 20.0, 4.8)

if st.button("🚀 INICIAR ANÁLISIS DE MERCADOS", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # =================================================================
    # NUEVO: RECOLECCIÓN DE SUGERENCIAS DE TODOS LOS MERCADOS
    # =================================================================
    pool_sugerencias = []
    
    # 1. Mercados 1X2 y DC
    pool_sugerencias.append({"op": f"Gana {nl}", "p": res['1X2'][0]})
    pool_sugerencias.append({"op": "Empate", "p": res['1X2'][1]})
    pool_sugerencias.append({"op": f"Gana {nv}", "p": res['1X2'][2]})
    pool_sugerencias.append({"op": f"Doble Oportunidad 1X", "p": res['DC'][0]})
    pool_sugerencias.append({"op": f"Doble Oportunidad X2", "p": res['DC'][1]})
    pool_sugerencias.append({"op": f"Doble Oportunidad 12", "p": res['DC'][2]})
    
    # 2. Ambos Anotan
    pool_sugerencias.append({"op": "Ambos Anotan: SÍ", "p": res['BTTS'][0]})
    pool_sugerencias.append({"op": "Ambos Anotan: NO", "p": res['BTTS'][1]})
    
    # 3. Goles (Filtrando Over 0.5 y Under 5.5 por ser muy obvios)
    for line, probs in res['GOLES'].items():
        if line > 0.5: pool_sugerencias.append({"op": f"Over {line} Goles", "p": probs[0]})
        if line < 5.5: pool_sugerencias.append({"op": f"Under {line} Goles", "p": probs[1]})
        
    # 4. Tarjetas y Corners (Over y Under)
    for line, probs in res['TARJETAS'].items():
        pool_sugerencias.append({"op": f"Over {line} Tarjetas", "p": probs[0]})
        pool_sugerencias.append({"op": f"Under {line} Tarjetas", "p": probs[1]})
    for line, probs in res['CORNERS'].items():
        pool_sugerencias.append({"op": f"Over {line} Corners", "p": probs[0]})
        pool_sugerencias.append({"op": f"Under {line} Corners", "p": probs[1]})

    # 5. Marcadores Exactos (El Top 1)
    top_score, top_score_p = res['TOP'][0]
    pool_sugerencias.append({"op": f"Marcador Exacto: {top_score}", "p": top_score_p})

    # FILTRAR Y ORDENAR: Buscamos lo más probable que no sea una "obviedad" (>92% suele ser cuota ínfima)
    mejores_opciones = sorted([s for s in pool_sugerencias if s['p'] < 92], key=lambda x: x['p'], reverse=True)[:4]

    # MOSTRAR APARTADO DE SUGERENCIAS
    st.markdown("### 💎 Veredicto Maestro: Sugerencias de Alta Probabilidad")
    cols = st.columns(4)
    for i, sugerencia in enumerate(mejores_opciones):
        with cols[i]:
            st.markdown(f"""
                <div class="verdict-card">
                    <p style="color:#00ffcc; font-size:0.8em; margin:0;">OPCIÓN #{i+1}</p>
                    <h4 style="margin:10px 0; color:white; font-size:1em;">{sugerencia['op']}</h4>
                    <p style="font-weight:bold; color:#fff; margin:0;">{sugerencia['p']:.1f}%</p>
                </div>
            """, unsafe_allow_html=True)

    # Botón Compartir
    texto_share = f"📊 *Análisis ProStats OR936*\n⚽ {nl} vs {nv}\n\n🔥 *Sugerencias Top:*\n"
    for s in mejores_opciones: texto_share += f"✅ {s['op']} ({s['p']:.1f}%)\n"
    url_wa = f"https://wa.me/?text={urllib.parse.quote(texto_share)}"
    st.markdown(f'<a href="{url_wa}" target="_blank" class="share-btn">📲 COMPARTIR ANÁLISIS EN WHATSAPP</a>', unsafe_allow_html=True)
    
    st.divider()

    # --- PESTAÑAS DETALLADAS (SIN CAMBIOS) ---
    t1, t2, t3, t4 = st.tabs(["🏆 Resultados 1X2", "🥅 Goles O/U", "🚩 Especiales", "📊 Matriz"])

    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Probabilidades 1X2")
            def val(p, o): return " <span class='value-badge'>VALUE</span>" if (p/100*o) > 1.10 else ""
            st.write(f"**{nl}:** {res['1X2'][0]:.1f}% {val(res['1X2'][0], o1)}", unsafe_allow_html=True)
            st.progress(res['1X2'][0]/100)
            st.write(f"**Empate:** {res['1X2'][1]:.1f}% {val(res['1X2'][1], ox)}", unsafe_allow_html=True)
            st.progress(res['1X2'][1]/100)
            st.write(f"**{nv}:** {res['1X2'][2]:.1f}% {val(res['1X2'][2], o2)}", unsafe_allow_html=True)
            st.progress(res['1X2'][2]/100)
        with c2:
            st.markdown("##### Doble Oportunidad")
            st.write(f"**1X:** {res['DC'][0]:.1f}%")
            st.progress(res['DC'][0]/100)
            st.write(f"**X2:** {res['DC'][1]:.1f}%")
            st.progress(res['DC'][1]/100)
            st.write(f"**12:** {res['DC'][2]:.1f}%")
            st.progress(res['DC'][2]/100)

    with t2:
        g1, g2 = st.columns(2)
        for i, (line, probs) in enumerate(res['GOLES'].items()):
            with (g1 if i < 3 else g2):
                st.write(f"**Línea {line}**: O {probs[0]:.1f}% | U {probs[1]:.1f}%")
                st.progress(probs[0]/100)
        st.divider()
        st.write(f"**Ambos Anotan:** SÍ {res['BTTS'][0]:.1f}% | NO {res['BTTS'][1]:.1f}%")

    with t3:
        tj, co = st.columns(2)
        with tj:
            st.markdown("##### 🎴 Tarjetas")
            for k, v in res['TARJETAS'].items():
                st.write(f"Línea {k}: O {v[0]:.1f}% | U {v[1]:.1f}%")
                st.progress(v[0]/100)
        with co:
            st.markdown("##### 🚩 Corners")
            for k, v in res['CORNERS'].items():
                st.write(f"Línea {k}: O {v[0]:.1f}% | U {v[1]:.1f}%")
                st.progress(v[0]/100)

    with t4:
        st.markdown("##### Mapa de Calor de Marcadores")
        df_m = pd.DataFrame(res['MATRIZ'])
        fig = px.imshow(df_m, color_continuous_scale='Viridis', text_auto=".1f", labels=dict(x=f"Goles {nv}", y=f"Goles {nl}"))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: gray; font-size: 0.8em;'>ProStats OR936 v2.5 - All Markets Analysis Active</p>", unsafe_allow_html=True)
