import streamlit as st
import google.generativeai as genai
from newsapi import NewsApiClient
import json
import re
from datetime import datetime
from streamlit_folium import st_folium
import folium

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="WorldMirror Matrix", page_icon="⚖️", layout="wide")

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    NEWS_API_KEY = st.secrets["NEWS_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
except:
    st.error("❌ Nastavte API klíče v Secrets!")
    st.stop()

# --- 2. SIDEBAR A VOLBA KATEGORIÍ (PREMIUM) ---
st.sidebar.title("💎 WorldMirror Premium")
is_premium = st.sidebar.toggle("Aktivovat Premium funkce", value=False)

moje_kategorie = []
if is_premium:
    moje_kategorie = st.sidebar.multiselect(
        "Co vás dnes zajímá?",
        ["Válka", "Ekonomika", "Technologie", "AI", "Česko", "Evropa", "Asie", "USA", "Sport", "Showbyznys", "Bulvár"],
        default=["Válka", "Ekonomika"]
    )
    st.sidebar.info("✨ Jako Premium uživatel máte prioritní přístup k Gemini 1.5 Pro.")
else:
    st.sidebar.warning("🔓 Ve verzi Zdarma vidíte 6 hlavních globálních témat.")

# --- 3. LOGIKA CACHINGU (PRO FREE VERZI) ---
@st.cache_data(ttl=3600) # Cache na 1 hodinu
def ziskej_globalni_sken():
    # Tato funkce se spustí jen 1x za hodinu pro všechny uživatele
    return spustit_analyzu(pocet=6, priority=None)

def spustit_analyzu(pocet=10, priority=None):
    model = genai.GenerativeModel('gemini-1.5-pro') # Pro byznys verzi rovnou Pro
    
    # 1. Stažení zpráv (NewsAPI)
    # Pokud máme priority (Premium), hledáme šířeji přes 'everything'
    if priority:
        dotaz = " OR ".join(priority)
        data = newsapi.get_everything(q=dotaz, language='en', sort_by='relevancy', page_size=60)
    else:
        data = newsapi.get_top_headlines(language='en', page_size=60)
    
    clanky = data.get('articles', [])
    text_ai = ""
    pro_web = []
    for i, c in enumerate(clanky):
        text_ai += f"ID:{i} - {c['source']['name']}: {c['title']}\n"
        pro_web.append({"id": i, "zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']})

    # 2. Prompt pro Gemini
    priority_text = f"Prioritně se zaměř na témata: {', '.join(priority)}." if priority else "Zaměř se na nejdůležitější globální zprávy."
    
    prompt = f"""
    Jsi špičkový analytik. Vyber přesně {pocet} témat. {priority_text}
    Odpověď vrať POUZE jako platný JSON (seznam objektů).
    JSON pole: tema, kategorie, lat, lon, bleskovka, fakta, usa, eu, asie, vychod, jih, levice, pravice, bod_svaru, clanek (300 slov), zdroje_id (list).
    
    ZDROJE: {text_ai}
    """
    
    res = model.generate_content(prompt)
    json_match = re.search(r"```json\s*(.*?)\s*```", res.text, re.DOTALL)
    analyza = json.loads(json_match.group(1) if json_match else res.text)
    
    return {"cas": datetime.now().strftime("%H:%M"), "data": analyza, "zdroje": pro_web}

# --- 4. ZOBRAZENÍ ---
if 'view' not in st.session_state: st.session_state.view = 'map'

if is_premium and st.sidebar.button("⚡ Generovat můj výběr"):
    st.session_state.result = spustit_analyzu(pocet=10, priority=moje_kategorie)
    st.session_state.view = 'map'
elif 'result' not in st.session_state:
    # Pokud není Premium nebo první spuštění, načteme globální cache
    st.session_state.result = ziskej_globalni_sken()

# --- DASHBOARD ---
res = st.session_state.result
seznam_temat = res['data']

if st.session_state.view == 'map':
    st.title(f"🌍 WorldMirror Matrix {'[PREMIUM]' if is_premium else ''}")
    st.caption(f"Aktualizováno: {res['cas']} | Režim: {'Personalizovaný' if is_premium else 'Globální radar'}")

    # MAPA
    m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
    BARVY = {"Válka": "#FF4B4B", "Ekonomika": "#29B09D", "Politika": "#007BFF", "Technologie": "#7D44CF", "Sport": "#FFA500", "Bulvár": "#FF69B4"}
    
    for idx, t in enumerate(seznam_temat):
        try:
            folium.CircleMarker(
                location=[float(t['lat']), float(t['lon'])],
                radius=12, popup=f"Téma:{t['tema']}",
                color=BARVY.get(t['kategorie'], "gray"), fill=True, fill_opacity=0.8
            ).add_to(m)
        except: continue
    
    st_folium(m, width="100%", height=400)

    # DLAŽDICE
    st.divider()
    for i in range(0, len(seznam_temat), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = i + j
            if idx < len(seznam_temat):
                t = seznam_temat[idx]
                barva = BARVY.get(t['kategorie'], "#333")
                with cols[j]:
                    st.markdown(f"""
                        <div style="border-left: 10px solid {barva}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                            <h4 style="margin: 0;">{idx + 1}. {t['tema']}</h4>
                            <p style="font-size: 0.9em; color: #555;">{t['bleskovka']}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"🔎 Detail {idx+1}", key=f"btn_{idx}"):
                        st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                        st.rerun()

elif st.session_state.view == 'detail':
    t = seznam_temat[st.session_state.selected_idx]
    st.button("⬅️ Zpět", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔎 {t['tema']}")
    
    # MATICE 5 HRÁČŮ
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t['usa'])
    with c2: st.markdown("🇪🇺 **Evropská unie**"); st.caption(t['eu'])
    with c3: st.markdown("🟣 **Vyspělá Asie**"); st.caption(t['asie'])
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ**"); st.caption(t['vychod'])
    with c5: st.markdown("🌏 **Globální Jih**"); st.caption(t['jih'])
    
    st.divider()
    st.subheader("📝 Hloubková reportáž")
    st.markdown(f"""<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: 'Georgia', serif; line-height: 1.6; font-size: 1.1em;">{t['clanek']}</div>""", unsafe_allow_html=True)
