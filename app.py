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
st.set_page_config(page_title="WorldMirror Matrix V8", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except:
    st.error("Chybí API klíče v Secrets!")
    st.stop()

# Inicializace stavu
if 'global_data' not in st.session_state: st.session_state.global_data = None
if 'personal_data' not in st.session_state: st.session_state.personal_data = None
if 'view' not in st.session_state: st.session_state.view = 'map'

# --- 2. MODEL A BARVY ---
def ziskej_funkcni_model():
    """Najde přesný název modelu dostupný pro daný API klíč."""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Priorita: 1.5-pro, pak 1.5-flash
        vybrany = next((m for m in models if "1.5-pro" in m), 
                       next((m for m in models if "1.5-flash" in m), models[0]))
        return genai.GenerativeModel(vybrany)
    except Exception as e:
        st.error(f"Nelze nalézt AI model: {e}")
        return None

BARVY = {
    "Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF",
    "AI": "#00FFFF", "Ekologie": "#32CD32", "Akciové trhy": "#FFD700", "Průmysl": "#808080",
    "Showbyznys": "#FF69B4", "Cestování": "#FFA500", "Krimi": "#000000"
}

def get_color(kat):
    k = str(kat).strip().capitalize()
    for kl, val in BARVY.items():
        if kl[:4] in k: return val
    return "gray"

# --- 3. SBĚR DAT (RSS + API) ---
def stahni_zpravy_v8(query, extra_czech=False):
    vse = []
    # NewsAPI
    try:
        res = newsapi.get_everything(q=query, language='en', sort_by='relevancy', page_size=40)
        vse += [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in res.get('articles', [])]
    except: pass
    
    # RSS (Ruské, Arabské a ČESKÉ FINANČNÍ)
    rss_urls = [
        "https://www.seznamzpravy.cz/rss",
        "https://archiv.hn.cz/rss/",
        "https://tass.com/rss/v2.xml",
        "https://www.aljazeera.com/xml/rss/all.xml"
    ]
    for url in rss_urls:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:10]:
                vse.append({"zdroj": "RSS/Direct", "titulek": e.title, "link": e.link})
        except: continue
        
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_ai

