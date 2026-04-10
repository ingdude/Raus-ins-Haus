import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium

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
    df = conn.read(worksheet=sheet_name, ttl=0)
    return df.fillna("")

def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- GEOCODING (Für die Karten-Punkte) ---
@st.cache_data
def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="raus_ins_haus_finder_v8")
        location = geolocator.geocode(f"{address}, Österreich")
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

# --- DYNAMISCHE USER-LISTE LADEN ---
try:
    user_df = load_data("User")
    if not user_df.empty and "Name" in user_df.columns:
        user_liste = sorted(user_df["Name"].replace("", pd.NA).dropna().unique().tolist())
    else:
        user_liste = ["Anja", "Jan", "Katja", "Laurenz", "Timo"]
except:
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
        # Durchschnitts-Berechnung
        score_cols = [col for col in df.columns if col.startswith("Score_")]
        if score_cols:
            df[score_cols] = df[score_cols].replace("", pd.NA).apply(pd.to_numeric, errors='coerce')
            df["Durchschnitt"] = df[score_cols].mean(axis=1).fillna(0)
        else:
            df["Durchschnitt"] = 0

        # LAYOUT-ANPASSUNG: Dropdowns nebeneinander
        col_filter, col_sort = st.columns(2)
        
        with col_filter:
            kat = st.selectbox("Kategorie filtern:", ["Alle", "Haus", "Grundstück"])
            
        with col_sort:
            sort_wahl = st.selectbox(
                "Liste sortieren nach:", 
                ["🔥 Beste Bewertung", "💰 Günstigster Preis", "🚗 Kürzeste Fahrt nach Wien"]
            )
        
        st.divider()
        
        # Sortierungs-Logik
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
                # TITLE ROW MIT 3-PUNKTE MENÜ
                c_title, c_menu = st.columns([0.9, 0.1])
                with c_title:
                    st.markdown(f"### #{i+1} | {row.get('Titel', 'Objekt')}")
                with c_menu:
                    with st.popover("⋮"):
                        st.markdown("**✏️ Bearbeiten / Löschen**")
                        with st.form(f"edit_{real_index}"):
                            e_titel = st.text_input("Titel", row.get("Titel", ""))
                            p_val = float(row.get('Kaufpreis', 0) or 0)
                            e_preis = st.number_input("Preis (€)", value=p_val)
                            e_w_f = st.number_input("Wohnfläche", value=float(row.get("Wohnfläche", 0) or 0))
                            e_g_f = st.number_input("Grundfläche", value=float(row.get("Grundfläche", 0) or 0))
                            e_km = st.number_input("Km nach Wien", value=float(row.get("Distanz_Wien", 0) or 0))
                            e_url = st.text_input("Anzeigen-Link", row.get("URL", ""))
                            e_bild = st.text_input("Bild-URL", row.get("Bild-URL", ""))
                            
                            if st.form_submit_button("Änderungen speichern"):
                                df.at[real_index, "Titel"] = e_titel
                                df.at[real_index, "Kaufpreis"] = e_preis
                                df.at[real_index, "Wohnfläche"] = e_w_f
                                df.at[real_index, "Grundfläche"] = e_g_f
                                df.at[real_index, "Distanz_Wien"] = e_km
                                df.at[real_index, "URL"] = e_url
                                df.at[real_index, "Bild-URL"] = e_bild
                                save_data(df)
                                st.rerun()
                                
                        if st.button("🗑️ Objekt löschen", key=f"del_{real_index}"):
                            save_data(df.drop(real_index))
                            st.rerun()

                # CONTENT ROW (Bild links, Text rechts) - Sichere Spaltenzuweisung
                col_img, col_txt = st.columns(2)
                with col_img:
                    bild_url = str(row.get("Bild-URL", ""))
                    if bild_url.startswith("http"):
                        st.image(bild_url, use_container_width=True)
                    else:
                        st.info("Kein Bild")
                with col_txt:
                    p = float(row.get('Kaufpreis', 0) or 0)
                    preis_form = f"{int(p):,}".replace(",", ".") + " €"
                    
                    st.write(f"**Preis:** {preis_form} | **Lage:** {row.get('Lage', '')}")
                    st.write(f"**Fahrstrecke Wien:** {row.get('Distanz_Wien', 0)} km")
                    st.write(f"**Wohnfläche:** {row.get('Wohnfläche', 0)} m² | **Grundfläche:** {row.get('Grundfläche', 0)} m²")
                    
                    ds = row.get("Durchschnitt", 0)
                    if ds > 0:
                        st.markdown(f"### 🔥 Ø Bewertung: {round(ds, 1)} / 5")
                    else:
                        st.markdown("### ⚪ Noch keine Bewertungen")
                        
                    st.caption(f"Hinzugefügt von: {row.get('User', 'Unbekannt')}")
                    if str(row.get("URL", "")).startswith("http"):
                        st.link_button("🔗 Anzeige öffnen", row["URL"])
                        
                    st.divider()
                    
                    # KOMMENTARE OFFEN ANZEIGEN
                    st.markdown("##### 💬 Feedback der Gruppe")
                    comm_cols = [col for col in df.columns if col.startswith("Kommentar_")]
                    hat_kommentare = False
                    
                    for c_col in comm_cols:
                        txt = str(row.get(c_col, "")).strip()
                        if txt and txt != "nan":
                            user_wer = c_col.replace('Kommentar_', '')
                            st.markdown(f"""
                            <div style='background-color: rgba(128,128,128,0.1); padding: 8px; border-radius: 5px; margin-bottom: 5px; font-size: 0.85em;'>
                                <strong>{user_wer}:</strong> {txt}
                            </div>
                            """, unsafe_allow_html=True)
                            hat_kommentare = True
                            
                    if not hat_kommentare:
                        st.markdown("<div style='font-size: 0.85em; font-style: italic; margin-bottom: 10px;'>Noch keine Kommentare vorhanden.</div>", unsafe_allow_html=True)
                    
                    # EIGENE BEWERTUNG KOMPAKT
                    mein_score_col = f"Score_{st.session_state.user_name}"
                    mein_comm_col = f"Kommentar_{st.session_state.user_name}"
                    
                    raw_score = row.get(mein_score_col, 3)
                    safe_score = 3 if pd.isna(raw_score) or raw_score == "" else int(float(raw_score))
                        
                    c_slide, c_text = st.columns()
                    with c_slide:
                        new_score = st.slider(f"Deine Note", 1, 5, safe_score, key=f"s_{real_index}")
                        if st.button("Speichern", key=f"btn_{real_index}", use_container_width=True):
                            df.at[real_index, mein_score_col] = st.session_state[f"s_{real_index}"]
                            df.at[real_index, mein_comm_col] = st.session_state[f"c_{real_index}"]
                            save_data(df)
                            st.rerun()
                    with c_text:
                        st.text_area("Dein Kommentar", str(row.get(mein_comm_col, "")).replace("nan", ""), key=f"c_{real_index}", height=100)

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
        with st.spinner("Lade Standorte..."):
            for i, row in df.iterrows():
                address = row.get("Lage", "")
                if address:
                    lat, lon = get_coords(address)
                    if lat and lon:
                        map_points.append({
                            "lat": lat, 
                            "lon": lon, 
                            "Titel": f"#{i+1}: {row.get('Titel', 'Objekt')}"
                        })
        
        if map_points:
            avg_lat = sum(p["lat"] for p in map_points) / len(map_points)
            avg_lon = sum(p["lon"] for p in map_points) / len(map_points)
            
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=9)
            
            # STABILE LÖSUNG: CircleMarker statt Image-Marker
            for p in map_points:
                folium.CircleMarker(
                    location=[p["lat"], p["lon"]],
                    radius=10, # Größe des Kreises
                    color="#1f77b4", # Randfarbe
                    fill=True,
                    fill_color="#1f77b4", # Füllfarbe
                    fill_opacity=0.8, # Leicht transparent
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
        kat = st.selectbox("Typ", ["Haus", "Grundstück"])
        preis = st.number_input("Preis (€)", step=1000)
        w_f = st.number_input("Wohnfläche (m²)", step=1)
        g_f = st.number_input("Grundfläche (m²)", step=10)
        ort = st.text_input("Ort / PLZ")
        km = st.number_input("Fahrstrecke nach Wien (km)", step=1)
        
        if st.form_submit_button("Objekt speichern"):
            new_row = pd.DataFrame([{
                "Titel": titel, "URL": url, "Bild-URL": bild, "Kategorie": kat,
                "Kaufpreis": preis, "Wohnfläche": w_f, "Grundfläche": g_f,
                "Lage": ort, "Distanz_Wien": km, "User": st.session_state.user_name
            }])
            save_data(pd.concat([df, new_row], ignore_index=True))
            st.success("Erfolgreich hinzugefügt!")

# --- 📅 KALENDER ---
elif menu == "📅 Besichtigungs-Kalender":
    st.title("Besichtigungs-Planer")
    try:
        df_cal = load_data("Kalender")
    except:
        df_cal = pd.DataFrame([{"Datum / Tag": "Samstag Vormittag", "Wer kann?": "", "Anmerkung": ""}])
        
    edited_df = st.data_editor(df_cal, num_rows="dynamic", use_container_width=True)
    
    if st.button("Kalender speichern"):
        save_data(edited_df, sheet_name="Kalender")
        st.success("Gespeichert!")
        st.rerun()

    st.divider()
    st.subheader("🔥 Top Termine (>= 2 Personen)")
    for idx, row in edited_df.iterrows():
        namen = [n.strip() for n in str(row.get("Wer kann?", "")).split(",") if n.strip()]
        if len(namen) >= 2:
            st.success(f"✅ **{row.get('Datum / Tag', 'Unbekannt')}**: {', '.join(namen)}")

# --- ⚙️ ADMIN (USER-VERWALTUNG) ---
elif menu == "
