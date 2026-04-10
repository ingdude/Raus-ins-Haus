import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from geopy.geocoders import Nominatim

# --- CONFIG & LOGIN ---
st.set_page_config(page_title="Raus ins Haus", layout="wide")

# Sicherheit: Passwort aus dem Streamlit-Tresor
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

# LOGIN-MENÜ (Dropdown)
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

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name="Immobilien"):
    df = conn.read(worksheet=sheet_name, ttl=0)
    return df.fillna("")

def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- GEOCODING (Für die Karte) ---
@st.cache_data
def get_coords(address):
    try:
        # Suche auf Österreich einschränken für bessere Treffer
        geolocator = Nominatim(user_agent="raus_ins_haus_finder_v3")
        location = geolocator.geocode(f"{address}, Österreich")
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "🗺️ Kartenansicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender"])

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title("Raus ins Haus 🏠")
    st.caption(f"Eingeloggt als: {st.session_state.user_name}")
    
    df = load_data("Immobilien")
    
    if df is not None and not df.empty:
        # Score-Check und Sortierung
        if "Score" not in df.columns: df["Score"] = 3
        df["Score"] = pd.to_numeric(df["Score"], errors='coerce').fillna(3)
        df = df.sort_values(by="Score", ascending=False)

        kat = st.selectbox("Kategorie filtern", ["Alle", "Haus", "Grundstück"])
        display_df = df.copy()
        if kat != "Alle":
            display_df = display_df[display_df["Kategorie"] == kat]

        for index, row in display_df.iterrows():
            with st.container(border=True):
                # Die wichtige Spalten-Zuweisung
                col_img, col_txt = st.columns(2)
                
                with col_img:
                    bild_url = str(row.get("Bild-URL", ""))
                    if bild_url.startswith("http"):
                        st.image(bild_url, use_container_width=True)
                    else:
                        st.info("Kein Bild vorhanden")
                
                with col_txt:
                    st.subheader(row.get("Titel", "Objekt"))
                    
                    # Preis-Formatierung
                    p = float(row.get('Kaufpreis', 0) or 0)
                    preis_form = f"{int(p):,}".replace(",", ".") + " €"
                    
                    st.write(f"**Preis:** {preis_form} | **Lage:** {row.get('Lage', '')}")
                    st.write(f"**Entfernung Wien:** {row.get('Distanz_Wien', 0)} km")
                    st.write(f"**Wohnfläche:** {row.get('Wohnfläche', 0)} m² | **Grundfläche:** {row.get('Grundfläche', 0)} m²")
                    
                    # User-Fix
                    user_val = row.get("User", "")
                    st.caption(f"Hinzugefügt von: {user_val if user_val else 'Unbekannt'}")
                    
                    with st.expander("⭐ Bewertung & Details"):
                        new_score = st.slider("Präferenz (1-5)", 1, 5, int(row["Score"]), key=f"s_{index}")
                        new_comm = st.text_area("Kommentar", row.get("Kommentar", ""), key=f"c_{index}")
                        if st.button("Speichern", key=f"btn_{index}"):
                            df.at[index, "Score"] = new_score
                            df.at[index, "Kommentar"] = new_comm
                            save_data(df)
                            st.rerun()

                    with st.expander("✏️ Bearbeiten / Löschen"):
                        with st.form(f"edit_{index}"):
                            e_titel = st.text_input("Titel", row["Titel"])
                            e_preis = st.number_input("Preis (€)", value=p)
                            if st.form_submit_button("Änderungen speichern"):
                                df.at[index, "Titel"] = e_titel
                                df.at[index, "Kaufpreis"] = e_preis
                                save_data(df)
                                st.rerun()
                        if st.button("🗑️ Objekt löschen", key=f"del_{index}"):
                            save_data(df.drop(index))
                            st.rerun()
                    
                    if str(row.get("URL", "")).startswith("http"):
                        st.link_button("🔗 Zur Anzeige", row["URL"])
    else:
        st.info("Noch keine Objekte vorhanden.")

# --- 🗺️ KARTENANSICHT (EINFACH) ---
elif menu == "🗺️ Kartenansicht":
    st.title("Wo liegen die Objekte? 🗺️")
    df = load_data("Immobilien")
    
    if not df.empty:
        map_points = []
        with st.spinner("Lade Standorte..."):
            for idx, row in df.iterrows():
                address = row.get("Lage", "")
                if address:
                    lat, lon = get_coords(address)
                    if lat and lon:
                        map_points.append({"lat": lat, "lon": lon, "Titel": row["Titel"]})
        
        if map_points:
            st.map(pd.DataFrame(map_points))
            st.write("### Liste der Standorte")
            st.dataframe(pd.DataFrame(map_points)[["Titel", "lat", "lon"]], use_container_width=True)
        else:
            st.warning("Keine gültigen Standorte in der Spalte 'Lage' gefunden.")

# --- ➕ OBJEKT HINZUFÜGEN ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt erfassen")
    df = load_data("Immobilien")
    with st.form("add_form", clear_on_submit=True):
        titel = st.text_input("Titel")
        url = st.text_input("Link")
        bild = st.text_input("Bild-URL")
        kat = st.selectbox("Typ", ["Haus", "Grundstück"])
        preis = st.number_input("Preis (€)", step=1000)
        w_f = st.number_input("Wohnfläche", step=1)
        g_f = st.number_input("Grundfläche", step=10)
        ort = st.text_input("Lage (Ort oder PLZ)")
        km = st.number_input("Km nach Wien", step=1)
        
        if st.form_submit_button("Speichern"):
            new_row = pd.DataFrame([{
                "Titel": titel, "URL": url, "Bild-URL": bild, "Kategorie": kat,
                "Kaufpreis": preis, "Wohnfläche": w_f, "Grundfläche": g_f,
                "Lage": ort, "Distanz_Wien": km, "User": st.session_state.user_name,
                "Score": 3, "Kommentar": ""
            }])
            save_data(pd.concat([df, new_row], ignore_index=True))
            st.success("Erfolgreich hinzugefügt!")

# --- 📅 KALENDER ---
elif menu == "📅 Besichtigungs-Kalender":
    st.title("Besichtigungs-Planer")
    df_cal = load_data("Kalender")
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