def text_na_audio(text):
    if not text or len(text) < 10: return ""
    try:
        tts = gTTS(text=text[:2000], lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except: return ""

# --- 4. RENDERER ---
def render_matrix_v8(data, zdroje, key_type):
    if not data:
        st.info("Žádná data. Klikněte na skenování.")
        return

    m = folium.Map(location=[25, 12], zoom_start=2, tiles="CartoDB dark_matter")
    for i, t in enumerate(data):
        c = get_color(t.get('kategorie'))
        try:
            folium.CircleMarker(
                location=[float(t.get('lat', 0)), float(t.get('lon', 0))], radius=12,
                popup=t.get('tema'), tooltip=t.get('tema'), color=c, fill=True, fill_opacity=0.8
            ).add_to(m)
        except: continue
    
    res_map = st_folium(m, width="100%", height=450, key=f"map_{key_type}")
    
    if res_map.get('last_object_clicked_popup'):
        pop = res_map['last_object_clicked_popup']
        for obj in data:
            if obj.get('tema') == pop:
                st.session_state.selected_data = {"item": obj, "zdroje": zdroje}
                st.session_state.view = 'detail'
                st.rerun()

    st.divider()
    for i in range(0, len(data), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(data):
                t_item = data[idx]
                c_code = get_color(t_item.get('kategorie'))
                with cols[j]:
                    st.markdown(f'<div style="border-left: 10px solid {c_code}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t_item.get("tema")}</h4><p>{t_item.get("bleskovka")}</p></div>', unsafe_allow_html=True)
                    if st.button(f"🔍 Rozbor {idx+1}", key=f"btn_{key_type}_{idx}"):
                        st.session_state.selected_data = {"item": t_item, "zdroje": zdroje}
                        st.session_state.view = 'detail'
                        st.rerun()

# --- 5. LOGIKA ---
if st.session_state.view == 'map':
    st.sidebar.title("💎 WorldMirror Matrix V8")
    reg_sel = st.sidebar.multiselect("Regiony:", ["ČR", "Slovensko", "EU", "USA", "Rusko", "Asie"], default=["ČR", "Slovensko"])
    tem_sel = st.sidebar.multiselect("Kategorie:", list(BARVY.keys()), default=["Akciové trhy", "AI"])
    
    if st.sidebar.button("🗑️ Reset"):
        st.session_state.clear()
        st.rerun()

    t1, t2 = st.tabs(["🔥 Hot News ze světa", "✨ Tvůj vlastní svět"])

    with t1:
        if st.button("🚀 Skenovat Globální Radar"):
            with st.spinner("Trianguluji velmoci..."):
                model = ziskej_funkcni_model()
                clanky, text_ai = stahni_zpravy_v8("geopolitics OR world news OR major war")
                prompt = f"""Vyber 10 klíčových globálních témat. Kategorie POUZE: Válka, Ekonomika, Politika, Technologie.
                Analýzy (usa, eu, asie, vychod, jih, levice, pravice) musí být TEXTOVÉ (min 3 věty). 
                Reportáž (clanek) musí být DLOUHÁ (min 500 slov) a v ČEŠTINĚ. JSON formát. ZDROJE: {text_ai}"""
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.global_data = {"data": json.loads(res.text), "zdroje": clanky}
                st.rerun()
        if st.session_state.global_data:
            st.markdown("🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie")
            render_matrix(st.session_state.global_data["data"], st.session_state.global_data["zdroje"], "glob")

    with t2:
        if st.button("⚡ Sestavit Můj Svět"):
            with st.spinner("Hledám české a specifické zprávy..."):
                model = ziskej_funkcni_model()
                q = f"({ ' OR '.join(reg_sel) }) AND ({ ' OR '.join(tem_sel) })"
                clanky, text_ai = stahni_zpravy_v8(q)
                prompt = f"""Jsi osobní analytik. Zaměř se na {reg_sel} a {tem_sel}. Vyber 10 témat. 
                DŮLEŽITÉ: Pokud jsou v datech zprávy o českém byznysu (CSG, ČEZ, PPF, IPO), dej jim prioritu!
                Reportáž (clanek) musí mít MINIMÁLNĚ 500 slov. JSON formát. ZDROJE: {text_ai}"""
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                st.session_state.personal_data = {"data": json.loads(res.text), "zdroje": clanky}
                st.rerun()
        if st.session_state.personal_data:
            st.markdown("🔴 Válka 🟢 Ekonomika 🔵 Politika 🟣 Tech 🤖 AI 💹 Trhy 🌿 Eko")
            render_matrix(st.session_state.personal_data["data"], st.session_state.personal_data["zdroje"], "pers")

elif st.session_state.view == 'detail':
    sel = st.session_state.selected_data
    t, zdroje = sel["item"], sel["zdroje"]
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    
    st.title(f"🔍 {t.get('tema')}")
    st.markdown(text_na_audio(t.get('fakta')), unsafe_allow_html=True)
    st.info(t.get('fakta'))
    
    st.markdown("### 🌍 Geopolitická matice")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(str(t.get('usa')))
    with c2: st.markdown("🇪🇺 **EU**"); st.caption(str(t.get('eu')))
    with c3: st.markdown("🟣 **Asie**"); st.caption(str(t.get('asie')))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ**"); st.caption(str(t.get('vychod')))
    with c5: st.markdown("🌏 **Jih / Arab**"); st.caption(str(t.get('jih')))
    
    st.divider()
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal / Levice**\n\n{str(t.get('levice'))}")
    with cr: st.error(f"🦅 **Conservative / Pravice**\n\n{str(t.get('pravice'))}")
    
    st.subheader("📝 Hloubková reportáž")
    st.markdown(text_na_audio(t.get('clanek')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.8; font-size: 1.1em;">{t.get("clanek")}</div>', unsafe_allow_html=True)
