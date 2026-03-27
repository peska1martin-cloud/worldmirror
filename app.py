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
st.set_page_config(page_title="WorldMirror: Global Triangulation", page_icon="⚖️", layout="wide")

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

def stahni_multipolar_zpravy():
    """Stahuje zprávy z různorodých geopolitických zdrojů."""
    try:
        # Cíleně hledáme v doménách z různých bloků
        data = newsapi.get_everything(
            q='geopolitics OR war OR economy OR conflict',
            domains='tass.com,rt.com,aljazeera.com,scmp.com,reuters.com,apnews.com,dw.com',
            language='en',
            sort_by='publishedAt',
            page_size=80
        )
        clanky = data.get('articles', [])
        text_pro_ai = ""
        pro_web = []
        for i, c in enumerate(clanky):
            text_pro_ai += f"ID:{i} [{c['source']['name']}]: {c['title']}\n"
            pro_web.append({"id": i, "zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']})
        return pro_web, text_pro_ai
    except Exception as e:
        st.error(f"Chyba NewsAPI: {e}")
        return [], ""

def ziskej_nejlepsi_model():
    """Pokusí se získat 1.5 Pro, jinak Flash."""
    try:
        modely = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        vybrany = next((m for m in modely if "1.5-pro" in m), 
                  next((m for m in modely if "flash" in m), modely[0]))
        return genai.GenerativeModel(vybrany)
    except: return None

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
    st.title("⚖️ WorldMirror: Globální Triangulace")
    st.caption("Analýza světa skrze optiku Západu, Východu a Globálního Jihu.")
    
    if st.button("🚀 Spustit hloubkovou analýzu (Gemini 1.5 Pro)"):
        with st.spinner("Sbírám data z TASS, Al-Jazeera, Reuters a SCMP..."):
            model = ziskej_nejlepsi_model()
            clanky, text_ai = stahni_multipolar_zpravy()
            if model and clanky:
                prompt = f"""
                Jsi elitní analytik mezinárodních vztahů. Tvým úkolem je vytvořit naprosto objektivní rozbor.
                Z těchto zpráv vyber 10 klíčových témat. U každého zmapuj střet narativů.
                
                Vrať POUZE JSON (seznam 10 objektů):
                [
                  {{
                    "tema": "Název tématu",
                    "kategorie": "Válka/Ekonomika/Politika/Technologie",
                    "lat": 0.0, "lon": 0.0,
                    "bleskovka": "Stručná věta",
                    "fakta": "Co se objektivně stalo (společný základ)",
                    "usa": "ZÁPADNÍ POHLED: Jak to interpretuje Washington/Brusel",
                    "eu": "EVROPSKÁ SPECIFIKA: Kde se EU liší od USA (např. humanitární právo, Green Deal)",
                    "asie": "ASIE (JPN/KOR/TWN): Technologické a regionální zájmy",
                    "vychod": "VÝCHODNÍ POHLED: Jak to interpretuje Moskva a Peking",
                    "jih": "GLOBÁLNÍ JIH / ARABSKÝ SVĚT: Jak to vidí Al-Jazeera a rozvojový svět",
                    "levice": "Liberal/Progresivní narativ",
                    "pravice": "Conservative/Suverénní narativ",
                    "bod_svaru": "Klíčový bod, kde se tyto strany nejvíce rozcházejí",
                    "clanek": "Hloubková reportáž (300 slov) srovnávající tyto propagandy.",
                    "zdroje_id": [indexy]
                  }}
                ]
                ZDROJE (včetně ruských a arabských):
                {text_ai}
                """
                try:
                    result = model.generate_content(prompt)
                    cleaned_response = re.search(r"```json(.*)```", result.text, re.DOTALL)
                    json_str = cleaned_response.group(1).strip() if cleaned_response else result.text.strip()
                    uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": json.loads(json_str), "zdroje": clanky})
                    st.rerun()
                except Exception as e:
                    st.error(f"Chyba AI: {e}")

    if historie:
        report = historie[0]
        seznam_temat = report.get('analyza_json', [])[:10]
        
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for t in seznam_temat:
            kat = t.get('kategorie', 'Politika').strip().capitalize()
            try:
                folium.CircleMarker(
                    location=[float(t['lat']), float(t['lon'])], radius=12,
                    popup=t['tema'], color=BARVY.get(kat, "gray"), fill=True
                ).add_to(m)
            except: continue
        
        st_folium(m, width="100%", height=400)
        
        st.divider()
        for i in range(0, len(seznam_temat), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam_temat):
                    t = seznam_temat[idx]
                    kat = t.get('kategorie', 'Politika').strip().capitalize()
                    with cols[j]:
                        st.markdown(f"""<div style="border-left: 10px solid {BARVY.get(kat, '#333')}; background-color: {BARVY_BG.get(kat, '#f0f0f0')}; padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                                    <h4 style="margin: 0; color: #111;">{idx + 1}. {t.get('tema')}</h4>
                                    <p style="margin: 5px 0; color: #444; font-size: 0.9em;">{t.get('bleskovka')}</p></div>""", unsafe_allow_html=True)
                        if st.button(f"🔍 Otevřít analýzu narativů {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    t = historie[0]['analyza_json'][st.session_state.selected_idx]
    st.button("⬅️ Zpět na dashboard", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 Rozbor: {t.get('tema')}")
    st.info(f"**Objektivní fakta:** {t.get('fakta')}")
    
    st.markdown("### 🌍 Střet geopolitických narativů")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **Západ (USA/EU)**"); st.caption(f"**USA:** {t.get('usa')}\n\n**EU 🇪🇺:** {t.get('eu')}")
    with c2: st.markdown("🟥 **Východ (RUS/CHN)**"); st.caption(t.get('vychod'))
    with c3: st.markdown("🌏 **Arabský svět / Jih**"); st.caption(t.get('jih'))
    
    st.divider()
    st.subheader("📝 Hloubková reportáž (Srovnání propagandy)")
    st.markdown(f"""<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: 'Georgia', serif; line-height: 1.6; font-size: 1.1em;">{t.get('clanek')}</div>""", unsafe_allow_html=True)
    
    st.error(f"⚠️ **Kritický bod sváru:** {t.get('bod_svaru')}")
    
    st.divider()
    st.subheader("🔗 Zdrojové články")
    for aid in t.get('zdroje_id', []):
        if aid < len(historie[0]['zdroje']):
            art = historie[0]['zdroje'][aid]
            st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
