import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import os
import re
from datetime import datetime
from streamlit_folium import st_folium
import folium

# --- 1. KONFIGURACE A KLÍČE ---
st.set_page_config(page_title="WorldMirror Matrix Map", page_icon="🌍", layout="wide")

try:
    # Načtení klíčů ze Streamlit Secrets (Trezoru)
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception:
    st.error("❌ CHYBA: Klíče nejsou správně nastaveny v Secrets na Streamlit Cloudu!")
    st.stop()

# --- 2. INICIALIZACE STAVU (Session State) ---
if 'view' not in st.session_state:
    st.session_state.view = 'map'
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = None

# --- 3. POMOCNÉ FUNKCE ---

def ziskej_funkcni_model():
    try:
        modely = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        vybrany = next((m for m in modely if "flash" in m.lower()), modely[0])
        return genai.GenerativeModel(vybrany)
    except: return None

def vytahni(text, klic):
    # Robustní Regex: najde klíč bez ohledu na hvězdičky, mezery nebo velikost písmen
    pattern = rf"(?i)^\s*\*{{0,2}}{klic}\*{{0,2}}\s*:?\s*(.*)"
    for line in text.split("\n"):
        match = re.search(pattern, line.strip())
        if match:
            res = match.group(1).strip()
            return res if res else "Informace chybí"
    return "Nenalezeno"

def nacti_historii():
    if os.path.exists("historie.json"):
        with open("historie.json", "r", encoding="utf-8") as f: return json.load(f)
    return []

def uloz_do_historie(novy_zaznam):
    historie = nacti_historii()
    historie.insert(0, novy_zaznam)
    with open("historie.json", "w", encoding="utf-8") as f:
        json.dump(historie, f, ensure_ascii=False, indent=4)

def stahni_zpravy():
    try:
        data = newsapi.get_top_headlines(language='en', page_size=50)
        clanky = data.get('articles', [])
        text_pro_ai = ""
        pro_web = []
        for i, c in enumerate(clanky):
            zdroj = c['source']['name']
            text_pro_ai += f"[{i}] {zdroj}: {c['title']}\n"
            pro_web.append({"id": i, "zdroj": zdroj, "titulek": c['title'], "link": c['url'], "info": c.get('description', '')})
        return pro_web, text_pro_ai
    except: return [], ""

# --- 4. HLAVNÍ LOGIKA APLIKACE ---

st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

# --- POHLED A: MAPA A DASHBOARD ---
if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Geopolitická Mapa")
    
    if st.button("🚀
