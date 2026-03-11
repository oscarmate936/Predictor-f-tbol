import streamlit as st
import math
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# =================================================================
# CONFIGURACIÓN API (Inalterada)
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.7
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.2
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.5
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.1

@st.cache_data(ttl=3600)
def api_request(action, params=None):
    if params is None: params = {}
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except:
        return []

# =================================================================
# MOTOR MATEMÁTICO (Inalterado)
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
# DISEÑO PREMIUM (UI/UX CUSTOM)
# =================================================================
st.set_page_config(page_title="OR936 PRO ELITE", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: radial-gradient(circle at top right, #1a1f25, #0a0c10); }
    
    /* Contenedores Principales */
    .master-card { 
        background: rgba(22, 27, 34, 0.7); 
        padding: 30px; 
        border-radius: 20px; 
        border: 1px solid rgba(212, 175, 55, 0.2); 
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        margin-bottom: 25px;
        backdrop-filter: blur(10px);
    }

    /* Veredictos */
    .verdict-item { 
        background: linear-gradient(90deg, rgba(0, 255, 163, 0.1) 0%, rgba(0,0,0,0) 100%);
        border-left: 3px solid #00ffa3; 
        padding: 12px 15px; 
        margin-bottom: 10px; 
        border-radius: 4px 12px 12px 4px;
        color: #e0e0e0;
        font-size: 0.95em;
    }
    
    /* Marcadores */
    .score-badge { 
        background: #000; 
        padding: 12px; 
        border-radius: 12px; 
        border: 1px solid #333; 
        margin-bottom: 8px; 
        text-align: center;
        color: #d4af37;
        font-weight: 900;
        font-size: 1.1em;
        letter-spacing: 1px;
    }

    /* Botón Pro */
    .stButton>button { 
        background: linear-gradient(135deg, #d4af37 0%, #aa8a2e 100%); 
        color: #000 !important; 
        font-weight: 800; 
        border: none; 
        padding: 15px; 
        border-radius: 12px; 
        text-transform: uppercase;
        letter-spacing: 2px;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover { 
        box-shadow: 0 0 20px rgba(212, 175, 55, 0.4); 
        transform: translateY(-2px);
    }

    /* Inputs */
    .stNumberInput, .stTextInput { border-radius: 8px; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0a0c10; border-right: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

def triple_bar(p1, px_val, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin: 25px 0; background: #000; padding: 20px; border-radius: 15px; border: 1px solid #222;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #888; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 1px;">
                <span style="color:#00ffa3">{n1}: <b>{p1:.1f}%</b></span>
                <span>{nx}: <b>{px_val:.1f}%</b></span>
                <span style="color:#d4af37">{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: #111;">
                <div style="width: {p1}%; background: #00ffa3; box-shadow: 0 0 15px rgba(0,255,163,0.4);"></div>
                <div style="width: {px_val}%; background: #333;"></div>
                <div style="width: {p2}%; background: #d4af37; box-shadow: 0 0 15px rgba(212,175,55,0.4);"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffa3"):
    st.markdown(f"""
        <div style="margin-bottom: 18px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #bbb; margin-bottom: 6px;">
                <span>{label_over}: <b>{prob_over:.1f}%</b></span>
                <span style="opacity: 0.6;">{prob_under:.1f}% : {label_under}</span>
            </div>
            <div style="display: flex; background: #000; height: 8px; border-radius: 4px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color}; box-shadow: 0 0 8px {color}66;"></div>
                <div style="width: {prob_under}%; background: #1a1a1a;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# INTERFAZ Y SIDEBAR
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, 
        "UEFA Champions": 3, "Copa Libertadores": 13, "Brasileirão Serie A": 99, 
        "Liga Mayor SLV": 601, "Copa Presidente SLV": 603, "FA Cup": 145
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha de Jornada", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Eventos en Vivo", list(op_p.keys()))

        if st.button("SYNC DATA"):
            standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
            if standings and isinstance(standings, list):
                total_g = sum(int(t['overall_league_GF']) for t in standings)
                total_pj = sum(int(t['overall_league_payed']) for t in standings)

                llaves = ['p_liga_auto', 'lgf_auto', 'lgc_auto', 'vgf_auto', 'vgc_auto', 'nl_auto', 'nv_auto']
                for k in llaves:
                    if k in st.session_state: del st.session_state[k]

                st.session_state['p_liga_auto'] = float(total_g / (total_pj / 2)) if total_pj > 0 else 2.5

                def buscar(n):
                    for t in standings: 
                        if n.lower() in t['team_name'].lower() or t['team_name'].lower() in n.lower(): return t
                    return None

                dl, dv = buscar(op_p[p_sel]['match_hometeam_name']), buscar(op_p[p_sel]['match_awayteam_name'])
                if dl and dv:
                    st.session_state['lgf_auto'] = float(dl['overall_league_GF'])/int(dl['overall_league_payed'])
                    st.session_state['lgc_auto'] = float(dl['overall_league_GA'])/int(dl['overall_league_payed'])
                    st.session_state['vgf_auto'] = float(dv['overall_league_GF'])/int(dv['overall_league_payed'])
                    st.session_state['vgc_auto'] = float(dv['overall_league_GA'])/int(dv['overall_league_payed'])
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.rerun()

# CONTENIDO PRINCIPAL
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666; font-size: 0.9em; margin-bottom: 40px;'>PREDICTIVE INTELLIGENCE ENGINE V3.2</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-left: 2px solid #00ffa3; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🏠 LOCAL</h3></div>", unsafe_allow_html=True)
    nl = st.text_input("Nombre", key='nl_auto', label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf = la.number_input("Goles Favor L", 0.0, 10.0, step=0.1, key='lgf_auto')
    lgc = lb.number_input("Goles Contra L", 0.0, 10.0, step=0.1, key='lgc_auto')
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.3, step=0.1), lb.number_input("Corners L", 0.0, 20.0, 5.5, step=0.1)

with col_v:
    st.markdown("<div style='border-left: 2px solid #d4af37; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🚀 VISITANTE</h3></div>", unsafe_allow_html=True)
    nv = st.text_input("Nombre", key='nv_auto', label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf = va.number_input("Goles Favor V", 0.0, 10.0, step=0.1, key='vgf_auto')
    vgc = vb.number_input("Goles Contra V", 0.0, 10.0, step=0.1, key='vgc_auto')
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, 2.2, step=0.1), vb.number_input("Corners V", 0.0, 20.0, 4.8, step=0.1)

st.markdown("<br>", unsafe_allow_html=True)
p_liga = st.slider("Media de Goles de la Liga (Referencia)", 0.5, 5.0, key='p_liga_auto')

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    motor = MotorMatematico()
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    # SUGERENCIAS
    pool = []
    pool.append({"t": "Doble Oportunidad 1X", "p": res['DC'][0]})
    pool.append({"t": "Doble Oportunidad X2", "p": res['DC'][1]})
    pool.append({"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]})
    for line, p in res['GOLES'].items():
        if 1.5 <= line <= 3.5:
            pool.append({"t": f"Over {line} Goles", "p": p[0]})
            pool.append({"t": f"Under {line} Goles", "p": p[1]})

    sug = sorted([s for s in pool if 65 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:6]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown("<h4 style='color:#d4af37; margin-top:0;'>💎 TOP SELECCIONES ELITE</h4>", unsafe_allow_html=True)
        for s in sug: st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; margin-top:0;'>⚽ MARCADOR EXACTO</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']:
            st.markdown(f'<div class="score-badge">{score} <span style="font-weight:300; font-size:0.7em; color:#888;">({prob:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "Empate", nv)

    tab_g, tab_dc, tab_spec, tab_m = st.tabs(["🥅 GOLES", "🏆 MERCADOS 1X2", "🚩 ESPECIALES", "📊 MATRIZ"])

    with tab_g:
        ga, gb = st.columns(2)
        with ga:
            for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
                p = res['GOLES'][line]
                dual_bar_explicit(f"OVER {line}", p[0], f"UNDER {line}", p[1])
        with gb:
            dual_bar_explicit("AMBOS ANOTAN: SÍ", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")

    with tab_dc:
        dual_bar_explicit(f"1X ({nl} o Empate)", res['DC'][0], f"2 Directo", 100-res['DC'][0], color="#d4af37")
        dual_bar_explicit(f"X2 ({nv} o Empate)", res['DC'][1], f"1 Directo", 100-res['DC'][1], color="#d4af37")
        dual_bar_explicit(f"12 (Cualquiera Gana)", res['DC'][2], "Empate", 100-res['DC'][2], color="#00ffa3")

    with tab_spec:
        tj_sec, co_sec = st.columns(2)
        with tj_sec:
            st.markdown("<h5 style='color:#d4af37;'>🎴 TARJETAS</h5>", unsafe_allow_html=True)
            for line, p in res['TARJETAS'].items():
                dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color="#ff4b4b")
        with co_sec:
            st.markdown("<h5 style='color:#00ffa3;'>🚩 TIROS DE ESQUINA</h5>", unsafe_allow_html=True)
            for line, p in res['CORNERS'].items(): 
                dual_bar_explicit(f"Over {line}", p[0], f"Under {line}", p[1], color="#00ffa3")

    with tab_m:
        df_matriz = pd.DataFrame(res['MATRIZ'])
        fig = px.imshow(df_matriz, 
                        labels=dict(x="Goles Visitante", y="Goles Local", color="%"),
                        x=[str(i) for i in range(6)],
                        y=[str(i) for i in range(6)],
                        color_continuous_scale=['#0a0c10', '#00ffa3', '#d4af37'], text_auto=".1f")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#eee")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<br><br><p style='text-align: center; color: #444; font-size: 0.7em; letter-spacing: 2px;'>SYSTEM AUTHENTICATED | DIXON-COLES MODEL | OR936 ELITE v3.2</p>", unsafe_allow_html=True)