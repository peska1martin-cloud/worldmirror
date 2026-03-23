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

# --- 2. POMOCNÉ FUNKCE ---
def vytahni(text, klic):
    if not text: return ""
    pattern = rf"(?i)^\s*[-*•]?\s*\*{{0,2}}{klic}\*{{0,2}}\s*:?\s*(.*)"
    lines = text.split("\n")
    for i, line in enumerate(lines):
        match = re.search(pattern, line.strip())
        if match:
            # Pokud jde o CLANEK, vezmeme i následující řádky, dokud nenarazíme na další klíč
            if klic.upper() == "CLANEK":
                obsah = [match.group(1).strip()]
                for next_line in lines[i+1:]:
                    if any(k + ":" in next_line.upper() for k in ["TÉMA", "USA", "EU", "VYCHOD", "ZDROJE_ID"]):
                        break
                    obsah.append(next_line.strip())
                return "\n".join(obsah).replace("*", "")
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

# Definice barev
BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF"}
BARVY_BG = {"Válka": "#FFECEC", "Ekonomika": "#E6F4F1", "Politika": "#E6F0FF", "Technologie": "#F3E6FF"}

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Geopolitika")
    
    if st.button("🚀 Spustit hloubkový sken světa"):
        with st.spinner("Skenuji planetu a píši reportáže..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi špičkový analytik a novinář. Vyber 10 nejdůležitějších témat.
                Každé téma odděl '---'. U každého tématu uveď:
                TÉMA: [Název]
                KATEGORIE: [Válka/Ekonomika/Politika/Technologie]
                LAT: [Šířka]
                LON: [Délka]
                BLESKOVKA: [Stručná věta]
                FAKTA: [Popis v 2-3 větách]
                USA: [Postoj USA]
                EU: [Postoj Evropy]
                ASIE: [Postoj JPN/TWN/KOR]
                VYCHOD: [Postoj RUS/CHN]
                JIH: [Pohled Globálního Jihu]
                LEVICE: [Levicový pohled]
                PRAVICE: [Pravicový pohled]
                BOD_SVARU: [Klíčový rozpor]
                CLANEK: [Napiš souvislou, hloubkovou reportáž o tomto tématu v češtině o délce cca 300 slov. Jdi do hloubky, vysvětli souvislosti a historický kontext.]
                ZDROJE_ID: [ID čísel článků oddělená čárkou]
                ---
                ZDROJE ČLÁNKŮ S ID:
                {text_ai}
                """
                odpoved = model.generate_content(prompt).text
                uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza": odpoved, "zdroje": clanky})
                st.rerun()

    if historie:
        report = historie[0]
        seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()][:10]
        
        # MAPA
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for i, t_data in enumerate(seznam_temat):
            kat = vytahni(t_data, "KATEGORIE")
            lat, lon, nazev = vytahni(t_data, "LAT"), vytahni(t_data, "LON"), vytahni(t_data, "TÉMA")
            try:
                folium.CircleMarker(
                    location=[float(lat), float(lon)], radius=12,
                    popup=f"Téma:{nazev}", color=BARVY.get(kat, "gray"), fill=True, fill_opacity=0.8
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
                    kat = vytahni(t_data, "KATEGORIE")
                    barva_hex = BARVY.get(kat, "#333")
                    bg_hex = BARVY_BG.get(kat, "#f0f0f0")
                    
                    with cols[j]:
                        # Barevná dlaždice přes HTML/Markdown
                        st.markdown(f"""
                            <div style="border-left: 10px solid {barva_hex}; background-color: {bg_hex}; padding: 15px; border-radius: 5px; margin-bottom: 10px; min-height: 120px;">
                                <h4 style="margin: 0; color: #111;">{idx + 1}. {vytahni(t_data, 'TÉMA')}</h4>
                                <p style="margin: 5px 0; color: #444; font-size: 0.9em;">{vytahni(t_data, 'BLESKOVKA')}</p>
                            </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"🔎 Otevřít reportáž k tématu {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()][:10]
    t_data = seznam_temat[st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 Detail: {vytahni(t_data, 'TÉMA')}")
    
    st.markdown("### 🌍 Geopolitická matice")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(vytahni(t_data, 'USA'))
    with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(vytahni(t_data, 'EU'))
    with c3: st.markdown("🟣 **Vyspělá Asie**"); st.caption(vytahni(t_data, 'ASIE'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(vytahni(t_data, 'VYCHOD'))
    with c5: st.markdown("🌏 **Globální Jih**"); st.caption(vytahni(t_data, 'JIH'))
    
    st.markdown("---")
    st.markdown("### 🧠 Ideologické spektrum")
    c6, c7 = st.columns(2)
    with c6: st.success(f"🌿 **Levice / Liberal**\n\n{vytahni(t_data, 'LEVICE')}")
    with c7: st.error(f"🦅 **Pravice / Conservative**\n\n{vytahni(t_data, 'PRAVICE')}")
    
    st.error(f"⚠️ **Bod sváru:** {vytahni(t_data, 'BOD_SVARU')}")

    # --- NOVINKA: HLOUBKOVÁ REPORTÁŽ ---
    st.divider()
    st.subheader("📝 Hloubková reportáž (WorldMirror Specil)")
    st.markdown(f"""
    <div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: 'Georgia', serif; line-height: 1.6; font-size: 1.1em;">
        {vytahni(t_data, 'CLANEK')}
    </div>
    """, unsafe_allow_html=True)
    
    # --- ODKAZY ---
    st.divider()
    st.subheader("🔗 Zdrojové články pro ověření")
    zdroje_ids = vytahni(t_data, "ZDROJE_ID")
    try:
        id_list = [int(x.strip()) for x in zdroje_ids.replace("[", "").replace("]", "").split(",") if x.strip().isdigit()]
        for aid in id_list:
            if aid < len(report['zdroje']):
                a = report['zdroje'][aid]
                st.markdown(f"✅ **{a['zdroj']}**: [{a['titulek']}]({a['link']})")
    except: st.write("Odkazy se nepodařilo načíst.")
