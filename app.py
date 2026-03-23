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
st.set_page_config(page_title="WorldMirror Matrix ULTIMATE", page_icon="⚖️", layout="wide")

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
def ziskej_funkcni_model():
    try:
        modely = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        vybrany = next((m for m in modely if "flash" in m.lower()), modely[0])
        return genai.GenerativeModel(vybrany)
    except: return None

def vytahni(text, klic):
    pattern = rf"(?i)^\s*\*{{0,2}}{klic}\*{{0,2}}\s*:?\s*(.*)"
    for line in text.split("\n"):
        match = re.search(pattern, line.strip())
        if match:
            res = match.group(1).strip()
            return res if res else "Informace chybí"
    return "Nenalezeno"

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
            text_pro_ai += f"[{i}] {c['source']['name']}: {c['title']}\n"
            pro_web.append({"id": i, "zdroj": c['source']['name'], "titulek": c['title'], "link": c['url'], "info": c.get('description', '')})
        return pro_web, text_pro_ai
    except: return [], ""

# --- 3. HLAVNÍ LOGIKA ---
st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Analytik")
    
    if st.button("🚀 Spustit hloubkový sken"):
        with st.spinner("Skenuji planetu, geopolitiku i ideologie..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi expert na mediální analýzu. Z těchto 50 zpráv vyber 10 klíčových.
                U každého tématu vypracuj rozbor (v češtině, bez hvězdiček u klíčů):

                TÉMA: [Název]
                KATEGORII: [Válka / Ekonomika / Politika / Technologie]
                LAT: [Zeměpisná šířka - číslo]
                LON: [Zeměpisná délka - číslo]
                BLESKOVKA: [Stručná věta]
                FAKTA: [Popis události]
                
                ZAPAD: [Pohled USA/EU]
                VYCHOD: [Pohled RUS/CHN]
                JIH: [Pohled Globálního Jihu / Arabský svět / Indie]
                
                LEVICE: [Jak o tom píší progresivní/levicová média?]
                PRAVICE: [Jak o tom píší konzervativní/pravicová média?]
                
                BOD_SVARU: [V čem se tyto světy nejvíce rozcházejí?]
                ---
                ZDROJE: {text_ai}
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
            kat, lat, lon, nazev = vytahni(t_data, "KATEGORII"), vytahni(t_data, "LAT"), vytahni(t_data, "LON"), vytahni(t_data, "TÉMA")
            try: folium.CircleMarker(location=[float(lat), float(lon)], radius=12, popup=f"{nazev}", color=barvy.get(kat, "gray"), fill=True).add_to(m)
            except: continue
        st_folium(m, width="100%", height=400)

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
                            if st.button(f"🔎 Otevřít analýzu", key=f"btn_{idx}"):
                                st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                                st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
    t_data = seznam_temat[st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na dashboard", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    nazev = vytahni(t_data, 'TÉMA')
    st.title(f"🔍 Detailní rozbor: {nazev}")
    
    st.subheader("📌 Shrnutí události")
    st.write(vytahni(t_data, "FAKTA"))
    
    st.markdown("### 🌍 Geopolitické srovnání")
    c1, c2, c3 = st.columns(3)
    with c1: st.info(f"🟦 **Západní blok**\n\n{vytahni(t_data, 'ZAPAD')}")
    with c2: st.warning(f"🟥 **Východní blok**\n\n{vytahni(t_data, 'VYCHOD')}")
    with c3: st.success(f"🌏 **Globální Jih**\n\n{vytahni(t_data, 'JIH')}")
    
    st.markdown("### 🧠 Ideologické spektrum")
    c4, c5 = st.columns(2)
    with c4: st.success(f"🌿 **Levice / Liberal**\n\n{vytahni(t_data, 'LEVICE')}")
    with c5: st.error(f"🦅 **Pravice / Conservative**\n\n{vytahni(t_data, 'PRAVICE')}")
    
    st.divider()
    st.error(f"⚠️ **Bod sváru:** {vytahni(t_data, 'BOD_SVARU')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články z médií")
    klice = nazev.lower().split()[:2]
    najite = 0
    for c in report['zdroje']:
        if any(k in c['titulek'].lower() for k in klice) or najite < 3:
            st.markdown(f"**{c['zdroj']}**: [{c['titulek']}]({c['link']})")
            najite += 1
            if najite > 5: break
