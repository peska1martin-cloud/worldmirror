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
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception:
    st.error("❌ CHYBA: Nastavte API klíče v Secrets na Streamlit Cloudu!")
    st.stop()

if 'view' not in st.session_state: st.session_state.view = 'map'
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = None

# --- 2. FUNKCE PRO ZPRACOVÁNÍ DAT (Verze JSON) ---
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

# Definice barev
BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF"}
BARVY_BG = {"Válka": "#FFECEC", "Ekonomika": "#E6F4F1", "Politika": "#E6F0FF", "Technologie": "#F3E6FF"}

if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Geopolitika")
    
    if st.button("🚀 Spustit hloubkovou analýzu světa"):
        with st.spinner("Skenuji planetu, geopolitiku a píši reportáže... (Může to trvat minutu)"):
            model = ziskej_funkcni_model()
            clanky, text_ai = ststahni_zpravy()
            if model and clanky:
                # --- NOVÝ PROMPT PRO JSON ODPOVĚĎ ---
                prompt = f"""
                Jsi špičkový analytik a novinář. Z těchto zpráv vyber 10 nejdůležitějších globálních témat.
                Tvůj úkol je vytvořit strukturovanou, hloubkovou analýzu v češtině a vrátit ji POUZE ve formátu JSON.
                Nepoužívej hvězdičky pro tučné písmo.

                ODPOVĚĎ MUSÍ BÝT PLATNÝ JSON S NÁSLEDUJÍCÍM FORMÁTEM (Seznam objektů):
                [
                  {{
                    "tema": "Název tématu",
                    "kategorie": "Válka/Ekonomika/Politika/Technologie",
                    "lat": 1.23,
                    "lon": 4.56,
                    "bleskovka": "Stručná věta pro dlaždici",
                    "fakta": "Popis události v 2-3 větách",
                    "usa": "Postoj USA",
                    "eu": "Postoj Evropy (hledej rozdíly od USA)",
                    "asie": "Pohled Japonska, Taiwanu a J. Koreje",
                    "vychod": "Pohled Ruska a Číny",
                    "jih": "Pohled Globálního Jihu / Arabský svět",
                    "levice": "Levicový pohled",
                    "pravice": "Pravicový pohled",
                    "bod_svaru": "Klíčový rozpor",
                    "clanek": "Napiš souvislou, hloubkovou reportáž o tomto tématu v češtině o délce cca 300 slov.",
                    "zdroje_id": [0, 5, 12]
                  }},
                  ...dalších 9 témat
                ]

                ZDROJE ČLÁNKŮ S ID:
                {text_ai}
                """
                
                try:
                    # Nařídíme AI vrátit JSON. To zajistí platnou strukturu.
                    result = model.generate_content(prompt)
                    # Zkusíme najít JSON kód v odpovědi (Gemini ho občas balí do ```json ... ```)
                    cleaned_response = re.search(r"```json(.*)```", result.text, re.DOTALL)
                    if cleaned_response:
                        analyza_json_str = cleaned_response.group(1).strip()
                    else:
                        analyza_json_str = result.text.strip()
                    
                    # Ověříme, zda je to platný JSON. Pokud ne, aplikace spadne a uživatel uvidí chybu.
                    analyza_json = json.loads(analyza_json_str)
                    
                    if analyza_json and len(analyza_json) > 0:
                        novy_zaznam = {
                            "cas": datetime.now().strftime("%d.%m.%Y %H:%M"),
                            "analyza_json": analyza_json, # Ukládáme jako JSON, ne jako text!
                            "zdroje": clanky
                        }
                        uloz_do_historie(novy_zaznam)
                        st.rerun()
                    else:
                        st.error("Chyba: AI vrátila prázdnou analýzu.")

                except json.JSONDecodeError:
                    st.error("Kritická chyba: AI nevrátila data ve správném formátu JSON. Zkuste sken zopakovat.")
                    st.stop()
                except Exception as e:
                    st.error(f"Chyba při komunikaci s AI: {e}")

    if historie:
        report = historie[0]
        # Přečteme JSON data. Omezíme na 10 pro jistotu.
        # Starší historie může mít analýzu jako text, takže ji ignorujeme a chceme jen novou.
        if "analyza_json" in report:
            seznam_temat = report['analyza_json'][:10]
        else:
            st.warning("Upozornění: Vaše historie obsahuje starší analýzy, které nejsou kompatibilní. Klikněte na 'Vymazat historii' a spusťte sken znovu.")
            seznam_temat = []

        if seznam_temat:
            # --- MAPA ---
            m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
            for t_data in seznam_temat:
                kat = t_data.get('kategorie', 'Politika')
                lat = t_data.get('lat')
                lon = t_data.get('lon')
                nazev = t_data.get('tema')
                
                # Vykreslíme bod. Souřadnice jsou už čísla.
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
            st.subheader("📌 Top 10 témat dne (klikni pro detail)")
            for i in range(0, len(seznam_temat), 2):
                cols = st.columns(2)
                for j in range(2):
                    idx = i + j
                    if idx < len(seznam_temat):
                        t_data = seznam_temat[idx]
                        kat = t_data.get('kategorie')
                        barva_hex = BARVY.get(kat, "#333")
                        bg_hex = BARVY_BG.get(kat, "#f0f0f0")
                        
                        with cols[j]:
                            # HTML dlaždice. První už nebude prázdná!
                            st.markdown(f"""
                                <div style="border-left: 10px solid {barva_hex}; background-color: {bg_hex}; padding: 15px; border-radius: 5px; margin-bottom: 10px; min-height: 120px;">
                                    <h4 style="margin: 0; color: #111;">{idx + 1}. {t_data.get('tema')}</h4>
                                    <p style="margin: 5px 0; color: #444; font-size: 0.9em;">{t_data.get('bleskovka')}</p>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # Tlačítko pro detail
                            if st.button(f"🔎 Otevřít analýzu k tématu {idx+1}", key=f"btn_{idx}"):
                                st.session_state.selected_idx = idx
                                st.session_state.view = 'detail'
                                st.rerun()

elif st.session_state.view == 'detail':
    report = historie[0]
    # Čteme JSON data
    if "analyza_json" in report:
        seznam_temat = report['analyza_json'][:10]
    else:
        st.error("Chyba při načítání detailu.")
        st.stop()
        
    t_data = seznam_temat[st.session_state.selected_idx]
    
    # Hlavička detailu
    st.button("⬅️ Zpět na dashboard", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 Detail: {t_data.get('tema')}")
    
    st.info(f"**Fakta:** {t_data.get('fakta')}")
    
    # --- GEOPOLITICKÁ MATICE (4 SLOUPCE) ---
    st.markdown("### 🌍 Geopolitická křižovatka")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t_data.get('usa'))
    with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(t_data.get('eu')) # Opraveno!
    with c3: st.markdown("🟣 **Vyspělá Asie**"); st.caption(t_data.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(t_data.get('vychod'))
    with c5: st.markdown("🌏 **Globální Jih**"); st.caption(t_data.get('jih'))
    
    # --- IDEOLOGICKÁ SEKCE ---
    st.markdown("---")
    st.markdown("### 🧠 Ideologické spektrum")
    c6, c7 = st.columns(2)
    with c6: st.success(f"🌿 **Levice / Liberal**\n\n{t_data.get('levice')}")
    with c7: st.error(f"🦅 **Pravice / Conservative**\n\n{t_data.get('pravice')}")
    
    st.error(f"⚠️ **Bod sváru:** {t_data.get('bod_svaru')}")

    # --- REPORTÁŽ "A5" ---
    st.divider()
    st.subheader("📝 Hloubková reportáž")
    st.markdown(f"""
    <div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: 'Georgia', serif; line-height: 1.6; font-size: 1.1em;">
        {t_data.get('clanek')}
    </div>
    """, unsafe_allow_html=True)
    
    # --- ODKAZY NA ČLÁNKY (NOVÉ!) ---
    st.divider()
    st.subheader("🔗 Zdrojové články pro ověření")
    zdroje_ids = t_data.get("zdroje_id")
    if zdroje_ids:
        for article_id in zdroje_ids:
            if article_id < len(report['zdroje']):
                art = report['zdroje'][article_id]
                st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
    else: st.write("Odkazy nebyly AI přiřazeny.")
