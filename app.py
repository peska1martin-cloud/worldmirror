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

# --- 2. FUNKCE ---
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
            for entry in feed.entries[:12]:
                vysledky.append({"zdroj": zdroj, "titulek": entry.title, "link": entry.link})
        except: continue
    return vysledky

def stahni_vsechna_data():
    try:
        data = newsapi.get_everything(
            q='geopolitics OR war OR economy',
            domains='reuters.com,apnews.com,dw.com,japantimes.co.jp,koreaherald.com',
            language='en', sort_by='publishedAt', page_size=40
        )
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: clanky = []
    
    vse = clanky + stahni_rss_zpravy()
    text_pro_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_pro_ai

def text_na_audio(text):
    try:
        tts = gTTS(text=text, lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return "Audio nelze vygenerovat."

# --- 3. BARVY A MAPOVÁNÍ ---
BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF"}
BARVY_BG = {"Válka": "#FFECEC", "Ekonomika": "#E6F4F1", "Politika": "#E6F0FF", "Technologie": "#F3E6FF"}

def get_color(kat):
    k = str(kat).strip().capitalize()
    if "Vál" in k: return BARVY["Válka"]
    if "Eko" in k: return BARVY["Ekonomika"]
    if "Pol" in k: return BARVY["Politika"]
    if "Tech" in k or "Ai" in k: return BARVY["Technologie"]
    return "gray"

# --- 4. HLAVNÍ LOGIKA ---
st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Triangulace")
    
    if st.button("🚀 Spustit multipolární analýzu"):
        with st.spinner("Trianguluji RSS feedy z Ruska, Číny a Západu..."):
            model = genai.GenerativeModel('gemini-1.5-pro')
            clanky, text_ai = stahni_vsechna_data()
            prompt = f"""
            Jsi elitní analytik. Vyber 10 nejdůležitějších témat z těchto zpráv. 
            Vrať POUZE JSON pole 10 objektů. Kategorie musí být přesně: Válka, Ekonomika, Politika nebo Technologie.
            
            JSON objekt: {{
              "tema": "Název", "kategorie": "Válka", "lat": 0.0, "lon": 0.0, "bleskovka": "...", "fakta": "...",
              "usa": "...", "eu": "...", "asie": "...", "vychod": "...", "jih": "...",
              "levice": "...", "pravice": "...", "bod_svaru": "...", "clanek": "...", "zdroje_id": [indexy]
            }}
            ZDROJE: {text_ai}
            """
            try:
                res = model.generate_content(prompt)
                j_str = re.search(r"```json(.*)```", res.text, re.DOTALL).group(1).strip()
                uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": json.loads(j_str), "zdroje": clanky})
                st.rerun()
            except: st.error("AI selhala. Zkuste to znovu.")

    if historie:
        report = historie[0]
        seznam = report.get('analyza_json', [])[:10]
        
   # --- MAPA S PROKLIKEM ---
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for i, t in enumerate(seznam):
            c = get_color(t.get('kategorie'))
            try:
                folium.CircleMarker(
                    location=[float(t['lat']), float(t['lon'])], radius=12,
                    # ZDE JE ZMĚNA: Místo CLICK_IDX:i tam dáme název tématu
                    popup=t['tema'], 
                    tooltip=f"Klikni pro detail: {t['tema']}",
                    color=c, fill=True, fill_opacity=0.8
                ).add_to(m)
            except: continue
        
        st.subheader("🌍 Klikněte na tečku pro detail analýzy")
        map_res = st_folium(m, width="100%", height=450)

  # Detekce prokliku
        if map_res.get('last_object_clicked_popup'):
            popup_val = map_res['last_object_clicked_popup']
            # ZDE JE ZMĚNA: Hledáme v seznamu téma, které se jmenuje stejně jako text v bublině
            for i, t_obj in enumerate(seznam):
                if t_obj['tema'] == popup_val:
                    st.session_state.selected_idx = i
                    st.session_state.view = 'detail'
                    st.rerun()

        st.markdown('<div style="text-align: center; font-weight: bold;">🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie</div>', unsafe_allow_html=True)
        st.divider()

        # Dlaždice
        for i in range(0, len(seznam), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam):
                    t = seznam[idx]
                    c = get_color(t.get('kategorie'))
                    bg = BARVY_BG.get(t.get('kategorie', 'Politika'), "#f0f0f0")
                    with cols[j]:
                        st.markdown(f'<div style="border-left: 10px solid {c}; background-color: {bg}; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t["tema"]}</h4><p>{t["bleskovka"]}</p></div>', unsafe_allow_html=True)
                        if st.button(f"🔍 Rozbor {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    t = historie[0]['analyza_json'][st.session_state.selected_idx]
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema')}")
    
    st.subheader("🔊 Audio: Fakta")
    st.markdown(text_na_audio(t.get('fakta')), unsafe_allow_html=True)
    st.info(t.get('fakta'))
    
    st.markdown("### 🌍 Geopolitická křižovatka")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t.get('usa'))
    with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(t.get('eu'))
    with c3: st.markdown("🟣 **Asie (JPN/KOR/TWN)**"); st.caption(t.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (TASS/RT/CHN)**"); st.caption(t.get('vychod'))
    with c5: st.markdown("🌏 **Jih (Al Jazeera)**"); st.caption(t.get('jih'))
    
    st.divider()
    st.markdown("### 🧠 Ideologické narativy")
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal / Levice**\n\n{t.get('levice')}")
    with cr: st.error(f"🦅 **Conservative / Pravice**\n\n{t.get('pravice')}")
    
    st.subheader("📝 Hloubková reportáž")
    st.markdown(text_na_audio(t.get('clanek')), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.6; font-size: 1.1em;">{t.get("clanek")}</div>', unsafe_allow_html=True)
    
    st.error(f"⚠️ **Bod sváru:** {t.get('bod_svaru')}")
