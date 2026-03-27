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
st.set_page_config(page_title="WorldMirror Matrix V7", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except:
    st.error("Chybí API klíče v Secrets!")
    st.stop()

# Inicializace stavu (aby se nic nemazalo při překliku)
if 'global_data' not in st.session_state: st.session_state.global_data = None
if 'personal_data' not in st.session_state: st.session_state.personal_data = None
if 'view' not in st.session_state: st.session_state.view = 'map'

# --- 2. BARVY A DEFINICE ---
BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF",
         "AI": "#00FFFF", "Ekologie": "#32CD32", "Akciové trhy": "#FFD700", "Průmysl": "#808080",
         "Showbyznys": "#FF69B4", "Cestování": "#FFA500", "Krimi": "#000000"}

def get_color(kat):
    k = str(kat).strip().lower()
    mapping = {"vál": "#FF4B4B", "eko": "#29B09D", "pol": "#007BFF", "tech": "#7D44CF", "ai": "#00FFFF", "akci": "#FFD700"}
    for klicek, barva in mapping.items():
        if klicek in k: return barva
    return "gray"

# --- 3. SBĚR DAT (S ČESKOU INJEKCÍ) ---
def stahni_vse(query_str, je_osobni=False):
    vysledky = []
    # 1. News API (Globální zdroje)
    try:
        res = newsapi.get_everything(q=query_str, language='en', sort_by='relevancy', page_size=40)
        vysledky += [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in res.get('articles', [])]
    except: pass

    # 2. RSS Kanály (Východ + ARAB + ČESKÝ BYZNYS)
    rss_urls = [
        "https://www.seznamzpravy.cz/rss", # Seznam pro české info (CSG, atd.)
        "https://archiv.hn.cz/rss/",       # Hospodářky
        "https://tass.com/rss/v2.xml", 
        "https://www.aljazeera.com/xml/rss/all.xml"
    ]
    for url in rss_urls:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:10]:
                vysledky.append({"zdroj": "RSS/Direct", "titulek": e.title, "link": e.link})
        except: continue
    
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vysledky)])
    return vysledky, text_ai

