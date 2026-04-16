import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
import json
from datetime import datetime

# --- CONFIG & LOGIN ---
st.set_page_config(page_title="Raus ins Haus", layout="wide")

try:
    PASSWORD = st.secrets["APP_PASSWORD"]
except KeyError:
    st.error("Fehler: Bitte lege 'APP_PASSWORD' in den Streamlit-Secrets an!")
    st.stop()

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        pwd = st.text_input("Passwort eingeben", type="password")
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            if pwd: st.error("Falsches Passwort")
            st.stop()

check_password()

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name="Immobilien"):
    try:
        df = conn.read(worksheet=sheet_name, ttl=600)
        df = df.fillna("")
        
        # Hilfsfunktion für Booleans (Archiviert & Privat)
        def is_true_val(v):
            if isinstance(v, bool): return v
            if isinstance(v, str): return v.lower().strip() in ['true', '1', 'yes', 'wahr', 't', 'y', 'ja', 'j']
            try: return float(v) > 0
            except: return False

        if sheet_name == "Immobilien":
            if "Archiviert" not in df.columns: df["Archiviert"] = False
            else: df["Archiviert"] = df["Archiviert"].apply(is_true_val)
            
            if "Privat" not in df.columns: df["Privat"] = False
            else: df["Privat"] = df["Privat"].apply(is_true_val)
            
        return df
    except Exception as e:
        st.error(f"Datenbank-Fehler: {e}")
        return pd.DataFrame()

def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- GEOCODING ---
@st.cache_data
def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="raus_ins_haus_finder_v9")
        location = geolocator.geocode(f"{address}, Österreich")
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        st.warning(f"Geocoding-Warnung für '{address}': API überlastet oder Ort nicht gefunden.")
        return None, None
    return None, None

# --- DYNAMISCHE USER-LISTE LADEN ---
try:
    user_df = load_data("User")
    if not user_df.empty and "Name" in user_df.columns:
        user_liste = sorted(user_df["Name"].replace("", pd.NA).dropna().unique().tolist())
    else:
        user_liste = ["Anja", "Jan", "Katja", "Laurenz", "Timo"]
except Exception as e:
    user_liste = ["Anja", "Jan", "Katja", "Laurenz", "Timo"]

