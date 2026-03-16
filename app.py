import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from fuzzywuzzy import process
import time

# =================================================================
# 1. CONFIGURACIÓN API (RAPIDAPI) & ESTADO
# =================================================================
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf081e5e5b62"
API_HOST = "free-api-live-football-data.p.rapidapi.com"
BASE_URL = "https://free-api-live-football-data.p.rapidapi.com"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": API_HOST
}

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'elo_bias' not in st.session_state: st.session_state['elo_bias'] = (1.0, 1.0)
if 'h2h_bias' not in st.session_state: st.session_state['h2h_bias'] = (1.0, 1.0)
if 'audit_results' not in st.session_state: st.session_state['audit_results'] = []

# =================================================================
# 2. FUNCIONES DE LÓGICA ULTRA-RESILIENTE
# =================================================================

def api_request_rapid(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    try:
        res = requests.get(url, headers=headers, params=params, timeout=12)
        if res.status_code == 200:
            data = res.json()
            # Esta API entrega los datos en 'response' o 'data'. Buscamos ambos.
            for key in ['response', 'data', 'results']:
                if key in data and data[key]:
                    return data[key]
            return data if isinstance(data, list) else []
        return []
    except: return []

def get_v(obj, *keys):
    """Busca un valor en un objeto probando múltiples nombres de campo."""
    if not obj or not isinstance(obj, dict): return 0
    for k in keys:
        if k in obj and obj[k] is not None:
            try: return float(obj[k]) if "." in str(obj[k]) else int(obj[k])
            except: return obj[k]
    return 0

@st.cache_data(ttl=600)
def get_all_leagues():
    """Obtiene todas las ligas disponibles para llenar el selector."""
    res = api_request_rapid("football-get-all-leagues")
    if res:
        return {l.get('league_name', 'Unknown'): l.get('league_id') for l in res if l.get('league_id')}
    return {"Premier League": 152, "La Liga": 302, "Serie A": 207} # Backup

@st.cache_data(ttl=300)
def get_h2h_data(id_l, id_v):
    res = api_request_rapid("football-get-h2h", {"firstTeamId": id_l, "secondTeamId": id_v})
    if not res or not isinstance(res, list): return 1.0, 1.0
    l_pts, v_pts = 0, 0
    for m in res[:6]:
        hs = get_v(m, 'match_hometeam_score', 'home_score', 'score_home')
        vs = get_v(m, 'match_awayteam_score', 'away_score', 'score_away')
        hid = str(get_v(m, 'match_hometeam_id', 'home_id'))
        if hs > vs:
            if hid == str(id_l): l_pts += 3
            else: v_pts += 3
        elif hs < vs:
            if hid == str(id_l): v_pts += 3
            else: l_pts += 3
        else: l_pts += 1; v_pts += 1
    total = l_pts + v_pts if (l_pts + v_pts) > 0 else 1
    return 0.95 + (l_pts/total * 0.1), 0.95 + (v_pts/total * 0.1)

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM (MANTENIDO INTACTO)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.16 if league_avg < 2.4 else -0.12

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def procesar(self, xg_l, xg_v, tj_total, co_total):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        g_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]; h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        g_probs = {t: [0.0, 0.0] for t in g_lines}; h_probs_l = {h: 0.0 for h in h_lines}; h_probs_v = {h: 0.0 for h in h_lines}
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
                    if (i + h) > j: h_probs_l[h] += p
                    if (j + h) > i: h_probs_v[h] += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)
        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        return {"1X2": (p1/total*100, px/total*100, p2/total*100), "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100), "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()}, "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}}, "TARJETAS": {t: (np.sum(np.random.poisson(tj_total, 5000) > t)/50, np.sum(np.random.poisson(tj_total, 5000) <= t)/50) for t in [2.5, 3.5, 4.5, 5.5]}, "CORNERS": {t: (np.sum(np.random.poisson(co_total, 5000) > t)/50, np.sum(np.random.poisson(co_total, 5000) <= t)/50) for t in [7.5, 8.5, 9.5, 10.5]}, "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], "MATRIZ": matriz, "BRIER": confianza}

# =================================================================
# 4. UI & SIDEBAR (CORRECCIÓN TOTAL DE DATOS VACÍOS)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

