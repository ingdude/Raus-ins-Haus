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
        return df.fillna("")
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
    st.warning("Konnte User nicht laden. Nutze Standardliste.")
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
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "🗺️ Kartenansicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender", "⚙️ Admin (User)"])

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title("Raus ins Haus 🏠")
    st.caption(f"Eingeloggt als: {st.session_state.user_name}")
    
    df = load_data("Immobilien")
    
    if df is not None and not df.empty:
        if "Chat_Historie" not in df.columns:
            df["Chat_Historie"] = "[]"

        score_cols = [col for col in df.columns if col.startswith("Score_")]
        if score_cols:
            df[score_cols] = df[score_cols].replace("", pd.NA).apply(pd.to_numeric, errors='coerce')
            df["Durchschnitt"] = df[score_cols].mean(axis=1).fillna(0)
        else:
            df["Durchschnitt"] = 0

        col_filter, col_sort = st.columns(2)
        
        with col_filter:
            kat = st.selectbox("Kategorie filtern:", ["Alle", "Haus", "Grundstück"])
            
        with col_sort:
            sort_wahl = st.selectbox(
                "Liste sortieren nach:", 
                ["🔥 Beste Bewertung", "💰 Günstigster Preis", "🚗 Kürzeste Fahrt nach Wien"]
            )
        
        st.divider()
        
        if sort_wahl == "🔥 Beste Bewertung":
            df = df.sort_values(by="Durchschnitt", ascending=False)
        elif sort_wahl == "💰 Günstigster Preis":
            df["Kaufpreis"] = pd.to_numeric(df["Kaufpreis"], errors='coerce').fillna(999999999)
            df = df.sort_values(by="Kaufpreis", ascending=True)
            df["Kaufpreis"] = df["Kaufpreis"].replace(999999999, 0)
        elif sort_wahl == "🚗 Kürzeste Fahrt nach Wien":
            df["Distanz_Wien"] = pd.to_numeric(df["Distanz_Wien"], errors='coerce').fillna(999)
            df = df.sort_values(by="Distanz_Wien", ascending=True)

        display_df = df.copy()
        if kat != "Alle":
            display_df = display_df[display_df["Kategorie"] == kat]

        display_df = display_df.reset_index(drop=False)

        for i, row in display_df.iterrows():
            real_index = row['index'] 
            
            with st.container(border=True):
                # Titel breit, Score und Menü ganz rechts
                # vertical_alignment="center" sorgt für die mittige Höhe
                c_title, c_score, c_menu = st.columns([0.75, 0.20, 0.05], vertical_alignment="center")
                
                with c_title:
                    st.markdown(f"### #{i+1} | {row.get('Titel', 'Objekt')}")
                    
                with c_score:
                    ds = row.get("Durchschnitt", 0)
                    # Mit HTML machen wir die Schrift größer (h2) und schieben sie an den rechten Rand
                    if ds > 0:
                        st.markdown(f"<h2 style='text-align: right; margin: 0;'>🔥 {round(ds, 1)}</h2>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h2 style='text-align: right; margin: 0;'>⚪ -</h2>", unsafe_allow_html=True)
                        
                with c_menu:
                    with st.popover("⋮"):
                        st.markdown("**✏️ Bearbeiten / Löschen**")
                        with st.form(f"edit_{real_index}"):
                            e_titel = st.text_input("Titel", row.get("Titel", ""))
                            e_lage = st.text_input("Lage (Ort / PLZ)", row.get("Lage", ""))
                            p_val = float(row.get('Kaufpreis', 0) or 0)
                            e_preis = st.number_input("Preis (€)", value=p_val)
                            e_w_f = st.number_input("Wohnfläche", value=float(row.get("Wohnfläche", 0) or 0))
                            e_g_f = st.number_input("Grundfläche", value=float(row.get("Grundfläche", 0) or 0))
                            e_km = st.number_input("Km nach Wien", value=float(row.get("Distanz_Wien", 0) or 0))
                            e_url = st.text_input("Anzeigen-Link", row.get("URL", ""))
                            e_bild = st.text_input("Bild-URL", row.get("Bild-URL", ""))
                            e_drive = st.text_input("Google Drive Ordner Link", row.get("Drive-Link", ""))
                            
                            if st.form_submit_button("Änderungen speichern"):
                                df.at[real_index, "Titel"] = e_titel
                                df.at[real_index, "Kaufpreis"] = e_preis
                                df.at[real_index, "Wohnfläche"] = e_w_f
                                df.at[real_index, "Grundfläche"] = e_g_f
                                df.at[real_index, "Distanz_Wien"] = e_km
                                df.at[real_index, "URL"] = e_url
                                df.at[real_index, "Bild-URL"] = e_bild
                                df.at[real_index, "Drive-Link"] = e_drive
                                
                                alte_lage = str(row.get("Lage", ""))
                                if e_lage != alte_lage:
                                    neu_lat, neu_lon = get_coords(e_lage)
                                    df.at[real_index, "lat"] = neu_lat if neu_lat else ""
                                    df.at[real_index, "lon"] = neu_lon if neu_lon else ""
                                    df.at[real_index, "Lage"] = e_lage
                                
                                save_data(df)
                                st.rerun()
                                
                        if st.button("🗑️ Objekt löschen", key=f"del_{real_index}"):
                            save_data(df.drop(real_index))
                            st.rerun()

                col_img, col_txt = st.columns(2)
                with col_img:
                    bild_url = str(row.get("Bild-URL", ""))
                    if bild_url.startswith("http"):
                        try:
                            st.image(bild_url, use_container_width=True)
                        except Exception:
                            st.error("Bild-Link defekt")
                    else:
                        st.info("Kein Bild")
                with col_txt:
                    p = float(row.get('Kaufpreis', 0) or 0)
                    preis_form = f"{int(p):,}".replace(",", ".") + " €"
                    
                    st.write(f"**Preis:** {preis_form} | **Lage:** {row.get('Lage', '')}")
                    st.write(f"**Fahrstrecke Wien:** {row.get('Distanz_Wien', 0)} km")
                    st.write(f"**Wohnfläche:** {row.get('Wohnfläche', 0)} m² | **Grundfläche:** {row.get('Grundfläche', 0)} m²")
                    st.caption(f"Hinzugefügt von: {row.get('User', 'Unbekannt')}")
                    
                    st.divider()

                    # Die 3er-Werkzeugleiste 
                    c_btn1, c_btn2, c_btn3 = st.columns(3)
                    
                    with c_btn1:
                        if str(row.get("URL", "")).startswith("http"):
                            st.link_button("🔗 Anzeige", row["URL"], use_container_width=True)
                            
                    with c_btn2:
                        mein_score_col = f"Score_{st.session_state.user_name}"
                        raw_score = row.get(mein_score_col, 3)
                        safe_score = 3 if pd.isna(raw_score) or raw_score == "" else int(float(raw_score))
                        
                        with st.popover("⭐️ Bewerten", use_container_width=True):
                            new_score = st.selectbox("Deine Note", options= [1, 2, 3, 4, 5], index=safe_score - 1, key=f"s_{real_index}")
                            if st.button("Speichern", key=f"btn_score_{real_index}", use_container_width=True):
                                df.at[real_index, mein_score_col] = new_score
                                save_data(df)
                                st.rerun()
                                
                    with c_btn3:
                        drive_url = str(row.get("Drive-Link", ""))
                        if drive_url.startswith("http"):
                            st.link_button("📂 Drive", drive_url, use_container_width=True)
                        
                    st.divider()
                    
                    # ---------------------------------------------------------
                    # GRUPPEN-CHAT
                    # ---------------------------------------------------------
                    st.markdown("##### 💬 Haus-Chat")
                    
                    chat_raw = str(row.get("Chat_Historie", "[]")).strip()
                    if not chat_raw.startswith("["): chat_raw = "[]"
                    
                    try:
                        chat_history = json.loads(chat_raw)
                    except:
                        chat_history = []

                    with st.container(height=250): 
                        if not chat_history:
                            st.info("Noch keine Nachrichten. Schreib als Erster!")
                        else:
                            for msg in chat_history:
                                with st.chat_message(msg["user"]):
                                    st.markdown(f"**{msg['user']}** <span style='font-size:0.7em; color:gray;'>({msg['time']})</span>", unsafe_allow_html=True)
                                    st.write(msg["text"])

                    c_msg, c_send = st.columns([0.8, 0.2])
                    with c_msg:
                        new_msg = st.text_input("Nachricht...", key=f"chat_in_{real_index}", label_visibility="collapsed", placeholder="Schreibe eine Nachricht...")
                    with c_send:
                        if st.button("Senden", key=f"chat_btn_{real_index}", use_container_width=True):
                            if new_msg.strip():
                                now_str = datetime.now().strftime("%d.%m. %H:%M")
                                chat_history.append({"user": st.session_state.user_name, "time": now_str, "text": new_msg.strip()})
                                df.at[real_index, "Chat_Historie"] = json.dumps(chat_history)
                                save_data(df)
                                st.rerun()