if "user_name" not in st.session_state:
    st.write("### Wer bist du?")
    with st.form("login_form"):
        u_name = st.selectbox("Bitte wähle deinen Namen:", user_liste)
        submitted = st.form_submit_button("Einloggen")
        if submitted:
            st.session_state.user_name = u_name
            st.rerun()
    st.stop()

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "🗺️ Kartenansicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender", "🔗 Link-Sammlung", "🗃️ Archiv", "⚙️ Admin (User)"])

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title("Raus ins Haus 🏠")
    st.caption(f"Eingeloggt als: {st.session_state.user_name}")
    
    df = load_data("Immobilien")
    
    if not df.empty:
        # Score-Durchschnitt berechnen
        score_cols = [col for col in df.columns if col.startswith("Score_")]
        if score_cols:
            df[score_cols] = df[score_cols].replace("", pd.NA).apply(pd.to_numeric, errors='coerce')
            df["Durchschnitt"] = df[score_cols].mean(axis=1).fillna(0)
        else:
            df["Durchschnitt"] = 0

        col_filter, col_sort = st.columns(2)
        with col_filter:
            kat = st.selectbox("Kategorie filtern:", ["Alle", "Haus", "Grundstück", "🕵️ Private Schätze"])
            
        with col_sort:
            sort_wahl = st.selectbox("Sortieren nach:", ["🔥 Beste Bewertung", "💰 Günstigster Preis", "🚗 Kürzeste Fahrt nach Wien"])
        
        st.divider()

        # Sortierung anwenden
        if sort_wahl == "🔥 Beste Bewertung":
            df = df.sort_values(by="Durchschnitt", ascending=False)
        elif sort_wahl == "💰 Günstigster Preis":
            df["Kaufpreis"] = pd.to_numeric(df["Kaufpreis"], errors='coerce').fillna(999999999)
            df = df.sort_values(by="Kaufpreis", ascending=True)
        elif sort_wahl == "🚗 Kürzeste Fahrt nach Wien":
            df["Distanz_Wien"] = pd.to_numeric(df["Distanz_Wien"], errors='coerce').fillna(999)
            df = df.sort_values(by="Distanz_Wien", ascending=True)

        # Logik für Sichtbarkeit & Filter
        # 1. Andere private Objekte immer rausfiltern
        display_df = df[ (df["Privat"] == False) | (df["User"] == st.session_state.user_name) ]
        # 2. Archivierte raus
        display_df = display_df[display_df["Archiviert"] != True]
        
        # 3. Kategorie-Filter anwenden
        if kat == "🕵️ Private Schätze":
            display_df = display_df[display_df["Privat"] == True]
        elif kat != "Alle":
            display_df = display_df[(display_df["Kategorie"] == kat) & (display_df["Privat"] == False)]

        display_df = display_df.reset_index(drop=False)

        for i, row in display_df.iterrows():
            real_index = row['index'] 
            with st.container(border=True):
                c_title_score, c_menu = st.columns([0.95, 0.05], vertical_alignment="center")
                with c_title_score:
                    ds = row.get("Durchschnitt", 0)
                    score_str = f"&nbsp;&nbsp;&nbsp; <span style='color: #ffaa00;'>🔥 {round(ds, 1)}</span>" if ds > 0 else "&nbsp;&nbsp;&nbsp; ⚪ -"
                    privat_tag = " <span style='color: #ff4b4b;'>(PRIVAT)</span>" if row.get("Privat", False) else ""
                    st.markdown(f"### #{i+1} | {row.get('Titel', 'Objekt')}{privat_tag} {score_str}", unsafe_allow_html=True)
                        
                with c_menu:
                    with st.popover("⋮"):
                        with st.form(f"edit_{real_index}"):
                            e_titel = st.text_input("Titel", row.get("Titel", ""))
                            e_privat = st.checkbox("Privat (nur für mich sichtbar)", value=row.get("Privat", False))
                            e_lage = st.text_input("Lage", row.get("Lage", ""))
                            e_preis = st.number_input("Preis (€)", value=float(row.get('Kaufpreis', 0) or 0))
                            e_w_f = st.number_input("Wohnfläche", value=float(row.get("Wohnfläche", 0) or 0))
                            e_g_f = st.number_input("Grundfläche", value=float(row.get("Grundfläche", 0) or 0))
                            e_km = st.number_input("Km nach Wien", value=float(row.get("Distanz_Wien", 0) or 0))
                            e_url = st.text_input("Anzeigen-Link", row.get("URL", ""))
                            e_bild = st.text_input("Bild-URL", row.get("Bild-URL", ""))
                            e_drive = st.text_input("Drive Link", row.get("Drive-Link", ""))
                            e_maps = st.text_input("Maps Link", row.get("Maps-Link", ""))
                            
                            if st.form_submit_button("Änderungen speichern"):
                                df.at[real_index, "Titel"] = e_titel
                                df.at[real_index, "Privat"] = e_privat
                                df.at[real_index, "Kaufpreis"] = e_preis
                                df.at[real_index, "Lage"] = e_lage
                                df.at[real_index, "Wohnfläche"] = e_w_f
                                df.at[real_index, "Grundfläche"] = e_g_f
                                df.at[real_index, "Distanz_Wien"] = e_km
                                df.at[real_index, "URL"] = e_url
                                df.at[real_index, "Bild-URL"] = e_bild
                                df.at[real_index, "Drive-Link"] = e_drive
                                df.at[real_index, "Maps-Link"] = e_maps
                                save_data(df); st.rerun()
                                
                        if st.button("🗄️ Objekt archivieren", key=f"arch_{real_index}"):
                            df.at[real_index, "Archiviert"] = True
                            save_data(df); st.rerun()
                        if st.button("🗑️ Objekt löschen", key=f"del_{real_index}"):
                            save_data(df.drop(real_index)); st.rerun()

                col_img, col_txt = st.columns(2)
                with col_img:
                    bild_url = str(row.get("Bild-URL", ""))
                    if bild_url.startswith("http"): st.image(bild_url, use_container_width=True)
                    else: st.info("Kein Bild")
                with col_txt:
                    p = float(row.get('Kaufpreis', 0) or 0)
                    st.markdown(f"<p style='font-size: 1.1em;'><b>Preis:</b> {int(p):,} € | <b>Lage:</b> {row.get('Lage', '')}</p>".replace(",", "."), unsafe_allow_html=True)
                    st.markdown(f"**Wohnfläche:** {row.get('Wohnfläche', 0)} m² | **Grundfläche:** {row.get('Grundfläche', 0)} m²")
                    
                    # User & Datum Info
                    user = row.get('User', 'Unbekannt')
                    zeit = row.get('Zeitpunkt', '')
                    info_text = f"Hinzugefügt von: {user}"
                    if zeit: info_text += f" am: {zeit}"
                    st.markdown(f"<p style='color: gray; font-size: 0.85em; margin-top: 1em;'>{info_text}</p>", unsafe_allow_html=True)
                    
                    st.divider()

                    # Buttons
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: 
                        if str(row.get("URL", "")).startswith("http"): st.link_button("🔗 Anzeige", row["URL"], use_container_width=True)
                    with c2:
                        mein_score_col = f"Score_{st.session_state.user_name}"
                        with st.popover("⭐️ Bewerten", use_container_width=True):
                            new_score = st.selectbox("Note", options=[1, 2, 3, 4, 5], index=2, key=f"s_{real_index}")
                            if st.button("Speichern", key=f"b_s_{real_index}"):
                                df.at[real_index, mein_score_col] = new_score
                                save_data(df); st.rerun()
                    with c3:
                        if str(row.get("Drive-Link", "")).startswith("http"): st.link_button("📂 Drive", row["Drive-Link"], use_container_width=True)
                    with c4:
                        if str(row.get("Maps-Link", "")).startswith("http"): st.link_button("🗺️ Maps", row["Maps-Link"], use_container_width=True)

                    st.divider()
                    st.markdown("##### 💬 Haus-Chat")
                    chat_raw = str(row.get("Chat_Historie", "[]"))
                    chat_history = json.loads(chat_raw) if chat_raw.startswith("[") else []
                    with st.container(height=180):
                        if not chat_history: st.info("Noch keine Nachrichten.")
                        for msg in chat_history:
                            with st.chat_message(msg["user"]):
                                st.write(f"**{msg['user']}** ({msg['time']}): {msg['text']}")
                    
                    c_msg, c_send = st.columns([0.8, 0.2])
                    new_msg = c_msg.text_input("Nachricht...", key=f"chat_in_{real_index}", label_visibility="collapsed")
                    if c_send.button("Senden", key=f"chat_btn_{real_index}") and new_msg:
                        chat_history.append({"user": st.session_state.user_name, "time": datetime.now().strftime("%d.%m. %H:%M"), "text": new_msg})
                        df.at[real_index, "Chat_Historie"] = json.dumps(chat_history)
                        save_data(df); st.rerun()