# Estilos (Manteniendo tu estética Gold)
st.markdown("<style>.stApp { background: #05070a; color: #e0e0e0; } .master-card { background: #141923; padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; } .whatsapp-btn { background: #25D366; color: white !important; padding: 10px; border-radius: 10px; text-decoration: none; font-weight: 700; }</style>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    if st.button("📡 VERIFICAR CONEXIÓN"):
        test = api_request_rapid("football-get-all-leagues")
        if test: st.success(f"ONLINE: {len(test)} Ligas halladas")
        else: st.error("ERROR DE LLAVE O CUOTA")

    dict_ligas = get_all_leagues()
    nombre_liga = st.selectbox("🏆 Elige Competición", list(dict_ligas.keys()))
    id_liga_sel = dict_ligas[nombre_liga]
    fecha_analisis = st.date_input("📅 Fecha de Jornada", value=ahora_sv.date())
    
    # Búsqueda de partidos
    raw_events = api_request_rapid("football-get-matches-by-date", {"date": fecha_analisis.strftime('%Y-%m-%d'), "league_id": id_liga_sel})

    if raw_events:
        op_p = {}
        for e in raw_events:
            h = e.get('match_hometeam_name') or e.get('home_team') or e.get('home') or "Local"
            v = e.get('match_awayteam_name') or e.get('away_team') or e.get('away') or "Visita"
            t = e.get('match_time') or "00:00"
            op_p[f"{t} | {h} vs {v}"] = e
        
        p_sel = st.selectbox("📍 Partidos Hoy", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Sincronizando..."):
                standings = api_request_rapid("football-get-standings-all", {"league_id": id_liga_sel})
                m_info = op_p[p_sel]
                
                if standings:
                    # Cálculo de promedios
                    h_g = sum(get_v(t, 'home_league_GF', 'home_GF', 'goals_for') for t in standings)
                    a_g = sum(get_v(t, 'away_league_GF', 'away_GF', 'goals_for') for t in standings)
                    pj = sum(get_v(t, 'overall_league_payed', 'played', 'matches_played') for t in standings)
                    st.session_state['p_liga_auto'] = (h_g + a_g) / (max(1, pj) / 2)
                    st.session_state['hfa_league'] = h_g / a_g if a_g > 0 else 1.1

                    def find_t(n):
                        names = [t.get('team_name', t.get('team')) for t in standings]
                        m, s = process.extractOne(n, names)
                        return next((t for t in standings if t.get('team_name', t.get('team')) == m), None)

                    n_h = m_info.get('match_hometeam_name') or m_info.get('home_team') or m_info.get('home')
                    n_v = m_info.get('match_awayteam_name') or m_info.get('away_team') or m_info.get('away')
                    dl, dv = find_t(n_h), find_t(n_v)

                    if dl and dv:
                        id_l, id_v = get_v(dl, 'team_id', 'id'), get_v(dv, 'team_id', 'id')
                        st.session_state['h2h_bias'] = get_h2h_data(id_l, id_v)
                        st.session_state['lgf_auto'] = get_v(dl, 'home_league_GF', 'home_GF') / max(1, get_v(dl, 'home_league_payed', 'home_played'))
                        st.session_state['lgc_auto'] = get_v(dl, 'home_league_GA', 'home_GA') / max(1, get_v(dl, 'home_league_payed', 'home_played'))
                        st.session_state['vgf_auto'] = get_v(dv, 'away_league_GF', 'away_GF') / max(1, get_v(dv, 'away_league_payed', 'away_played'))
                        st.session_state['vgc_auto'] = get_v(dv, 'away_league_GA', 'away_GA') / max(1, get_v(dv, 'away_league_payed', 'away_played'))
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl.get('team_name'), dv.get('team_name')
                        st.rerun()
    else:
        st.warning("No hay partidos para esta fecha/liga en la API.")

# =================================================================
# 5. GENERACIÓN DE REPORTE (Mismo Motor Quantum)
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF L", 0.0, 10.0, value=float(st.session_state.get('lgf_auto', 1.5)))
with col2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF V", 0.0, 10.0, value=float(st.session_state.get('vgf_auto', 1.2)))

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(st.session_state['p_liga_auto'])
    res = motor.procesar(lgf, vgf, 4.5, 9.5) # Ejemplo tarjetas/corners
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💎 Picks Sugeridos")
        st.write(f"• 1X2 Local: {res['1X2'][0]:.1f}%")
        st.write(f"• Ambos Anotan: {res['BTTS'][0]:.1f}%")
    with c2:
        st.subheader("🎯 Marcador")
        st.info(f"Predominante: {res['TOP'][0][0]}")
    st.markdown('</div>', unsafe_allow_html=True)

    # Compartir WhatsApp
    msg = f"OR936 ELITE: {nl} vs {nv}\nMarcador: {res['TOP'][0][0]}\nConfianza: {res['BRIER']*100:.1f}%"
    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" class="whatsapp-btn">📲 COMPARTIR</a>', unsafe_allow_html=True)