def text_na_audio(text):
    if not text or len(text) < 10: return ""
    try:
        tts = gTTS(text=text[:1500], lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{base64.b64encode(fp.read()).decode()}" type="audio/mp3"></audio>'
    except: return ""

# --- 4. RENDERER ---
def render_matrix(data_list, zdroje_list, key_type):
    if not data_list:
        st.warning("Žádná data k zobrazení. Spusťte analýzu.")
        return

    m = folium.Map(location=[25, 15], zoom_start=2, tiles="CartoDB dark_matter")
    for i, t in enumerate(data_list):
        c = get_color(t.get('kategorie'))
        try:
            folium.CircleMarker(
                location=[float(t.get('lat', 0)), float(t.get('lon', 0))], radius=12,
                popup=t.get('tema'), tooltip=t.get('tema'), color=c, fill=True, fill_opacity=0.8
            ).add_to(m)
        except: continue
    
    map_res = st_folium(m, width="100%", height=450, key=f"map_{key_type}")
    
    if map_res.get('last_object_clicked_popup'):
        pop = map_res['last_object_clicked_popup']
        for t_obj in data_list:
            if t_obj.get('tema') == pop:
                st.session_state.selected_data = {"item": t_obj, "zdroje": zdroje_list}
                st.session_state.view = 'detail'
                st.rerun()

    st.markdown("---")
    for i in range(0, len(data_list), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(data_list):
                t = data_list[idx]
                c = get_color(t.get('kategorie'))
                with cols[j]:
                    st.markdown(f'<div style="border-left: 10px solid {c}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t.get("tema")}</h4><p>{t.get("bleskovka")}</p></div>', unsafe_allow_html=True)
                    if st.button(f"🔍 Otevřít {idx+1}", key=f"btn_{key_type}_{idx}"):
                        st.session_state.selected_data = {"item": t, "zdroje": zdroje_list}
                        st.session_state.view = 'detail'
                        st.rerun()

# --- 5. LOGIKA STRÁNEK ---
if st.session_state.view == 'map':
    st.sidebar.title("💎 WorldMirror Matrix")
    reg = st.sidebar.multiselect("Regiony:", ["ČR", "Slovensko", "EU", "USA", "Rusko", "Asie"], default=["ČR", "Slovensko"])
    tem = st.sidebar.multiselect("Kategorie:", list(BARVY.keys()), default=["Akciové trhy", "AI"])
    
    if st.sidebar.button("🗑️ Reset"):
        st.session_state.clear()
        st.rerun()

    st.title("⚖️ WorldMirror: Dualitní Matrix V7")
    t1, t2 = st.tabs(["🔥 Hot News ze světa", "✨ Tvůj vlastní svět"])

    with t1:
        if st.button("🚀 Skenovat Globální Radar"):
            with st.spinner("Trianguluji velmoci..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                clanky, text_ai = stahni_vse("geopolitics OR world economy OR major war")
                prompt = f"""Analyzuj zprávy a vyber 10 klíčových globálních témat. Kategorie: Válka, Ekonomika, Politika, Technologie. 
                U VŠECH polí (usa, eu, asie, vychod, jih, levice, pravice) napiš podrobnou analýzu (min 3 věty). NESMÍŠ napsat 'Analýza nedostupná'.
                Reportáž (clanek) musí mít alespoň 400 slov. JSON formát. ZDROJE: {text_ai}"""
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.global_data = {"data": json.loads(res.text), "zdroje": clanky}
        
        if st.session_state.global_data:
            render_matrix(st.session_state.global_data["data"], st.session_state.global_data["zdroje"], "glob")

    with t2:
        if st.button("⚡ Sestavit Můj Svět"):
            with st.spinner("Hledám české i světové zprávy..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                q = f"({ ' OR '.join(reg) }) AND ({ ' OR '.join(tem) })"
                clanky, text_ai = stahni_vse(q, je_osobni=True)
                prompt = f"""Jsi osobní analytik. Zaměř se na {reg} a {tem}. Vyber 10 témat. Pokud jsou v datech zprávy o českých firmách (např. CSG, ČEZ, PPF), dej jim absolutní prioritu. 
                U každého pole napiš podrobný rozbor. Reportáž (clanek) musí být Dlouhá a analytická (min 400 slov). JSON formát. ZDROJE: {text_ai}"""
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.personal_data = {"data": json.loads(res.text), "zdroje": clanky}
        
        if st.session_state.personal_data:
            render_matrix(st.session_state.personal_data["data"], st.session_state.personal_data["zdroje"], "pers")

elif st.session_state.view == 'detail':
    sel = st.session_state.selected_data
    t, zdroje = sel["item"], sel["zdroje"]
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    
    st.title(f"🔍 {t.get('tema')}")
    st.markdown(text_na_audio(t.get('fakta')), unsafe_allow_html=True)
    st.info(t.get('fakta', 'Bez popisu'))
    
    st.markdown("### 🌍 Geopolitická matice")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t.get('usa'))
    with c2: st.markdown("🇪🇺 **EU**"); st.caption(t.get('eu'))
    with c3: st.markdown("🟣 **Asie**"); st.caption(t.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ**"); st.caption(t.get('vychod'))
    with c5: st.markdown("🌏 **Jih / Arab**"); st.caption(t.get('jih'))
    
    st.divider()
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal / Levice**\n\n{t.get('levice')}")
    with cr: st.error(f"🦅 **Conservative / Pravice**\n\n{t.get('pravice')}")
    
    st.subheader("📝 Hloubková reportáž")
    st.markdown(text_na_audio(t.get('clanek')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.8; font-size: 1.1em;">{t.get("clanek")}</div>', unsafe_allow_html=True)
    st.error(f"⚠️ **Bod sváru:** {t.get('bod_svaru')}")
