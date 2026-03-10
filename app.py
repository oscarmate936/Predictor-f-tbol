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
# COMPONENTES VISUALES PERSONALIZADOS
# =================================================================
def dual_bar(label_left, prob_left, label_right, prob_right, color_left="#00ffcc", color_right="#ff4b4b"):
    """Genera una barra comparativa entre dos probabilidades"""
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; font-size: 0.85em; margin-bottom: 2px; color: #ddd;">
            <span>{label_left}: <b>{prob_left:.1f}%</b></span>
            <span>{label_right}: <b>{prob_right:.1f}%</b></span>
        </div>
        <div style="background-color: #333; height: 8px; border-radius: 4px; display: flex; overflow: hidden; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.1);">
            <div style="width: {prob_left}%; background-color: {color_left}; box-shadow: 0 0 10px {color_left}55;"></div>
            <div style="width: {prob_right}%; background-color: {color_right};"></div>
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
        try: return (math.exp(-lam) * (lam**k)) / math.factorial(k)
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
# INTERFAZ PROFESIONAL (MASTER DASHBOARD)
# =================================================================
st.set_page_config(page_title="OR936 Elite Analysis", layout="wide")

st.markdown("""
    <style>
    .master-card {
        background: linear-gradient(135deg, #1e1e26 0%, #111118 100%);
        padding: 30px; border-radius: 20px; border: 1px solid #00ffcc;
        box-shadow: 0 10px 30px rgba(0,255,204,0.15); margin-bottom: 25px;
    }
    .verdict-item {
        border-left: 3px solid #00ffcc; padding-left: 15px; margin-bottom: 12px;
        background: rgba(255,255,255,0.02); padding: 8px 15px; border-radius: 0 8px 8px 0;
    }
    .share-btn { 
        width: 100%; background-color: #25D366; color: white !important; border: none; 
        padding: 15px; border-radius: 12px; font-weight: bold; text-align: center; 
        display: block; text-decoration: none; margin-top: 20px;
    }
    .score-badge {
        background: rgba(255,255,255,0.05); padding: 10px; border-radius: 10px;
        border: 1px solid rgba(0,255,204,0.3); text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ Configuración")
    
    st.subheader("🤖 Sincronización API")
    ligas_api = {
        "La Liga (ESP)": 302,
        "Premier League (ENG)": 152,
        "Serie A (ITA)": 207,
        "Bundesliga (GER)": 175,
        "Ligue 1 (FRA)": 168,
        "UEFA Champions League": 3,
        "Copa Libertadores": 13,
        "Brasileirão Serie A": 99,
        "Liga Mayor (SLV)": 601,
        "Copa Presidente (SLV)": 603,
        "FA Cup (ENG)": 145,
        "AFC Champions League Elite": 504
    }
    nombre_liga = st.selectbox("Selecciona Competición", list(ligas_api.keys()))
    league_id = ligas_api[nombre_liga]
    
    fecha_analisis = st.date_input("Selecciona fecha de partidos", datetime.now())
    fecha_str = fecha_analisis.strftime("%Y-%m-%d")
    
    eventos = api_request("get_events", {"from": fecha_str, "to": fecha_str, "league_id": league_id})
    
    if eventos and isinstance(eventos, list):
        opciones_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        partido_sel = st.selectbox("Partidos encontrados", list(opciones_p.keys()))
        
        if st.button("⚡ SINCRONIZAR DATOS"):
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
                
                dl = buscar(data_p['match_hometeam_name'], standings)
                dv = buscar(data_p['match_awayteam_name'], standings)
                
                if dl and dv:
                    pjl, pjv = max(1, int(dl['overall_league_payed'])), max(1, int(dv['overall_league_payed']))
                    st.session_state['lgf_auto'] = float(dl['overall_league_GF']) / pjl
                    st.session_state['lgc_auto'] = float(dl['overall_league_GA']) / pjl
                    st.session_state['vgf_auto'] = float(dv['overall_league_GF']) / pjv
                    st.session_state['vgc_auto'] = float(dv['overall_league_GA']) / pjv
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.success("¡Sincronizado con éxito!")
    
    st.divider()
    p_liga = st.number_input("Promedio Goles Liga", 0.1, 10.0, st.session_state.get('p_liga_auto', 2.5))
    st.subheader("Cuotas del Mercado")
    o1 = st.number_input("Cuota Local", 1.01, 50.0, 2.10)
    ox = st.number_input("Cuota Empate", 1.01, 50.0, 3.20)
    o2 = st.number_input("Cuota Visita", 1.01, 50.0, 3.50)

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 ELITE ANALYSIS</h1>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Equipo L", st.session_state.get('nl_auto', "Local"), label_visibility="collapsed")
    c1, c2 = st.columns(2)
    lgf = c1.number_input("Goles Favor L", 0.0, 10.0, st.session_state.get('lgf_auto', 1.7))
    lgc = c2.number_input("Goles Contra L", 0.0, 10.0, st.session_state.get('lgc_auto', 1.2))
    ltj = c1.number_input("Tarjetas L", 0.0, 15.0, 2.3)
    lco = c2.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Equipo V", st.session_state.get('nv_auto', "Visitante"), label_visibility="collapsed")
    c3, c4 = st.columns(2)
    vgf = c3.number_input("Goles Favor V", 0.0, 10.0, st.session_state.get('vgf_auto', 1.5))
    vgc = c4.number_input("Goles Contra V", 0.0, 10.0, st.session_state.get('vgc_auto', 1.1))
    vtj = c3.number_input("Tarjetas V", 0.0, 15.0, 2.2)
    vco = c4.number_input("Corners V", 0.0, 20.0, 4.8)

if st.button("🚀 PROCESAR ANÁLISIS COMPLETO", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # Sugerencias (Lógica interna)
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
        st.markdown("#### 💎 Veredicto Maestro")
        for s in sugerencias:
            st.markdown(f'<div class="verdict-item"><span style="color:#00ffcc; font-weight:bold;">{s["p"]:.1f}%</span> | {s["t"]}</div>', unsafe_allow_html=True)
    with v_col2:
        st.markdown("#### ⚽ Marcadores Probables")
        for i, (score, prob) in enumerate(res['TOP']):
            st.markdown(f'<div class="score-badge" style="margin-bottom:8px;"><span style="color:#00ffcc; font-weight:bold;">#{i+1}</span> | {score} ({prob:.1f}%)</div>', unsafe_allow_html=True)

    url_wa = f"https://wa.me/?text={urllib.parse.quote('📊 Análisis ProStats OR936 v2.7')}"
    st.markdown(f'<a href="{url_wa}" target="_blank" class="share-btn">📲 COMPARTIR ESTE ANÁLISIS</a>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🏆 Resultados 1X2", "🥅 Goles (O/U)", "🚩 Especiales"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.write("##### Probabilidad Directa")
            dual_bar(nl, res['1X2'][0], "Empate/Visita", res['1X2'][1] + res['1X2'][2])
            dual_bar("Empate", res['1X2'][1], "Local/Visita", res['1X2'][0] + res['1X2'][2], color_left="#aaa")
            dual_bar(nv, res['1X2'][2], "Local/Empate", res['1X2'][0] + res['1X2'][1], color_left="#3498db")
        with c2:
            st.write("##### Doble Oportunidad")
            dual_bar("1X (Local o X)", res['DC'][0], "2 (Visita Directa)", 100-res['DC'][0])
            dual_bar("X2 (Visita o X)", res['DC'][1], "1 (Local Directo)", 100-res['DC'][1])

    with tab2:
        g1, g2 = st.columns(2)
        with g1:
            st.write("##### Over/Under Goles")
            for line in [1.5, 2.5, 3.5]:
                p = res['GOLES'][line]
                dual_bar(f"Over {line}", p[0], f"Under {line}", p[1])
        with g2:
            st.write("##### Ambos Anotan")
            dual_bar("BTTS SÍ", res['BTTS'][0], "BTTS NO", res['BTTS'][1], color_left="#f1c40f", color_right="#95a5a6")

    with tab3:
        tj, co = st.columns(2)
        with tj:
            st.write("🎴 **Tarjetas**")
            dual_bar("Over 4.5", res['TARJETAS'][4.5][0], "Under 4.5", res['TARJETAS'][4.5][1], color_left="#e74c3c")
            dual_bar("Over 5.5", res['TARJETAS'][5.5][0], "Under 5.5", res['TARJETAS'][5.5][1], color_left="#c0392b")
        with co:
            st.write("🚩 **Corners**")
            dual_bar("Over 8.5", res['CORNERS'][8.5][0], "Under 8.5", res['CORNERS'][8.5][1], color_left="#2ecc71")
            dual_bar("Over 9.5", res['CORNERS'][9.5][0], "Under 9.5", res['CORNERS'][9.5][1], color_left="#27ae60")

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8em;'>ProStats Engine OR936 v2.7 | Sistema de Análisis Bidimensional</p>", unsafe_allow_html=True)