# --- 🗺️ KARTENANSICHT ---
elif menu == "🗺️ Kartenansicht":
    st.title("Wo liegen die Objekte? 🗺️")
    st.write("Fahre mit der Maus über einen blauen Kreis, um zu sehen, um welches Haus es sich handelt!")
    
    df = load_data("Immobilien")
    
    if not df.empty:
        s_cols = [col for col in df.columns if col.startswith("Score_")]
        if s_cols:
            df[s_cols] = df[s_cols].replace("", pd.NA).apply(pd.to_numeric, errors='coerce')
            df["Durchschnitt"] = df[s_cols].mean(axis=1).fillna(0)
        else:
            df["Durchschnitt"] = 0
            
        df = df.sort_values(by="Durchschnitt", ascending=False).reset_index(drop=True)

        map_points = []
        with st.spinner("Lade Karte..."):
            for i, row in df.iterrows():
                address = row.get("Lage", "")
                if address:
                    lat = row.get("lat", "")
                    lon = row.get("lon", "")
                    
                    if pd.isna(lat) or lat == "":
                        lat, lon = get_coords(address)
                        
                    if lat and lon:
                        map_points.append({
                            "lat": float(lat), 
                            "lon": float(lon), 
                            "Titel": f"#{i+1}: {row.get('Titel', 'Objekt')}"
                        })
        
        if map_points:
            avg_lat = sum(p["lat"] for p in map_points) / len(map_points)
            avg_lon = sum(p["lon"] for p in map_points) / len(map_points)
            
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=9)
            
            for p in map_points:
                folium.CircleMarker(
                    location=[p["lat"], p["lon"]],
                    radius=10, 
                    color="#1f77b4", 
                    fill=True,
                    fill_color="#1f77b4", 
                    fill_opacity=0.8, 
                    tooltip=p["Titel"],
                    popup=p["Titel"]
                ).add_to(m)
            
            st_folium(m, width=800, height=500, returned_objects=[])
            
            st.write("### Liste der Standorte auf der Karte")
            st.dataframe(pd.DataFrame(map_points)[["Titel", "lat", "lon"]], use_container_width=True)
        else:
            st.warning("Keine gültigen Standorte in der Spalte 'Lage' gefunden.")
    else:
        st.info("Noch keine Objekte vorhanden.")