# --- ➕ OBJEKT HINZUFÜGEN ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt erfassen")
    df = load_data("Immobilien")
    with st.form("add_form", clear_on_submit=True):
        titel = st.text_input("Titel (z.B. Haus am See)")
        is_privat = st.checkbox("Privat (nur für mich sichtbar)")
        url = st.text_input("Anzeigen-Link (URL)")
        bild = st.text_input("Bild-URL")
        kat = st.selectbox("Typ", ["Haus", "Grundstück"])
        preis = st.number_input("Preis (€)", step=1000)
        ort = st.text_input("Ort / PLZ")
        w_f = st.number_input("Wohnfläche (m²)")
        g_f = st.number_input("Grundfläche (m²)")
        km = st.number_input("Km nach Wien")
        
        if st.form_submit_button("Objekt speichern"):
            lat, lon = get_coords(ort)
            new_row = pd.DataFrame([{
                "Titel": titel, "URL": url, "Bild-URL": bild, "Kategorie": kat, "Kaufpreis": preis, "Lage": ort, 
                "Wohnfläche": w_f, "Grundfläche": g_f, "Distanz_Wien": km, "User": st.session_state.user_name,
                "Zeitpunkt": datetime.now().strftime("%d.%m.%y"), "Privat": is_privat,
                "lat": lat if lat else "", "lon": lon if lon else "", "Chat_Historie": "[]", "Archiviert": False
            }])
            save_data(pd.concat([df, new_row], ignore_index=True))
            st.success("Erfolgreich hinzugefügt!"); st.rerun()

