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

# --- 1. ZÁKLADNÍ NASTAVENÍ ---
st.set_page_config(page_title="WorldMirror Matrix: Ultimate Edition", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except:
    st.error("Chybí API klíče v Secrets!")
    st.stop()

# Správa stavu aplikace
if 'view' not in st.session_state: st.session_state.view = 'map'
if 'selected_data' not in st.session_state: st.session_state.selected_data = None
if 'global_data' not in st.session_state: st.session_state.global_data = None
if 'personal_data' not in st.session_state: st.session_state.personal_data = None

# --- 2. BARVY A MAPOVÁNÍ REGIONŮ ---
BARVY = {
    "Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF",
    "AI": "#00FFFF", "Ekologie": "#32CD32", "Akciové trhy": "#FFD700", "Průmysl": "#808080",
    "Showbyznys": "#FF69B4", "Cestování": "#FFA500", "Krimi": "#000000"
}

REGION_MAP = {
    "ČR": "Czech Republic", "Slovensko": "Slovakia", "EU": "Europe", 
    "USA": "USA", "Rusko": "Russia", "Asie": "Asia", "Blízký východ": "Middle East"
}

def get_clean_color(kat):
    k = str(kat).strip().lower()
    if "vál" in k: return BARVY["Válka"]
    if "eko" in k: return BARVY["Ekonomika"]
    if "pol" in k: return BARVY["Politika"]
    if "tech" in k: return BARVY["Technologie"]
    if "ai" in k: return BARVY["AI"]
    if "akci" in k or "trh" in k: return BARVY["Akciové trhy"]
    return "gray"

# --- 3. POMOCNÉ MOZKOVÉ FUNKCE ---

def ziskej_aktivni_model():
    """Najde funkční model na tvém účtu (řeší NotFound error)."""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        vybrany = next((m for m in models if "1.5-pro" in m), models[0])
        return genai.GenerativeModel(vybrany)
    except: return None

def stahni_data_komplet(query_str):
    """Kombinuje globální NewsAPI a české/východní RSS feedy."""
    vse = []
    # NewsAPI
    try:
        res = newsapi.get_everything(q=query_str, language='en', sort_by='relevancy', page_size=40)
        vse += [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in res.get('articles', [])]
    except: pass
    
    # RSS - Seznam Zprávy, HN, TASS, Al Jazeera
    rss_urls = ["https://www.seznamzpravy.cz/rss", "https://archiv.hn.cz/rss/", "https://tass.com/rss/v2.xml", "https://www.aljazeera.com/xml/rss/all.xml"]
    for url in rss_urls:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:8]:
                vse.append({"zdroj": "RSS/Direct", "titulek": e.title, "link": e.link})
        except: continue
    
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_ai