# --- ➕ OBJEKT HINZUFÜGEN ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt erfassen")
    df = load_data("Immobilien")
    with st.form("add_form", clear_on_submit=True):
        titel = st.text_input("Titel (z.B. Haus am See)")
        url = st.text_input("Anzeigen-Link (URL)")
        bild = st.text_input("Bild-URL (Rechtsklick auf Bild -> Adresse kopieren)")
        drive = st.text_input("Google Drive Ordner Link (für eigene Fotos/PDFs)")
        kat = st.selectbox("Typ", ["Haus", "Grundstück"])
        preis = st.number_input("Preis (€)", step=1000)
        w_f = st.number_input("Wohnfläche (m²)", step=1)
        g_f = st.number_input("Grundfläche (m²)", step=10)
        ort = st.text_input("Ort / PLZ")
        km = st.number_input("Fahrstrecke nach Wien (km)", step=1)
        
        if st.form_submit_button("Objekt speichern"):
            with st.spinner("Ermittle Koordinaten für die Karte..."):
                lat, lon = get_coords(ort)
                
            new_row = pd.DataFrame([{
                "Titel": titel, "URL": url, "Bild-URL": bild, "Drive-Link": drive, "Kategorie": kat,
                "Kaufpreis": preis, "Wohnfläche": w_f, "Grundfläche": g_f,
                "Lage": ort, "Distanz_Wien": km, "User": st.session_state.user_name,
                "lat": lat if lat else "", 
                "lon": lon if lon else "",
                "Chat_Historie": "[]"
            }])
            save_data(pd.concat([df, new_row], ignore_index=True))
            st.success("Erfolgreich hinzugefügt!")

