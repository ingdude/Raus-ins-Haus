import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIG & LOGIN ---
st.set_page_config(page_title="Immo-Finder Gruppe", layout="wide")

PASSWORD = "dein_passwort_hier"  # ÄNDERE DAS HIER!

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

# User-Name Check
if "user_name" not in st.session_state:
    st.session_state.user_name = st.text_input("Wie heißt du?", key="name_input")
    if not st.session_state.user_name:
        st.stop()

# --- DATABASE CONNECTION ---
# Wir nutzen die offizielle Streamlit-Google-Sheets-Anbindung
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(worksheet="Immobilien", ttl="1m")

df = load_data()

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender"])

# --- HELPERS ---
def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title(f"Hallo {st.session_state.user_name}! 👋")
    
    # Filter
    kat = st.selectbox("Kategorie filtern", ["Alle", "Haus", "Grundstück"])
    display_df = df.copy()
    if kat != "Alle":
        display_df = display_df[display_df["Kategorie"] == kat]

    # Score-Berechnung & Sortierung (Beispiel-Logik)
    # Hier könnte man die Votes aus dem zweiten Tab einberechnen
    
    st.subheader("Aktuelle Objekte")
    
    # Grid Layout für Kacheln
    cols = st.columns(2)
    for index, row in display_df.iterrows():
        with cols[index % 2]:
            with st.container(border=True):
                if pd.notnull(row["Bild-URL"]):
                    st.image(row["Bild-URL"], use_container_width=True)
                st.markdown(f"### {row['Titel']}")
                st.markdown(f"**💰 Preis:** {row['Kaufpreis']} €")
                st.markdown(f"**📏 Fläche:** {row['Wohnfläche']} m² (Haus) / {row['Grundfläche']} m² (Grund)")
                st.markdown(f"**📍 Lage:** {row['Lage']} ({row['Distanz_Wien']} km nach Wien)")
                st.markdown(f"👤 Hinzugefügt von: {row['User']}")
                
                # Voting System
                vote = st.slider(f"Deine Bewertung für {row['Titel']}", 1, 5, 3, key=f"vote_{index}")
                if st.button(f"Vote speichern", key=f"btn_{index}"):
                    st.success("Gespeichert!")
                
                st.link_button("Anzeige öffnen", row["URL"])

# --- ➕ OBJEKT HINZUFÜGEN ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt erfassen")
    with st.form("add_form"):
        titel = st.text_input("Titel (z.B. Schönes Haus im Grünen)")
        url = st.text_input("Link zur Anzeige (Willhaben/ImmoScout)")
        bild_url = st.text_input("Link zum Vorschaubild (Rechtsklick auf Bild -> Bildadresse kopieren)")
        kat = st.selectbox("Kategorie", ["Haus", "Grundstück"])
        preis = st.number_input("Kaufpreis in €", step=1000)
        w_flaeche = st.number_input("Wohnfläche in m²", step=1)
        g_flaeche = st.number_input("Grundfläche in m²", step=10)
        lage = st.text_input("Ort / PLZ")
        distanz = st.number_input("Km bis Wien Stadtgrenze", step=1)
        
        submitted = st.form_submit_button("Objekt speichern")
        if submitted:
            new_data = pd.DataFrame([{
                "Titel": titel, "URL": url, "Bild-URL": bild_url, "Kategorie": kat,
                "Kaufpreis": preis, "Wohnfläche": w_flaeche, "Grundfläche": g_flaeche,
                "Lage": lage, "Distanz_Wien": distanz, "User": st.session_state.user_name
            }])
            updated_df = pd.concat([df, new_data], ignore_index=True)
            save_data(updated_df)
            st.success("Objekt wurde hinzugefügt!")

# --- 📅 KALENDER ---
elif menu == "📅 Besichtigungs-Kalender":
    st.title("Wann habt ihr Zeit für Besichtigungen?")
    st.info("Trage hier ein, wann du generell Zeit hättest.")
    
    # Hier würde eine Tabelle geladen, in der jeder User seine Namen-Zeile hat
    # Für den Anfang nutzen wir ein einfaches Textfeld pro User zur Koordination
    # In V2 bauen wir das zur Matrix aus.
    st.write("Hier folgt die Matrix-Ansicht der Verfügbarkeiten...")
