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
# CONFIGURACIÓN API (RAPIDAPI - API-FOOTBALL V3)
# =================================================================
# Clave verificada
API_KEY = "e7757069e7msh1aec6d4f74dd4ccp1b85c0jsnaf8f81aec6"
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3/"
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

# Sincronización horaria El Salvador (UTC-6)
tz_sv = timezone(timedelta(hours=-6))
ahora_sv = datetime.now(tz_sv)

if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visitante"

defaults = {
    'p_liga_auto': 2.5, 'hfa_league': 1.0, 'form_l': 1.0, 'form_v': 1.0,
    'lgf_auto': 1.7, 'lgc_auto': 1.2, 'vgf_auto': 1.5, 'vgc_auto': 1.1
}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# Función de Partidos (Fixtures) - CORREGIDA PARA MARZO 2026
def api_request_live(league_id, fecha_inicio, fecha_fin):
    endpoint = "fixtures"
    # IMPORTANTE: En marzo 2026, la temporada activa es 2025 para casi todas las ligas
    # Probamos ambas para asegurar resultados
    for season in [2025, 2026]:
        params = {
            "league": league_id,
            "season": season,
            "from": fecha_inicio,
            "to": fecha_fin
        }
        try:
            res = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params, timeout=10)
            data = res.json().get('response', [])
            if data:
                return [{'match_date': f['fixture']['date'][:10], 
                         'match_hometeam_name': f['teams']['home']['name'], 
                         'match_awayteam_name': f['teams']['away']['name']} for f in data]
        except: continue
    return []

# Función de Posiciones (Standings) - CORREGIDA
@st.cache_data(ttl=600)
def api_request_cached(league_id):
    endpoint = "standings"
    for season in [2025, 2026]:
        try:
            res = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params={"league": league_id, "season": season}, timeout=10)
            resp = res.json().get('response', [])
            if resp:
                standings_nested = resp[0]['league']['standings']
                normalized = []
                # Soporta ligas con grupos (como El Salvador o Champions)
                for group in standings_nested:
                    if not isinstance(group, list): group = [group]
                    for t in group:
                        normalized.append({
                            'team_name': t['team']['name'],
                            'overall_league_position': t['rank'],
                            'overall_league_payed': t['all']['played'],
                            'home_league_payed': t['home']['played'],
                            'home_league_GF': t['home']['goals']['for'],
                            'home_league_GA': t['home']['goals']['against'],
                            'away_league_payed': t['away']['played'],
                            'away_league_GF': t['away']['goals']['for'],
                            'away_league_GA': t['away']['goals']['against']
                        })
                return normalized
        except: continue
    return []

# =================================================================
# MOTOR MATEMÁTICO (Sin cambios)
# =================================================================
class MotorMatematico:
    def __init__(self, league_avg=2.5): 
        self.rho = -0.15 if 2.2 <= league_avg <= 3.0 else (-0.10 if league_avg > 3.0 else -0.18)

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
        h_lines = [-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5]
        h_probs_l = {h: 0.0 for h in h_lines}
        h_probs_v = {h: 0.0 for h in h_lines}

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
                if i < 6 and j < 6: fila.append(p * 100)
            if i < 6: matriz.append(fila)

        total = max(0.0001, p1 + px + p2)
        confianza = 1 - (abs(xg_l - xg_v) / (xg_l + xg_v + 1.0))
        sim_tj = np.random.poisson(tj_total, 15000)
        sim_co = np.random.poisson(co_total, 15000)

        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100), 
            "GOLES": {t: (p[0]/total*100, p[1]/total*100) for t, p in g_probs.items()},
            "HANDICAPS": {"L": {h: v/total*100 for h,v in h_probs_l.items()}, "V": {h: v/total*100 for h,v in h_probs_v.items()}},
            "TARJETAS": {t: (np.sum(sim_tj > t)/150, np.sum(sim_tj <= t)/150) for t in [2.5, 3.5, 4.5, 5.5, 6.5]},
            "CORNERS": {t: (np.sum(sim_co > t)/150, np.sum(sim_co <= t)/150) for t in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]},
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz, "BRIER": confianza
        }

# =================================================================
# INTERFAZ (UI)
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

