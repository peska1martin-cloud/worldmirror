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
st.set_page_config(page_title="WorldMirror Matrix Elite+", page_icon="⚖️", layout="wide")

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

# --- 2. POMOCNÉ FUNKCE ---
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
            pro_web.append({"id": i, "zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']})
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
    st.title("⚖️ WorldMirror: Globální Geopolitický Sken")
    
    if st.button("🚀 Spustit hloubkovou analýzu světa"):
        with st.spinner("Skenuji 5 globálních center moci..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi elitní geopolitický analytik. Z těchto 50 zpráv vyber 10 nejdůležitějších.
                Pro každé téma vytvoř rozbor. Důsledně rozlišuj mezi zájmy USA, EU a Vyspělé Asie.
                Odpovídej v češtině, bez hvězdiček u klíčů.

                TÉMA: [Název]
                KATEGORII: [Válka / Ekonomika / Politika / Technologie]
                LAT: [Šířka]
                LON: [Délka]
                BLESKOVKA: [Stručná věta]
                FAKTA: [Popis události]
                
                GEOPOLITIKA:
                USA: [Postoj a zájmy Washingtonu]
                EU: [Postoj a zájmy Bruselu/Evropy]
                ASIE_G7: [Postoj Japonska, Taiwanu a J. Koreje - důraz na technologie a regionální stabilitu]
                VYCHOD: [Pohled Ruska a Číny]
                JIH: [Pohled Globálního Jihu a Arabského světa]
                
                IDEOLOGIE:
                LEVICE: [Levicový/Liberal pohled]
                PRAVICE: [Pravicový/Conservative pohled]
                
                BOD_SVARU: [Kde se tyto zájmy nejvíce srážejí?]
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
                            if st.button(f"🔍 Otevřít analýzu", key=f"btn_{idx}"):
                                st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                                st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
    t_data = seznam_temat[st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na dashboard", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    nazev = vytahni(t_data, 'TÉMA')
    st.title(f"🔍 Hloubkový rozbor: {nazev}")
    
    st.subheader("📌 Co se stalo")
    st.info(vytahni(t_data, "FAKTA"))
    
    # --- GEOPOLITICKÁ MATICE (5 SLOUPCŮ VE DVOU ŘADÁCH) ---
    st.markdown("### 🌍 Globální mocenská křižovatka")
    r1_c1, r1_c2, r1_c3 = st.columns(3)
    with r1_c1: st.markdown("🟦 **USA**"); st.caption(vytahni(t_data, 'USA'))
    with r1_c2: st.markdown("🇪🇺 **EU**"); st.caption(vytahni(t_data, 'EU'))
    with r1_c3: st.markdown("🟣 **Vyspělá Asie (JPN/TWN/KOR)**"); st.caption(vytahni(t_data, 'ASIE_G7'))
    
    r2_c1, r2_c2 = st.columns(2)
    with r2_c1: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(vytahni(t_data, 'VYCHOD'))
    with r2_c2: st.markdown("🌏 **Globální Jih**"); st.caption(vytahni(t_data, 'JIH'))
    
    st.markdown("### 🧠 Ideologické spektrum")
    c5, c6 = st.columns(2)
    with c5: st.success(f"🌿 **Levice / Liberal**\n\n{vytahni(t_data, 'LEVICE')}")
    with c6: st.error(f"🦅 **Pravice / Conservative**\n\n{vytahni(t_data, 'PRAVICE')}")
    
    st.divider()
    st.error(f"⚠️ **Bod sváru:** {vytahni(t_data, 'BOD_SVARU')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    klice = nazev.lower().split()[:2]
    for c in report['zdroje']:
        if any(k in c['titulek'].lower() for k in klice):
            st.markdown(f"**{c['zdroj']}**: [{c['titulek']}]({c['link']})")
