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

# --- 2. POMOCNÉ FUNKCE (Zůstávají stejné) ---
def nacti_historii():
    if os.path.exists("historie.json"):
        with open("historie.json", "r", encoding="utf-8") as f: return json.load(f)
    return []

def uloz_do_historie(novy_zaznam):
    historie = nacti_historii()
    historie.insert(0, novy_zaznam)
    with open("historie.json", "w", encoding="utf-8") as f:
        json.dump(historie, f, ensure_ascii=False, indent=4)

def get_clean_color(kat):
    k = str(kat).strip().lower()
    mapping = {
        "vál": "#FF4B4B", "eko": "#29B09D", "pol": "#007BFF", "tech": "#7D44CF",
        "ai": "#00FFFF", "přír": "#32CD32", "klim": "#32CD32", "akci": "#FFD700",
        "prům": "#808080", "show": "#FF69B4", "cest": "#FFA500", "krim": "#000000"
    }
    for klicek, barva in mapping.items():
        if klicek in k: return barva
    return "#AAAAAA"

# --- 3. SBĚR DAT ---
def stahni_vsechna_data(regiony, temata):
    q = f"({ ' OR '.join(regiony) if regiony else 'World' }) AND ({ ' OR '.join(temata) if temata else 'Geopolitics' })"
    try:
        data = newsapi.get_everything(q=q, language='en', sort_by='publishedAt', page_size=40)
        clanky = [{"zdroj": c['source']['name'], "titulek": c['title'], "link": c['url']} for c in data.get('articles', [])]
    except: clanky = []
    
    rss_vysledky = []
    for url in ["https://tass.com/rss/v2.xml", "https://www.rt.com/rss/news/", "https://www.aljazeera.com/xml/rss/all.xml"]:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:5]: rss_vysledky.append({"zdroj": "RSS", "titulek": e.title, "link": e.link})
        except: continue
    
    vse = clanky + rss_vysledky
    text_ai = "".join([f"ID:{i} [{c['zdroj']}]: {c['titulek']}\n" for i, c in enumerate(vse)])
    return vse, text_ai

def text_na_audio(text):
    try:
        tts = gTTS(text=text, lang='cs')
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode()
        return f'<audio controls style="width: 100%; height: 35px;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except: return "Audio nelze vygenerovat."

# --- 4. HLAVNÍ LOGIKA S OPRAVOU JSON ---
st.sidebar.title("💎 WorldMirror Matrix")
reg = st.sidebar.multiselect("Regiony:", ["ČR", "Slovensko", "EU", "USA", "Rusko", "Asie", "Afrika"], default=["ČR", "EU"])
tem = st.sidebar.multiselect("Kategorie:", ["Válka", "Ekonomika", "Politika", "AI", "Akciové trhy", "Showbyznys"], default=["Válka", "Ekonomika"])

