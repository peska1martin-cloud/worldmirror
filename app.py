import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import os
import re
from datetime import datetime
from streamlit_folium import st_folium
import folium
from gtts import gTTS
import base64
from io import BytesIO
import feedparser

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="WorldMirror Matrix: Dual View", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception:
    st.error("❌ CHYBA: Nastavte API klíče v Secrets!")
    st.stop()

if 'view' not in st.session_state: st.session_state.view = 'map'
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = None

# --- 2. DEFINICE BAREV ---
BARVY = {
    "Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF",
    "AI": "#00FFFF", "Ekologie": "#32CD32", "Akciové trhy": "#FFD700", "Průmysl": "#808080",
    "Showbyznys": "#FF69B4", "Cestování": "#FFA500", "Krimi": "#000000"
}
BARVY_BG = {k: f"{v}22" for k, v in BARVY.items()}

def get_color(kat):
    k = str(kat).strip().capitalize()
    for kl, barva in BARVY.items():
        if kl[:4] in k: return barva
    return "gray"

# --- 3. LOGIKA SBĚRU DAT ---

@st.cache_data(ttl=3600) # Globální zprávy se uloží na hodinu
def stahni_globalni_data():
    # NewsAPI Top Headlines pro celý svět
    try:
        data = newsapi.get_top_headlines(language='en', page_size=40)
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: clanky = []
    
    # RSS Východ (TASS, RT...)
    vychod = []
    for url in ["https://tass.com/rss/v2.xml", "https://www.rt.com/rss/news/", "https://www.aljazeera.com/xml/rss/all.xml"]:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:5]: vychod.append({"zdroj": "RSS/Direct", "titulek": e.title, "link": e.link})
        except: continue
    
    vse = clanky + vychod
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_ai

def stahni_osobni_data(reg, tem):
    q = f"({ ' OR '.join(reg) if reg else 'World' }) AND ({ ' OR '.join(tem) if tem else 'News' })"
    try:
        data = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=40)
        vse = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
        text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
        return vse, text_ai
    except: return [], ""

def text_na_audio(text):
    try:
        tts = gTTS(text=text, lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return "Audio nelze vygenerovat."

# --- 4. SIDEBAR ---
st.sidebar.title("💎 WorldMirror Premium")
reg_sel = st.sidebar.multiselect("Regiony:", ["ČR", "Slovensko", "EU", "Severní Amerika", "Rusko", "Asie", "Blízký východ", "Oceánie", "Afrika"], default=["ČR", "Slovensko"])
tem_sel = st.sidebar.multiselect("Kategorie:", list(BARVY.keys()), default=["AI", "Akciové trhy"])

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.clear()
    st.rerun()

# --- 5. HLAVNÍ PLOCHA ---
if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror Informační Dualita")
    
    # Rozdělení na Taby
    tab1, tab2 = st.tabs(["🔥 Hot News ze světa", "✨ Tvůj vlastní svět"])
    
    with tab1:
        if st.button("🚀 Skenovat světový radar"):
            with st.spinner("Trianguluji globální velmoci..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                clanky, text_ai = stahni_globalni_data()
                prompt = f"Jsi analytik. Vyber 10 nejdůležitějších globálních témat. Odpověz VÝHRADNĚ jako JSON pole 10 objektů. Struktura: {{tema, kategorie, lat, lon, bleskovka, fakta, usa, eu, asie, vychod, jih, levice, pravice, bod_svaru, clanek, zdroje_id}}. ZDROJE: {text_ai}"
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.global_news = {"data": json.loads(res.text), "zdroje": clanky}
        
        if 'global_news' in st.session_state:
            res = st.session_state.global_news
            # Vykreslení mapy a dlaždic pro Globální News...
            # (Použijeme stejnou logiku jako dříve, ale s daty z res['data'])
            st.subheader("Aktuální stav planety")
            # [Zde by následoval kód pro mapu a dlaždice jako v předchozím funkčním kódu]

    with tab2:
        if st.button("⚡ Sestavit můj osobní svět"):
            with st.spinner(f"Hledám zprávy pro: {', '.join(reg_sel)}..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                clanky, text_ai = stahni_osobni_data(reg_sel, tem_sel)
                prompt = f"Jsi osobní analytik. Vyber 10 témat relevantních pro tyto regiony a kategorie: {reg_sel}, {tem_sel}. Odpověz VÝHRADNĚ jako JSON. ZDROJE: {text_ai}"
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.personal_news = {"data": json.loads(res.text), "zdroje": clanky}
        
        if 'personal_news' in st.session_state:
            st.subheader(f"Můj Svět: {', '.join(reg_sel)}")
            # [Zde by následoval kód pro mapu a dlaždice s daty z st.session_state.personal_news]

# --- 6. UNIVERZÁLNÍ ZOBRAZENÍ (MAPA + DLAŽDICE) ---
# Tuto část kódu je nejlepší zabalit do funkce, abychom ji nemuseli psát 2x pro každý tab.
