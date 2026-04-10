import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIG & LOGIN ---
st.set_page_config(page_title="Immo-Finder Gruppe", layout="wide")

PASSWORD = "waldsauna" # ÄNDERE DAS FALLS NÖTIG

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

if "user_name" not in st.session_state:
    user_name = st.text_input("Wie heißt du?")
    if user_name:
        st.session_state.user_name = user_name
        st.rerun()
    else:
        st.stop()

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name="Immobilien"):
    return conn.read(worksheet=sheet_name, ttl="0") # ttl=0 erzwingt frische Daten

# Daten laden
df = load_data("Immobilien")
# Kalender-Daten laden (Falls der Reiter leer ist, erstellen wir eine Grundstruktur)
try:
    df_cal = conn.read(worksheet="Kalender", ttl="0")
except:
    df_cal = pd.DataFrame(columns=["Zeitraum", "Status"])

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender"])

# --- HELPERS ---
def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- 🏠 ÜBERSICHT (INKL. LÖSCHEN & FIX FÜR 'NAN') ---
if menu == "🏠 Übersicht":
    st.title(f"Hallo {st.session_state.user_name}! 👋")
    
    kat = st.selectbox("Kategorie filtern", ["Alle", "Haus", "Grundstück"])
    display_df = df.copy()
    if kat != "Alle":
        display_df = display_df[display_df["Kategorie"] == kat]

    st.subheader("Aktuelle Objekte")
    
    if display_df.empty:
        st.info("Noch keine Objekte vorhanden. Füge eins hinzu!")
    else:
        # Wir zeigen die Kacheln an
        for index, row in display_df.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns(3)
                
                with col1:
                    if pd.notnull(row["Bild-URL"]) and str(row["Bild-URL"]).startswith("http"):
                        st.image(row["Bild-URL"], use_container_width=True)
                    else:
                        st.info("Kein Bild verfügbar")
                
                with col2:
                    st.markdown(f"### {row['Titel']}")
                    st.write(f"**💰 {row['Kaufpreis']} €** | 📍 {row['Lage']} ({row['Distanz_Wien']} km nach Wien)")
                    st.write(f"📏 {row['Wohnfläche']} m² Wohnfläche / {row['Grundfläche']} m² Grund")
                    
                    # Fix für den Namen: Wir prüfen, ob der Wert "nan" ist
                    user_added = row['User'] if pd.notnull(row['User']) else "Unbekannt"
                    st.caption(f"Hinzugefügt von: {user_added}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.link_button("🔗 Anzeige", row["URL"])
                    with c2:
                        # LÖSCH-FUNKTION
                        if st.button("🗑️ Löschen", key=f"del_{index}"):
                            # Wir löschen die Zeile aus dem Haupt-DataFrame df (nicht display_df)
                            updated_df = df.drop(index)
                            save_data(updated_df)
                            st.success("Gelöscht! Seite lädt neu...")
                            st.rerun()

# --- ➕ OBJEKT HINZUFÜGEN ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt erfassen")
    with st.form("add_form", clear_on_submit=True):
        titel = st.text_input("Titel")
        url = st.text_input("Link zur Anzeige")
        bild_url = st.text_input("Bild-URL (Rechtsklick auf Bild -> Adresse kopieren)")
        kat = st.selectbox("Kategorie", ["Haus", "Grundstück"])
        preis = st.number_input("Preis (€)", step=1000)
        w_flaeche = st.number_input("Wohnfläche (m²)", step=1)
        g_flaeche = st.number_input("Grundfläche (m²)", step=10)
        lage = st.text_input("Lage")
        distanz = st.number_input("Km nach Wien", step=1)
        
        submitted = st.form_submit_button("Objekt speichern")
        if submitted:
            # WICHTIG: Der Spaltenname 'User' muss exakt so im Google Sheet stehen!
            new_row = {
                "Titel": titel, "URL": url, "Bild-URL": bild_url, "Kategorie": kat,
                "Kaufpreis": preis, "Wohnfläche": w_flaeche, "Grundfläche": g_flaeche,
                "Lage": lage, "Distanz_Wien": distanz, "User": st.session_state.user_name
            }
            new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(new_df)
            st.success("Gespeichert!")
            st.rerun()

# --- 📅 BESICHTIGUNGS-KALENDER (INTERAKTIV) ---
elif menu == "📅 Besichtigungs-Kalender":
    st.title("Besichtigungs-Planer")
    st.write("Trage hier ein, wer wann Zeit hat (z.B. 'Laurenz, Max, Susi').")
    
    # Ein interaktiver Editor für das Google Sheet
    # Wir zeigen eine Tabelle an, die man direkt bearbeiten kann
    st.info("Einfach in die Zellen klicken und tippen. Danach 'Speichern' klicken.")
    
    # Falls das Sheet leer ist, geben wir eine Struktur vor
    if df_cal.empty:
        df_cal = pd.DataFrame([
            {"Zeitraum": "Samstag Vormittag", "Wer hat Zeit?": ""},
            {"Zeitraum": "Samstag Nachmittag", "Wer hat Zeit?": ""},
            {"Zeitraum": "Sonntag Vormittag", "Wer hat Zeit?": ""},
            {"Zeitraum": "Unter der Woche ab 17h", "Wer hat Zeit?": ""}
        ])
    
    edited_df = st.data_editor(df_cal, num_rows="dynamic", use_container_width=True)
    
    if st.button("Kalender speichern"):
        save_data(edited_df, sheet_name="Kalender")
        st.success("Kalender aktualisiert!")
