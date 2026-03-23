import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import os
import re
from datetime import datetime
from streamlit_folium import st_folium
import folium

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

# --- 2. ROBUSTNÍ FUNKCE PRO ČIŠTĚNÍ TEXTU ---
def vytahni(text, klic):
    if not text: return ""
    pattern = rf"(?i)^\s*[-*•]?\s*\*{{0,2}}{klic}\*{{0,2}}\s*:?\s*(.*)"
    for line in text.split("\n"):
        match = re.search(pattern, line.strip())
        if match:
            return match.group(1).strip().replace("*", "")
    return ""

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
            # Očíslujeme články pro AI
            text_pro_ai += f"ID:{i} - {c['source']['name']}: {c['title']}\n"
            pro_web.append({"id": i, "zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']})
        return pro_web, text_pro_ai
    except: return [], ""

def ziskej_funkcni_model():
    try:
        modely = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        vybrany = next((m for m in modely if "flash" in m.lower()), modely[0])
        return genai.GenerativeModel(vybrany)
    except: return None

# --- 3. HLAVNÍ LOGIKA ---
st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Geopolitika")
    
    if st.button("🚀 Spustit hloubkovou analýzu světa"):
        with st.spinner("Skenuji světové zdroje a páruji články..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi elitní analytik. Z těchto 50 zpráv vyber 10 nejdůležitějších témat.
                U každého tématu vypracuj rozbor v češtině.

                FORMÁT:
                Každé téma odděl '---'. Nepoužívej hvězdičky u klíčů.
                TÉMA: [Název]
                KATEGORIE: [Válka/Ekonomika/Politika/Technologie]
                LAT: [Šířka - číslo]
                LON: [Délka - číslo]
                BLESKOVKA: [Stručná věta]
                FAKTA: [Popis]
                USA: [Postoj USA]
                EU: [Postoj EU]
                ASIE: [Postoj JPN/TWN/KOR]
                VYCHOD: [Pohled RUS/CHN]
                JIH: [Pohled Globálního Jihu]
                LEVICE: [Levicový pohled]
                PRAVICE: [Pravicový pohled]
                BOD_SVARU: [Hlavní rozpor]
                ZDROJE_ID: [Uveď ID čísel článků ze seznamu, které k tématu patří, oddělené čárkou, např: 1, 5, 12]
                ---
                ZDROJE ČLÁNKŮ S ID:
                {text_ai}
                """
                odpoved = model.generate_content(prompt).text
                uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza": odpoved, "zdroje": clanky})
                st.rerun()

    if historie:
        report = historie[0]
        seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
        
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        barvy = {"Válka": "red", "Ekonomika": "green", "Politika": "blue", "Technologie": "purple"}
        for i, t_data in enumerate(seznam_temat):
            kat, lat, lon, nazev = vytahni(t_data, "KATEGORIE"), vytahni(t_data, "LAT"), vytahni(t_data, "LON"), vytahni(t_data, "TÉMA")
            try:
                folium.CircleMarker(
                    location=[float(lat), float(lon)], radius=12,
                    popup=f"Téma:{nazev}", color=barvy.get(kat, "gray"), fill=True
                ).add_to(m)
            except: continue
        
        st_folium(m, width="100%", height=400)
        st.caption("🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie")

        st.subheader("📌 Top 10 témat (klikni pro detail)")
        for i in range(0, len(seznam_temat), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam_temat):
                    t_data = seznam_temat[idx]
                    with cols[j]:
                        with st.container(border=True):
                            st.markdown(f"**{idx + 1}. {vytahni(t_data, 'TÉMA')}**")
                            st.write(vytahni(t_data, "BLESKOVKA"))
                            if st.button(f"🔎 Otevřít rozbor", key=f"btn_{idx}"):
                                st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                                st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
    t_data = seznam_temat[st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 Detail: {vytahni(t_data, 'TÉMA')}")
    
    st.info(f"**Shrnutí:** {vytahni(t_data, 'FAKTA')}")
    
    st.markdown("### 🌍 Geopolitická situace")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(vytahni(t_data, 'USA'))
    with c2: st.markdown("🇪🇺 **EU**"); st.caption(vytahni(t_data, 'EU'))
    with c3: st.markdown("🟣 **Asijští Tygři**"); st.caption(vytahni(t_data, 'ASIE'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(vytahni(t_data, 'VYCHOD'))
    with c5: st.markdown("🌏 **Globální Jih**"); st.caption(vytahni(t_data, 'JIH'))
    
    st.markdown("### 🧠 Ideologické spektrum")
    c6, c7 = st.columns(2)
    with c6: st.success(f"🌿 **Levice**\n\n{vytahni(t_data, 'LEVICE')}")
    with c7: st.error(f"🦅 **Pravice**\n\n{vytahni(t_data, 'PRAVICE')}")
    
    st.error(f"⚠️ **Bod sváru:** {vytahni(t_data, 'BOD_SVARU')}")
    
    # --- PŘÍMÉ ODKAZY NA ČLÁNKY PODLE ID ---
    st.divider()
    st.subheader("🔗 Zdrojové články pro toto téma")
    zdroje_ids = vytahni(t_data, "ZDROJE_ID")
    
    try:
        # Převedeme textové ID (např. "1, 5, 12") na seznam čísel
        id_list = [int(x.strip()) for x in zdroje_ids.replace("[", "").replace("]", "").split(",") if x.strip().isdigit()]
        
        if id_list:
            for article_id in id_list:
                if article_id < len(report['zdroje']):
                    art = report['zdroje'][article_id]
                    st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
        else:
            st.write("AI nepřiřadila konkrétní články, zkuste nový sken.")
    except:
        st.write("Chyba při načítání odkazů.")