# --- 🗺️ KARTENANSICHT ---
elif menu == "🗺️ Kartenansicht":
    st.title("Wo liegen die Objekte? 🗺️")
    df = load_data("Immobilien")
    # Nur öffentliche oder eigene private auf Karte zeigen
    df = df[(df["Archiviert"] != True) & ((df["Privat"] == False) | (df["User"] == st.session_state.user_name))]
    if not df.empty:
        m = folium.Map(location=[48.2, 16.37], zoom_start=9)
        for _, r in df.iterrows():
            if r["lat"] and r["lon"]:
                color = "red" if r["Privat"] else "blue"
                folium.CircleMarker([r["lat"], r["lon"]], radius=10, color=color, fill=True, tooltip=r["Titel"]).add_to(m)
        st_folium(m, width=800, height=500)
    else:
        st.info("Keine Objekte für die Karte vorhanden.")

# --- 🔗 LINK-SAMMLUNG ---
elif menu == "🔗 Link-Sammlung":
    st.title("Link-Sammlung 🔗")
    try: df_links = load_data("Links")
    except: df_links = pd.DataFrame(columns=["URL", "Beschreibung"])
    
    if not df_links.empty:
        for i, row in df_links.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([0.85, 0.15])
                c1.markdown(f"[{row['URL']}]({row['URL']}) | <span style='color:gray;'>{row['Beschreibung']}</span>", unsafe_allow_html=True)
                if c2.button("🗑️", key=f"dl_{i}"):
                    save_data(df_links.drop(i), "Links"); st.rerun()
    
    with st.form("new_link"):
        new_u = st.text_input("URL")
        new_b = st.text_input("Beschreibung")
        if st.form_submit_button("Hinzufügen") and new_u:
            new_l = pd.DataFrame([{"URL": new_u, "Beschreibung": new_b}])
            save_data(pd.concat([df_links, new_l]), "Links"); st.rerun()

# --- 🗃️ ARCHIV ---
elif menu == "🗃️ Archiv":
    st.title("Archivierte Objekte 🗃️")
    df = load_data("Immobilien")
    arch = df[(df["Archiviert"] == True) & ((df["Privat"] == False) | (df["User"] == st.session_state.user_name))]
    if arch.empty: st.info("Das Archiv ist leer.")
    for i, row in arch.iterrows():
        with st.container(border=True):
            st.write(f"### {row['Titel']}")
            if st.button("↩️ Wiederherstellen", key=f"res_{i}"):
                df.at[i, "Archiviert"] = False
                save_data(df); st.rerun()

# --- ⚙️ ADMIN ---
elif menu == "⚙️ Admin (User)":
    st.title("User verwalten")
    u_df = load_data("User")
    edited = st.data_editor(u_df, num_rows="dynamic", use_container_width=True)
    if st.button("Speichern"): save_data(edited, "User"); st.success("Gespeichert!")