# --- 📅 NEUER DOODLE-STYLE KALENDER ---
elif menu == "📅 Besichtigungs-Kalender":
    st.title("Besichtigungs-Matrix (Doodle-Style)")
    st.write("Neue Terminvorschläge einfach in die erste Spalte tippen. Häkchen setzen, wo ihr Zeit habt!")
    
    try:
        df_cal = load_data("Kalender")
        if df_cal.empty:
            raise ValueError("Leere Tabelle")
    except Exception:
        init_data = {"Terminvorschlag": ["Samstag 10:00", "Sonntag 14:00"]}
        for user in user_liste:
            init_data[user] = [False, False]
        df_cal = pd.DataFrame(init_data)
        
    for user in user_liste:
        if user not in df_cal.columns:
            df_cal[user] = False
            
    for user in user_liste:
        df_cal[user] = df_cal[user].astype(bool)

    edited_df = st.data_editor(
        df_cal, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("Speichern & Auswerten", type="primary"):
        save_data(edited_df, sheet_name="Kalender")
        st.success("Kalender gespeichert!")
        st.rerun()

    st.divider()
    st.subheader("🔥 Top Termine")
    
    gute_termine = []
    for idx, row in edited_df.iterrows():
        zusagen = sum([1 for user in user_liste if row.get(user) == True])
        if zusagen >= 2:
            teilnehmer = [user for user in user_liste if row.get(user) == True]
            gute_termine.append({
                "termin": row.get('Terminvorschlag', 'Unbekannt'),
                "anzahl": zusagen,
                "wer": ', '.join(teilnehmer)
            })
            
    if gute_termine:
        gute_termine_sortiert = sorted(gute_termine, key=lambda x: x["anzahl"], reverse=True)
        for t in gute_termine_sortiert:
            st.success(f"✅ **{t['termin']}**: {t['anzahl']} Zusagen ({t['wer']})")
    else:
        st.info("Aktuell gibt es noch keine Termine mit mind. 2 Zusagen.")

# --- ⚙️ ADMIN (USER-VERWALTUNG) ---
elif menu == "⚙️ Admin (User)":
    st.title("User verwalten")
    st.write("Hier kannst du Namen hinzufügen oder entfernen, die im Login-Menü erscheinen.")
    
    try:
        current_user_df = load_data("User")
    except Exception:
        current_user_df = pd.DataFrame({"Name": ["Anja", "Jan", "Katja", "Laurenz", "Timo"]})
        
    edited_user_df = st.data_editor(current_user_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("User-Liste speichern"):
        save_data(edited_user_df, sheet_name="User")
        st.success("Die User-Liste wurde aktualisiert!")
