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
st.set_page_config(page_title="WorldMirror Matrix Elite+ PRO", page_icon="⚖️", layout="wide")

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

# --- 2. DEFINICE BAREV A KATEGORIÍ ---
BARVY = {
    "Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", 
    "Technologie": "#7D44CF", "AI": "#00FFFF", "Ekologie": "#32CD32", 
    "Akciové trhy": "#FFD700", "Průmysl": "#808080", "Showbyznys": "#FF69B4", 
    "Cestování": "#FFA500", "Krimi": "#000000"
}
BARVY_BG = {k: f"{v}22" for k, v in BARVY.items()}

def get_clean_color(kat):
    k = str(kat).strip().lower()
    if "vál" in k: return BARVY["Válka"]
    if "eko" in k: return BARVY["Ekonomika"]
    if "pol" in k: return BARVY["Politika"]
    if "tech" in k: return BARVY["Technologie"]
    if "ai" in k: return BARVY["AI"]
    if "přír" in k or "ekol" in k: return BARVY["Ekologie"]
    if "akci" in k or "trh" in k: return BARVY["Akciové trhy"]
    if "prům" in k: return BARVY["Průmysl"]
    if "show" in k or "kult" in k: return BARVY["Showbyznys"]
    if "cest" in k: return BARVY["Cestování"]
    if "krim" in k: return BARVY["Krimi"]
    return "#AAAAAA"

# --- 3. POMOCNÉ FUNKCE (Historie, Audio, Sběr) ---
def nacti_historii():
    if os.path.exists("historie_v4.json"):
        with open("historie_v4.json", "r", encoding="utf-8") as f: return json.load(f)
    return {"global": [], "personal": []}

def uloz_do_historie(klic, zaznam):
    h = nacti_historii()
    h[klic] = [zaznam] # Ukládáme vždy jen poslední sken pro daný tab
    with open("historie_v4.json", "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=4)

def stahni_data(query_str="geopolitics OR war OR economy"):
    # News API
    try:
        data = newsapi.get_everything(q=query_str, language='en', sort_by='publishedAt', page_size=40)
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: clanky = []
    # RSS Direct (Východ + Arab)
    rss_vysledky = []
    for url in ["https://tass.com/rss/v2.xml", "https://www.rt.com/rss/news/", "https://www.aljazeera.com/xml/rss/all.xml"]:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:5]: rss_vysledky.append({"zdroj": "RSS/Direct", "titulek": e.title, "link": e.link})
        except: continue
    vse = clanky + rss_vysledky
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_ai

