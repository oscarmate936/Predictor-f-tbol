import streamlit as st
import math
import pandas as pd
import plotly.express as px
import urllib.parse
import requests
from datetime import datetime
import difflib

# =================================================================
# CONFIGURACIÓN API (apiv3.apifootball.com)
# =================================================================
# Nota: Asegúrate de que tu API Key esté activa y con créditos.
API_KEY = "d1d66e3f2bd12ea7496a1ab73069b2161f66b8c87656c5874eda75d1f8201655"
BASE_URL = "https://apiv3.apifootball.com/"

# Inicialización de estados críticos
keys_to_init = {
    'p_liga_auto': 2.5,
    'estilo_auto': "Equilibrada",
    'nl_auto': "Local",
    'nv_auto': "Visitante",
    'lgf_auto': 1.7, 'lgc_auto': 1.2,
    'vgf_auto': 1.5, 'vgc_auto': 1.1,
    'last_sync': None
}

for key, value in keys_to_init.items():
    if key not in st.session_state:
        st.session_state[key] = value

@st.cache_data(ttl=600) # Reducido el cache para detectar cambios más rápido
def api_request(action, params={}):
    params.update({"action": action, "APIkey": API_KEY})
    try:
        res = requests.get(BASE_URL, params=params, timeout=10)
        data = res.json()
        # Si la API devuelve un error (diccionario con llave 'error'), lo manejamos
        if isinstance(data, dict) and 'error' in data:
            return []
        return data
    except: 
        return []

def get_best_match(name, choices):
    matches = difflib.get_close_matches(name, choices, n=1, cutoff=0.3) # Umbral más flexible
    return matches[0] if matches else None

