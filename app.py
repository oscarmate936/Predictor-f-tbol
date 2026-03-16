import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import time

# =================================================================
# 1. CONFIGURACIÓN API & IDENTIDAD
# =================================================================
API_KEY = "123" 
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# Estados de sesión
state_keys = ['nl_auto', 'nv_auto', 'lgf_auto', 'lgc_auto', 'vgf_auto', 'vgc_auto', 'l_badge', 'v_badge']
defaults = ["Local", "Visitante", 1.5, 1.0, 1.2, 1.3, None, None]
for key, val in zip(state_keys, defaults):
    if key not in st.session_state: st.session_state[key] = val

# =================================================================
# 2. MOTOR MATEMÁTICO QUANTUM (SIN CAMBIOS)
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

    def procesar(self, xg_l, xg_v):
        p1, px, p2, btts_si = 0.0, 0.0, 0.0, 0.0
        marcadores, matriz = {}, []
        for i in range(7): 
            fila = []
            for j in range(7):
                p = (self.poisson_prob(i, xg_l) * self.poisson_prob(j, xg_v)) * self.dixon_coles_ajuste(i, j, xg_l, xg_v)
                if i > j: p1 += p
                elif i == j: px += p
                else: p2 += p
                if i > 0 and j > 0: btts_si += p
                if i <= 4 and j <= 4: marcadores[f"{i}-{j}"] = p * 100
                if i < 6 and j < 6: fila.append(p * 100)
            matriz.append(fila)
        total = max(0.0001, p1 + px + p2)
        return {
            "1X2": (p1/total*100, px/total*100, p2/total*100), 
            "DC": ((p1+px)/total*100, (p2+px)/total*100, (p1+p2)/total*100),
            "BTTS": (btts_si/total*100, (1 - btts_si/total)*100),
            "TOP": sorted(marcadores.items(), key=lambda x: x[1], reverse=True)[:3], 
            "MATRIZ": matriz[:6]
        }

# =================================================================
# 3. LÓGICA DE SINCRONIZACIÓN ULTRA-RESILIENTE
# =================================================================
def fetch_team_hardened(name):
    if not name: return None
    try:
        # Paso 1: Búsqueda del equipo para obtener ID
        r = requests.get(f"{BASE_URL}searchteams.php?t={name}", headers=HEADERS).json()
        if not r or not r.get('teams'): return None
        team = r['teams'][0]
        t_id = team['idTeam']
        
        # Datos iniciales (Escudo y Nombre siempre se obtienen aquí)
        data = {'name': team['strTeam'], 'badge': team['strBadge'], 'gf': 1.5, 'gc': 1.0, 'status': 'Nombre/Logo OK'}

        # Paso 2: Intentar obtener los últimos 5 partidos (Más estable que la tabla de liga)
        try:
            res_last = requests.get(f"{BASE_URL}eventslast.php?id={t_id}", headers=HEADERS).json()
            if res_last and res_last.get('results'):
                matches = res_last['results']
                g_favor = 0
                g_contra = 0
                count = 0
                for m in matches:
                    h_score = m.get('intHomeScore')
                    a_score = m.get('intAwayScore')
                    if h_score is not None and a_score is not None:
                        count += 1
                        if m['idHomeTeam'] == t_id:
                            g_favor += int(h_score)
                            g_contra += int(a_score)
                        else:
                            g_favor += int(a_score)
                            g_contra += int(h_score)
                if count > 0:
                    data['gf'] = round(g_favor / count, 2)
                    data['gc'] = round(g_contra / count, 2)
                    data['status'] = f"Datos: OK ({count} juegos)"
                    return data # Si esto funciona, es la mejor data
        except: pass

        # Paso 3: Fallback a la tabla de posiciones (Si lo anterior falló)
        try:
            res_table = requests.get(f"{BASE_URL}lookuptable.php?l={team['idLeague']}", headers=HEADERS).json()
            if res_table and res_table.get('table'):
                stats = next((x for x in res_table['table'] if x['idTeam'] == t_id), None)
                if stats:
                    pj = max(1, int(stats['intPlayed']))
                    data['gf'] = round(int(stats['intGoalsFor']) / pj, 2)
                    data['gc'] = round(int(stats['intGoalsAgainst']) / pj, 2)
                    data['status'] = "Datos: OK (Tabla Liga)"
                    return data
        except: pass

        data['status'] = "Datos: BLOQUEADOS (Ingreso Manual)"
        return data
    except Exception as e:
        return None