def text_na_audio(text):
    if not text or len(str(text)) < 10: return ""
    try:
        tts = gTTS(text=str(text)[:2000], lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except: return ""

# --- 4. RENDERER (DASHBOARD) ---

def render_matrix_view(data_list, zdroje_list, key_prefix):
    if not data_list:
        st.info("Žádná data. Spusťte skenování tlačítkem výše.")
        return

    # Mapa
    m = folium.Map(location=[25, 15], zoom_start=2, tiles="CartoDB dark_matter")
    for i, t in enumerate(data_list):
        barva = get_clean_color(t.get('kategorie'))
        folium.CircleMarker(
            location=[float(t.get('lat', 0)), float(t.get('lon', 0))], radius=12,
            popup=t.get('tema'), tooltip=t.get('tema'), color=barva, fill=True, fill_opacity=0.8
        ).add_to(m)
    
    map_res = st_folium(m, width="100%", height=450, key=f"map_{key_prefix}")
    
    # Kliknutí na mapu
    if map_res.get('last_object_clicked_popup'):
        pop = map_res['last_object_clicked_popup']
        for obj in data_list:
            if obj.get('tema') == pop:
                st.session_state.selected_data = {"item": obj, "zdroje": zdroje_list}
                st.session_state.view = 'detail'
                st.rerun()

    # Legenda
    if key_prefix == "glob":
        st.markdown('<div style="text-align: center; font-weight: bold; margin: 10px;">🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align: center; font-weight: bold; margin: 10px;">🔴 Válka 🟢 Eko 🔵 Pol 🟣 Tech 🤖 AI 💹 Trhy 🌿 Eko 💄 Show</div>', unsafe_allow_html=True)

    st.divider()

    # Dlaždice
    for i in range(0, len(data_list), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(data_list):
                t_item = data_list[idx]
                c_code = get_clean_color(t_item.get('kategorie'))
                with cols[j]:
                    st.markdown(f'<div style="border-left: 10px solid {c_code}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t_item.get("tema")}</h4><p>{t_item.get("bleskovka")}</p></div>', unsafe_allow_html=True)
                    if st.button(f"🔍 Detail zprávy {idx+1}", key=f"btn_{key_prefix}_{idx}"):
                        st.session_state.selected_data = {"item": t_item, "zdroje": zdroje_list}
                        st.session_state.view = 'detail'
                        st.rerun()

# --- 5. LOGIKA STRÁNEK ---

if st.session_state.view == 'map':
    # Sidebar nastavení
    st.sidebar.title("💎 WorldMirror Matrix")
    reg_sel = st.sidebar.multiselect("Regiony (Můj Svět):", list(REGION_MAP.keys()), default=["ČR", "Slovensko"])
    tem_sel = st.sidebar.multiselect("Kategorie (Můj Svět):", list(BARVY.keys()), default=["AI", "Akciové trhy"])
    
    if st.sidebar.button("🗑️ Resetovat aplikaci"):
        st.session_state.clear()
        st.rerun()

    st.title("⚖️ WorldMirror: Dualitní Matrix")
    t_hot, t_my = st.tabs(["🔥 Hot News ze světa", "✨ Tvůj vlastní svět"])

    with t_hot:
        if st.button("🚀 Skenovat Globální Radar"):
            with st.spinner("Provádím multipolární sken..."):
                model = ziskej_aktivni_model()
                clanky, text_ai = stahni_data_komplet("geopolitics OR world news OR economy")
                prompt = f"""Vyber 10 nejdůležitějších globálních témat. Kategorie JEN: Válka, Ekonomika, Politika, Technologie. 
                U analýz (usa, eu, asie, vychod, jih, levice, pravice) napiš aspoň 3 věty TEXTU. 
                Reportáž (clanek) musí mít alespoň 500 slov. JSON formát. ZDROJE: {text_ai}"""
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.global_data = {"data": json.loads(res.text), "zdroje": clanky}
                st.rerun()
        if st.session_state.global_data:
            render_matrix_view(st.session_state.global_data["data"], st.session_state.global_data["zdroje"], "glob")

    with t_my:
        if st.button("⚡ Sestavit Můj Svět"):
            with st.spinner("Hledám lokální a byznysové zprávy..."):
                model = ziskej_aktivni_model()
                eng_regions = [REGION_MAP[r] for r in reg_sel]
                q_p = f"({ ' OR '.join(eng_regions) }) AND ({ ' OR '.join(tem_sel) })"
                clanky_p, text_ai_p = stahni_data_komplet(q_p)
                prompt_p = f"""Jsi osobní analytik pro {reg_sel}. Vyber 10 témat. 
                DŮLEŽITÉ: Pokud jsou v datech zprávy o českých firmách (ČEZ, CSG, PPF, IPO), dej jim prioritu!
                Analýzy musí být TEXTOVÉ. Reportáž (clanek) musí mít alespoň 500 slov. JSON formát. ZDROJE: {text_ai_p}"""
                res_p = model.generate_content(prompt_p, generation_config={"response_mime_type": "application/json"})
                st.session_state.personal_data = {"data": json.loads(res_p.text), "zdroje": clanky_p}
                st.rerun()
        if st.session_state.personal_data:
            render_matrix_view(st.session_state.personal_data["data"], st.session_state.personal_data["zdroje"], "pers")

elif st.session_state.view == 'detail':
    sel = st.session_state.selected_data
    t, zdroje = sel["item"], sel["zdroje"]
    
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema')}")
    
    st.subheader("🔊 Audio: Fakta")
    st.markdown(text_na_audio(t.get('fakta')), unsafe_allow_html=True)
    st.info(t.get('fakta', 'Popis chybí.'))
    
    st.markdown("### 🌍 Geopolitická matice (5 stran)")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(str(t.get('usa', 'Analýza nedostupná')))
    with c2: st.markdown("🇪🇺 **EU**"); st.caption(str(t.get('eu', 'Analýza nedostupná')))
    with c3: st.markdown("🟣 **Asie**"); st.caption(str(t.get('asie', 'Analýza nedostupná')))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ**"); st.caption(str(t.get('vychod', 'Analýza nedostupná')))
    with c5: st.markdown("🌏 **Jih / Arabský svět**"); st.caption(str(t.get('jih', 'Analýza nedostupná')))
    
    st.divider()
    st.markdown("### 🧠 Ideologické narativy")
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal / Levice**\n\n{str(t.get('levice', 'Analýza nedostupná'))}")
    with cr: st.error(f"🦅 **Conservative / Pravice**\n\n{str(t.get('pravice', 'Analýza nedostupná'))}")
    
    st.subheader("📝 Hloubková reportáž")
    st.write("🔊 *Přečíst reportáž:*")
    st.markdown(text_na_audio(t.get('clanek')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.8; font-size: 1.1em;">{t.get("clanek", "Reportáž nebyla vygenerována.")}</div>', unsafe_allow_html=True)
    
    st.error(f"⚠️ **Bod sváru:** {t.get('bod_svaru', 'Nespecifikováno')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    for aid in t.get('zdroje_id', []):
        if isinstance(aid, int) and aid < len(zdroje):
            art = zdroje[aid]
            st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
