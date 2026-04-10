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
        geolocator = Nominatim(user_agent="raus_ins_haus_finder_v7")
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
                    # Das neue Popover 3-Punkte Menü
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
                            e