# =================================================================
# 4. INTERFAZ STREAMLIT
# =================================================================
st.set_page_config(page_title="OR936 QUANTUM ELITE", layout="wide")
st.markdown("""<style>
    .stApp { background: #05070a; color: #e0e0e0; font-family: 'Outfit', sans-serif; }
    .master-card { background: rgba(20,25,35,0.9); padding: 25px; border-radius: 20px; border: 1px solid #d4af3733; margin-bottom: 20px; }
    .score-badge { background: #000; padding: 10px; border-radius: 10px; border: 1px solid #d4af37; text-align: center; color: #d4af37; font-weight: 800; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.title("TERMINAL DE ORO")
    
    st.markdown("### 🛠 DIAGNÓSTICO API")
    if st.button("PROBAR CONEXIÓN"):
        status, detail = ("✅ ONLINE", "Conexión estable") if requests.get(BASE_URL + "searchteams.php?t=Arsenal").status_code == 200 else ("❌ ERROR", "Servidor no responde")
        st.write(f"**Sistema:** {status}")
    
    st.write("---")
    st.subheader("🔍 BUSCADOR")
    t1_input = st.text_input("Local (Escribe y pulsa Enter)")
    t2_input = st.text_input("Visita (Escribe y pulsa Enter)")

    if st.button("⚡ SINCRONIZAR TODO"):
        with st.spinner("Extrayendo estadísticas profundas..."):
            d1 = fetch_team_hardened(t1_input)
            d2 = fetch_team_hardened(t2_input)
            
            if d1:
                st.session_state.update({'nl_auto': d1['name'], 'lgf_auto': d1['gf'], 'lgc_auto': d1['gc'], 'l_badge': d1['badge']})
                st.sidebar.success(f"L: {d1['status']}")
            if d2:
                st.session_state.update({'nv_auto': d2['name'], 'vgf_auto': d2['gf'], 'vgc_auto': d2['gc'], 'v_badge': d2['badge']})
                st.sidebar.success(f"V: {d2['status']}")
            st.rerun()

# CUERPO PRINCIPAL
st.markdown("<h1 style='text-align: center;'>OR936 <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

# Logos de Equipos
b1, b2, b3 = st.columns([1, 2, 1])
with b1:
    if st.session_state['l_badge']: st.image(st.session_state['l_badge'], width=120)
with b3:
    if st.session_state['v_badge']: st.image(st.session_state['v_badge'], width=120)

st.write("---")

col1, col2 = st.columns(2)
with col1:
    nl = st.text_input("Local", value=st.session_state['nl_auto'])
    lgf = st.number_input("GF Local", value=float(st.session_state['lgf_auto']), step=0.1)
    lgc = st.number_input("GC Local", value=float(st.session_state['lgc_auto']), step=0.1)
with col2:
    nv = st.text_input("Visitante", value=st.session_state['nv_auto'])
    vgf = st.number_input("GF Visita", value=float(st.session_state['vgf_auto']), step=0.1)
    vgc = st.number_input("GC Visita", value=float(st.session_state['vgc_auto']), step=0.1)

media_liga = st.slider("Media de Goles de la Liga", 1.0, 4.0, 2.5)

if st.button("GENERAR PREDICCIÓN"):
    motor = MotorMatematico(media_liga)
    xg_l = (lgf/media_liga)*(vgc/media_liga)*media_liga * 1.1 
    xg_v = (vgf/media_liga)*(lgc/media_liga)*media_liga * 0.9 
    res = motor.procesar(xg_l, xg_v)
    
    st.markdown('<div class="master-card">', unsafe_allow_html=True)
    v1, v2 = st.columns([2, 1])
    with v1:
        st.subheader("💎 SUGERENCIAS")
        st.write(f"✅ **Doble Oportunidad 1X**: {res['DC'][0]:.1f}%")
        st.write(f"✅ **Ambos Anotan**: {res['BTTS'][0]:.1f}%")
        st.write(f"📊 **Probabilidades**: L({res['1X2'][0]:.1f}%) E({res['1X2'][1]:.1f}%) V({res['1X2'][2]:.1f}%)")
    with v2:
        st.subheader("🎯 MARCADORES")
        for sc, pr in res['TOP']: 
            st.markdown(f'<div class="score-badge">{sc} ({pr:.1f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.plotly_chart(px.imshow(res['MATRIZ'], text_auto=".1f", color_continuous_scale='Turbo'), use_container_width=True)

st.markdown("<p style='text-align:center; color:#333;'>OR936 ELITE | ENGINE v4.5 | HYBRID SYNC</p>", unsafe_allow_html=True)
