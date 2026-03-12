import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime
import urllib.parse

# =================================================================
# CONFIGURACIÓN SEGURA Y API
# =================================================================
try:
    API_KEY = st.secrets["FOOTBALL_API_KEY"]
except:
    # Si no está en secrets, usamos la que tenías (pero se recomienda configurar secrets)
    API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"

BASE_URL = "https://apiv3.apifootball.com/"

# Inicialización de estados
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
        return res.json() if res.status_code == 200 else []
    except: return []

# =================================================================
# MOTOR MATEMÁTICO V3.5 (Dixon-Coles + NumPy + Handicap)
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.10 if league_avg > 3.0 else -0.18 if league_avg < 2.2 else -0.15

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
        # 1. MATRIZ BASE Y MERCADOS PRINCIPALES
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}

        for i in range(12): # Ampliamos rango para precisión de hándicap
            fila = []
            for j in range(12):
                prob = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                prob = max(0, prob)
                if i > j: p1 += prob
                elif i == j: px += prob
                else: p2 += prob
                if i > 0 and j > 0: btts_si += prob
                for t in g_lines:
                    if (i + j) > t: g_probs[t][0] += prob
                    else: g_probs[t][1] += prob
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = prob * 100
                if i < 6 and j < 6: fila.append(prob * 100)
            if i < 6: matriz.append(fila)

        # 2. HÁNDICAPS (Cálculo sobre la matriz de 12x12)
        h_lines = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
        h_res = {}
        for h in h_lines:
            p_h_l = 0
            for i in range(12):
                for j in range(12):
                    p_score = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                    if (i + h) > j: p_h_l += p_score
            h_res[h] = (p_h_l * 100, (1 - p_h_l) * 100)

        # 3. MONTECARLO VECTORIZADO (NumPy)
        iteraciones = 15000
        s_tj = np.random.poisson(tj_total, iteraciones)
        s_co = np.random.poisson(co_total, iteraciones)
        
        tarjetas = {t: (np.mean(s_tj > t)*100, np.mean(s_tj <= t)*100) for t in [2.5, 3.5, 4.5, 5.5, 6.5]}
        corners = {t: (np.mean(s_co > t)*100, np.mean(s_co <= t)*100) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]}

        total = p1 + px + p2
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": h_res,
            "TARJETAS": tarjetas,
            "CORNERS": corners,
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz,
            "BRIER": confianza
        }

