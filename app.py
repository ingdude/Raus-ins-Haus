import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIG & LOGIN ---
st.set_page_config(page_title="Immo-Finder Gruppe", layout="wide")

PASSWORD = "waldsauna" 

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
    # ttl=0 stellt sicher, dass wir immer die aktuellsten Daten ziehen
    return conn.read(worksheet=sheet_name, ttl="0")

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender"])

def save_data(data, sheet_name="Immobilien"):
    conn.update(worksheet=sheet_name, data=data)
    st.cache_data.clear()

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title(f"Immo-Dashboard von {st.session_state.user_name} 🏠")
    
    df = load_data("Immobilien")
    
    if df is not None and not df.empty:
        # Fehlende Spalten abfangen
        if "Score" not in df.columns: df["Score"] = 3
        if "Kommentar" not in df.columns: df["Kommentar"] = ""

        # Sortierung: Höchster Score zuerst
        df = df.sort_values(by="Score", ascending=False)

        kat = st.selectbox("Kategorie filtern", ["Alle", "Haus", "Grundstück"])
        display_df = df.copy()
        if kat != "Alle":
            display_df = display_df[display_df["Kategorie"] == kat]

        for index, row in display_df.iterrows():
            with st.container(border=True):
                # FIX: Hier müssen 2 Variablen für 2 Spalten stehen!
                col_img, col_txt = st.columns()
                
                with col_img:
                    if pd.notnull(row.get("Bild-URL")) and str(row["Bild-URL"]).startswith("http"):
                        st.image(row["Bild-URL"], use_container_width=True)
                    else:
                        st.info("Kein Bild")
                
                with col_txt:
                    st.subheader(row.get("Titel", "Objekt"))
                    st.write(f"**Preis:** {row.get('Kaufpreis', 0)} € | **Lage:** {row.get('Lage', 'N/A')}")
                    st.write(f"**Wien:** {row.get('Distanz_Wien', 0)} km | **Fläche:** {row.get('Wohnfläche', 0)}m² / {row.get('Grundfläche', 0)}m²")
                    st.caption(f"Hinzugefügt von: {row.get('User', 'Unbekannt')}")
                    
                    # Voting & Kommentar Sektion
                    with st.expander("Bewertung & Details"):
                        new_score = st.slider("Deine Präferenz (1-5)", 1, 5, int(row["Score"]), key=f"score_{index}")
                        new_comm = st.text_area("Kommentar", row["Kommentar"], key=f"comm_{index}")
                        
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("Speichern", key=f"save_{index}"):
                                df.at[index, "Score"] = new_score
                                df.at[index, "Kommentar"] = new_comm
                                save_data(df)
                                st.rerun()
                        with c2:
                            st.link_button("Zur Anzeige", row["URL"])
                        with c3:
                            if st.button("🗑️ Löschen", key=f"del_{index}"):
                                updated_df = df.drop(index)
                                save_data(updated_df)
                                st.rerun()
    else:
        st.info("Noch keine Immobilien da. Klick links auf 'Objekt hinzufügen'!")

# --- ➕ OBJEKT HINZUFÜGEN ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt erfassen")
    df = load_data("Immobilien")
    with st.form("add_form"):
        titel = st.text_input("Titel")
        url = st.text_input("Anzeigen-Link")
        bild = st.text_input("Bild-URL (Rechtsklick auf Bild -> Adresse kopieren)")
        kat = st.selectbox("Typ", ["Haus", "Grundstück"])
        preis = st.number_input("Preis (€)", step=1000)
        w_f = st.number_input("Wohnfläche (m²)", step=1)
        g_f = st.number_input("Grundfläche (m²)", step=10)
        ort = st.text_input("Ort")
        km = st.number_input("Km nach Wien", step=1)
        
        if st.form_submit_button("Objekt speichern"):
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
    st.title("Besichtigungs-Planer")
    st.write("Wer hat wann Zeit? Einfach Namen in die Zellen schreiben.")
    
    try:
        df_cal = load_data("Kalender")
    except:
        df_cal = pd.DataFrame([{"Zeitraum": "Samstag Vormittag", "Verfügbar": ""}])
    
    edited_df = st.data_editor(df_cal, num_rows="dynamic", use_container_width=True)
    
    if st.button("Kalender speichern"):
        save_data(edited_df, sheet_name="Kalender")
        st.success("Kalender wurde aktualisiert!")
