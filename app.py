import streamlit as st
import math
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN API
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

# Inicialización de estados
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"

# Limpieza de caché si la API falla
@st.cache_data(ttl=600) # Reducido a 10 min para evitar datos estancados
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=15)
        data = res.json()
        if isinstance(data, list) and len(data) > 0: return data
        return []
    except: return []

# =================================================================
# COMPONENTES VISUALES PREMIUM
# =================================================================
def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin-top: 20px; margin-bottom: 25px; background: #161b22; padding: 20px; border-radius: 20px; border: 1px solid #30363d; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <p style='color:#8b949e; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:15px;'>ANÁLISIS DE RESULTADO DIRECTO (1X2)</p>
            <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight:600; margin-bottom: 10px; color: #e1e1e1;">
                <span style="color:#00ffcc;">{n1}: {p1:.1f}%</span>
                <span style="color:#8b949e;">{nx}: {px_val:.1f}%</span>
                <span style="color:#3498db;">{n2}: {p2:.1f}%</span>
            </div>
            <div style="display: flex; height: 12px; border-radius: 10px; overflow: hidden; background: #30363d;">
                <div style="width: {p1}%; background: #00ffcc;"></div>
                <div style="width: {px_val}%; background: #444;"></div>
                <div style="width: {p2}%; background: #3498db;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffcc"):
    st.markdown(f"""
        <div style="margin-bottom: 18px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight:600; color: #e1e1e1; margin-bottom: 6px;">
                <span>{label_over}: {prob_over:.1f}%</span>
                <span>{label_under}: {prob_under:.1f}%</span>
            </div>
            <div style="display: flex; background: #30363d; height: 8px; border-radius: 10px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color};"></div>
                <div style="width: {prob_under}%; background: rgba(255,255,255,0.05);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

class MotorMatematico:
    def __init__(self): self.rho = -0.15
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
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}
        for i in range(10): 
            fila = []
            for j in range(10):
                p = max(0, (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v))
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += p
                    else: g_probs[t][1] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)
        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "TARJETAS": {t: self.calcular_ou_prob(tj_total, t) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: self.calcular_ou_prob(co_total, t) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz
        }

# =================================================================
# INTERFAZ Y SIDEBAR
# =================================================================
st.set_page_config(page_title="OR936 Elite v3.2", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #e1e1e1; }
    .stApp { background-color: #0b0e11; }
    .master-card { background: #161b22; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 20px; }
    .verdict-item { background: rgba(0, 255, 204, 0.05); border-left: 3px solid #00ffcc; padding: 12px; margin-bottom: 10px; border-radius: 0 10px 10px 0; font-weight: 600; display: flex; justify-content: space-between; }
    .score-badge { background: #1c2128; padding: 15px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 10px; text-align: center; }
    .stButton>button { background: linear-gradient(90deg, #00ffcc 0%, #008577 100%); color: #000 !important; font-weight: 800; border: none; padding: 15px; border-radius: 12px; text-transform: uppercase; letter-spacing: 1px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#00ffcc;'>⚙️ PANEL API</h2>", unsafe_allow_html=True)
    ligas_api = {"La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, "UEFA Champions": 3, "Libertadores": 13, "Brasil Serie A": 99, "Liga Mayor SLV": 601, "Copa SLV": 603}
    nombre_liga = st.selectbox("Liga", list(ligas_api.keys()))
    fecha_analisis = st.date_input("Fecha", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    p_sel = "manual"
    if eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("Seleccionar Partido", list(op_p.keys()))

        if st.button("⚡ SINCRONIZAR DATOS"):
            # 1. Obtener Tabla de Posiciones
            standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
            
            if standings:
                # Calcular promedio de la liga
                try:
                    total_g = sum(int(t['overall_league_GF']) for t in standings)
                    total_pj = sum(int(t['overall_league_payed']) for t in standings)
                    st.session_state['p_liga_auto'] = float(total_g / (total_pj / 2)) if total_pj > 0 else 2.5
                except: pass

                # Función de búsqueda robusta
                def buscar_equipo(nombre_api):
                    for t in standings:
                        # Buscamos coincidencia exacta o contenida
                        if nombre_api.lower().strip() in t['team_name'].lower().strip() or t['team_name'].lower().strip() in nombre_api.lower().strip():
                            return t
                    return None

                # 2. Identificar equipos del partido seleccionado
                match_data = op_p[p_sel]
                home_stat = buscar_equipo(match_data['match_hometeam_name'])
                away_stat = buscar_equipo(match_data['match_awayteam_name'])

                if home_stat and away_stat:
                    # Reset de llaves manuales para forzar actualización
                    keys_to_clear = [f"slider_goles_{p_sel}", f"lgf_{p_sel}", f"lgc_{p_sel}", f"vgf_{p_sel}", f"vgc_{p_sel}"]
                    for k in keys_to_clear:
                        if k in st.session_state: del st.session_state[k]

                    # Guardar promedios reales
                    pj_h = int(home_stat['overall_league_payed'])
                    pj_a = int(away_stat['overall_league_payed'])
                    
                    st.session_state['lgf_auto'] = float(home_stat['overall_league_GF']) / pj_h if pj_h > 0 else 1.5
                    st.session_state['lgc_auto'] = float(home_stat['overall_league_GA']) / pj_h if pj_h > 0 else 1.2
                    st.session_state['vgf_auto'] = float(away_stat['overall_league_GF']) / pj_a if pj_a > 0 else 1.3
                    st.session_state['vgc_auto'] = float(away_stat['overall_league_GA']) / pj_a if pj_a > 0 else 1.1
                    st.session_state['nl_auto'] = home_stat['team_name']
                    st.session_state['nv_auto'] = away_stat['team_name']
                    
                    st.success(f"Sincronizado: {home_stat['team_name']} vs {away_stat['team_name']}")
                    st.rerun()
                else:
                    st.error("No se encontraron estadísticas para estos equipos en la tabla.")

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 ELITE ANALYSIS v3.2</h1>", unsafe_allow_html=True)

# ENTRADA DE DATOS
col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<h3 style='color:#00ffcc;'>🏠 Local</h3>", unsafe_allow_html=True)
    nl = st.text_input("Nombre", st.session_state.get('nl_auto', "Local"), key=f"name_l_{p_sel}")
    la, lb = st.columns(2)
    lgf = la.number_input("Favor L", 0.0, 10.0, st.session_state.get('lgf_auto', 1.7), step=0.1, key=f"lgf_{p_sel}")
    lgc = lb.number_input("Contra L", 0.0, 10.0, st.session_state.get('lgc_auto', 1.2), step=0.1, key=f"lgc_{p_sel}")
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.3, step=0.1, key=f"ltj_{p_sel}"), lb.number_input("Corners L", 0.0, 20.0, 5.5, step=0.1, key=f"lco_{p_sel}")

with col_v:
    st.markdown("<h3 style='color:#3498db;'>🚀 Visitante</h3>", unsafe_allow_html=True)
    nv = st.text_input("Nombre", st.session_state.get('nv_auto', "Visitante"), key=f"name_v_{p_sel}")
    va, vb = st.columns(2)
    vgf = va.number_input("Favor V", 0.0, 10.0, st.session_state.get('vgf_auto', 1.5), step=0.1, key=f"vgf_{p_sel}")
    vgc = vb.number_input("Contra V", 0.0, 10.0, st.session_state.get('vgc_auto', 1.1), step=0.1, key=f"vgc_{p_sel}")
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, 2.2, step=0.1, key=f"vtj_{p_sel}"), vb.number_input("Corners V", 0.0, 20.0, 4.8, step=0.1, key=f"vco_{p_sel}")

p_liga = st.slider("Media Goles Liga", 0.5, 5.0, value=st.session_state.get('p_liga_auto', 2.5), key=f"slider_goles_{p_sel}")

if st.button("🚀 PROCESAR ANÁLISIS ELITE", use_container_width=True):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "BTTS SÍ", "p": res['BTTS'][0]}]
    for line, p in res['GOLES'].items():
        if 1.5 <= line <= 3.5:
            pool.append({"t": f"Over {line} Goles", "p": p[0]})
            pool.append({"t": f"Under {line} Goles", "p": p[1]})
    sug = sorted([s for s in pool if 65 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:6]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.2, 1])
    with v1:
        st.markdown("<h4 style='color:#8b949e; font-size:0.8rem;'>💎 SUGERENCIAS MAESTRAS</h4>", unsafe_allow_html=True)
        for s in sug: st.markdown(f'<div class="verdict-item"><span>{s["t"]}</span> <span style="color:#00ffcc;">{s["p"]:.1f}%</span></div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#8b949e; font-size:0.8rem;'>⚽ MARCADORES PROBABLES</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge"><b style="font-size:1.2rem; color:#00ffcc;">{score}</b><br>{prob:.1f}%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "Empate", nv)

    tab_g, tab_spec, tab_m = st.tabs(["🥅 Goles", "🚩 Especiales", "📊 Matriz"])
    with tab_g:
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            p = res['GOLES'][line]
            dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1])
    with tab_spec:
        tj_sec, co_sec = st.columns(2)
        with tj_sec:
            for line, p in res['TARJETAS'].items(): dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color="#e74c3c")
        with co_sec:
            for line, p in res['CORNERS'].items(): dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color="#2ecc71")
    with tab_m:
        fig = px.imshow(pd.DataFrame(res['MATRIZ']), labels=dict(x="Visitante", y="Local", color="%"), x=[str(i) for i in range(6)], y=[str(i) for i in range(6)], color_continuous_scale='Viridis', text_auto=".1f")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#e1e1e1")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align: center; color: #555; font-size: 0.8rem;'>OR936 Elite v3.2 | Sync Optimizado</p>", unsafe_allow_html=True)
