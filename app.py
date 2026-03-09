import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests

# =================================================================
# CONFIGURACIÓN NUEVA API (apifootball.com)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apifootball.com/api/"

@st.cache_data(ttl=3600)
def obtener_equipos_y_stats(league_id):
    # En esta API, 'get_standings' nos da los goles a favor y en contra de todos
    url = f"{BASE_URL}?action=get_standings&league_id={league_id}&APIkey={API_KEY}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if "error" in data:
            st.error(f"Error de API: {data['error']}")
            return []
        return data
    except Exception as e:
        st.error(f"Fallo de conexión: {e}")
        return []

# =================================================================
# MOTOR MATEMÁTICO (PRO STATS ENGINE) - INTACTO
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
        marcadores, matriz_calor = {}, []
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
# INTERFAZ (UI)
# =================================================================
st.set_page_config(page_title="OR936 APIFootball Pro", layout="wide")

# CSS personalizado
st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    .master-card { background: linear-gradient(135deg, #1e1e26 0%, #111118 100%); padding: 30px; border-radius: 20px; border: 1px solid #00ffcc; box-shadow: 0 10px 30px rgba(0,255,204,0.15); margin-bottom: 25px; }
    .score-badge { background: rgba(255,255,255,0.05); padding: 10px; border-radius: 10px; border: 1px solid rgba(0,255,204,0.3); text-align: center; }
    .verdict-item { border-left: 3px solid #00ffcc; padding-left: 15px; margin-bottom: 12px; background: rgba(255,255,255,0.02); padding: 8px 15px; border-radius: 0 8px 8px 0; }
    .share-btn { width: 100%; background-color: #25D366; color: white !important; border: none; padding: 15px; border-radius: 12px; font-weight: bold; text-align: center; display: block; text-decoration: none; margin-top: 20px; }
    .value-tag { background: #00ffcc; color: black; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚽ API-Football Selector")
    # Diccionario de ligas comunes en apifootball.com
    ligas_dict = {"La Liga (ESP)": 302, "Premier League (ENG)": 152, "Serie A (ITA)": 207, "Bundesliga (GER)": 175, "Ligue 1 (FRA)": 168, "Champions League": 3}
    nombre_liga = st.selectbox("1. Selecciona Liga", list(ligas_dict.keys()))
    league_id = ligas_dict[nombre_liga]
    
    st.divider()
    
    standings = obtener_equipos_y_stats(league_id)
    if standings:
        lista_nombres = [t['team_name'] for t in standings]
        equipo_l = st.selectbox("2. Equipo Local", lista_nombres, index=0)
        equipo_v = st.selectbox("3. Equipo Visitante", lista_nombres, index=1)
        
        if st.button("📥 CARGAR DATOS AUTOMÁTICOS"):
            data_l = next(t for t in standings if t['team_name'] == equipo_l)
            data_v = next(t for t in standings if t['team_name'] == equipo_v)
            
            pj_l = float(data_l['overall_league_payed'])
            pj_v = float(data_v['overall_league_payed'])
            
            st.session_state['lgf'] = float(data_l['overall_league_GF']) / pj_l
            st.session_state['lgc'] = float(data_l['overall_league_GA']) / pj_l
            st.session_state['vgf'] = float(data_v['overall_league_GF']) / pj_v
            st.session_state['vgc'] = float(data_v['overall_league_GA']) / pj_v
            st.session_state['l_name'] = equipo_l
            st.session_state['v_name'] = equipo_v
            st.success("Estadísticas cargadas")

    st.divider()
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, 2.5)
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 ELITE ANALYSIS V3.5</h1>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Nombre L", st.session_state.get('l_name', 'Local'))
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Goles Favor L", 0.0, 10.0, st.session_state.get('lgf', 1.7))
    lgc = c2.number_input("Goles Contra L", 0.0, 10.0, st.session_state.get('lgc', 1.2))
    ltj = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3)
    lco = c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Nombre V", st.session_state.get('v_name', 'Visitante'))
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles Favor V", 0.0, 10.0, st.session_state.get('vgf', 1.5))
    vgc = c4.number_input("Goles Contra V", 0.0, 10.0, st.session_state.get('vgc', 1.1))
    vtj = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2)
    vco = c4.number_input("Corners V", 0.0, 20.0, 4.8)

if st.button("🚀 PROCESAR ANÁLISIS COMPLETO", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # Lógica de sugerencias
    pool = [{"t": "Doble Oportunidad 1X", "p": res['DC'][0]}, {"t": "Doble Oportunidad X2", "p": res['DC'][1]}, {"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]}]
    for line, p in res['GOLES'].items():
        if 0.5 < line < 4.5:
            pool.append({"t": f"Over {line} Goles", "p": p[0]})
            pool.append({"t": f"Under {line} Goles", "p": p[1]})
    
    sugerencias = sorted([s for s in pool if 66 < s['p'] < 93], key=lambda x: x['p'], reverse=True)[:4]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v_col1, v_col2 = st.columns([1.2, 1])
    with v_col1:
        st.markdown("#### 💎 Veredicto Maestro")
        for s in sugerencias:
            st.markdown(f'<div class="verdict-item"><span style="color:#00ffcc; font-weight:bold;">{s["p"]:.1f}%</span> | {s["t"]}</div>', unsafe_allow_html=True)
    with v_col2:
        st.markdown("#### ⚽ Probabilidades Clave")
        st.markdown(f'<div style="background:rgba(0,255,204,0.05); padding:10px; border-radius:10px; text-align:center; border:1px dashed #00ffcc; margin-bottom:15px;"><span style="color:#aaa; font-size:0.85em;">AMBOS ANOTAN</span><br><span style="color:white; font-weight:bold;">SÍ: {res["BTTS"][0]:.1f}%</span> | <span style="color:#aaa;">NO: {res["BTTS"][1]:.1f}%</span></div>', unsafe_allow_html=True)
        for i, (score, prob) in enumerate(res['TOP']):
            st.markdown(f'<div class="score-badge" style="margin-bottom:8px;"><span style="color:#00ffcc; font-weight:bold;">#{i+1}</span> | {score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    
    resumen_wa = f"📊 *Análisis OR936*\n⚽ {nl} vs {nv}\n\n🔥 *Sugerencias:*\n"
    for s in sugerencias: resumen_wa += f"✅ {s['t']} ({s['p']:.1f}%)\n"
    url_wa = f"https://wa.me/?text={urllib.parse.quote(resumen_wa)}"
    st.markdown(f'<a href="{url_wa}" target="_blank" class="share-btn">📲 COMPARTIR ANÁLISIS</a>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 1X2 & DC", "🥅 Goles", "🚩 Especiales", "📊 Matriz"])
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Probabilidades 1X2")
            for i, label, cuota in zip(range(3), [nl, 'Empate', nv], [o1, ox, o2]):
                val_tag = " <span class='value-tag'>VALUE</span>" if (res['1X2'][i]/100*cuota) > 1.15 else ""
                st.write(f"**{label}:** {res['1X2'][i]:.1f}%{val_tag}", unsafe_allow_html=True)
                st.progress(res['1X2'][i]/100)
    with tab2:
        g1, g2 = st.columns(2)
        for i, (line, probs) in enumerate(res['GOLES'].items()):
            with (g1 if i < 3 else g2):
                st.write(f"**Línea {line}**: Over {probs[0]:.1f}% | Under {probs[1]:.1f}%")
                st.progress(probs[0]/100)
    with tab3:
        tj, co = st.columns(2)
        with tj:
            st.write("🎴 **Tarjetas**")
            for k, v in res['TARJETAS'].items(): st.write(f"L {k}: O {v[0]:.1f}% | U {v[1]:.1f}%")
        with co:
            st.write("🚩 **Corners**")
            for k, v in res['CORNERS'].items(): st.write(f"L {k}: O {v[0]:.1f}% | U {v[1]:.1f}%")
    with tab4:
        df_m = pd.DataFrame(res['MATRIZ'])
        fig = px.imshow(df_m, color_continuous_scale='Viridis', text_auto=".1f", labels=dict(x=nv, y=nl))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8em;'>ProStats Engine OR936 v3.5 (apifootball.com version)</p>", unsafe_allow_html=True)