if st.session_state.view == 'map':
    st.title("🌍 WorldMirror: Globální Analytická Matice")
    
    if st.button("🚀 Spustit analýzu (Nová stabilní verze)"):
        with st.spinner("Provádím multipolární sken a opravuji narativy..."):
            model = genai.GenerativeModel('gemini-1.5-pro')
            clanky, text_ai = stahni_vsechna_data(reg, tem)
            
            # STRIKTNÍ PROMPT S PŘÍKLADEM
            prompt = f"""
            Jsi špičkový analytik. Vyber 10 témat. Odpověz VÝHRADNĚ jako čisté JSON pole.
            U kategorie 'Akciové trhy' uveď burzovní symboly ($AAPL, $NVDA atd.).
            
            FORMÁT:
            [
              {{
                "tema": "...", "kategorie": "...", "lat": 0.0, "lon": 0.0, "bleskovka": "...", "fakta": "...",
                "usa": "...", "eu": "...", "asie": "...", "vychod": "...", "jih": "...",
                "levice": "...", "pravice": "...", "bod_svaru": "...", "clanek": "Reportáž (max 200 slov)", "zdroje_id": []
              }}
            ]
            
            ZDROJE: {text_ai}
            """
            
            try:
                # Vynucení JSON módu
                res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                
                # Robustní parsování
                raw_text = res.text.strip()
                # Odstranění případných markdown značek, pokud by je AI přesto přidala
                if raw_text.startswith("```json"):
                    raw_text = re.sub(r'^```json\s*|\s*```$', '', raw_text, flags=re.MULTILINE)
                
                analyza_data = json.loads(raw_text)
                
                uloz_do_historie({"cas": datetime.now().strftime("%d.%m.%Y %H:%M"), "analyza_json": analyza_data, "zdroje": clanky})
                st.success("✅ Analýza úspěšně uložena.")
                st.rerun()
            
            except Exception as e:
                st.error("❌ Selhalo parsování JSONu.")
                with st.expander("Zobrazit syrová data od AI (proč to selhalo?)"):
                    st.write(f"Chyba: {e}")
                    st.code(res.text if 'res' in locals() else "Žádná odpověď")

    historie = nacti_historii()
    if historie:
        report = historie[0]
        seznam = report['analyza_json']
        
        m = folium.Map(location=[20, 10], zoom_start=2, tiles="CartoDB dark_matter")
        for i, t in enumerate(seznam):
            color = get_clean_color(t.get('kategorie'))
            folium.CircleMarker(
                location=[float(t['lat']), float(t['lon'])], radius=12,
                popup=t['tema'], tooltip=t['tema'],
                color=color, fill=True, fill_opacity=0.8
            ).add_to(m)
        
        map_res = st_folium(m, width="100%", height=450)
        
        # PROKLIK
        if map_res.get('last_object_clicked_popup'):
            pop = map_res['last_object_clicked_popup']
            for i, t_obj in enumerate(seznam):
                if t_obj['tema'] == pop:
                    st.session_state.selected_idx, st.session_state.view = i, 'detail'
                    st.rerun()

        # DLAŽDICE
        st.divider()
        for i in range(0, len(seznam), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(seznam):
                    t = seznam[idx]
                    c = get_clean_color(t.get('kategorie'))
                    with cols[j]:
                        st.markdown(f'<div style="border-left: 10px solid {c}; background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #111;"><h4>{idx+1}. {t["tema"]}</h4><p>{t["bleskovka"]}</p></div>', unsafe_allow_html=True)
                        if st.button(f"🔍 Rozbor {idx+1}", key=f"btn_{idx}"):
                            st.session_state.selected_idx, st.session_state.view = idx, 'detail'
                            st.rerun()

elif st.session_state.view == 'detail':
    hist = nacti_historii()
    if not hist: st.rerun()
    t = hist[0]['analyza_json'][st.session_state.selected_idx]
    
    st.button("⬅️ Zpět", on_click=lambda: setattr(st.session_state, 'view', 'map'))
    st.title(f"🔍 {t['tema']}")
    st.write(text_na_audio(t['fakta']), unsafe_allow_html=True)
    st.info(t['fakta'])
    
    # MATICE
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("🟦 **USA**"); st.caption(t.get('usa'))
    with c2: st.markdown("🇪🇺 **EU**"); st.caption(t.get('eu'))
    with c3: st.markdown("🟣 **Asie**"); st.caption(t.get('asie'))
    
    c4, c5 = st.columns(2)
    with c4: st.markdown("🟥 **Východ**"); st.caption(t.get('vychod'))
    with c5: st.markdown("🌏 **Jih**"); st.caption(t.get('jih'))
    
    st.divider()
    cl, cr = st.columns(2)
    with cl: st.success(f"🌿 **Liberal**\n\n{t.get('levice')}")
    with cr: st.error(f"🦅 **Conservative**\n\n{t.get('pravice')}")
    
    st.subheader("📝 Reportáž")
    st.write(text_na_audio(t['clanek']), unsafe_allow_html=True)
    st.markdown(f'<div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; border: 1px solid #ddd; font-family: Georgia, serif; line-height: 1.6;">{t["clanek"]}</div>', unsafe_allow_html=True)
    for aid in t.get('zdroje_id', []):
        if aid < len(historie[0]['zdroje']):
            art = historie[0]['zdroje'][aid]
            st.markdown(f"✅ **{art['zdroj']}**: [{art['titulek']}]({art['link']})")
