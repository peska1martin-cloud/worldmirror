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
st.set_page_config(page_title="WorldMirror Matrix V6", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception:
    st.error("❌ CHYBA: Nastavte API klíče v Secrets!")
    st.stop()

if 'view' not in st.session_state: st.session_state.view = 'map'
if 'selected_data' not in st.session_state: st.session_state.selected_data = None

# --- 2. MAPOVÁNÍ REGIONŮ A BAREV ---
REGION_MAP = {
    "ČR": "Czech Republic", "Slovensko": "Slovakia", "EU": "Europe", 
    "Severní Amerika": "USA Canada", "Rusko": "Russia", "Asie": "Asia", 
    "Blízký východ": "Middle East", "Afrika": "Africa", "Oceánie": "Australia Oceania"
}

BARVY = {
    "Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", 
    "Technologie": "#7D44CF", "AI": "#00FFFF", "Ekologie": "#32CD32", 
    "Akciové trhy": "#FFD700", "Průmysl": "#808080", "Showbyznys": "#FF69B4", 
    "Cestování": "#FFA500", "Krimi": "#000000"
}

def get_clean_color(kat):
    k = str(kat).strip().lower()
    mapping = {"vál": "#FF4B4B", "eko": "#29B09D", "pol": "#007BFF", "tech": "#7D44CF", "ai": "#00FFFF", "přír": "#32CD32", "akci": "#FFD700"}
    for klicek, barva in mapping.items():
        if klicek in k: return barva
    return "#AAAAAA"

# --- 3. FUNKCE ---
def nacti_historii():
    if os.path.exists("historie_v6.json"):
        with open("historie_v6.json", "r", encoding="utf-8") as f: return json.load(f)
    return {"global": [], "personal": []}

def uloz_do_historie(klic, zaznam):
    h = nacti_historii()
    h[klic] = [zaznam]
    with open("historie_v6.json", "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=4)

def ziskej_aktivni_model():
    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    preferovany = next((m for m in models if "1.5-pro" in m), models[0])
    return genai.GenerativeModel(preferovany)

def stahni_data_v6(query_str, include_rss=True):
    # NEWS API
    try:
        res = newsapi.get_everything(q=query_str, language='en', sort_by='relevancy', page_size=50)
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in res.get('articles', [])]
    except: clanky = []
    
    # RSS (jen pro globální nebo pokud si to uživatel přeje)
    rss_vysledky = []
    if include_rss:
        urls = ["https://tass.com/rss/v2.xml", "https://www.aljazeera.com/xml/rss/all.xml"]
        for u in urls:
            try:
                f = feedparser.parse(u)
                for e in f.entries[:5]: rss_vysledky.append({"zdroj": "RSS/Direct", "titulek": e.title, "link": e.link})
            except: continue
    
    vse = clanky + rss_vysledky
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_ai

def text_na_audio(text):
    if not text or len(text) < 5: return ""
    try:
        tts = gTTS(text=text[:1000], lang='cs') # Limit pro gTTS
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return ""

# --- 4. RENDERER ---
def render_v6_view(data_list, zdroje_list, key_prefix):
    if not data_list:
        st.info("Zatím zde nejsou žádná data. Klikněte na tlačítko pro skenování.")
        return

    m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
    for i, t in enumerate(data_list):
        barva = get_clean_color(t.get('kategorie', 'Politika'))
        try:
            folium.CircleMarker(
                location=[float(t.get('lat', 0)), float(t.get('lon', 0))], radius=12,
                popup=t.get('tema', 'Info'), tooltip=t.get('tema'), 
                color=barva, fill=True, fill_opacity=0.8
            ).add_to(m)
        except: continue
    
    map_res = st_folium(m, width="100%", height=450, key=f"map_{key_prefix}")
    
    if map_res.get('last_object_clicked_popup'):
        pop_val = map_res['last_object_clicked_popup']
        for t_obj in data_list:
            if t_obj.get('tema') == pop_val:
                st.session_state.selected_data = {"item": t_obj, "zdroje": zdroje_list}
                st.session_state.view = 'detail'
                st.rerun()

    st.divider()
    # DLAŽDICE
    for i in range(0, len(data_list), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(data_list):
                t_item = data_list[idx]
                c_code = get_clean_color(t_item.get('kategorie', 'Politika'))
                with cols[j]:
                    st.markdown(f'<div style="border-left: 10px solid {c_code}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t_item.get("tema", "Neznámé")}</h4><p>{t_item.get("bleskovka", "")}</p></div>', unsafe_allow_html=True)
                    if st.button(f"🔍 Detail {idx+1}", key=f"btn_{key_prefix}_{idx}"):
                        st.session_state.selected_data = {"item": t_item, "zdroje": zdroje_list}
                        st.session_state.view = 'detail'
                        st.rerun()

# --- 5. LOGIKA ---
historie = nacti_historii()

if st.session_state.view == 'map':
    st.sidebar.title("💎 WorldMirror Matrix")
    reg_sel = st.sidebar.multiselect("Regiony (Můj Svět):", list(REGION_MAP.keys()), default=["ČR", "Slovensko"])
    tem_sel = st.sidebar.multiselect("Kategorie (Můj Svět):", list(BARVY.keys()), default=["AI", "Akciové trhy"])
    
    if st.sidebar.button("🗑️ Vymazat historii"):
        if os.path.exists("historie_v6.json"): os.remove("historie_v6.json")
        st.session_state.clear()
        st.rerun()

    t_hot, t_pers = st.tabs(["🔥 Hot News ze světa", "✨ Tvůj vlastní svět"])

    with t_hot:
        if st.button("🚀 Skenovat Globální Radar"):
            with st.spinner("Analyzuji planetu..."):
                model = ziskej_aktivni_model()
                vse, txt = stahni_data_v6("geopolitics OR world economy", include_rss=True)
                prompt = f"""
                Jsi elitní geopolitický analytik. Vyber 10 nejdůležitějších globálních témat.
                Kategorie MUSÍ být jedna z těchto: Válka, Ekonomika, Politika, Technologie.
                U analytických polí (usa, eu, asie, vychod, jih, levice, pravice) napiš podrobný TEXTOVÝ rozbor, NE True/False.
                U pole 'clanek' napiš hloubkovou, barvitou reportáž v češtině o délce MINIMÁLNĚ 300 slov. 
                Vrať čistý JSON.
                ZDROJE: {txt}
                """
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                uloz_do_historie("global", {"data": json.loads(res.text), "zdroje": vse})
                st.rerun()
        if historie["global"]:
            st.markdown("🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie")
            render_v6_view(historie["global"][0].get("data"), historie["global"][0].get("zdroje"), "glob")

    with t_pers:
        if st.button("⚡ Sestavit Můj Svět"):
            with st.spinner("Hledám lokální a specifické zprávy..."):
                model = ziskej_aktivni_model()
                eng_regions = [REGION_MAP[r] for r in reg_sel]
                q_p = f"({ ' OR '.join(eng_regions) }) AND ({ ' OR '.join(tem_sel) if tem_sel else 'news' })"
                vse_p, txt_p = stahni_data_v6(q_p, include_rss=False)
                prompt_p = f"""
                Jsi analytik zaměřený na tyto regiony: {reg_sel} a témata: {tem_sel}.
                Prioritně vyber 10 témat, která se TÝKAJÍ TĚCHTO REGIONŮ.
                U pole 'clanek' napiš podrobnou reportáž o délce MINIMÁLNĚ 300 slov.
                U analytických polí piš VŽDY TEXT, nikdy ne True/False.
                Vrať čistý JSON.
                ZDROJE: {txt_p}
                """
                res_p = model.generate_content(prompt_p, generation_config={"response_mime_type": "application/json"})
                uloz_do_historie("personal", {"data": json.loads(res_p.text), "zdroje": vse_p})
                st.rerun()
        if historie["personal"]:
            st.markdown("🔴 Válka 🟢 Ekonomika 🔵 Politika 🟣 Tech 🤖 AI 💹 Trhy 🌿 Eko 🏗️ Průmysl 💄 Show 🚔 Krimi")
            render_v6_view(historie["personal"][0].get("data"), historie["personal"][0].get("zdroje"), "pers")

elif st.session_state.view == 'detail':
    sel = st.session_state.selected_data
    t, zdroje = sel["item"], sel["zdroje"]
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema', 'Detail')}")
    st.info(t.get('fakta', 'Bez popisu'))
    
    st.markdown("### 🌍 Geopolitická matice")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t.get('usa', 'Analýza nedostupná'))
    with c2: st.markdown("🇪🇺 **EU**"); st.caption(t.get('eu', 'Analýza nedostupná'))
    with c3: st.markdown("🟣 **Asie**"); st.caption(t.get('asie', 'Analýza nedostupná'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ**"); st.caption(t.get('vychod', 'Analýza nedostupná'))
    with c5: st.markdown("🌏 **Jih / Arab**"); st.caption(t.get('jih', 'Analýza nedostupná'))
    
    st.divider()
    st.markdown("### 🧠 Ideologické narativy")
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal / Levice**\n\n{t.get('levice', 'Analýza nedostupná')}")
    with cr: st.error(f"🦅 **Conservative / Pravice**\n\n{t.get('pravice', 'Analýza nedostupná')}")
    
    st.subheader("📝 Reportáž")
    st.write("🔊 *Přečíst reportáž:*")
    st.markdown(text_na_audio(t.get('clanek', '')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.6;">{t.get("clanek", "Reportáž nebyla vygenerována.")}</div>', unsafe_allow_html=True)
    st.error(f"⚠️ **Bod sváru:** {t.get('bod_svaru', 'Nespecifikováno')}")
