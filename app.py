import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import datetime, timedelta, timezone
import urllib.parse
from bs4 import BeautifulSoup
import time
import json
import google.generativeai as genai

# =================================================================
# 1. CONFIGURACIÓN IA
# =================================================================
# TU API KEY
GEMINI_API_KEY = "AIzaSyDxmkDZKvPT6qHHEEU21a6SZzrAmak6l64"

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Error configurando Gemini: {e}")

# Estados iniciales
if 'nl_auto' not in st.session_state: st.session_state['nl_auto'] = "Local"
if 'nv_auto' not in st.session_state: st.session_state['nv_auto'] = "Visita"
if 'news_current' not in st.session_state: st.session_state['news_current'] = None

# =================================================================
# 2. AGENTE IA CORREGIDO
# =================================================================

def scouting_total_ia(match_query, league):
    # User-Agent más real para evitar bloqueos de Google
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    
    query = f"football stats xG goals per match corners cards injuries {match_query} in {league} 2026"
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            st.error(f"Google bloqueó la búsqueda (Código {res.status_code}). Reintenta en unos segundos.")
            return None
            
        soup = BeautifulSoup(res.text, 'html.parser')
        snippets = [d.text for d in soup.find_all('div') if len(d.text) > 40][:12]
        context = "\n".join(snippets)

        prompt = f"""
        Extract football stats for {match_query} in {league}.
        Rules: xG_home (performance only at home), xG_away (performance only away), corners, cards.
        Check for injuries (goalies/strikers).
        Context: {context}
        Return JSON:
        {{"home_team": "str", "away_team": "str", "xg_home": float, "xg_away": float, "league_avg": float, "corners_home": float, "corners_away": float, "cards_home": float, "cards_away": float, "news": "str"}}
        """
        
        response = model.generate_content(prompt)
        # Limpiar respuesta de Gemini
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        st.error(f"Error en Scouting: {e}")
        return None

# =================================================================
# 3. MOTOR MATEMÁTICO (IDENTICO)
# =================================================================

class MotorMatematico:
    def __init__(self, league_avg=2.5): self.rho = -0.12
    def poisson_prob(self, k, lam):
        return (lam**k * math.exp(-lam)) / math.factorial(k) if lam > 0 else (1.0 if k==0 else 0.0)

    def procesar(self, xg_l, xg_v, tj, co):
        p1, px, p2, btts = 0.0, 0.0, 0.0, 0.0
        marcadores = {}
        for i in range(7):
            for j in range(7):
                p = self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
        
        total = p1 + px + p2
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100),
            "BTTS": (btts/total*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3]
        }

# =================================================================
# 4. INTERFAZ
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")

with st.sidebar:
    st.header("GOLD TERMINAL")
    q = st.text_input("Partido", placeholder="Real Madrid vs Barcelona")
    l = st.text_input("Liga", placeholder="La Liga")
    
    if st.button("🚀 SYNC IA"):
        if q and l:
            with st.spinner("IA TRABAJANDO..."):
                data = scouting_total_ia(q, l)
                if data:
                    st.session_state['nl_auto'] = data['home_team']
                    st.session_state['nv_auto'] = data['away_team']
                    st.session_state['lgf_val'] = data['xg_home']
                    st.session_state['vgf_val'] = data['xg_away']
                    st.session_state['pl_val'] = data['league_avg']
                    st.session_state['news_current'] = data['news']
                    st.rerun()

st.title("OR936 QUANTUM IA")

if st.session_state['news_current']:
    st.info(f"📰 **NOTICIAS:** {st.session_state['news_current']}")

c1, c2 = st.columns(2)
with c1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("xG Local", 0.0, 5.0, value=st.session_state.get('lgf_val', 1.5))
with c2:
    nv = st.text_input("Visita", value=st.session_state['nv_auto'])
    vgf = st.number_input("xG Visita", 0.0, 5.0, value=st.session_state.get('vgf_val', 1.2))

pl = st.slider("Media Liga", 1.5, 3.5, value=st.session_state.get('pl_val', 2.5))

if st.button("GENERAR REPORTE"):
    motor = MotorMatematico()
    res = motor.procesar(lgf, vgf, 4.0, 9.0)
    
    st.success(f"Prob. {nl}: {res['1X2'][0]:.1f}% | Empate: {res['1X2'][1]:.1f}% | {nv}: {res['1X2'][2]:.1f}%")
    st.write(f"Ambos Anotan: {res['BTTS']:.1f}%")
    
    cols = st.columns(3)
    for i, (m, p) in enumerate(res['TOP']):
        cols[i].metric(f"Marcador #{i+1}", m, f"{p:.1f}%")