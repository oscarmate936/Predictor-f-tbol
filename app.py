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
# 1. CONFIGURACIÓN API & ESTADO (MANTENIENDO TU DISEÑO)
# =================================================================
# He verificado la URL exacta para este host de RapidAPI
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf081e5e5b62"
API_HOST = "free-api-live-football-data.p.rapidapi.com"
BASE_URL = "https://free-api-live-football-data.p.rapidapi.com"

# Headers estándar de RapidAPI
headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": API_HOST
}

tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

# Inicialización de estados para evitar que la UI se rompa si no hay datos
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"
if 'p_liga_auto' not in st.session_state: st.session_state['p_liga_auto'] = 2.5
if 'lgf_auto' not in st.session_state: st.session_state['lgf_auto'] = 1.5
if 'lgc_auto' not in st.session_state: st.session_state['lgc_auto'] = 1.0
if 'vgf_auto' not in st.session_state: st.session_state['vgf_auto'] = 1.2
if 'vgc_auto' not in st.session_state: st.session_state['vgc_auto'] = 1.3
if 'hfa_league' not in st.session_state: st.session_state['hfa_league'] = 1.1

# =================================================================
# 2. FUNCIONES DE CONEXIÓN CON DIAGNÓSTICO
# =================================================================

def api_request_rapid(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    try:
        # Aumentamos el timeout por si la API de RapidAPI está lenta
        res = requests.get(url, headers=headers, params=params, timeout=20)
        
        # DEBUG: Si quieres ver el error en consola de Streamlit
        if res.status_code != 200:
            return {"error_status": res.status_code, "msg": res.text}
            
        data = res.json()
        # Buscamos la lista de datos en las llaves típicas de esta API
        if isinstance(data, dict):
            for k in ['data', 'response', 'results']:
                if k in data and data[k]: return data[k]
        return data if isinstance(data, list) else []
    except Exception as e:
        return {"error_status": "CONN_ERROR", "msg": str(e)}

@st.cache_data(ttl=600)
def fetch_leagues():
    res = api_request_rapid("football-get-all-leagues")
    # Si devuelve un error (diccionario con status), retornamos vacío
    if isinstance(res, dict) and "error_status" in res:
        return {}
    if not res: return {}
    return {l['league_name']: l['league_id'] for l in res if isinstance(l, dict) and 'league_id' in l}

# =================================================================
# 3. MOTOR MATEMÁTICO DIXON-COLES (MANTENIDO)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.12 # Ajuste de correlación para marcadores bajos (0-0, 1-1)

    def poisson_prob(self, k, lam):
        if lam <= 0: return 1.0 if k == 0 else 0.0
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def dixon_coles_ajuste(self, x, y, lam, mu):
        if x == 0 and y == 0: return 1 - (lam * mu * self.rho)
        elif x == 0 and y == 1: return 1 + (lam * self.rho)
        elif x == 1 and y == 0: return 1 + (mu * self.rho)
        elif x == 1 and y == 1: return 1 - self.rho
        return 1.0

    def procesar(self, xg_l, xg_v):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores = {}
        for i in range(10): 
            for j in range(10):
                p = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
        
        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "BTTS": (btts_si/total*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3]
        }

# =================================================================
# 4. SIDEBAR CON DIAGNÓSTICO DE ERRORES
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""<style>.stApp { background: #05070a; color: #e0e0e0; } .master-card { background: #141923; padding: 25px; border-radius: 15px; border: 1px solid #d4af3733; }</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    
    # BOTÓN DE VERIFICACIÓN CON DETECCIÓN DE ERROR
    if st.button("📡 VERIFICAR ESTADO API"):
        check = api_request_rapid("football-get-all-leagues")
        if isinstance(check, dict) and "error_status" in check:
            status = check["error_status"]
            if status == 403:
                st.error("Error 403: Llave no autorizada. Ve a RapidAPI y suscríbete al plan 'Free' de esta API.")
            elif status == 429:
                st.error("Error 429: Límite de peticiones alcanzado. Espera un minuto.")
            else:
                st.error(f"Error {status}: No hay respuesta correcta del servidor.")
        elif check:
            st.success(f"ONLINE: {len(check)} Ligas encontradas")
        else:
            st.warning("La API respondió pero no envió datos.")

    leagues = fetch_leagues()
    if leagues:
        l_name = st.selectbox("🏆 Elige Competición", list(leagues.keys()))
        l_id = leagues[l_name]
        f_sel = st.date_input("📅 Jornada", value=ahora_sv.date())
        
        matches = api_request_rapid("football-get-matches-by-date", {"date": f_sel.strftime('%Y-%m-%d'), "league_id": l_id})

        if matches and isinstance(matches, list):
            op_p = {f"{m.get('match_hometeam_name','L')} vs {m.get('match_awayteam_name','V')}": m for m in matches if isinstance(m, dict)}
            p_sel = st.selectbox("📍 Partidos Disponibles", list(op_p.keys()))

            if st.button("SYNC DATA"):
                with st.spinner("Quantum Sync..."):
                    standings = api_request_rapid("football-get-standings-all", {"league_id": l_id})
                    m_info = op_p[p_sel]
                    
                    if standings and isinstance(standings, list):
                        # Búsqueda Fuzzy de equipos
                        names = [t.get('team_name') for t in standings if isinstance(t, dict)]
                        h_best, _ = process.extractOne(m_info.get('match_hometeam_name'), names)
                        v_best, _ = process.extractOne(m_info.get('match_awayteam_name'), names)
                        
                        dl = next(t for t in standings if t.get('team_name') == h_best)
                        dv = next(t for t in standings if t.get('team_name') == v_best)

                        # Mapeo de datos a la UI
                        def val(o, *ks):
                            for k in ks:
                                if k in o and o[k] is not None: return float(o[k])
                            return 1.0

                        st.session_state['nl_auto'] = h_best
                        st.session_state['nv_auto'] = v_best
                        st.session_state['lgf_auto'] = val(dl, 'home_league_GF') / max(1, val(dl, 'home_league_payed'))
                        st.session_state['vgf_auto'] = val(dv, 'away_league_GF') / max(1, val(dv, 'away_league_payed'))
                        st.rerun()
        else:
            st.info("Sin partidos para esta fecha.")
    else:
        st.error("No se pudieron cargar las ligas. Verifica tu suscripción en RapidAPI.")

# =================================================================
# 5. REPORTE PRINCIPAL (MANTENIDO)
# =================================================================
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    local_name = st.text_input("Local", value=st.session_state['nl_auto'])
    xg_l = st.number_input("xG Local", 0.0, 10.0, value=float(st.session_state['lgf_auto']))
with col2:
    visit_name = st.text_input("Visitante", value=st.session_state['nv_auto'])
    xg_v = st.number_input("xG Visita", 0.0, 10.0, value=float(st.session_state['vgf_auto']))

if st.button("GENERAR REPORTE DE INTELIGENCIA"):
    res = MotorMatematico().procesar(xg_l, xg_v)
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    rl, rr = st.columns(2)
    with rl:
        st.markdown("### 💎 Probabilidades")
        st.write(f"Victoria {local_name}: **{res['1X2'][0]:.1f}%**")
        st.write(f"Empate: **{res['1X2'][1]:.1f}%**")
        st.write(f"Victoria {visit_name}: **{res['1X2'][2]:.1f}%**")
    with rr:
        st.markdown("### 🎯 Marcadores")
        for sc, pr in res['TOP']: st.success(f"{sc} — {pr:.1f}%")
    st.markdown('</div>', unsafe_allow_html=True)
