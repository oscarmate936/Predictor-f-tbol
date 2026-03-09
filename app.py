import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN API (apiv3.apifootball.com)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

@st.cache_data(ttl=3600)
def api_request(action, params={}):
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except:
        return []

# =================================================================
# MOTOR MATEMÁTICO (PRO STATS ENGINE)
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
st.set_page_config(page_title="OR936 Total Auto", layout="wide")

st.markdown("""
    <style>
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    .master-card { background: linear-gradient(135deg, #1e1e26 0%, #111118 100%); padding: 30px; border-radius: 20px; border: 1px solid #00ffcc; box-shadow: 0 10px 30px rgba(0,255,204,0.15); margin-bottom: 25px; }
    .verdict-item { border-left: 3px solid #00ffcc; padding-left: 15px; margin-bottom: 12px; background: rgba(255,255,255,0.02); padding: 8px 15px; border-radius: 0 8px 8px 0; }
    .value-tag { background: #00ffcc; color: black; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: 900; }
    .share-btn { width: 100%; background-color: #25D366; color: white !important; border: none; padding: 15px; border-radius: 12px; font-weight: bold; text-align: center; display: block; text-decoration: none; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("🤖 Scouting Total")
    ligas = {"La Liga (ESP)": 302, "Premier League (ENG)": 152, "Serie A (ITA)": 207, "Bundesliga (GER)": 175, "Ligue 1 (FRA)": 168}
    nombre_liga = st.selectbox("1. Liga", list(ligas.keys()))
    league_id = ligas[nombre_liga]
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    eventos = api_request("get_events", {"from": hoy, "to": hoy, "league_id": league_id})
    
    if eventos and isinstance(eventos, list):
        opciones_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        seleccion = st.selectbox("2. Partido de Hoy", list(opciones_p.keys()))
        partido_data = opciones_p[seleccion]
        
        if st.button("⚡ SINCRONIZAR TODO (AUTO)"):
            standings = api_request("get_standings", {"league_id": league_id})
            if standings:
                # --- CÁLCULO PROMEDIO DE LIGA AUTOMÁTICO ---
                total_goles = sum(int(t['overall_league_GF']) for t in standings)
                total_pj = sum(int(t['overall_league_payed']) for t in standings)
                avg_league = total_goles / (total_pj / 2) if total_pj > 0 else 2.5
                st.session_state['p_liga'] = avg_league
                
                # --- DATOS EQUIPOS ---
                def buscar_eq(nombre, tabla):
                    for t in tabla:
                        if nombre.lower() in t['team_name'].lower() or t['team_name'].lower() in nombre.lower(): return t
                    return None
                
                dl = buscar_eq(partido_data['match_hometeam_name'], standings)
                dv = buscar_eq(partido_data['match_awayteam_name'], standings)
                
                if dl and dv:
                    pj_l, pj_v = max(1, int(dl['overall_league_payed'])), max(1, int(dv['overall_league_payed']))
                    st.session_state['lgf'] = float(dl['overall_league_GF']) / pj_l
                    st.session_state['lgc'] = float(dl['overall_league_GA']) / pj_l
                    st.session_state['vgf'] = float(dv['overall_league_GF']) / pj_v
                    st.session_state['vgc'] = float(dv['overall_league_GA']) / pj_v
                    st.session_state['l_name'], st.session_state['v_name'] = dl['team_name'], dv['team_name']
                    st.success("✅ Sincronización Completa")
    else: st.info("Sin partidos hoy.")

    st.divider()
    # Ahora p_liga toma el valor automático del session_state
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, st.session_state.get('p_liga', 2.5))
    st.subheader("Cuotas Mercado")
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 TOTAL-AUTO V3.9</h1>", unsafe_allow_html=True)

# PANEL DE CONTROL
col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Nombre", st.session_state.get('l_name', 'Local'))
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Goles Favor L", 0.0, 10.0, st.session_state.get('lgf', 1.7))
    lgc = c2.number_input("Goles Contra L", 0.0, 10.0, st.session_state.get('lgc', 1.2))
    ltj, lco = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3), c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Nombre", st.session_state.get('v_name', 'Visitante'))
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles Favor V", 0.0, 10.0, st.session_state.get('vgf', 1.5))
    vgc = c4.number_input("Goles Contra V", 0.0, 10.0, st.session_state.get('vgc', 1.1))
    vtj, vco = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2), c4.number_input("Corners V", 0.0, 20.0, 4.8)

# PROCESAR
if st.button("🚀 PROCESAR ANÁLISIS COMPLETO", use_container_width=True):
    motor = MotorMatematico()
    # El xG ahora es más preciso gracias al promedio de liga automático
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # Pool de mercados (Over/Under completos)
    pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "Ambos Anotan", "p": res['BTTS'][0]}]
    for line, probs in res['GOLES'].items():
        pool.append({"t": f"Over {line}", "p": probs[0]})
        pool.append({"t": f"Under {line}", "p": probs[1]})
    
    sugerencias = sorted([s for s in pool if 66 < s['p'] < 93], key=lambda x: x['p'], reverse=True)[:4]

    # RESULTADOS VISUALES
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.2, 1])
    with v1:
        st.markdown("#### 💎 Veredicto Maestro")
        for s in sugerencias:
            st.markdown(f'<div class="verdict-item"><span style="color:#00ffcc; font-weight:bold;">{s["p"]:.1f}%</span> | {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("#### ⚽ Probabilidades Clave")
        st.markdown(f'<div style="background:rgba(0,255,204,0.05); padding:10px; border-radius:10px; text-align:center; border:1px dashed #00ffcc; margin-bottom:15px;"><span style="color:#aaa; font-size:0.85em;">AMBOS ANOTAN</span><br><span style="color:white; font-weight:bold;">SÍ: {res["BTTS"][0]:.1f}%</span> | <span style="color:#aaa;">NO: {res["BTTS"][1]:.1f}%</span></div>', unsafe_allow_html=True)
        for i, (score, prob) in enumerate(res['TOP']):
            st.markdown(f'<div style="background:rgba(255,255,255,0.05); padding:8px; border-radius:8px; border:1px solid rgba(0,255,204,0.3); text-align:center; margin-bottom:5px;"><span style="color:#00ffcc;">#{i+1}</span> | {score} ({prob:.1f}%)</div>', unsafe_allow_html=True)
    
    # WhatsApp
    resumen_wa = f"📊 *Análisis OR936*\n⚽ {nl} vs {nv}\n\n🔥 *Sugerencias:*\n"
    for s in sugerencias: resumen_wa += f"✅ {s['t']} ({s['p']:.1f}%)\n"
    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(resumen_wa)}" target="_blank" class="share-btn">📲 COMPARTIR ANÁLISIS</a>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # TABS DETALLADOS
    t1, t2, t3, t4 = st.tabs(["🏆 1X2 & DC", "🥅 Goles", "🚩 Especiales", "📊 Matriz"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            for i, lab, cuo in zip(range(3), [nl, 'Empate', nv], [o1, ox, o2]):
                v_tag = " <span class='value-tag'>VALUE</span>" if (res['1X2'][i]/100*cuo) > 1.15 else ""
                st.write(f"**{lab}:** {res['1X2'][i]:.1f}%{v_tag}", unsafe_allow_html=True)
                st.progress(res['1X2'][i]/100)
    with t2:
        g1, g2 = st.columns(2)
        for i, (line, probs) in enumerate(res['GOLES'].items()):
            with (g1 if i < 3 else g2):
                st.write(f"**Línea {line}**: Over {probs[0]:.1f}% | Under {probs[1]:.1f}%")
                st.progress(probs[0]/100)
    with t3:
        tj, co = st.columns(2)
        with tj:
            for k, v in res['TARJETAS'].items(): st.write(f"L {k}: O {v[0]:.1f}% | U {v[1]:.1f}%")
        with co:
            for k, v in res['CORNERS'].items(): st.write(f"L {k}: O {v[0]:.1f}% | U {v[1]:.1f}%")
    with t4:
        fig = px.imshow(pd.DataFrame(res['MATRIZ']), color_continuous_scale='Viridis', text_auto=".1f", labels=dict(x=nv, y=nl))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8em;'>ProStats Engine OR936 v3.9 Full-Auto Mode</p>", unsafe_allow_html=True)
