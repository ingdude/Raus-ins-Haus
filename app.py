import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIG & LOGIN ---
st.set_page_config(page_title="Immo-Finder Gruppe", layout="wide")

PASSWORD = "waldsauna" # Hier wieder euer Passwort eintragen

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
    u_name = st.text_input("Wie heißt du?")
    if u_name:
        st.session_state.user_name = u_name
        st.rerun()
    else:
        st.stop()

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name="Immobilien"):
    # Lädt die Daten frisch aus Google Sheets
    df = conn.read(worksheet=sheet_name, ttl=0)
    # Füllt leere Zellen (NaN) mit leeren Strings, um Fehler zu vermeiden
    return df.fillna("")

def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender"])

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title(f"Immo-Dashboard von {st.session_state.user_name} 🏠")
    
    df = load_data("Immobilien")
    
    if df is not None and not df.empty:
        # Sicherstellen, dass Score und Kommentar existieren
        if "Score" not in df.columns: df["Score"] = 3
        if "Kommentar" not in df.columns: df["Kommentar"] = ""

        # Konvertiere Score in Zahlen für die Sortierung
        df["Score"] = pd.to_numeric(df["Score"], errors='coerce').fillna(3)
        df = df.sort_values(by="Score", ascending=False)

        kat = st.selectbox("Kategorie filtern", ["Alle", "Haus", "Grundstück"])
        display_df = df.copy()
        if kat != "Alle":
            display_df = display_df[display_df["Kategorie"] == kat]

        for index, row in display_df.iterrows():
            with st.container(border=True):
                # HIER IST DER FIX: MUSS in der Klammer stehen!
                col_img, col_txt = st.columns()
                
                with col_img:
                    bild_url = str(row.get("Bild-URL", ""))
                    if bild_url.startswith("http"):
                        st.image(bild_url, use_container_width=True)
                    else:
                        st.info("Kein Bild")
                
                with col_txt:
                    st.subheader(row.get("Titel", "Unbenanntes Objekt"))
                    st.write(f"**Preis:** {row.get('Kaufpreis', 0)} € | **Lage:** {row.get('Lage', '')}")
                    st.write(f"**Wien:** {row.get('Distanz_Wien', 0)} km | **Fläche:** {row.get('Wohnfläche', 0)}m² / {row.get('Grundfläche', 0)}m²")
                    
                    user_val = row.get("User", "")
                    st.caption(f"Hinzugefügt von: {user_val if user_val else 'Unbekannt'}")
                    
                    # 1. EXPANDER: Voten & Kommentieren
                    with st.expander("⭐ Bewertung & Details"):
                        new_score = st.slider("Präferenz (1=Naja, 5=Traumhaus)", 1, 5, int(row["Score"]), key=f"score_{index}")
                        new_comm = st.text_area("Kommentar", row["Kommentar"], key=f"comm_{index}")
                        
                        if st.button("Bewertung speichern", key=f"save_vote_{index}"):
                            df.at[index, "Score"] = new_score
                            df.at[index, "Kommentar"] = new_comm
                            save_data(df)
                            st.rerun()

                    # 2. EXPANDER: Editieren & Löschen
                    with st.expander("✏️ Objekt bearbeiten / löschen"):
                        with st.form(key=f"edit_form_{index}"):
                            e_titel = st.text_input("Titel", row.get("Titel", ""))
                            e_preis = st.number_input("Preis (€)", value=float(row.get("Kaufpreis", 0) or 0), step=1000.0)
                            e_w_f = st.number_input("Wohnfläche", value=float(row.get("Wohnfläche", 0) or 0))
                            e_g_f = st.number_input("Grundfläche", value=float(row.get("Grundfläche", 0) or 0))
                            e_url = st.text_input("Anzeigen-Link", row.get("URL", ""))
                            e_bild = st.text_input("Bild-URL", row.get("Bild-URL", ""))
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.form_submit_button("💾 Änderungen speichern"):
                                    df.at[index, "Titel"] = e_titel
                                    df.at[index, "Kaufpreis"] = e_preis
                                    df.at[index, "Wohnfläche"] = e_w_f
                                    df.at[index, "Grundfläche"] = e_g_f
                                    df.at[index, "URL"] = e_url
                                    df.at[index, "Bild-URL"] = e_bild
                                    save_data(df)
                                    st.success("Aktualisiert!")
                                    st.rerun()
                                    
                        # Löschen Button (außerhalb der Form)
                        if st.button("🗑️ Komplettes Objekt löschen", key=f"del_{index}"):
                            updated_df = df.drop(index)
                            save_data(updated_df)
                            st.rerun()
                            
                    # Link zur Originalanzeige
                    if str(row.get("URL", "")).startswith("http"):
                        st.link_button("🔗 Anzeige bei Willhaben/ImmoScout öffnen", row.get("URL", ""))

    else:
        st.info("Noch keine Immobilien da. Klick links auf 'Objekt hinzufügen'!")

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
        km = st.number_input("Km nach Wien", step=1)
        
        if st.form_submit_button("Objekt in Datenbank speichern"):
            new_row = pd.DataFrame([{
                "Titel": titel, "URL": url, "Bild-URL": bild, "Kategorie": kat,
                "Kaufpreis": preis, "Wohnfläche": w_f, "Grundfläche": g_f,
                "Lage": ort, "Distanz_Wien": km, "User": st.session_state.user_name,
                "Score": 3, "Kommentar": ""
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            save_data(updated_df)
            st.success("Erfolgreich hinzugefügt!")

# --- 📅 KALENDER ---
elif menu == "📅 Besichtigungs-Kalender":
    st.title("Wann habt ihr Zeit?")
    st.write("Einfach in die Tabelle klicken, eintragen und speichern.")
    
    try:
        df_cal = load_data("Kalender")
        if df_cal.empty:
            raise ValueError("Leere Tabelle")
    except:
        # Falls die Tabelle leer ist oder noch nicht existiert, bauen wir eine Vorlage
        df_cal = pd.DataFrame([
            {"Datum / Tag": "Samstag Vormittag", "Wer kann?": "", "Anmerkung": ""},
            {"Datum / Tag": "Samstag Nachmittag", "Wer kann?": "", "Anmerkung": ""},
            {"Datum / Tag": "Sonntag", "Wer kann?": "", "Anmerkung": ""}
        ])
    
    # Hier nutzen wir den Editor. num_rows="dynamic" erlaubt das Hinzufügen neuer Zeilen!
    edited_df = st.data_editor(df_cal, num_rows="dynamic", use_container_width=True, height=300)
    
    if st.button("💾 Kalender in Google Sheets speichern"):
        save_data(edited_df, sheet_name="Kalender")
        st.success("Kalender wurde aktualisiert!")
