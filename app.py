import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import re
import os
from datetime import datetime
from streamlit_folium import st_folium
import folium

# --- 1. RUČNÍ NASTAVENÍ KLÍČŮ (Pro lokální běh) ---
# Tady si doplň své klíče, dokud nebudeme v cloudu
GOOGLE_API_KEY = "SEM_VLOZ_GEMINI_KLIC"
NEWS_API_KEY = "SEM_VLOZ_NEWS_API_KLIC"

genai.configure(api_key=GOOGLE_API_KEY)
newsapi = NewsApiClient(api_key=NEWS_API_KEY)

st.set_page_config(page_title="WorldMirror Local Dev", page_icon="⚖️", layout="wide")

# --- 2. DYNAMICKÝ VÝBĚR MODELU (Oprava NotFound) ---
def ziskej_funkcni_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Hledáme Pro, pak Flash, pak cokoliv
        vybrany = next((m for m in available if "1.5-pro" in m), 
                  next((m for m in available if "1.5-flash" in m), 
                  available[0]))
        return genai.GenerativeModel(vybrany)
    except Exception as e:
        st.error(f"Chyba při hledání modelu: {e}")
        return None

# --- 3. LOGIKA CACHINGU A ANALÝZY ---
@st.cache_data(ttl=3600)
def get_global_data():
    return spustit_analyzu(pocet=6, priority=None)

def spustit_analyzu(pocet=10, priority=None):
    model = ziskej_funkcni_model()
    if not model: return None

    # NewsAPI volání
    if priority:
        q = " OR ".join(priority)
        data = newsapi.get_everything(q=q, language='en', sort_by='relevancy', page_size=50)
    else:
        data = newsapi.get_top_headlines(language='en', page_size=50)

    clanky = data.get('articles', [])
    text_ai = "".join([f"ID:{i} - {c['source']['name']}: {c['title']}\n" for i, c in enumerate(clanky)])
    pro_web = [{"id": i, "zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for i, c in enumerate(clanky)]

    prompt = f"""
    Jsi geopolitický expert. Vyber {pocet} témat. {f'Priority: {priority}' if priority else ''}
    Vrať POUZE JSON (seznam objektů). Žádný úvodní text.
    Pole: tema, kategorie, lat, lon, bleskovka, fakta, usa, eu, asie, vychod, jih, levice, pravice, bod_svaru, clanek, zdroje_id (list).
    Kategorie: Válka, Ekonomika, Politika, Technologie, Sport, Showbyznys.
    U EU napiš postoj Evropské unie 🇪🇺.
    ZDROJE: {text_ai}
    """

    res = model.generate_content(prompt)
    try:
        json_str = re.search(r"```json\s*(.*?)\s*```", res.text, re.DOTALL).group(1) if "```" in res.text else res.text
        return {"data": json.loads(json_str), "zdroje": pro_web, "cas": datetime.now().strftime("%H:%M")}
    except:
        st.error("AI vrátila neplatný formát. Zkus to znovu.")
        return None

# --- 4. UI A DASHBOARD ---
if 'view' not in st.session_state: st.session_state.view = 'map'

# Sidebar - Simulace Premium
st.sidebar.title("🛠️ Vývojářský panel")
is_premium = st.sidebar.toggle("Aktivovat Premium Režim", value=False)

if is_premium:
    kat = st.sidebar.multiselect("Filtry (Premium):", ["Válka", "Ekonomika", "AI", "Sport", "Showbyznys", "Česko"], default=["Válka"])
    if st.sidebar.button("⚡ Generovat výběr"):
        st.session_state.result = spustit_analyzu(pocet=10, priority=kat)
else:
    if 'result' not in st.session_state:
        st.session_state.result = get_global_data()

# --- Zobrazení ---
res = st.session_state.result
if res:
    seznam = res['data']
    BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF", "Sport": "#FFA500", "Showbyznys": "#FF69B4"}
    BG = {"Válka": "#FFECEC", "Ekonomika": "#E6F4F1", "Politika": "#E6F0FF", "Technologie": "#F3E6FF", "Sport": "#FFF5E6", "Showbyznys": "#FFECF5"}

    if st.session_state.view == 'map':
        st.title(f"🌍 WorldMirror Matrix {'[PREMIUM]' if is_premium else '[FREE]'}")
        st.caption(f"Aktualizováno: {res['cas']} | Režim: {'Individuální' if is_premium else 'Globální radar (1h cache)'}")

        # MAPA
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for t in seznam:
            try:
                folium.CircleMarker(
                    location=[float(t['lat']), float(t['lon'])], radius=12,
                    popup=f"Téma:{t['tema']}", color=BARVY.get(t['kategorie'], "gray"), fill=True, fill_opacity=0.8
                ).add_to(m)
            except: continue
        
        st_folium(m, width="100%", height=400)

        # DLAŽDICE
        st.subheader("📌 Top události")
        for i in range(0, len(seznam), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam):
                    t = seznam[idx]
                    with cols[j]:
                        st.markdown(f"""
                            <div style="border-left: 10px solid {BARVY.get(t['kategorie'], '#333')}; background-color: {BG.get(t['kategorie'], '#f0f0f0')}; padding: 15px; border-radius: 5px; margin-bottom: 10px; min-height: 100px;">
                                <h4 style="margin: 0; color: #111;">{idx + 1}. {t['tema']}</h4>
                                <p style="margin: 5px 0; color: #444; font-size: 0.9em;">{t['bleskovka']}</p>
                            </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"🔍 Rozbor {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

    elif st.session_state.view == 'detail':
        t = seznam[st.session_state.selected_idx]
        st.button("⬅️ Zpět", on_click=lambda: setattr(st.session_state, 'view', 'map'))
        st.title(f"🔎 {t['tema']}")
        
        # Geopolitika
        st.markdown("### 🌍 Geopolitická matice")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown("🟦 **USA**"); st.caption(t['usa'])
        with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(t['eu'])
        with c3: st.markdown("🟣 **Vyspělá Asie**"); st.caption(t['asie'])
        
        # Reportáž
        st.divider()
        st.subheader("📝 Hloubková reportáž")
        st.markdown(f"""<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: 'Georgia', serif; line-height: 1.6; font-size: 1.1em;">{t['clanek']}</div>""", unsafe_allow_html=True)
        
        # Odkazy
        st.divider()
        st.subheader("🔗 Zdroje")
        for aid in t.get('zdroje_id', []):
            if aid < len(res['zdroje']):
                a = res['zdroje'][aid]
                st.markdown(f"✅ **{a['zdroj']}**: [{a['titulek']}]({a['link']})")