# =================================================================
# UI/UX - ESTILOS
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
# SIDEBAR - SINCRONIZACIÓN CORREGIDA
# =================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_api = {
        "Brasileirão Betano (A)": 99, "Brasileirão Série B": 100, "Premier League": 152, "La Liga": 302, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, 
        "Champions League": 3, "Europa League": 4, "Libertadores": 13, "Liga Mayor (ES)": 601
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_api.keys()))
    fecha_analisis = st.date_input("📅 Fecha", datetime.now())

    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})

    if eventos and isinstance(eventos, list) and "error" not in eventos:
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("📍 Eventos", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Sincronizando..."):
                standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
                if standings and isinstance(standings, list) and "error" not in standings:
                    h_goals = sum(int(t.get('home_league_GF', 0)) for t in standings)
                    a_goals = sum(int(t.get('away_league_GF', 0)) for t in standings)
                    total_pj = sum(int(t.get('overall_league_payed', 0)) for t in standings)
                    
                    st.session_state['p_liga_auto'] = float((h_goals + a_goals) / (total_pj / 2)) if total_pj > 0 else 2.5
                    st.session_state['hfa_league'] = float(h_goals / a_goals) if a_goals > 0 else 1.0

                    def buscar_flexible(nombre):
                        n = nombre.lower().strip()
                        for t in standings:
                            tn = t['team_name'].lower().strip()
                            if n in tn or tn in n: return t
                        return None

                    dl = buscar_flexible(op_p[p_sel]['match_hometeam_name'])
                    dv = buscar_flexible(op_p[p_sel]['match_awayteam_name'])

                    if dl and dv:
                        pj_h, pj_v = int(dl.get('home_league_payed', 1)), int(dv.get('away_league_payed', 1))
                        st.session_state['lgf_auto'] = float(dl['home_league_GF'])/pj_h if pj_h>0 else 1.2
                        st.session_state['lgc_auto'] = float(dl['home_league_GA'])/pj_h if pj_h>0 else 1.0
                        st.session_state['vgf_auto'] = float(dv['away_league_GF'])/pj_v if pj_v>0 else 1.0
                        st.session_state['vgc_auto'] = float(dv['away_league_GA'])/pj_v if pj_v>0 else 1.2
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.success(f"Sincronizado: {dl['team_name']} vs {dv['team_name']}")
                        st.rerun()
                    else:
                        st.error("No se encontró uno de los equipos en la tabla de esta liga.")

# =================================================================
# CONTENIDO PRINCIPAL
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff; font-weight: 900; margin-bottom: 0;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666; font-size: 0.9em; margin-bottom: 40px;'>V3.5 PRO: DIXON-COLES + HANDICAPS + NUMPY ENGINE</p>", unsafe_allow_html=True)

col_l, col_v = st.columns(2)
with col_l:
    st.markdown("<div style='border-left: 2px solid #00ffa3; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🏠 LOCAL</h3></div>", unsafe_allow_html=True)
    nl = st.text_input("Nombre", key='nl_auto', label_visibility="collapsed")
    la, lb = st.columns(2)
    lgf, lgc = la.number_input("GF L", 0.0, 10.0, step=0.1, key='lgf_auto'), lb.number_input("GC L", 0.0, 10.0, step=0.1, key='lgc_auto')
    ltj, lco = la.number_input("Tj L", 0.0, 15.0, 2.3, step=0.1), lb.number_input("Cr L", 0.0, 20.0, 5.5, step=0.1)

with col_v:
    st.markdown("<div style='border-left: 2px solid #d4af37; padding-left: 15px;'><h3 style='margin-bottom:20px; color:#fff;'>🚀 VISITANTE</h3></div>", unsafe_allow_html=True)
    nv = st.text_input("Nombre", key='nv_auto', label_visibility="collapsed")
    va, vb = st.columns(2)
    vgf, vgc = va.number_input("GF V", 0.0, 10.0, step=0.1, key='vgf_auto'), vb.number_input("GC V", 0.0, 10.0, step=0.1, key='vgc_auto')
    vtj, vco = va.number_input("Tj V", 0.0, 15.0, 2.2, step=0.1), vb.number_input("Cr V", 0.0, 20.0, 4.8, step=0.1)

p_liga = st.slider("Media Goles Liga", 0.5, 5.0, key='p_liga_auto')

b1, b2 = st.columns([2, 1])
with b1: generar = st.button("GENERAR REPORTE DE INTELIGENCIA")

if generar:
    motor = MotorMatematico(league_avg=p_liga)
    hfa, f_l, f_v = st.session_state['hfa_league'], st.session_state['form_l'], st.session_state['form_v']
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * hfa * f_l
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * (1/hfa) * f_v
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)

    pool = [{"t": "1X", "p": res['DC'][0]}, {"t": "X2", "p": res['DC'][1]}, {"t": "BTTS: SI", "p": res['BTTS'][0]}]
    for line, p in res['GOLES'].items():
        if 1.5 <= line <= 3.5:
            pool.append({"t": f"Over {line}", "p": p[0]}); pool.append({"t": f"Under {line}", "p": p[1]})
    sug = sorted([s for s in pool if 65 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:6]

    msg = urllib.parse.quote(f"*OR936 ELITE*\n{nl} vs {nv}\nTop Pick: {sug[0]['t']} ({sug[0]['p']:.1f}%)\nEstabilidad: {res['BRIER']*100:.1f}%")
    with b2: st.markdown(f'<a href="https://wa.me/?text={msg}" target="_blank" class="whatsapp-btn">📲 COMPARTIR</a>', unsafe_allow_html=True)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.5, 1])
    with v1:
        st.markdown(f"<h4 style='color:#d4af37; margin-top:0;'>💎 TOP SELECCIONES (Confianza: {res['BRIER']*100:.1f}%)</h4>", unsafe_allow_html=True)
        for s in sug:
            clase = "elite-alert" if s['p'] > 85 else ""
            st.markdown(f'<div class="verdict-item {clase}"><b>{s["p"]:.1f}%</b> — {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("<h4 style='color:#fff; margin-top:0;'>⚽ MARCADOR EXACTO</h4>", unsafe_allow_html=True)
        for sc, pr in res['TOP']: st.markdown(f'<div class="score-badge">{sc} <span style="font-size:0.7em; color:#888;">({pr:.1f}%)</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "X", nv)
    
    tab_g, tab_dc, tab_h, tab_spec, tab_m = st.tabs(["🥅 GOLES", "🏆 1X2", "📉 HANDICAP", "🚩 ESPECIALES", "📊 MATRIZ"])
    
    with tab_g:
        ga, gb = st.columns(2)
        with ga:
            for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: dual_bar_explicit(f"OVER {l}", res['GOLES'][l][0], f"UNDER {l}", res['GOLES'][l][1])
        with gb: dual_bar_explicit("AMBOS ANOTAN: SI", res['BTTS'][0], "AMBOS ANOTAN: NO", res['BTTS'][1], color="#d4af37")
    
    with tab_dc:
        dual_bar_explicit(f"1X ({nl}/X)", res['DC'][0], "2", 100-res['DC'][0], color="#d4af37")
        dual_bar_explicit(f"X2 ({nv}/X)", res['DC'][1], "1", 100-res['DC'][1], color="#d4af37")
        dual_bar_explicit("12", res['DC'][2], "X", 100-res['DC'][2])

    with tab_h:
        st.markdown("<h5 style='color:#d4af37;'>MERCADOS DE VENTAJA (+/-)</h5>", unsafe_allow_html=True)
        ha, hb = st.columns(2)
        for idx, (h, p) in enumerate(res['HANDICAPS'].items()):
            col = ha if idx < 3 else hb
            with col:
                lbl_l = f"{nl} {'+' if h>0 else ''}{h}"
                lbl_v = f"{nv} {'+' if -h>0 else ''}{-h}"
                dual_bar_explicit(lbl_l, p[0], lbl_v, p[1], color="#00ffa3" if h < 0 else "#d4af37")

    with tab_spec:
        ta, tb = st.columns(2)
        with ta:
            for l, p in res['TARJETAS'].items(): dual_bar_explicit(f"Tarjetas >{l}", p[0], f"<{l}", p[1], color="#ff4b4b")
        with tb:
            for l, p in res['CORNERS'].items(): dual_bar_explicit(f"Corners >{l}", p[0], f"<{l}", p[1], color="#00ffa3")
            
    with tab_m:
        fig = px.imshow(pd.DataFrame(res['MATRIZ']), labels=dict(x="Visitante", y="Local", color="%"), x=[str(i) for i in range(6)], y=[str(i) for i in range(6)], color_continuous_scale=['#0a0c10', '#00ffa3', '#d4af37'], text_auto=".1f")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#eee")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("<p style='text-align:center; color:#444; font-size:0.7em;'>MONTE CARLO | DIXON-COLES | OR936 ELITE PRO</p>", unsafe_allow_html=True)
