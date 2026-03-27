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
st.set_page_config(page_title="WorldMirror Global Matrix", page_icon="⚖️", layout="wide")

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
    if "ai" in k or "inteligen" in k: return BARVY["AI"]
    if "přír" in k or "klim" in k or "ekol" in k: return BARVY["Ekologie"]
    if "akci" in k or "burz" in k or "trh" in k: return BARVY["Akciové trhy"]
    if "prům" in k or "energ" in k: return BARVY["Průmysl"]
    if "show" in k or "celeb" in k or "kult" in k: return BARVY["Showbyznys"]
    if "cest" in k: return BARVY["Cestování"]
    if "krim" in k or "bezp" in k: return BARVY["Krimi"]
    return "#AAAAAA"

# --- 3. FUNKCE PRO HISTORII A DATA ---
def nacti_historii():
    if os.path.exists("historie.json"):
        with open("historie.json", "r", encoding="utf-8") as f: return json.load(f)
    return []

def uloz_do_historie(novy_zaznam):
    historie = nacti_historii()
    historie.insert(0, novy_zaznam)
    with open("historie.json", "w", encoding="utf-8") as f:
        json.dump(historie, f, ensure_ascii=False, indent=4)

def stahni_multipolar_zpravy(regiony_list, temata_list):
    q_region = " OR ".join(regiony_list) if regiony_list else "World"
    q_topic = " OR ".join(temata_list) if temata_list else "Geopolitics"
    full_query = f"({q_region}) AND ({q_topic})"
    try:
        data = newsapi.get_everything(q=full_query, language='en', sort_by='publishedAt', page_size=50)
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: clanky = []
    
    rss_urls = ["https://tass.com/rss/v2.xml", "https://www.rt.com/rss/news/", "https://www.aljazeera.com/xml/rss/all.xml"]
    rss_vysledky = []
    for url in rss_urls:
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

# --- 4. UI SIDEBAR ---
st.sidebar.title("💎 WorldMirror Premium")
regiony_sel = st.sidebar.multiselect("Regiony:", ["ČR", "Slovensko", "EU", "USA", "Rusko", "Asie", "Blízký východ", "Afrika", "Oceánie"], default=["ČR", "EU"])
temata_sel = st.sidebar.multiselect("Kategorie:", list(BARVY.keys()), default=["Válka", "Ekonomika", "Politika", "Akciové trhy"])

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

historie = nacti_historii()

# --- 5. HLAVNÍ PLOCHA ---
if st.session_state.view == 'map':
    st.title("🌍 WorldMirror: Globální Analytická Matice")
    
    if st.button("🚀 Spustit hloubkovou analýzu"):
        with st.spinner("Skenuji multipolární zdroje..."):
            model = genai.GenerativeModel('gemini-1.5-pro')
            clanky, text_ai = stahni_multipolar_zpravy(regiony_sel, temata_sel)
            
            if not clanky:
                st.warning("Žádné zprávy pro tento výběr nebyly nalezeny.")
            else:
                prompt = f"""
                Jsi elitní analytik. Vyber 10 nejdůležitějších témat. 
                PRO PREMIUM: U kategorie 'Akciové trhy' povinně uveď konkrétní firmy a symboly (např. $NVDA).
                
                ODPOVĚZ POUZE JAKO VALIDNÍ JSON POLE. Nic jiného nepiš.
                Kategorie musí být z výběru: {', '.join(BARVY.keys())}.
                
                Struktura: {{ "tema", "kategorie", "lat", "lon", "bleskovka", "fakta", "usa", "eu", "asie", "vychod", "jih", "levice", "pravice", "bod_svaru", "clanek", "zdroje_id" }}
                ZDROJE: {text_ai}
                """
                try:
                    res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                    uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": json.loads(res.text), "zdroje": clanky})
                    st.rerun()
                except Exception as e:
                    st.error("AI selhala při generování JSONu. Zkuste to znovu.")

    if historie:
        report = historie[0]
        seznam = report['analyza_json']
        
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for i, t in enumerate(seznam):
            color = get_clean_color(t.get('kategorie'))
            folium.CircleMarker(
                location=[float(t['lat']), float(t['lon'])], radius=12,
                popup=t['tema'], tooltip=f"Klikni: {t['tema']}",
                color=color, fill=True, fill_opacity=0.8
            ).add_to(m)
        
        map_res = st_folium(m, width="100%", height=450)
        
        if map_res.get('last_object_clicked_popup'):
            pop = map_res['last_object_clicked_popup']
            for i, t_obj in enumerate(seznam):
                if t_obj['tema'] == pop:
                    st.session_state.selected_idx, st.session_state.view = i, 'detail'
                    st.rerun()

        st.divider()
        for i in range(0, len(seznam), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam):
                    t = seznam[idx]
                    c = get_clean_color(t.get('kategorie'))
                    bg = BARVY_BG.get(t.get('kategorie', 'Politika'), "#f0f0f0")
                    with cols[j]:
                        st.markdown(f'<div style="border-left: 10px solid {c}; background-color: {bg}; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t["tema"]}</h4><p>{t["bleskovka"]}</p></div>', unsafe_allow_html=True)
                        if st.button(f"🔍 Detail {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    t = historie[0]['analyza_json'][st.session_state.selected_idx]
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema')}")
    
    st.subheader("🔊 Audio: Fakta")
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
    st.markdown("### 🧠 Ideologie")
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
        if aid < len(historie[0]['zdroje']):
            art = historie[0]['zdroje'][aid]
            st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
