import streamlit as st
import math
import pandas as pd

# =================================================================
# MOTOR MATEMÁTICO (SÍNTESIS PRO - ORIGEN: ultima.py)
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
# INTERFAZ WEB ADAPTADA AL MÓVIL
# =================================================================
st.set_page_config(page_title="Ultimate Stats Web", layout="centered")

st.markdown("<h2 style='text-align: center;'>📊 Predictor Pro Web</h2>", unsafe_allow_html=True)

# LIGA Y CUOTAS
with st.expander("⚙️ CONFIGURACIÓN Y CUOTAS", expanded=True):
    p_liga = st.number_input("Promedio Goles Liga", 2.5)
    c1, cx, c2 = st.columns(3)
    o1 = c1.number_input("Cuota Local", 1.0)
    ox = cx.number_input("Cuota Empate", 1.0)
    o2 = c2.number_input("Cuota Visita", 1.0)

# DATOS LOCAL/VISITANTE
t1, t2 = st.tabs(["🏠 LOCAL", "🚀 VISITANTE"])
with t1:
    nl = st.text_input("Nombre Local", "LOCAL")
    lgf = st.number_input("Goles Favor (L)", 1.7)
    lgc = st.number_input("Goles Contra (L)", 1.2)
    ltj = st.number_input("Tarjetas (L)", 2.3)
    lco = st.number_input("Corners (L)", 5.5)
with t2:
    nv = st.text_input("Nombre Visitante", "VISITANTE")
    vgf = st.number_input("Goles Favor (V)", 1.5)
    vgc = st.number_input("Goles Contra (V)", 1.1)
    vtj = st.number_input("Tarjetas (V)", 2.2)
    vco = st.number_input("Corners (V)", 4.8)

if st.button("🚀 ANALIZAR PARTIDO", use_container_width=True):
    motor = MotorMatematico()
    res = motor.procesar((lgf/p_liga)*(vgc/p_liga)*p_liga, (vgf/p_liga)*(lgc/p_liga)*p_liga, ltj+vtj, lco+vco)

    # SUGERENCIAS (>78%)
    picks = []
    if res['DC'][0] > 78: picks.append(f"1X {nl}")
    if res['DC'][1] > 78: picks.append(f"X2 {nv}")
    for l, p in res['GOLES'].items():
        if p[0] > 78: picks.append(f"Over {l}")
        if p[1] > 78: picks.append(f"Under {l}")
    
    if picks:
        st.warning(f"⚡ **SUGERENCIAS:** {' | '.join(picks[:3])}")

    # 1X2 CON VALUE CHECK
    st.subheader("🏆 Probabilidades 1X2")
    m1, mx, m2 = st.columns(3)
    def val(p, o): return " 🔥" if (p/100*o) > 1.10 else ""
    m1.metric(nl, f"{res['1X2'][0]:.1f}%", help=val(res['1X2'][0], o1))
    mx.metric("Empate", f"{res['1X2'][1]:.1f}%", help=val(res['1X2'][1], ox))
    m2.metric(nv, f"{res['1X2'][2]:.1f}%", help=val(res['1X2'][2], o2))

    # DOBLE OPORTUNIDAD Y BTTS
    c_dc, c_btts = st.columns(2)
    with c_dc:
        st.write("**🎯 Doble Oportunidad**")
        st.write(f"1X: {res['DC'][0]:.1f}% | X2: {res['DC'][1]:.1f}% | **12: {res['DC'][2]:.1f}%**")
    with c_btts:
        st.write("**⚽ Ambos Anotan**")
        st.write(f"SÍ: {res['BTTS'][0]:.1f}% | NO: {res['BTTS'][1]:.1f}%")

    # TABLAS DE MERCADOS
    st.subheader("🥅 Mercado de Goles O/U")
    st.table(pd.DataFrame([{"Línea": f"Goles {k}", "Over": f"{v[0]:.1f}%", "Under": f"{v[1]:.1f}%"} for k, v in res['GOLES'].items()]))

    # ESPECIALES
    st.subheader("🎴 Tarjetas y 🚩 Corners")
    for k, v in res['TARJETAS'].items(): st.write(f"Tarjetas {k}: O {v[0]:.0f}% | U {v[1]:.0f}%")
    for k, v in res['CORNERS'].items(): st.write(f"Corners {k}: O {v[0]:.0f}% | U {v[1]:.0f}%")