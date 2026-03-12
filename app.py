import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime
import urllib.parse
from fuzzywuzzy import fuzz, process

# =================================================================
# CONFIGURACIÓN API
# =================================================================
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

# Inicialización persistente de estados
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.0
if 'form_l' not in st.session_state: st.session_state['form_l'] = 1.0
if 'form_v' not in st.session_state: st.session_state['form_v'] = 1.0
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
        data = res.json()
        return data if isinstance(data, list) else []
    except: return []

# =================================================================
# MOTOR MATEMÁTICO ELITE
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        if league_avg > 3.0: self.rho = -0.10
        elif league_avg < 2.2: self.rho = -0.18
        else: self.rho = -0.15

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

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines, h_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5], [-1.5, -0.5, 0.5, 1.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}
        h_probs = {t: 0.0 for t in h_lines}

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
                for h in h_lines:
                    if (i + h) > j: h_probs[h] += p
                
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        iteraciones = 15000
        sim_tj = np.random.poisson(tj_total, iteraciones)
        sim_co = np.random.poisson(co_total, iteraciones)
        tj_probs = {t: (np.sum(sim_tj > t)/iteraciones*100, np.sum(sim_tj <= t)/iteraciones*100) for t in [2.5, 3.5, 4.5, 5.5, 6.5]}
        co_probs = {t: (np.sum(sim_co > t)/iteraciones*100, np.sum(sim_co <= t)/iteraciones*100) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]}
        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAP": {t: p/total*100 for t, p in h_probs.items()},
            "TARJETAS": tj_probs, "CORNERS": co_probs,
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# DISEÑO UI/UX
# =================================================================
st.set_page_config(page_title="OR936 PRO ELITE", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: radial-gradient(circle at top right, #1a1f25, #0a0c10); }
    .master-card { background: rgba(22, 27, 34, 0.7); padding: 30px; border-radius: 20px; border: 1px solid rgba(212, 175, 55, 0.2); box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 25px; backdrop-filter: blur(10px); }
    .verdict-item { background: linear-gradient(90deg, rgba(0, 255, 163, 0.1) 0%, rgba(0,0,0,0) 100%); border-left: 3px solid #00ffa3; padding: 12px 15px; margin-bottom: 10px; border-radius: 4px 12px 12px 4px; color: #e0e0e0; font-size: 0.95em; }
    .elite-alert { background: linear-gradient(90deg, rgba(0, 255, 163, 0.2) 0%, rgba(212, 175, 55, 0.1) 100%); border: 1px solid #00ffa3; box-shadow: 0 0 15px rgba(0, 255, 163, 0.3); font-weight: 700; }
    .score-badge { background: #000; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 8px; text-align: center; color: #d4af37; font-weight: 900; font-size: 1.1em; letter-spacing: 1px; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #aa8a2e 100%); color: #000 !important; font-weight: 800; border: none; padding: 15px; border-radius: 12px; text-transform: uppercase; letter-spacing: 2px; transition: all 0.3s ease; width: 100%; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background-color: #25D366; color: white !important; padding: 12px; border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 0.9em; margin-top: 10px; text-align: center; }
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
# SIDEBAR - LÓGICA DE SINCRONIZACIÓN MEJORADA
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Brasileirão Betano (Série A)": 99, "Brasileirão Série B": 100, "Brasileirão Série C": 103, "Copa de Brasil": 101,
        "Premier League (Inglaterra)": 152, "La Liga (España)": 302, "Serie A (Italia)": 207, "Bundesliga (Alemania)": 175, "Ligue 1 (Francia)": 168, 
        "UEFA Champions League": 3, "UEFA Europa League": 4, "UEFA Conference League": 683, "Copa Libertadores": 13,
        "FA Cup (Inglaterra)": 145, "EFL Cup (Inglaterra)": 146, "Copa del Rey (España)": 300, "Coppa Italia (Italia)": 209, "DFB Pokal (Alemania)": 177, "Coupe de France (Francia)": 169,
        "Liga Mayor (El Salvador)": 601, "Copa Presidente (El Salvador)": 603
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha de Jornada", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Eventos en Vivo", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Analizando métricas de competición..."):
                standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
                if standings and isinstance(standings, list):
                    # Robustez en llaves: 'payed' o 'played'
                    g_h = sum(int(t.get('home_league_GF', 0)) for t in standings)
                    g_a = sum(int(t.get('away_league_GF', 0)) for t in standings)
                    pj_total = sum(int(t.get('overall_league_payed', t.get('overall_league_played', 0))) for t in standings)

                    if pj_total > 0:
                        st.session_state['p_liga_auto'] = float((g_h + g_a) / (pj_total / 2))
                        st.session_state['hfa_league'] = float(g_h / g_a) if g_a > 0 else 1.0

                    def buscar_fuzzy(n, lista):
                        nombres = [t['team_name'] for t in lista]
                        match, score = process.extractOne(n, nombres, scorer=fuzz.token_set_ratio)
                        return next((t for t in lista if t['team_name'] == match), None) if score > 65 else None

                    dl = buscar_fuzzy(op_p[p_sel]['match_hometeam_name'], standings)
                    dv = buscar_fuzzy(op_p[p_sel]['match_awayteam_name'], standings)
                    
                    if dl and dv:
                        st.session_state['form_l'] = 1.15 if int(dl['overall_league_position']) < int(dv['overall_league_position']) else 0.95
                        st.session_state['form_v'] = 1.10 if int(dv['overall_league_position']) < int(dl['overall_league_position']) else 0.90
                        
                        pj_h = int(dl.get('home_league_payed', dl.get('home_league_played', 1)))
                        pj_v = int(dv.get('away_league_payed', dv.get('away_league_played', 1)))
                        
                        st.session_state['lgf_auto'] = float(dl.get('home_league_GF', 0)) / (pj_h if pj_h > 0 else 1)
                        st.session_state['lgc_auto'] = float(dl.get('home_league_GA', 0)) / (pj_h if pj_h > 0 else 1)
                        st.session_state['vgf_auto'] = float(dv.get('away_league_GF', 0)) / (pj_v if pj_v > 0 else 1)
                        st.session_state['vgc_auto'] = float(dv.get('away_league_GA', 0)) / (pj_v if pj_v > 0 else 1)
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.rerun()

# CONTENIDO PRINCIPAL
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666; font-size: 0.9em; margin-bottom: 40px;'>PREDICTIVE INTELLIGENCE ENGINE V3.5 PRO + FUZZY MONTE CARLO</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-left: 2px solid #00ffa3; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🏠 LOCAL</h3></div>", unsafe_allow_html=True)
    nl = st.text_input("Nombre", key='nl_auto', label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("Goles Favor L", 0.0, 10.0, step=0.1, key='lgf_auto'), lb.number_input("Goles Contra L", 0.0, 10.0, step=0.1, key='lgc_auto')
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.3, step=0.1), lb.number_input("Corners L", 0.0, 20.0, 5.5, step=0.1)

with col_v:
    st.markdown("<div style='border-left: 2px solid #d4af37; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🚀 VISITANTE</h3></div>", unsafe_allow_html=True)
    nv = st.text_input("Nombre", key='nv_auto', label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("Goles Favor V", 0.0, 10.0, step=0.1, key='vgf_auto'), vb.number_input("Goles Contra V", 0.0, 10.0, step=0.1, key='vgc_auto')
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, 2.2, step=0.1), vb.number_input("Corners V", 0.0, 20.0, 4.8, step=0.1)

p_liga = st.slider("Media de Goles de la Liga (Referencia)", 0.5, 5.0, key='p_liga_auto')

b1, b2 = st.columns([2, 1])
with b1: generar = st.button("GENERAR REPORTE DE INTELIGENCIA")

if generar:
    motor = MotorMatematico(league_avg=p_liga)
    hfa = st.session_state['hfa_league']
    f_l, f_v = st.session_state['form_l'], st.session_state['form_v']
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * hfa * f_l
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/hfa) * f_v
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    pool = [{"t": "Doble Oportunidad 1X", "p": res['DC'][0]}, {"t": "Doble Oportunidad X2", "p": res['DC'][1]}, {"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]}]
    for line, p in res['GOLES'].items():
        if 1.5 <= line <= 3.5: pool.append({"t": f"Over {line} Goles", "p": p[0]})

    sug = sorted([s for s in pool if 65 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:6]

    msg = f"*OR936 ELITE PRO*\n⚽ {nl} vs {nv}\n\n*TOP PICKS:*\n"
    for s in sug: msg += f"• {s['t']}: {s['p']:.1f}%\n"
    encoded_msg = urllib.parse.quote(msg + f"\n*MARCADOR:* {res['TOP'][0][0]}\n*CONFIANZA:* {res['BRIER']*100:.1f}%")
    with b2: st.markdown(f'<a href="https://wa.me/?text={encoded_msg}" target="_blank" class="whatsapp-btn">📲 COMPARTIR</a>', unsafe_allow_html=True)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:#d4af37; margin-top:0;'>💎 TOP SELECCIONES ELITE (Confianza: {res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
        for s in sug:
            clase = "elite-alert" if s['p'] > 85 else ""
            st.markdown(f'<div class="verdict-item {clase}"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; margin-top:0;'>⚽ MARCADOR EXACTO</h4>", unsafe_allow_html=True)
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge">{score} <span style="font-weight:300; font-size:0.7em; color:#888;">({prob:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "Empate", nv)
    
    # REORDENAMIENTO DE PESTAÑAS
    tab_dc, tab_g, tab_h, tab_spec, tab_m = st.tabs(["🏆 MERCADOS 1X2", "🥅 GOLES", "⚖️ HANDICAP", "🚩 ESPECIALES", "📊 MATRIZ"])
    
    with tab_dc:
        dual_bar_explicit(f"1X ({nl} o Empate)", res['DC'][0], f"2 Directo", 100-res['DC'][0], color="#d4af37")
        dual_bar_explicit(f"X2 ({nv} o Empate)", res['DC'][1], f"1 Directo", 100-res['DC'][1], color="#d4af37")
        dual_bar_explicit(f"12 (Cualquiera Gana)", res['DC'][2], "Empate", 100-res['DC'][2], color="#00ffa3")
    
    with tab_g:
        ga, gb = st.columns(2)
        with ga:
            for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with gb: dual_bar_explicit("AMBOS ANOTAN: SÍ", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")
    
    with tab_h:
        st.markdown(f"<h5 style='color:#d4af37; margin-bottom:20px;'>LÍNEAS DE HANDICAP (Referencia: {nl})</h5>", unsafe_allow_html=True)
        for h, prob in res['HANDICAP'].items():
            signo = "+" if h > 0 else ""
            dual_bar_explicit(f"H. Asiático {signo}{h}", prob, f"H. Rival", 100-prob, color="#00ffa3")

    with tab_spec:
        tj_sec, co_sec = st.columns(2)
        with tj_sec:
            st.markdown("<h5 style='color:#d4af37;'>🎴 TARJETAS</h5>", unsafe_allow_html=True)
            for l, p in res['TARJETAS'].items(): dual_bar_explicit(f"Over {l}", p[0], f"Under {l}", p[1], color="#ff4b4b")
        with co_sec:
            st.markdown("<h5 style='color:#00ffa3;'>🚩 TIROS DE ESQUINA</h5>", unsafe_allow_html=True)
            for l, p in res['CORNERS'].items(): dual_bar_explicit(f"Over {l}", p[0], f"Under {l}", p[1], color="#00ffa3")
    
    with tab_m:
        fig = px.imshow(pd.DataFrame(res['MATRIZ']), labels=dict(x="Visitante", y="Local", color="%"), x=[str(i) for i in range(6)], y=[str(i) for i in range(6)], color_continuous_scale=['#0a0c10', '#00ffa3', '#d4af37'], text_auto=".1f")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#eee")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<br><br><p style='text-align: center; color: #444; font-size: 0.7em; letter-spacing: 2px;'>SYSTEM AUTHENTICATED | FUZZY MATCHING ACTIVE | DIXON-COLES MODEL | OR936 ELITE v3.5 PRO</p>", unsafe_allow_html=True)
