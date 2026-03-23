import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import os
import re
from datetime import datetime
from streamlit_folium import st_folium
import folium

# --- 1. KONFIGURACE A KLÍČE ---
st.set_page_config(page_title="WorldMirror Matrix Map", page_icon="🌍", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception:
    st.error("❌ CHYBA: Klíče nejsou správně nastaveny v Secrets na Streamlit Cloudu!")
    st.stop()

# --- 2. INICIALIZACE STAVU ---
if 'view' not in st.session_state:
    st.session_state.view = 'map'
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = None

# --- 3. POMOCNÉ FUNKCE ---
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
            zdroj = c['source']['name']
            text_pro_ai += f"[{i}] {zdroj}: {c['title']}\n"
            pro_web.append({"id": i, "zdroj": zdroj, "titulek": c['title'], "link": c['url'], "info": c.get('description', '')})
        return pro_web, text_pro_ai
    except: return [], ""

# --- 4. HLAVNÍ LOGIKA ---
st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.view = 'map'
    st.rerun()

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Geopolitická Mapa")
    
    if st.button("🚀 Spustit globální sken světa"):
        with st.spinner("Skenuji planetu a analyzuji narativy..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi špičkový analytik. Z těchto 50 zpráv vyber 10 nejdůležitějších globálních témat.
                U každého tématu urči přesně tyto údaje (BEZ HVĚZDIČEK U KLÍČŮ):
                TÉMA: [Název]
                KATEGORII: [Válka / Ekonomika / Politika / Technologie]
                LAT: [Zeměpisná šířka, jen číslo, např. 48.8]
                LON: [Zeměpisná délka, jen číslo, např. 2.3]
                BLESKOVKA: [Jedna krátká věta]
                FAKTA: [Popis události]
                ZAPAD: [Pohled USA a EU]
                VYCHOD: [Pohled Ruska a Číny]
                JIH: [Pohled Arabského světa/Al Jazeery]
                BOD_SVARU: [Hlavní konflikt v informování]
                ---
                ZDROJE:
                {text_ai}
                """
                odpoved = model.generate_content(prompt).text
                uloz_do_historie({
                    "cas": datetime.now().strftime("%d.%m.%Y %H:%M"),
                    "analyza": odpoved,
                    "zdroje": clanky
                })
                st.rerun()

    if historie:
        report = historie[0]
        seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
        
        st.subheader("🌍 Aktuální ohniska zájmu")
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        barvy = {"Válka": "red", "Ekonomika": "green", "Politika": "blue", "Technologie": "purple"}
        
        for i, t_data in enumerate(seznam_temat):
            kat = vytahni(t_data, "KATEGORII")
            lat = vytahni(t_data, "LAT")
            lon = vytahni(t_data, "LON")
            nazev = vytahni(t_data, "TÉMA")
            try:
                folium.CircleMarker(
                    location=[float(lat), float(lon)],
                    radius=12,
                    popup=f"{i+1}. {nazev} ({kat})",
                    color=barvy.get(kat, "gray"),
                    fill=True,
                    fill_opacity=0.8
                ).add_to(m)
            except: continue
        
        st_folium(m, width="100%", height=500)
        st.caption("🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie")

        st.divider()
        st.subheader("📌 Top 10 témat dne (klikni pro detail)")
        for i in range(0, len(seznam_temat), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam_temat):
                    t_data = seznam_temat[idx]
                    nazev = vytahni(t_data, "TÉMA")
                    blesk = vytahni(t_data, "BLESKOVKA")
                    with cols[j]:
                        with st.container(border=True):
                            st.markdown(f"**{idx + 1}. {nazev}**")
                            st.write(blesk)
                            if st.button(f"🔍 Analyzovat", key=f"btn_{idx}"):
                                st.session_state.selected_idx = idx
                                st.session_state.view = 'detail'
                                st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
    t_data = seznam_temat[st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    
    nazev = vytahni(t_data, "TÉMA")
    st.title(f"🔎 Detail: {nazev}")
    
    st.subheader("📌 Co se děje (Fakta)")
    st.write(vytahni(t_data, "FAKTA"))
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🟦 **Západní narativ (USA/EU)**\n\n{vytahni(t_data, 'ZAPAD')}")
    with col2:
        st.warning(f"🟥 **Východní narativ (RUS/CHN)**\n\n{vytahni(t_data, 'VYCHOD')}")
    
    st.markdown(f"🌍 **Globální Jih / Regionální pohled:** {vytahni(t_data, 'JIH')}")
    st.error(f"⚠️ **Bod sváru (Střet informací):** {vytahni(t_data, 'BOD_SVARU')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    klice = nazev.lower().split()[:2]
    for c in report['zdroje']:
        if any(k in c['titulek'].lower() for k in klice):
            st.markdown(f"**{c['zdroj']}**: [{c['titulek']}]({c['link']})")