st.markdown("""
    <style>
    :root { --primary: #d4af37; --secondary: #00ffa3; --bg: #05070a; }
    .stApp { background: var(--bg); color: #e0e0e0; }
    .master-card { background: linear-gradient(145deg, rgba(20,25,35,0.9), rgba(10,12,18,0.9)); padding: 35px; border-radius: 24px; border: 1px solid rgba(212, 175, 55, 0.15); margin-bottom: 30px; }
    .verdict-item { background: rgba(0, 255, 163, 0.03); border-left: 4px solid var(--secondary); padding: 15px 20px; margin-bottom: 12px; border-radius: 8px 18px 18px 8px; font-size: 1.1em; }
    .score-badge { background: #000; padding: 15px; border-radius: 16px; border: 1px solid var(--primary); margin-bottom: 10px; text-align: center; color: var(--primary); font-weight: 800; font-size: 1.2em; }
    .stButton>button { background: linear-gradient(135deg, #d4af37 0%, #8a6d1d 100%); color: #000 !important; font-weight: 900; width: 100%; border-radius: 14px; padding: 20px; }
    .whatsapp-btn { display: flex; align-items: center; justify-content: center; background: #25D366; color: white !important; padding: 14px; border-radius: 14px; text-decoration: none; font-weight: 700; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37; text-align:center;'>GOLD TERMINAL</h2>", unsafe_allow_html=True)
    ligas_ids = {
        "Liga Mayor (El Salvador)": 242, "Premier League (Inglaterra)": 39, "La Liga (España)": 140, 
        "Serie A (Italia)": 135, "Bundesliga (Alemania)": 78, "Ligue 1 (Francia)": 61, 
        "UEFA Champions League": 2, "Brasileirão Série A": 71, "Saudi Pro League": 307
    }
    nombre_liga = st.selectbox("🏆 Competición", list(ligas_ids.keys()))
    fecha_sel = st.date_input("📅 Seleccionar Fecha", value=ahora_sv.date())
    
    # Rango de 7 días alrededor de la fecha seleccionada
    f_inicio = (fecha_sel - timedelta(days=3)).strftime('%Y-%m-%d')
    f_fin = (fecha_sel + timedelta(days=3)).strftime('%Y-%m-%d')

    raw_events = api_request_live(ligas_ids[nombre_liga], f_inicio, f_fin)

    if raw_events:
        opciones = {f"({e['match_date']}) {e['match_hometeam_name']} vs {e['match_awayteam_name']}": e for e in raw_events}
        partido_sel = st.selectbox("📍 Partidos Encontrados", list(opciones.keys()))

        if st.button("SINCRONIZAR DATOS"):
            st.cache_data.clear()
            with st.spinner("Analizando tabla de posiciones..."):
                standings = api_request_cached(ligas_ids[nombre_liga])
                if standings:
                    def buscar_equipo(nombre):
                        nombres = [t['team_name'] for t in standings]
                        match, score = process.extractOne(nombre, nombres)
                        return next(t for t in standings if t['team_name'] == match) if score > 50 else None

                    dl = buscar_equipo(opciones[partido_sel]['match_hometeam_name'])
                    dv = buscar_equipo(opciones[partido_sel]['match_awayteam_name'])
                    
                    if dl and dv:
                        pj_l, pj_v = max(1, int(dl['home_league_payed'])), max(1, int(dv['away_league_payed']))
                        st.session_state['lgf_auto'] = float(dl['home_league_GF']) / pj_l
                        st.session_state['lgc_auto'] = float(dl['home_league_GA']) / pj_l
                        st.session_state['vgf_auto'] = float(dv['away_league_GF']) / pj_v
                        st.session_state['vgc_auto'] = float(dv['away_league_GA']) / pj_v
                        st.session_state['nl_auto'], st.session_state['nv_auto'] = dl['team_name'], dv['team_name']
                        st.success("¡Datos cargados!")
                        st.rerun()
                else:
                    st.error("No se pudo obtener la tabla de posiciones de esta temporada.")
    else:
        st.warning("No hay partidos en esta fecha. Intenta cambiar de liga o fecha.")

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span> V3.5</h1>", unsafe_allow_html=True)
st.markdown("---")

c1, c2 = st.columns(2)
with c1:
    st.markdown("<h4 style='color:var(--secondary)'>LOCAL</h4>", unsafe_allow_html=True)
    nl = st.text_input("Equipo", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF (Promedio)", 0.0, 10.0, key='lgf_auto')
    lgc = st.number_input("GC (Promedio)", 0.0, 10.0, key='lgc_auto')
with c2:
    st.markdown("<h4 style='color:var(--primary)'>VISITANTE</h4>", unsafe_allow_html=True)
    nv = st.text_input("Equipo ", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF (Promedio) ", 0.0, 10.0, key='vgf_auto')
    vgc = st.number_input("GC (Promedio) ", 0.0, 10.0, key='vgc_auto')

p_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR REPORTE QUANTUM"):
    motor = MotorMatematico(p_liga)
    # XG Estimado
    xg_l = (lgf/p_liga)*(vgc/p_liga)*p_liga * 1.10
    xg_v = (vgf/p_liga)*(lgc/p_liga)*p_liga * 0.90
    res = motor.procesar(xg_l, xg_v, 4.5, 9.5)

    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    res_c1, res_c2 = st.columns([1.5, 1])
    with res_c1:
        st.subheader("💎 TOP PICKS")
        picks = [("1X (Local o Empate)", res['DC'][0]), ("X2 (Visita o Empate)", res['DC'][1]), 
                 ("Ambos Anotan: SI", res['BTTS'][0]), ("Over 2.5 Goles", res['GOLES'][2.5][0])]
        for t, p in sorted(picks, key=lambda x: x[1], reverse=True):
            st.markdown(f'<div class="verdict-item"><b>{p:.1f}%</b> — {t}</div>', unsafe_allow_html=True)
    with res_c2:
        st.subheader("🎯 MARCADORES")
        for s, p in res['TOP']:
            st.markdown(f'<div class="score-badge">{s} <br> <span style="font-size:0.6em">PROB: {p:.1f}%</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Matriz
    fig = px.imshow(res['MATRIZ'], labels=dict(x=nv, y=nl, color="%"), text_auto=".1f", color_continuous_scale='YlGnBu')
    st.plotly_chart(fig, use_container_width=True)

    # Botón compartir
    msg = f"*REPORTE ELITE: {nl} vs {nv}*\nTop Pick: {sorted(picks, key=lambda x: x[1], reverse=True)[0][0]} ({sorted(picks, key=lambda x: x[1], reverse=True)[0][1]:.1f}%)\nMarcador: {res['TOP'][0][0]}"
    st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" target="_blank" class="whatsapp-btn">📲 COMPARTIR EN WHATSAPP</a>', unsafe_allow_html=True)
