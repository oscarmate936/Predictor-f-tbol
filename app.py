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
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.1

# =================================================================
# 2. FUNCIONES DE LÓGICA (CORREGIDAS PARA EVITAR ATTRIBUTEERROR)
# =================================================================

def api_request_rapid(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    try:
        res = requests.get(url, headers=headers, params=params, timeout=12)
        if res.status_code == 200:
            data = res.json()
            # Verificación jerárquica de la respuesta
            if isinstance(data, dict):
                # Intentar extraer la lista de datos de las llaves comunes de RapidAPI
                for key in ['response', 'data', 'results']:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return [data] if data else []
            return data if isinstance(data, list) else []
        return []
    except:
        return []

@st.cache_data(ttl=600)
def get_all_leagues():
    """Obtiene ligas evitando que elementos que no sean diccionarios rompan el código."""
    res = api_request_rapid("football-get-all-leagues")
    leagues_dict = {}
    
    if isinstance(res, list):
        for l in res:
            # Validación: solo procesar si 'l' es un diccionario
            if isinstance(l, dict):
                # Soporte para múltiples nombres de llaves (league_name, name, etc)
                name = l.get('league_name') or l.get('name') or l.get('league')
                lid = l.get('league_id') or l.get('id')
                if name and lid:
                    leagues_dict[str(name)] = str(lid)
                    
    # Si la API falla, devolvemos un set mínimo para que el selector no esté vacío
    return leagues_dict if leagues_dict else {"Premier League": "152", "La Liga": "302"}

def get_v(obj, *keys):
    """Extrae valores de forma segura probando múltiples llaves."""
    if not isinstance(obj, dict): return 0
    for k in keys:
        if k in obj and obj[k] is not None:
            try: return float(obj[k])
            except: continue
    return 0

# =================================================================
# 3. MOTOR MATEMÁTICO QUANTUM (MANTENIDO)
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
                if i < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)
        
        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.8))
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3],
            "BRIER": confianza,
            "MATRIZ": matriz
        }

# =================================================================
# 4. UI & SIDEBAR (DISEÑO ORIGINAL PRESERVADO)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    .stApp { background: #05070a; color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: linear-gradient(145deg, #141923, #0a0c12); padding: 30px; border-radius: 20px; border: 1px solid #d4af3733; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    .whatsapp-btn { background: #25D366; color: white !important; padding: 12px 24px; border-radius: 12px; text-decoration: none; font-weight: 700; display: inline-block; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    if st.button("📡 STATUS CONNECTION"):
        test = api_request_rapid("football-get-all-leagues")
        if test: st.success("ONLINE")
        else: st.error("OFFLINE/CHECK KEY")

    dict_ligas = get_all_leagues()
    nombre_liga = st.selectbox("🏆 Competición", list(dict_ligas.keys()))
    id_liga_sel = dict_ligas[nombre_liga]
    fecha_sel = st.date_input("📅 Jornada", value=ahora_sv.date())
    
    raw_events = api_request_rapid("football-get-matches-by-date", {"date": fecha_sel.strftime('%Y-%m-%d'), "league_id": id_liga_sel})

    if raw_events and isinstance(raw_events, list):
        op_p = {}
        for e in raw_events:
            if isinstance(e, dict):
                h = e.get('match_hometeam_name') or e.get('home_team') or "Local"
                v = e.get('match_awayteam_name') or e.get('away_team') or "Visita"
                op_p[f"{h} vs {v}"] = e
        
        p_sel = st.selectbox("📍 Partidos", list(op_p.keys()))

        if st.button("SYNC DATA"):
            with st.spinner("Quantum Sync..."):
                standings = api_request_rapid("football-get-standings-all", {"league_id": id_liga_sel})
                if standings:
                    hg = sum(get_v(t, 'home_league_GF', 'home_GF') for t in standings if isinstance(t, dict))
                    ag = sum(get_v(t, 'away_league_GF', 'away_GF') for t in standings if isinstance(t, dict))
                    pj = sum(get_v(t, 'overall_league_payed', 'played') for t in standings if isinstance(t, dict))
                    st.session_state['p_liga_auto'] = (hg + ag) / (max(1, pj) / 2)
                    
                    # Buscador de equipos para el Sync
                    m_info = op_p[p_sel]
                    n_h = m_info.get('match_hometeam_name') or m_info.get('home_team')
                    n_v = m_info.get('match_awayteam_name') or m_info.get('away_team')
                    
                    def find_t(name):
                        for t in standings:
                            t_name = t.get('team_name') or t.get('team')
                            if t_name and name and (name in t_name or t_name in name): return t
                        return None
                    
                    dl, dv = find_t(n_h), find_t(n_v)
                    if dl and dv:
                        ph = max(1, get_v(dl, 'home_league_payed', 'home_played'))
                        pa = max(1, get_v(dv, 'away_league_payed', 'away_played'))
                        st.session_state['lgf_auto'] = get_v(dl, 'home_league_GF', 'home_GF') / ph
                        st.session_state['vgf_auto'] = get_v(dv, 'away_league_GF', 'away_GF') / pa
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = n_h, n_v
                        st.rerun()

# =================================================================
# 5. MAIN CONTENT (MANTENIDO)
# =================================================================
st.markdown("<h1 style='text-align: center; color: #fff;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("xG Local", 0.0, 10.0, value=float(st.session_state.get('lgf_auto', 1.5)))
with c2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("xG Visita", 0.0, 10.0, value=float(st.session_state.get('vgf_auto', 1.2)))

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(st.session_state['p_liga_auto'])
    res = motor.procesar(lgf, vgf, 4.5, 9.5)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.markdown(f"### 💎 Picks (Confianza: {res['BRIER']*100:.1f}%)")
        st.write(f"• Victoria {nl}: **{res['1X2'][0]:.1f}%**")
        st.write(f"• Empate: **{res['1X2'][1]:.1f}%**")
        st.write(f"• Ambos Anotan (SÍ): **{res['BTTS'][0]:.1f}%**")
    with res_col2:
        st.markdown("### 🎯 Marcador Probable")
        for score, prob in res['TOP']:
            st.success(f"{score} — ({prob:.1f}%)")
    st.markdown('</div>', unsafe_allow_html=True)

    msg = f"OR936 ELITE: {nl} vs {nv}\nMarcador: {res['TOP'][0][0]}\nProb: {res['TOP'][0][1]:.1f}%"
    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" class="whatsapp-btn">📲 COMPARTIR REPORTE</a>', unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #333; margin-top: 40px;'>OR936 ELITE v4.5 | QUANTUM ENGINE</p>", unsafe_allow_html=True)