def text_na_audio(text):
    try:
        tts = gTTS(text=text, lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return "Audio nelze vygenerovat."

# --- 4. RENDERER (SPOLEČNÝ PRO OBA TABY) ---
def render_dashboard(data_list, zdroje_list):
    # Mapa
    m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
    for i, t in enumerate(data_list):
        c = get_clean_color(t.get('kategorie'))
        folium.CircleMarker(
            location=[float(t['lat']), float(t['lon'])], radius=12,
            popup=t['tema'], tooltip=t['tema'], color=c, fill=True, fill_opacity=0.8
        ).add_to(m)
    
    map_res = st_folium(m, width="100%", height=450, key=f"map_{st.session_state.view}")
    
    # Detekce kliku
    if map_res.get('last_object_clicked_popup'):
        pop = map_res['last_object_clicked_popup']
        for i, t_obj in enumerate(data_list):
            if t_obj['tema'] == pop:
                st.session_state.selected_data = {"item": t_obj, "zdroje": zdroje_list}
                st.session_state.view = 'detail'
                st.rerun()

    st.markdown('<div style="text-align: center; font-weight: bold;">🔴 Válka 🟢 Ekonomika 🔵 Politika 🟣 Tech 🤖 AI 💹 Trhy 🌿 Eko</div>', unsafe_allow_html=True)
    st.divider()

    # Dlaždice
    for i in range(0, len(data_list), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(data_list):
                t = data_list[idx]
                c = get_clean_color(t.get('kategorie'))
                with cols[j]:
                    st.markdown(f'<div style="border-left: 10px solid {c}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t["tema"]}</h4><p>{t["bleskovka"]}</p></div>', unsafe_allow_html=True)
                    if st.button(f"🔍 Detail {idx+1}", key=f"btn_{idx}_{t['tema'][:5]}"):
                        st.session_state.selected_data = {"item": t, "zdroje": zdroje_list}
                        st.session_state.view = 'detail'
                        st.rerun()

# --- 5. HLAVNÍ PLOCHA ---
historie = nacti_historii()

if st.session_state.view == 'map':
    st.sidebar.title("💎 Nastavení")
    # Regiony a Kategorie pro "Tvůj Svět"
    reg_sel = st.sidebar.multiselect("Sledované regiony:", ["ČR", "Slovensko", "EU", "USA", "Rusko", "Asie", "Blízký východ", "Afrika"], default=["ČR", "Slovensko"])
    tem_sel = st.sidebar.multiselect("Moje kategorie:", list(BARVY.keys()), default=["AI", "Akciové trhy", "Ekologie"])
    
    if st.sidebar.button("🗑️ Vymazat historii"):
        if os.path.exists("historie_v4.json"): os.remove("historie_v4.json")
        st.session_state.clear()
        st.rerun()

    st.title("⚖️ WorldMirror: Dualitní Matrix")
    t1, t2 = st.tabs(["🔥 Hot News ze světa", "✨ Tvůj vlastní svět"])

    with t1:
        if st.button("🚀 Skenovat Globální Radar"):
            with st.spinner("Trianguluji velmoci..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                clanky, text_ai = stahni_data("geopolitics OR war OR world economy")
                prompt = f"Jsi špičkový analytik. Vyber 10 nejdůležitějších globálních témat. Odpověz VÝHRADNĚ jako JSON pole 10 objektů. Kategorie MUSÍ být z: {list(BARVY.keys())}. Struktura: {{tema, kategorie, lat, lon, bleskovka, fakta, usa, eu, asie, vychod, jih, levice, pravice, bod_svaru, clanek, zdroje_id}}. ZDROJE: {text_ai}"
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                uloz_do_historie("global", {"data": json.loads(res.text), "zdroje": clanky})
                st.rerun()
        
        if historie["global"]:
            render_dashboard(historie["global"][0]["data"], historie["global"][0]["zdroje"])

    with t2:
        if st.button("⚡ Sestavit Můj Svět"):
            with st.spinner(f"Hledám: {', '.join(reg_sel)}..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                q_personal = f"({ ' OR '.join(reg_sel) }) AND ({ ' OR '.join(tem_sel) if tem_sel else 'news' })"
                clanky, text_ai = stahni_data(q_personal)
                prompt = f"Jsi osobní analytik. Vyber 10 témat pro tyto zájmy: {reg_sel}, {tem_sel}. Odpověz VÝHRADNĚ jako JSON pole 10 objektů se stejnou strukturou jako globální sken. ZDROJE: {text_ai}"
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                uloz_do_historie("personal", {"data": json.loads(res.text), "zdroje": clanky})
                st.rerun()
        
        if historie["personal"]:
            render_dashboard(historie["personal"][0]["data"], historie["personal"][0]["zdroje"])

elif st.session_state.view == 'detail':
    sel = st.session_state.selected_data
    t, zdroje = sel["item"], sel["zdroje"]
    
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema')}")
    st.markdown(text_na_audio(t.get('fakta')), unsafe_allow_html=True)
    st.info(t.get('fakta'))
    
    st.markdown("### 🌍 Geopolitická matice")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t.get('usa'))
    with c2: st.markdown("🇪🇺 **EU 🇪🇺**"); st.caption(t.get('eu'))
    with c3: st.markdown("🟣 **Asie (JPN/KOR/TWN)**"); st.caption(t.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(t.get('vychod'))
    with c5: st.markdown("🌏 **Jih / Arabský svět**"); st.caption(t.get('jih'))
    
    st.divider()
    st.markdown("### 🧠 Ideologické narativy")
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal / Levice**\n\n{t.get('levice')}")
    with cr: st.error(f"🦅 **Conservative / Pravice**\n\n{t.get('pravice')}")
    
    st.subheader("📝 Hloubková reportáž")
    st.markdown(text_na_audio(t.get('clanek')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.6; font-size: 1.1em;">{t.get("clanek")}</div>', unsafe_allow_html=True)
    st.error(f"⚠️ **Bod sváru:** {t.get('bod_svaru')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    for aid in t.get('zdroje_id', []):
        if aid < len(zdroje):
            art = zdroje[aid]
            st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
