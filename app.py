import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from geopy.geocoders import Nominatim

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

# --- GEOCODING (Für die Karte) ---
@st.cache_data
def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="raus_ins_haus_finder_v4")
        location = geolocator.geocode(f"{address}, Österreich")
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

# --- NAVIGATION ---
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "🗺️ Kartenansicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender", "⚙️ Admin (User)"])

# --- 🏠 ÜBERSICHT ---
if menu == "🏠 Übersicht":
    st.title("Raus ins Haus 🏠")
    st.caption(f"Eingeloggt als: {st.session_state.user_name}")
    
    df = load_data("Immobilien")
    
    if df is not None and not df.empty:
        # Durchschnitts-Berechnung (Multi-User)
        score_cols = [col for col in df.columns if col.startswith("Score_")]
        if score_cols:
            df[score_cols] = df[score_cols].replace("", pd.NA) 
            df[score_cols] = df[score_cols].apply(pd.to_numeric, errors='coerce')
            df["Durchschnitt"] = df[score_cols].mean(axis=1).fillna(0)
        else:
            df["Durchschnitt"] = 0

        df = df.sort_values(by="Durchschnitt", ascending=False)

        kat = st.selectbox("Kategorie filtern", ["Alle", "Haus", "Grundstück"])
        display_df = df.copy()
        if kat != "Alle":
            display_df = display_df[display_df["Kategorie"] == kat]

        for index, row in display_df.iterrows():
            with st.container(border=True):
                col_img, col_txt = st.columns(2)
                with col_img:
                    bild_url = str(row.get("Bild-URL", ""))
                    if bild_url.startswith("http"):
                        st.image(bild_url, use_container_width=True)
                    else:
                        st.info("Kein Bild")
                with col_txt:
                    st.subheader(row.get("Titel", "Objekt"))
                    p = float(row.get('Kaufpreis', 0) or 0)
                    preis_form = f"{int(p):,}".replace(",", ".") + " €"
                    
                    # WIEDER DA: Alle wichtigen Objekt-Infos!
                    st.write(f"**Preis:** {preis_form} | **Lage:** {row.get('Lage', '')}")
                    st.write(f"**Entfernung Wien:** {row.get('Distanz_Wien', 0)} km")
                    st.write(f"**Wohnfläche:** {row.get('Wohnfläche', 0)} m² | **Grundfläche:** {row.get('Grundfläche', 0)} m²")
                    
                    ds = row.get("Durchschnitt", 0)
                    if ds > 0:
                        st.markdown(f"### 🔥 Ø Bewertung: {round(ds, 1)} / 5")
                    else:
                        st.markdown("### ⚪ Noch keine Bewertungen")
                        
                    st.caption(f"Hinzugefügt von: {row.get('User', 'Unbekannt')}")
                    
                    with st.expander("💬 Bewertungen & Kommentare"):
                        # Gruppen-Chat anzeigen
                        comm_cols = [col for col in df.columns if col.startswith("Kommentar_")]
                        hat_kommentare = False
                        for c_col in comm_cols:
                            txt = str(row.get(c_col, "")).strip()
                            if txt and txt != "nan":
                                st.info(f"**{c_col.replace('Kommentar_', '')}:** {txt}")
                                hat_kommentare = True
                        if not hat_kommentare:
                            st.write("📝 *Noch keine Kommentare vorhanden.*")
                        
                        st.divider()
                        
                        # FIX: Robuster Slider für die eigene Note
                        mein_score_col = f"Score_{st.session_state.user_name}"
                        mein_comm_col = f"Kommentar_{st.session_state.user_name}"
                        
                        # Sicheres Auslesen des Scores (verhindert den Absturz bei leeren Zellen)
                        raw_score = row.get(mein_score_col, 3)
                        if pd.isna(raw_score) or raw_score == "":
                            safe_score = 3
                        else:
                            safe_score = int(float(raw_score))
                            
                        new_score = st.slider("Deine Präferenz (1-5)", 1, 5, safe_score, key=f"s_{index}")
                        new_comm = st.text_area("Dein Kommentar", str(row.get(mein_comm_col, "")).replace("nan", ""), key=f"c_{index}")
                        
                        if st.button("Speichern", key=f"btn_{index}"):
                            df.at[index, mein_score_col] = new_score
                            df.at[index, mein_comm_col] = new_comm
                            save_data(df)
                            st.rerun()

                    with st.expander("✏️ Bearbeiten / Löschen"):
                        with st.form(f"edit_{index}"):
                            e_titel = st.text_input("Titel", row.get("Titel", ""))
                            e_preis = st.number_input("Preis (€)", value=p)
                            e_w_f = st.number_input("Wohnfläche", value=float(row.get("Wohnfläche", 0) or 0))
                            e_g_f = st.number_input("Grundfläche", value=float(row.get("Grundfläche", 0) or 0))
                            e_url = st.text_input("Anzeigen-Link", row.get("URL", ""))
                            e_bild = st.text_input("Bild-URL", row.get("Bild-URL", ""))
                            
                            if st.form_submit_button("Änderungen speichern"):
                                df.at[index, "Titel"] = e_titel
                                df.at[index, "Kaufpreis"] = e_preis
                                df.at[index, "Wohnfläche"] = e_w_f
                                df.at[index, "Grundfläche"] = e_g_f
                                df.at[index, "URL"] = e_url
                                df.at[index, "Bild-URL"] = e_bild
                                save_data(df)
                                st.rerun()
                                
                        if st.button("🗑️ Objekt unwiderruflich löschen", key=f"del_{index}"):
                            save_data(df.drop(index))
                            st.rerun()
                    
                    if str(row.get("URL", "")).startswith("http"):
                        st.link_button("🔗 Anzeige öffnen", row["URL"])

# --- 🗺️ KARTENANSICHT (WIEDER DA!) ---
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
                        map_points.append({"lat": lat, "lon": lon, "Titel": row.get("Titel", "Objekt")})
        
        if map_points:
            # Zeigt die rote-Punkt Karte an
            st.map(pd.DataFrame(map_points))
            st.write("### Liste der Standorte")
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
        km = st.number_input("Km nach Wien", step=1)
        
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
elif menu == "⚙️ Admin (User)":
    st.title("User verwalten")
    st.write("Hier kannst du Namen hinzufügen oder entfernen, die im Login-Menü erscheinen.")
    
    try:
        current_user_df = load_data("User")
    except:
        current_user_df = pd.DataFrame({"Name": ["Anja", "Jan", "Katja", "Laurenz", "Timo"]})
        
    edited_user_df = st.data_editor(current_user_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("User-Liste speichern"):
        save_data(edited_user_df, sheet_name="User")