# =================================================================
# MOTOR MATEMÁTICO (PRO STATS ENGINE)
# =================================================================
class MotorMatematico:
    def __init__(self, rho=-0.15): self.rho = rho
    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        try: return (lam**k * math.exp(-lam)) / math.factorial(k)
        except: return 0.0
    def neg_binomial_prob(self, k, mu, dispersion=1.5):
        if mu <= 0: return 1.0 if k == 0 else 0.0
        var = mu * dispersion
        p = mu / var
        r = (mu**2) / (var - mu) if (var - mu) != 0 else 100
        try:
            return math.comb(int(k + r - 1), int(k)) * (p**r) * ((1 - p)**k)
        except: return self.poisson_prob(k, mu)
    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0
    def calcular_ou_prob(self, valor_esperado, threshold, use_nb=False):
        if use_nb: prob_under = sum(self.neg_binomial_prob(k, valor_esperado) for k in range(int(math.floor(threshold)) + 1))
        else: prob_under = sum(self.poisson_prob(k, valor_esperado) for k in range(int(math.floor(threshold)) + 1))
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
        return {"1X2": (p1/total*100, px/total*100, p2/total*100), "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
                "BTTS": (btts_si/total*100, (1-btts_si/total)*100), "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
                "TARJETAS": {t: self.calcular_ou_prob(tj_total, t, True) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
                "CORNERS": {t: self.calcular_ou_prob(co_total, t, True) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
                "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], "MATRIZ": matriz}

# =================================================================
# COMPONENTES VISUALES
# =================================================================
def triple_bar(p1, px, p2, n1, nx, n2):
    st.markdown(f"""
        <div style="margin-top: 20px; margin-bottom: 25px; background: #161b22; padding: 15px; border-radius: 12px; border: 1px solid #30363d;">
            <p style='color:#00ffcc; font-size:0.9em; font-weight:bold; margin-bottom:10px;'>RESULTADO DIRECTO (1X2)</p>
            <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 10px; color: #eee;">
                <span>{n1}: <b>{p1:.1f}%</b></span><span>Empate: <b>{px:.1f}%</b></span><span>{n2}: <b>{p2:.1f}%</b></span>
            </div>
            <div style="display: flex; height: 18px; border-radius: 9px; overflow: hidden; background: #333;">
                <div style="width: {p1}%; background: #00ffcc;"></div><div style="width: {px}%; background: #444;"></div><div style="width: {p2}%; background: #3498db;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def dual_bar_explicit(label_over, prob_over, label_under, prob_under, color="#00ffcc"):
    st.markdown(f"""
        <div style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #eee; margin-bottom: 3px;">
                <span><b>{label_over}:</b> {prob_over:.1f}%</span><span><b>{label_under}:</b> {prob_under:.1f}%</span>
            </div>
            <div style="display: flex; background: #222; height: 8px; border-radius: 4px; overflow: hidden;">
                <div style="width: {prob_over}%; background: {color};"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =================================================================
# INTERFAZ PRINCIPAL
# =================================================================
st.set_page_config(page_title="OR936 Elite v3.4.1", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .master-card { background: #161b22; padding: 25px; border-radius: 15px; border: 1px solid #30363d; margin-bottom: 20px; }
    .verdict-item { border-left: 4px solid #00ffcc; background: rgba(255,255,255,0.03); padding: 10px; margin-bottom: 8px; border-radius: 0 8px 8px 0; }
    .score-badge { background: #1c2128; padding: 8px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 5px; text-align: center; }
    .stButton>button { background: linear-gradient(90deg, #00ffcc 0%, #008577 100%); color: black !important; font-weight: bold; border-radius: 10px; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ PANEL CONTROL API")
    ligas_api = {"La Liga": 302, "Premier League": 152, "Serie A": 207, "Bundesliga": 175, "Ligue 1": 168, "Champions League": 3, "Brasileirão": 99, "Liga SLV": 601}
    nombre_liga = st.selectbox("Selecciona Liga", list(ligas_api.keys()))
    fecha_analisis = st.date_input("Fecha", datetime.now())
    
    eventos = api_request("get_events", {"from": fecha_analisis.strftime("%Y-%m-%d"), "to": fecha_analisis.strftime("%Y-%m-%d"), "league_id": ligas_api[nombre_liga]})
    
    if eventos and isinstance(eventos, list):
        op_p = {f"{e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in eventos}
        p_sel = st.selectbox("Partidos Detectados", list(op_p.keys()))
        
        if st.button("⚡ SINCRONIZAR DATOS", use_container_width=True):
            standings = api_request("get_standings", {"league_id": ligas_api[nombre_liga]})
            if isinstance(standings, list) and len(standings) > 0:
                total_g = sum(int(t['overall_league_GF']) for t in standings)
                total_pj = sum(int(t['overall_league_payed']) for t in standings)
                nuevo_promedio = float(total_g / (total_pj / 2)) if total_pj > 0 else 2.5
                st.session_state['p_liga_auto'] = nuevo_promedio
                
                if nuevo_promedio > 2.85: st.session_state['estilo_auto'] = "Ultra-Ofensiva"
                elif nuevo_promedio < 2.45: st.session_state['estilo_auto'] = "Defensiva"
                else: st.session_state['estilo_auto'] = "Equilibrada"
                
                nombres_api = [t['team_name'] for t in standings]
                match_l = get_best_match(op_p[p_sel]['match_hometeam_name'], nombres_api)
                match_v = get_best_match(op_p[p_sel]['match_awayteam_name'], nombres_api)
                
                dl = next((t for t in standings if t['team_name'] == match_l), None)
                dv = next((t for t in standings if t['team_name'] == match_v), None)
                
                if dl and dv:
                    st.session_state['lgf_auto'] = float(dl['overall_league_GF'])/max(1, int(dl['overall_league_payed']))
                    st.session_state['lgc_auto'] = float(dl['overall_league_GA'])/max(1, int(dl['overall_league_payed']))
                    st.session_state['vgf_auto'] = float(dv['overall_league_GF'])/max(1, int(dv['overall_league_payed']))
                    st.session_state['vgc_auto'] = float(dv['overall_league_GA'])/max(1, int(dv['overall_league_payed']))
                    st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                    st.success("✅ Sincronización Exitosa")
                    st.rerun()
                else:
                    st.warning("⚠️ No se encontraron datos para estos equipos en la tabla.")
            else:
                st.error("❌ Error de API: No se pudo obtener la tabla de posiciones.")
    else:
        st.info("📅 No hay partidos programados para esta fecha en la liga seleccionada.")

st.markdown("<h1 style='text-align: center; color: #00ffcc;'>OR936 ELITE ANALYSIS v3.4.1</h1>", unsafe_allow_html=True)

# PARÁMETROS DE ENTRADA
col_l, col_v = st.columns(2)
with col_l:
    st.markdown("### 🏠 Local")
    nl = st.text_input("Local", st.session_state['nl_auto'], key="nl_input")
    la, lb = st.columns(2)
    lgf = la.number_input("Favor L", 0.0, 10.0, st.session_state['lgf_auto'], step=0.1)
    lgc = lb.number_input("Contra L", 0.0, 10.0, st.session_state['lgc_auto'], step=0.1)
    ltj, lco = la.number_input("Tarjetas L", 0.0, 15.0, 2.3), lb.number_input("Corners L", 0.0, 20.0, 5.5)

with col_v:
    st.markdown("### 🚀 Visitante")
    nv = st.text_input("Visitante", st.session_state['nv_auto'], key="nv_input")
    va, vb = st.columns(2)
    vgf = va.number_input("Favor V", 0.0, 10.0, st.session_state['vgf_auto'], step=0.1)
    vgc = vb.number_input("Contra V", 0.0, 10.0, st.session_state['vgc_auto'], step=0.1)
    vtj, vco = va.number_input("Tarjetas V", 0.0, 15.0, 2.2), vb.number_input("Corners V", 0.0, 20.0, 4.8)

c_m1, c_m2 = st.columns(2)
p_liga = c_m1.slider("Media Goles Liga", 0.5, 5.0, st.session_state['p_liga_auto'], key="p_liga_slider")
estilo_liga = c_m2.select_slider("Estilo Detectado", ["Ultra-Ofensiva", "Equilibrada", "Defensiva"], value=st.session_state['estilo_auto'])

rho_map = {"Ultra-Ofensiva": -0.05, "Equilibrada": -0.15, "Defensiva": -0.22}

if st.button("🚀 PROCESAR ANÁLISIS ELITE", use_container_width=True):
    motor = MotorMatematico(rho=rho_map[estilo_liga])
    xg_l, xg_v = (lgf/p_liga)*(vgc/p_liga)*p_liga, (vgf/p_liga)*(lgc/p_liga)*p_liga
    res = motor.procesar(xg_l, xg_v, ltj+vtj, lco+vco)
    
    # Pool de Sugerencias (Reducido a 5 finalistas)
    pool = [
        {"t": "1X (Local o Empate)", "p": res['DC'][0]},
        {"t": "X2 (Visita o Empate)", "p": res['DC'][1]},
        {"t": "12 (Local o Visita)", "p": res['DC'][2]},
        {"t": "Ambos Anotan: SÍ", "p": res['BTTS'][0]},
        {"t": "Ambos Anotan: NO", "p": res['BTTS'][1]}
    ]
    for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: 
        pool.append({"t": f"Over {l} Goles", "p": res['GOLES'][l][0]})
        pool.append({"t": f"Under {l} Goles", "p": res['GOLES'][l][1]})
    
    sug = sorted([s for s in pool if 60 < s['p'] < 98], key=lambda x: x['p'], reverse=True)[:5]

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([1.2, 1])
    with v1:
        st.markdown(f"#### 💎 Top 5 Sugerencias ({estilo_liga})")
        for s in sug: st.markdown(f'<div class="verdict-item"><b>{s["p"]:.1f}%</b> | {s["t"]}</div>', unsafe_allow_html=True)
    with v2:
        st.markdown("#### ⚽ Marcadores")
        for score, prob in res['TOP']: st.markdown(f'<div class="score-badge"><b>{score}</b> — {prob:.1f}%</div>', unsafe_allow_html=True)
    
    msg = urllib.parse.quote(f"📊 *ANÁLISIS {nl} vs {nv}*\n🏆 Estilo: {estilo_liga}\n\n💎 *Top 5 Sugerencias:*\n" + "\n".join([f"• {s['t']}: {s['p']:.1f}%" for s in sug]))
    st.link_button("📲 COMPARTIR EN WHATSAPP", f"https://wa.me/?text={msg}", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    triple_bar(res['1X2'][0], res['1X2'][1], res['1X2'][2], nl, "X", nv)

    t1, t2, t3, t4 = st.tabs(["🏆 Oportunidad", "🥅 Goles", "🚩 Especiales", "📊 Matriz"])
    with t1:
        dual_bar_explicit("1X (Local o Empate)", res['DC'][0], "2 Directo", 100-res['DC'][0], "#9b59b6")
        dual_bar_explicit("X2 (Visitante o Empate)", res['DC'][1], "1 Directo", 100-res['DC'][1], "#f39c12")
        dual_bar_explicit("12 (Local o Visitante)", res['DC'][2], "X Directo", 100-res['DC'][2], "#e74c3c")
    with t2:
        c_ga, c_gb = st.columns(2)
        with c_ga: 
            for l in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]: dual_bar_explicit(f"Over {l}", res['GOLES'][l][0], f"Under {l}", res['GOLES'][l][1])
        with c_gb: dual_bar_explicit("Ambos Anotan", res['BTTS'][0], "No Anotan", res['BTTS'][1], "#f1c40f")
    with t3:
        c_sa, c_sb = st.columns(2)
        with c_sa: 
            st.markdown("🚩 **Corners**")
            for l, p in res['CORNERS'].items(): dual_bar_explicit(f"Over {l}", p[0], f"Under {l}", p[1], "#2ecc71")
        with c_sb:
            st.markdown("🎴 **Tarjetas**")
            for l, p in res['TARJETAS'].items(): dual_bar_explicit(f"Over {l}", p[0], f"Under {l}", p[1], "#e74c3c")
    with t4:
        st.plotly_chart(px.imshow(pd.DataFrame(res['MATRIZ'], columns=[f"{nv} {i}" for i in range(6)], index=[f"{nl} {i}" for i in range(6)]), text_auto=".1f", color_continuous_scale='Viridis'), use_container_width=True)

st.markdown(f"<p style='text-align: center; color: #555; font-size: 0.8em;'>OR936 Elite v3.4.1 | GPM Liga: {st.session_state['p_liga_auto']:.2f}</p>", unsafe_allow_html=True)
