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

# --- 1. KONFIGURACE A ÚSTAVA ---
st.set_page_config(page_title="WorldMirror Matrix Elite+ PRO", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except Exception:
    st.error("❌ CHYBA: Nastavte API klíče v Secrets!")
    st.stop()

# Inicializace stavů
if 'view' not in st.session_state: st.session_state.view = 'map'
if 'selected_idx' not in st.session_state: st.session_state.selected_idx = None
if 'active_report' not in st.session_state: st.session_state.active_report = None

# --- 2. POMOCNÉ FUNKCE (LOGIKA) ---

def ziskej_aktivni_model():
    """Zákon 1: Dynamická detekce modelu pro zamezení NotFound error."""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Vybere Pro, pokud není, zkusí první dostupný
        vybrany = next((m for m in models if "1.5-pro" in m), models[0])
        return genai.GenerativeModel(vybrany)
    except Exception as e:
        st.error(f"Nelze načíst modely: {e}")
        return None

def nacti_historii():
    """Načte uložené analýzy ze souboru."""
    if os.path.exists("historie.json"):
        try:
            with open("historie.json", "r", encoding="utf-8") as f: 
                return json.load(f)
        except: return []
    return []

def uloz_do_historie(novy_zaznam):
    """Uloží analýzu do souboru, držíme posledních 20 pro plynulost."""
    historie = nacti_historii()
    historie.insert(0, novy_zaznam)
    with open("historie.json", "w", encoding="utf-8") as f:
        json.dump(historie[:20], f, ensure_ascii=False, indent=4)

def stahni_vsechna_data():
    """Sběr dat z NewsAPI a RSS (Zákon: Priorita ČR a finanční feedy)."""
    vse = []
    # Globální NewsAPI
    try:
        data = newsapi.get_everything(
            q='geopolitics OR economy OR "Czech Republic"',
            language='en', sort_by='relevancy', page_size=40
        )
        vse += [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: pass
    
    # RSS zprávy (Včetně českých)
    rss_urls = [
        "https://www.seznamzpravy.cz/rss", 
        "https://archiv.hn.cz/rss/",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://tass.com/rss/v2.xml"
    ]
    for url in rss_urls:
        try:
            f = feedparser.parse(url)
            for entry in f.entries[:10]:
                vse.append({"zdroj": "RSS/Direct", "titulek": entry.title, "link": entry.link})
        except: continue
    
    # Připravíme jeden velký textový řetězec pro AI
    text_pro_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_pro_ai

def text_na_audio(text):
    """Vygeneruje audio přehrávač (Zákon: limit gTTS aby aplikace nepadala)."""
    if not text: return ""
    try:
        # gTTS limit cca 5000 znaků, bereme první část pro stabilitu
        tts = gTTS(text=text[:3000], lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return ""

# --- 3. BARVY ---
BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF"}

def get_color(kat):
    k = str(kat).strip().capitalize()
    return BARVY.get(k, "gray")

# --- 4. HLAVNÍ LOGIKA UI ---

st.sidebar.title("📚 WorldMirror Archiv")
historie = nacti_historii()

if st.sidebar.button("🗑️ Vymazat historii"):
    if os.path.exists("historie.json"): os.remove("historie.json")
    st.session_state.active_report = None
    st.rerun()

# Volba z historie v postranním panelu
if historie:
    vyber = st.sidebar.selectbox("Předchozí analýzy:", range(len(historie)), format_func=lambda x: historie[x]['cas'])
    if st.sidebar.button("Načíst z archivu"):
        st.session_state.active_report = historie[vyber]
        st.session_state.view = 'map'
        st.rerun()

# --- STRÁNKA: MAPA (HLAVNÍ POHLED) ---
if st.session_state.view == 'map':
    st.title("⚖️ WorldMirror: Globální Triangulace")
    
    if st.button("🚀 Spustit novou analýzu Matrixu"):
        with st.spinner("Provádím hloubkový sken a triangulaci (Západ/Východ/Jih)..."):
            model = ziskej_aktivni_model()
            if model:
                clanky, text_ai = stahni_vsechna_data()
                
                # ŽELEZNÉ ZÁKONY V PROMPTU
                prompt = f"""
                Jsi seniorní analytik. Vygeneruj 10 nejdůležitějších témat z dodaných zdrojů.
                ZÁKONY:
                1. JSON FORMÁT: Výstup MUSÍ být pole JSON objektů (žádný text okolo).
                2. ANALÝZA: Každé pole (usa, eu, asie, vychod, jih, levice, pravice) MUSÍ obsahovat min. 3 věty.
                3. DÉLKA REPORTÁŽE: Pole 'clanek' MUSÍ mít VŽDY minimálně 500 slov.
                4. PRIORITA ČR: Pokud jsou v datech zmínky o českých firmách nebo ekonomice (ČEZ, CSG, PPF atd.), dej je na přední místa.
                
                Struktura jednoho JSON objektu:
                {{
                  "tema": "Krátký název", "kategorie": "Válka" (nebo Ekonomika/Politika/Technologie),
                  "lat": 0.0, "lon": 0.0, "bleskovka": "Stručné shrnutí", "fakta": "Základní fakta",
                  "usa": "Pohled USA...", "eu": "Pohled EU...", "asie": "Pohled Asie...", 
                  "vychod": "Pohled Rusko/Čína...", "jih": "Pohled Globální Jih...",
                  "levice": "Liberální pohled...", "pravice": "Konzervativní pohled...", 
                  "bod_svaru": "Hlavní spor...", "clanek": "Hloubková reportáž (min 500 slov)..."
                }}
                ZDROJE k analýze:
                {text_ai}
                """
                
                try:
                    # Vynucení JSONu od modelu
                    res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                    
                    # ROBUSTNÍ PARSOVÁNÍ JSONU (Oprava "AI selhala")
                    raw_data = json.loads(res.text)
                    
                    # AI může vrátit rovnou pole [...], nebo objekt s klíčem {"analyza": [...]}
                    seznam_analyz = []
                    if isinstance(raw_data, list):
                        seznam_analyz = raw_data
                    elif isinstance(raw_data, dict):
                        # Zkusí najít jakýkoliv seznam uvnitř slovníku
                        for key, value in raw_data.items():
                            if isinstance(value, list):
                                seznam_analyz = value
                                break
                    
                    if not seznam_analyz:
                        raise ValueError("Nepodařilo se najít pole dat v JSON struktuře.")
                        
                    novy_report = {"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": seznam_analyz, "zdroje": clanky}
                    uloz_do_historie(novy_report)
                    st.session_state.active_report = novy_report
                    st.rerun()
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ AI nevrátila validní JSON. Zkuste to znovu. Detaily: {e}")
                    if 'res' in locals(): st.expander("Zobrazit raw výstup AI").code(res.text)
                except Exception as e:
                    st.error(f"❌ Nastala chyba při zpracování: {e}")
                    if 'res' in locals(): st.expander("Zobrazit raw výstup AI").code(res.text)

    # Zobrazení aktivního reportu na mapě
    report = st.session_state.active_report if st.session_state.active_report else (historie[0] if historie else None)
    
    if report:
        seznam = report.get('analyza_json', [])
        
        # Generování Mapy
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for i, t in enumerate(seznam):
            c = get_color(t.get('kategorie'))
            # Bezpečné získání souřadnic, pokud si je AI vymyslí jako string
            try:
                lat = float(t.get('lat', 0))
                lon = float(t.get('lon', 0))
            except:
                lat, lon = 0, 0
                
            folium.CircleMarker(
                location=[lat, lon], radius=12,
                popup=t.get('tema', 'Neznámé téma'), tooltip=t.get('tema', 'Klikni pro detail'),
                color=c, fill=True, fill_opacity=0.8
            ).add_to(m)
        
        map_res = st_folium(m, width="100%", height=450)

        # Logika po kliknutí na bod na mapě
        if map_res.get('last_object_clicked_popup'):
            t_name = map_res['last_object_clicked_popup']
            for i, obj in enumerate(seznam):
                if obj.get('tema') == t_name:
                    st.session_state.selected_idx = i
                    st.session_state.view = 'detail'
                    st.rerun()

        st.divider()
        st.markdown('<div style="text-align: center; font-weight: bold;">🔴 Válka | 🟢 Ekonomika | 🔵 Politika | 🟣 Technologie</div>', unsafe_allow_html=True)
        st.write("")

        # Dlaždice s výpisem zpráv
        for i in range(0, len(seznam), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam):
                    t = seznam[idx]
                    kat = t.get("kategorie", "Politika")
                    tema = t.get("tema", "Téma")
                    bleskovka = t.get("bleskovka", "")
                    with cols[j]:
                        st.markdown(f'<div style="border-left: 5px solid {get_color(kat)}; padding:15px; background:#1e1e1e; border-radius:5px; margin-bottom: 10px;"><h4>{idx+1}. {tema}</h4><small style="color: #ccc;">{bleskovka}</small></div>', unsafe_allow_html=True)
                        if st.button(f"🔍 Detail reportáže {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx = idx
                            st.session_state.view = 'detail'
                            st.rerun()

# --- STRÁNKA: DETAIL REPORTÁŽE ---
elif st.session_state.view == 'detail':
    report = st.session_state.active_report if st.session_state.active_report else historie[0]
    t = report['analyza_json'][st.session_state.selected_idx]
    
    st.button("⬅️ Zpět do Matrixu", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t.get('tema', 'Bez názvu')}")
    
    st.subheader("🔊 Audio brífink (Fakta + Shrnutí)")
    # Posíláme do audia fakta a začátek článku
    audio_text = f"{t.get('fakta', '')}. {t.get('clanek', '')[:500]}"
    st.markdown(text_na_audio(audio_text), unsafe_allow_html=True)
    
    st.info(f"**Fakta:** {t.get('fakta', 'Data nejsou k dispozici.')}")
    
    # Geopolitická matice
    st.markdown("### 🌍 Globální Matice Pohledů")
    c1, c2, c3 = st.columns(3)
    c1.metric("🇺🇸 Pohled USA", "Analýza"); c1.caption(t.get('usa', 'Chybí'))
    c2.metric("🇪🇺 Pohled Evropy", "Analýza"); c2.caption(t.get('eu', 'Chybí'))
    c3.metric("🟣 Pohled Asie", "Analýza"); c3.caption(t.get('asie', 'Chybí'))
    
    c4, c5 = st.columns(2)
    c4.metric("🟥 Pohled Východu (Rusko/Čína)", "Analýza"); c4.caption(t.get('vychod', 'Chybí'))
    c5.metric("🌏 Pohled Globálního Jihu", "Analýza"); c5.caption(t.get('jih', 'Chybí'))
    
    st.divider()
    
    # Ideologické narativy
    cl, cr = st.columns(2)
    with cl:
        st.success("🌿 **Liberal / Levice**")
        st.write(t.get('levice', 'Chybí'))
    with cr:
        st.error("🦅 **Conservative / Pravice**")
        st.write(t.get('pravice', 'Chybí'))
    
    # Hloubková reportáž
    st.subheader("📝 Hloubková analytická reportáž")
    clanek_obsah = t.get('clanek', 'Reportáž nebyla vygenerována.')
    st.markdown(f'<div style="background-color: #262730; padding: 30px; border-radius: 10px; border: 1px solid #444; font-family: Georgia, serif; font-size: 1.1em; line-height: 1.6;">{clanek_obsah}</div>', unsafe_allow_html=True)
    
    st.write("")
    st.warning(f"⚠️ **Kritický bod sváru:** {t.get('bod_svaru', 'Nespecifikováno')}")
