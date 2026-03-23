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
st.set_page_config(page_title="WorldMirror Matrix Elite+ PRO (JSON)", page_icon="⚖️", layout="wide")

try:
    # Pokud běžíš lokálně, můžeš klíče vložit přímo sem: GOOGLE_API_KEY = "TvůjKlíč"
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

# Definice barev (Klíče musí přesně sedět na to, co vrací AI)
BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF"}
BARVY_BG = {"Válka": "#FFECEC", "Ekonomika": "#E6F4F1", "Politika": "#E6F0FF", "Technologie": "#F3E6FF"}

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Geopolitika")
    
    if st.button("🚀 Spustit hloubkovou analýzu světa"):
        with st.spinner("Skenuji planetu, geopolitiku a píši reportáže..."):
            model = ziskej_funkcni_model()
            clanky, text_ai = stahni_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi špičkový analytik a novinář. Z těchto zpráv vyber 10 nejdůležitějších globálních témat.
                Tvůj úkol je vytvořit strukturovanou analýzu v češtině a vrátit ji POUZE ve formátu JSON.
                DŮLEŽITÉ: Kategorie musí být přesně jedno z těchto slov: Válka, Ekonomika, Politika, Technologie.

                ODPOVĚĎ MUSÍ BÝT PLATNÝ JSON:
                [
                  {{
                    "tema": "Název tématu",
                    "kategorie": "Válka",
                    "lat": 1.23,
                    "lon": 4.56,
                    "bleskovka": "Stručná věta pro dlaždici",
                    "fakta": "Popis události",
                    "usa": "Postoj USA",
                    "eu": "Postoj Evropy",
                    "asie": "Pohled JPN/KOR/TWN",
                    "vychod": "Pohled Ruska a Číny",
                    "jih": "Pohled Globálního Jihu",
                    "levice": "Levicový pohled",
                    "pravice": "Pravicový pohled",
                    "bod_svaru": "Klíčový rozpor",
                    "clanek": "Hloubková reportáž cca 300 slov v češtině.",
                    "zdroje_id": [0, 5, 12]
                  }}
                ]
                ZDROJE ČLÁNKŮ:
                {text_ai}
                """
                try:
                    result = model.generate_content(prompt)
                    cleaned_response = re.search(r"```json(.*)```", result.text, re.DOTALL)
                    analyza_json_str = cleaned_response.group(1).strip() if cleaned_response else result.text.strip()
                    analyza_json = json.loads(analyza_json_str)
                    
                    if analyza_json:
                        uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": analyza_json, "zdroje": clanky})
                        st.rerun()
                except Exception as e:
                    st.error(f"Chyba při zpracování AI: {e}")

    if historie:
        report = historie[0]
        if "analyza_json" in report:
            seznam_temat = report['analyza_json'][:10]
            
            # --- MAPA ---
            m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
            for t_data in seznam_temat:
                # Očista kategorie pro mapu (odstranění mezer a sjednocení velkých písmen)
                kat = t_data.get('kategorie', 'Politika').strip().capitalize()
                lat, lon, nazev = t_data.get('lat'), t_data.get('lon'), t_data.get('tema')
                
                try:
                    folium.CircleMarker(
                        location=[float(lat), float(lon)], radius=12,
                        popup=f"Téma:{nazev}", color=BARVY.get(kat, "gray"), fill=True, fill_opacity=0.8
                    ).add_to(m)
                except: continue
            
            st.subheader("🌍 Aktuální ohniska zájmu")
            st_folium(m, width="100%", height=400)
            st.caption("🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie")

            # --- DLAŽDICE DASHBOARDU ---
            st.divider()
            st.subheader("📌 Top 10 témat dne")
            for i in range(0, len(seznam_temat), 2):
                cols = st.columns(2)
                for j in range(2):
                    idx = i + j
                    if idx < len(seznam_temat):
                        t_data = seznam_temat[idx]
                        # Očista kategorie pro dlaždice
                        kat = t_data.get('kategorie', 'Politika').strip().capitalize()
                        barva_hex = BARVY.get(kat, "#333")
                        bg_hex = BARVY_BG.get(kat, "#f0f0f0")
                        
                        with cols[j]:
                            st.markdown(f"""
                                <div style="border-left: 10px solid {barva_hex}; background-color: {bg_hex}; padding: 15px; border-radius: 5px; margin-bottom: 10px; min-height: 120px; border-top: 1px solid #ddd; border-right: 1px solid #ddd; border-bottom: 1px solid #ddd;">
                                    <h4 style="margin: 0; color: #111;">{idx + 1}. {t_data.get('tema')}</h4>
                                    <p style="margin: 5px 0; color: #444; font-size: 0.9em;">{t_data.get('bleskovka')}</p>
                                </div>
                            """, unsafe_allow_html=True)
                            if st.button(f"🔎 Otevřít analýzu k tématu {idx+1}", key=f"btn_{idx}"):
                                st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                                st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    t_data = report['analyza_json'][st.session_state.selected_idx]
    
    st.button("⬅️ Zpět na dashboard", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 Detail: {t_data.get('tema')}")
    st.info(f"**Fakta:** {t_data.get('fakta')}")
    
    st.markdown("### 🌍 Geopolitická křižovatka")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t_data.get('usa'))
    with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(t_data.get('eu'))
    with c3: st.markdown("🟣 **Vyspělá Asie**"); st.caption(t_data.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(t_data.get('vychod'))
    with c5: st.markdown("🌏 **Globální Jih**"); st.caption(t_data.get('jih'))
    
    st.markdown("---")
    st.markdown("### 🧠 Ideologické spektrum")
    c6, c7 = st.columns(2)
    with c6: st.success(f"🌿 **Levice / Liberal**\n\n{t_data.get('levice')}")
    with c7: st.error(f"🦅 **Pravice / Conservative**\n\n{t_data.get('pravice')}")
    
    st.error(f"⚠️ **Bod sváru:** {t_data.get('bod_svaru')}")

    st.divider()
    st.subheader("📝 Hloubková reportáž")
    st.markdown(f"""<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: 'Georgia', serif; line-height: 1.6; font-size: 1.1em;">{t_data.get('clanek')}</div>""", unsafe_allow_html=True)
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    zdroje_ids = t_data.get("zdroje_id")
    if zdroje_ids:
        for article_id in zdroje_ids:
            if article_id < len(report['zdroje']):
                art = report['zdroje'][article_id]
                st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
