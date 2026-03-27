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
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = None

# --- 2. FUNKCE PRO HISTORII A DATA ---
def nacti_historii():
    if os.path.exists("historie.json"):
        with open("historie.json", "r", encoding="utf-8") as f: return json.load(f)
    return []

def uloz_do_historie(novy_zaznam):
    historie = nacti_historii()
    historie.insert(0, novy_zaznam)
    with open("historie.json", "w", encoding="utf-8") as f:
        json.dump(historie, f, ensure_ascii=False, indent=4)

def stahni_rss_zpravy():
    """Stahuje zprávy přímo z RSS kanálů (TASS, RT, Xinhua, Al Jazeera)."""
    rss_zdroje = {
        "TASS (RUS)": "https://tass.com/rss/v2.xml",
        "RT (RUS)": "https://www.rt.com/rss/news/",
        "Xinhua (CHN)": "http://www.xinhuanet.com/english/rss/worldrss.xml",
        "Al Jazeera (ARA)": "https://www.aljazeera.com/xml/rss/all.xml"
    }
    vysledky = []
    for zdroj, url in rss_zdroje.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                vysledky.append({"zdroj": zdroj, "titulek": entry.title, "link": entry.link})
        except: continue
    return vysledky

def stahni_vsechna_data():
    """Kombinuje News API (Západ) a RSS (Východ/Jih)."""
    try:
        data = newsapi.get_everything(
            q='geopolitics OR war OR economy',
            domains='reuters.com,apnews.com,dw.com,japantimes.co.jp,koreaherald.com',
            language='en', sort_by='publishedAt', page_size=40
        )
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: clanky = []
    
    vychod_jih = stahni_rss_zpravy()
    vse = clanky + vychod_jih
    text_pro_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_pro_ai

def text_na_audio(text):
    """Převede text na audio a vrátí HTML přehrávač."""
    try:
        tts = gTTS(text=text, lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return "Audio nelze vygenerovat."

def ziskej_model():
    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    vybrany = next((m for m in available if "1.5-pro" in m), next((m for m in available if "flash" in m), "gemini-1.5-flash"))
    return genai.GenerativeModel(vybrany)

# --- 3. HLAVNÍ LOGIKA ---
st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF"}
BARVY_BG = {"Válka": "#FFECEC", "Ekonomika": "#E6F4F1", "Politika": "#E6F0FF", "Technologie": "#F3E6FF"}

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror Matrix: Hardcore Žurnalistika")
    
    if st.button("🚀 Spustit multipolární analýzu (API + RSS)"):
        with st.spinner("Stahuji přímé zprávy z Moskvy, Pekingu, Tokia a Washingtonu..."):
            model = ziskej_model()
            clanky, text_ai = stahni_vsechna_data()
            if model and clanky:
                prompt = f"""
                Jsi elitní analytik. Z těchto REÁLNÝCH zpráv vyber 10 nejdůležitějších témat. 
                Důsledně srovnej narativy, které vidíš v přiložených zdrojích.
                
                Vrať POUZE JSON (seznam 10 objektů):
                [
                  {{
                    "tema": "Název tématu",
                    "kategorie": "Válka/Ekonomika/Politika/Technologie",
                    "lat": 0.0, "lon": 0.0,
                    "bleskovka": "Stručná věta",
                    "fakta": "Objektivní fakta ze zpráv",
                    "usa": "Zájem a postoj USA",
                    "eu": "Specifický zájem a postoj EU 🇪🇺",
                    "asie": "Zájem Asijských tygrů (JPN/KOR/TWN)",
                    "vychod": "Postoj Východu (TASS/RT/Xinhua)",
                    "jih": "Postoj Jihu/Arabů (Al Jazeera)",
                    "levice": "Liberal/Progresivní narativ",
                    "pravice": "Conservative/Souverénní narativ",
                    "bod_svaru": "Zásadní informační rozpor mezi zdroji",
                    "clanek": "Hloubková reportáž (300 slov) v češtině.",
                    "zdroje_id": [indexy]
                  }}
                ]
                ZDROJE: {text_ai}
                """
                try:
                    result = model.generate_content(prompt)
                    json_str = re.search(r"```json(.*)```", result.text, re.DOTALL).group(1).strip()
                    uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": json.loads(json_str), "zdroje": clanky})
                    st.rerun()
                except: st.error("AI selhala při analýze. Zkuste nový sken.")

    if historie:
        report = historie[0]
        seznam_temat = report.get('analyza_json', [])[:10]
        
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for t in seznam_temat:
            kat = t.get('kategorie', 'Politika').strip().capitalize()
            try: folium.CircleMarker(location=[float(t['lat']), float(t['lon'])], radius=12, popup=t['tema'], color=BARVY.get(kat, "gray"), fill=True, fill_opacity=0.8).add_to(m)
            except: continue
        st_folium(m, width="100%", height=400)
        
        st.markdown('<div style="display: flex; justify-content: center; gap: 20px; font-weight: bold;">🔴 Válka 🟢 Ekonomika 🔵 Politika 🟣 Technologie</div>', unsafe_allow_html=True)
        st.divider()

        for i in range(0, len(seznam_temat), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam_temat):
                    t = seznam_temat[idx]
                    kat = t.get('kategorie', 'Politika').strip().capitalize()
                    with cols[j]:
                        st.markdown(f'<div style="border-left: 10px solid {BARVY.get(kat, "#333")}; background-color: {BARVY_BG.get(kat, "#f0f0f0")}; padding: 15px; border-radius: 5px; margin-bottom: 10px;"><h4>{idx+1}. {t.get("tema")}</h4><p>{t.get("bleskovka")}</p></div>', unsafe_allow_html=True)
                        if st.button(f"🔎 Otevřít detail č. {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    t = report['analyza_json'][st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na dashboard", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema')}")
    
    st.subheader("🔊 Poslechnout si fakta")
    st.markdown(text_na_audio(t.get('fakta')), unsafe_allow_html=True)
    st.info(t.get('fakta'))
    
    st.markdown("### 🌍 Geopolitická matice")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t.get('usa'))
    with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(t.get('eu'))
    with c3: st.markdown("🟣 **Asie (JPN/KOR/TWN)**"); st.caption(t.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (TASS/RT/CHN)**"); st.caption(t.get('vychod'))
    with c5: st.markdown("🌏 **Jih (Al Jazeera)**"); st.caption(t.get('jih'))
    
    st.divider()
    st.markdown("### 🧠 Mediální ideologie")
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal Narativ**\n\n{t.get('levice')}")
    with cr: st.error(f"🦅 **Conservative Narativ**\n\n{t.get('pravice')}")
    
    st.subheader("📝 Hloubková reportáž")
    st.write("🔊 *Přečíst celou analýzu:*")
    st.markdown(text_na_audio(t.get('clanek')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.6; font-size: 1.1em;">{t.get("clanek")}</div>', unsafe_allow_html=True)
    
    st.error(f"⚠️ **Bod sváru:** {t.get('bod_svaru')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    for aid in t.get('zdroje_id', []):
        if aid < len(report['zdroje']):
            art = report['zdroje'][aid]
            st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
