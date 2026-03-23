import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import os
from datetime import datetime
from streamlit_folium import st_folium
import folium

# --- KONFIGURACE ---
st.set_page_config(page_title="WorldMirror Matrix Map", page_icon="🌍", layout="wide")

# 🔑 KLÍČE (Tady je budeš muset doplnit)
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
NEWS_API_KEY = st.secrets["NEWS_API_KEY"]

genai.configure(api_key=GOOGLE_API_KEY)
newsapi = NewsApiClient(api_key=NEWS_API_KEY)

# --- SESSION STATE ---
if 'view' not in st.session_state: st.session_state.view = 'map'
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = None

# --- POMOCNÉ FUNKCE ---
def ziskej_funkcni_model():
    try:
        modely = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        vybrany = next((m for m in modely if "flash" in m.lower()), modely[0])
        return genai.GenerativeModel(vybrany)
    except: return None

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

def vytahni(text, klic):
    for line in text.split("\n"):
        if line.replace("*","").strip().upper().startswith(klic.upper()):
            return line.replace("*","").replace(klic,"").replace(klic.upper(),"").strip(": ")
    return "Nenalezeno"

# --- HLAVNÍ PLOCHA ---
st.title("⚖️ WorldMirror: Geopolitická Mapa")

# NAČTENÍ HISTORIE (zjednodušeno pro Cloud)
if not os.path.exists("historie.json"):
    with open("historie.json", "w") as f: json.dump([], f)

with open("historie.json", "r") as f: historie = json.load(f)

# --- LOGIKA ---
if st.session_state.view == 'map':
    if st.button("🚀 Spustit globální sken"):
        with st.spinner("Skenuji svět a umisťuji body na mapu..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Z těchto 50 zpráv vyber 10 nejdůležitějších témat. 
                U každého urči:
                1. KATEGORII: (Válka, Ekonomika, Politika, Technologie)
                2. LOKACI: (Název země nebo regionu)
                3. LAT: (Zeměpisná šířka)
                4. LON: (Zeměpisná délka)
                + FAKTA, ZAPAD, VYCHOD, JIH, BOD_SVARU, BLESKOVKA.
                
                Vrať v češtině, odděluj témata '---'.
                ZDROJE: {text_ai}
                """
                odpoved = model.generate_content(prompt).text
                novy = {"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza": odpoved, "zdroje": clanky}
                historie.insert(0, novy)
                with open("historie.json", "w") as f: json.dump(historie, f)
                st.rerun()

    if historie:
        report = historie[0]
        seznam_temat = [t.strip() for t in report['analyza'].split("---") if "TÉMA" in t.upper()]
        
        # LEGENDA
        st.write("🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie")
        
        # MAPA
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
                    radius=10,
                    popup=f"{i+1}. {nazev}",
                    color=barvy.get(kat, "gray"),
                    fill=True,
                    fill_opacity=0.7
                ).add_to(m)
            except: pass

        st_folium(m, width=1200, height=500)
        
        # GRID PRO PŘEKLIK (Pod mapou)
        st.subheader("📌 Seznam témat (klikni pro detail)")
        for i in range(0, len(seznam_temat), 2):
            cols = st.columns(2)
            for j in range(2):
                if i+j < len(seznam_temat):
                    t_data = seznam_temat[i+j]
                    with cols[j]:
                        if st.button(f"{i+j+1}. {vytahni(t_data, 'TÉMA')}", key=f"btn_{i+j}"):
                            st.session_state.selected_idx = i+j
                            st.session_state.view = 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    # (Tady zůstává tvůj kód pro detail, který už znáš...)
    st.button("⬅️ Zpět na mapu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    # ... zbytek detailu ...
