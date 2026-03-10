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
# COMPONENTES VISUALES MEJORADOS
# =================================================================
def dual_bar(label_left, prob_left, label_right, prob_right, color_left="#00ffcc", color_right="#333", value_tag=""):
    """Barra de alta legibilidad: Probabilidad vs Riesgo"""
    st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 4px;">
                <span style="color:white; font-weight:bold;">{label_left} <span style="color:{color_left};">{prob_left:.1f}%</span> {value_tag}</span>
                <span style="color:#888;">{label_right} {prob_right:.1f}%</span>
            </div>
            <div style="background-color: {color_right}; height: 12px; border-radius: 6px; display: flex; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
                <div style="width: {prob_left}%; background: linear-gradient(90deg, {color_left}aa, {color_left}); box-shadow: 0 0 10px {color_left}44;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

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
# INTERFAZ (MASTER DASHBOARD)
# =================================================================
st.set_page_config(page_title="OR936 Elite Analysis", layout="wide")

st.markdown("""
    <style>
    .master-card {
        background: linear-gradient(135deg, #1e1e26 0%, #111118 100%);
        padding: 25px; border-radius: 15px; border: 1px solid #00ffcc;
        box-shadow: 0 10px 30px rgba(0,255,204,0.1); margin-bottom: 20px;
    }
    .verdict-item {
        border-left: 4px solid #00ffcc; padding: 10px 15px; margin-bottom: 10px;
        background: rgba(255,255,255,0.03); border-radius: 0 10px 10px 0;
    }
    .share-btn { 
        width: 100%; background: #25D366; color: white !important; border: none; 
        padding: 12px; border-radius: 10px; font-weight: bold; text-align: center; 
        display: block; text-decoration: none; margin-top: 15px;
    }
    .value-tag { background: #00ffcc; color: black; padding: 2px 5px; border-radius: 4px; font-size: 0.7em; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ PANEL CONTROL")
    ligas_api = {
        "La Liga (ESP)": 302, "Premier League (ENG)": 152, "Serie A (ITA)": 207,
        "Bundesliga (GER)": 175, "Ligue 1 (FRA)": 168, "UEFA Champions League": 3,
        "Copa Libertadores": 13, "Brasileirão Serie A": 99, "Liga Mayor (SLV)": 601,
        "Copa Presidente (SLV)": 603, "FA Cup (ENG)": 145, "AFC Champions Elite": 504
    }
    nombre_liga = st.selectbox("Selecciona Competición", list(ligas_api.keys()))
    league_id = ligas_api[nombre_liga]
    
    fecha_analisis = st.date_input("Fecha de partidos", datetime.now())
    fecha_str = fecha_analisis.strftime("%Y-%m-%d")
    
    eventos = api_request("get_events", {"from": fecha_str, "to": fecha_str, "league_id": league_id})
    
    if eventos and isinstance(eventos, list):
        opciones_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        partido_sel = st.selectbox("Partidos encontrados", list(opciones_p.keys()))
        
        if st.button("⚡ SINCRONIZAR API"):
            standings = api_request("get_standings", {"league_id": league_id})
            if standings:
                total_g = sum(int(t['overall_league_GF']) for t in standings)
                total_pj = sum(int(t['overall_league_payed']) for t in standings)
                st.session_state['p_liga_auto'] = total_g / (total_pj / 2) if total_pj > 0 else 2.5
                data_p = opciones_p[partido_sel]
                def buscar(n, tabla):
                    for t in tabla:
                        if n.lower() in t['team_name'].lower() or t['team_name'].lower() in n.lower(): return t
                    return None
                dl, dv = buscar(data_p['match_hometeam_name'], standings), buscar(data_p['match_awayteam_name'], standings)
                if dl and dv:
                    pjl, pjv = max(1, int(dl['overall_league_payed'])), max(1, int(dv['overall_league_payed']))
                    st.session_state['lgf_auto'] = float(dl['overall_league_GF']) / pjl
                    st.session_state['lgc_auto'] = float(dl['overall_league_GA']) / pjl
                    st.session_state['vgf_auto'] = float(dv['overall_league_GF']) / pjv
                    st.session_state['vgc_auto'] = float(dv['overall_league_GA']) / pjv
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.success("¡Sincronizado!")

    st.divider()
    p_liga = st.number_input("Goles Promedio Liga", 0.1, 10.0, st.session_state.get('p_liga_auto', 2.5))
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 ELITE ANALYSIS</h1>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    nl = st.text_input("Local", st.session_state.get('nl_auto', "Local"))
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Goles F. L", 0.0, 10.0, st.session_state.get('lgf_auto', 1.7))
    lgc = c2.number_input("Goles C. L", 0.0, 10.0, st.session_state.get('lgc_auto', 1.2))
    ltj = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3)
    lco = c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    nv = st.text_input("Visitante", st.session_state.get('nv_auto', "Visitante"))
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles F. V", 0.0, 10.0, st.session_state.get('vgf_auto', 1.5))
    vgc = c4.number_input("Goles C. V", 0.0, 10.0, st.session_state.get('vgc_auto', 1.1))
    vtj = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2)
    vco = c4.number_input("Corners V", 0.0, 20.0, 4.8)

if st.button("🚀 INICIAR PROCESAMIENTO ELITE", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # Lógica de Sugerencias
    pool = []
    pool.append({"t": "Doble Oportunidad 1X", "p": res['DC'][0]})
    pool.append({"t": "Doble Oportunidad X2", "p": res['DC'][1]})
    pool.append({"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]})
    pool.append({"t": "Ambos Anotan: NO", "p": res['BTTS'][1]})
    for line, p in res['GOLES'].items():
        if 0.5 < line < 4.5:
            pool.append({"t": f"Over {line} Goles", "p": p[0]})
            pool.append({"t": f"Under {line} Goles", "p": p[1]})
    sugerencias = sorted([s for s in pool if 65 < s['p'] < 93], key=lambda x: x['p'], reverse=True)[:4]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v_col1, v_col2 = st.columns([1.2, 1])
    with v_col1:
        st.markdown("#### 💎 Picks de Alta Probabilidad")
        for s in sugerencias:
            st.markdown(f'<div class="verdict-item"><span style="color:#00ffcc; font-weight:bold;">{s["p"]:.1f}%</span> | {s["t"]}</div>', unsafe_allow_html=True)
    with v_col2:
        st.markdown("#### ⚽ Top Marcadores")
        for i, (score, prob) in enumerate(res['TOP']):
            st.markdown(f'<div style="background:rgba(255,255,255,0.05); padding:8px; border-radius:8px; margin-bottom:5px; border:1px solid rgba(0,255,204,0.2); text-align:center;"><b>{score}</b> ({prob:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    t1, t2, t3, t4, t5 = st.tabs(["🏆 1X2 & DC", "🥅 Goles", "🎴 Tarjetas", "🚩 Corners", "📊 Matriz"])

    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.write("##### Mercado 1X2")
            v1 = "<span class='value-tag'>VALUE</span>" if (res['1X2'][0]/100*o1) > 1.10 else ""
            vx = "<span class='value-tag'>VALUE</span>" if (res['1X2'][1]/100*ox) > 1.10 else ""
            v2 = "<span class='value-tag'>VALUE</span>" if (res['1X2'][2]/100*o2) > 1.10 else ""
            dual_bar(f"Local ({nl})", res['1X2'][0], "Otros", 100-res['1X2'][0], value_tag=v1)
            dual_bar("Empate (X)", res['1X2'][1], "Otros", 100-res['1X2'][1], color_left="#aaa", value_tag=vx)
            dual_bar(f"Visita ({nv})", res['1X2'][2], "Otros", 100-res['1X2'][2], color_left="#3498db", value_tag=v2)
        with c2:
            st.write("##### Doble Oportunidad")
            dual_bar("1X", res['DC'][0], "2", 100-res['DC'][0])
            dual_bar("X2", res['DC'][1], "1", 100-res['DC'][1])
            dual_bar("12", res['DC'][2], "X", 100-res['DC'][2])

    with t2:
        g1, g2 = st.columns(2)
        with g1:
            st.write("##### Líneas de Goles")
            for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
                p = res['GOLES'][line]
                dual_bar(f"Over {line}", p[0], f"Under {line}", p[1], color_left="#00ccff" if p[0]>p[1] else "#ff4b4b")
        with g2:
            st.write("##### Ambos Anotan (BTTS)")
            dual_bar("SÍ Anotan", res['BTTS'][0], "NO Anotan", res['BTTS'][1], color_left="#f1c40f")

    with t3:
        st.write("##### Mercado de Tarjetas")
        tj1, tj2 = st.columns(2)
        for i, (line, p) in enumerate(res['TARJETAS'].items()):
            with (tj1 if i < 3 else tj2):
                dual_bar(f"Over {line}", p[0], f"Under {line}", p[1], color_left="#e74c3c")

    with t4:
        st.write("##### Mercado de Corners")
        co1, co2 = st.columns(2)
        for i, (line, p) in enumerate(res['CORNERS'].items()):
            with (co1 if i < 3 else co2):
                dual_bar(f"Over {line}", p[0], f"Under {line}", p[1], color_left="#2ecc71")

    with t5:
        st.write("##### Probabilidad de Marcadores Exactos")
        df_m = pd.DataFrame(res['MATRIZ'])
        fig = px.imshow(df_m, color_continuous_scale='Viridis', text_auto=".1f", 
                        labels=dict(x=f"Goles {nv}", y=f"Goles {nl}", color="%"))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8em;'>OR936 Elite v2.8 | Todos los mercados activos</p>", unsafe_allow_html=True)
