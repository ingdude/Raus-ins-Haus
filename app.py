import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

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

# --- NEU: DYNAMISCHE USER-LISTE LADEN ---
try:
    # Versuche die Namen aus dem Reiter "User" zu laden
    user_df = load_data("User")
    if not user_df.empty and "Name" in user_df.columns:
        # Sortiert die Namen alphabetisch
        user_liste = sorted(user_df["Name"].dropna().unique().tolist())
    else:
        # Backup, falls das Sheet leer ist
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
menu = st.sidebar.radio("Menü", ["🏠 Übersicht", "➕ Objekt hinzufügen", "📅 Besichtigungs-Kalender", "⚙️ Admin (User-Verwaltung)"])

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
                    st.write(f"**Preis:** {preis_form} | **Lage:** {row.get('Lage', '')}")
                    
                    ds = row.get("Durchschnitt", 0)
                    if ds > 0:
                        st.markdown(f"### 🔥 Ø Bewertung: {round(ds, 1)} / 5")
                    
                    with st.expander("💬 Bewertungen & Kommentare"):
                        # Kommentare anzeigen
                        comm_cols = [col for col in df.columns if col.startswith("Kommentar_")]
                        for c_col in comm_cols:
                            txt = str(row.get(c_col, "")).strip()
                            if txt and txt != "nan":
                                st.info(f"**{c_col.replace('Kommentar_', '')}:** {txt}")
                        
                        st.divider()
                        mein_score_col = f"Score_{st.session_state.user_name}"
                        mein_comm_col = f"Kommentar_{st.session_state.user_name}"
                        
                        new_score = st.slider("Deine Note", 1, 5, int(row.get(mein_score_col, 3) or 3), key=f"s_{index}")
                        new_comm = st.text_area("Dein Senf", str(row.get(mein_comm_col, "")).replace("nan", ""), key=f"c_{index}")
                        
                        if st.button("Speichern", key=f"btn_{index}"):
                            df.at[index, mein_score_col] = new_score
                            df.at[index, mein_comm_col] = new_comm
                            save_data(df)
                            st.rerun()

                    with st.expander("✏️ Bearbeiten / Löschen"):
                        if st.button("🗑️ Objekt unwiderruflich löschen", key=f"del_{index}"):
                            save_data(df.drop(index))
                            st.rerun()
                    
                    if str(row.get("URL", "")).startswith("http"):
                        st.link_button("🔗 Anzeige öffnen", row["URL"])

# --- ⚙️ ADMIN (USER-VERWALTUNG) ---
elif menu == "⚙️ Admin (User-Verwaltung)":
    st.title("User verwalten")
    st.write("Hier kannst du Namen hinzufügen oder entfernen, die im Login-Menü erscheinen.")
    
    current_user_df = load_data("User")
    edited_user_df = st.data_editor(current_user_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("User-Liste speichern"):
        save_data(edited_user_df, sheet_name="User")
        st.success("Die User-Liste wurde aktualisiert! Beim nächsten Login sind die neuen Namen verfügbar.")

# --- (Restliche Menüpunkte bleiben gleich: hinzufügen & Kalender) ---
elif menu == "➕ Objekt hinzufügen":
    st.title("Neues Objekt")
    df = load_data("Immobilien")
    with st.form("add"):
        t = st.text_input("Titel")
        u = st.text_input("Link")
        b = st.text_input("Bild-URL")
        p = st.number_input("Preis", step=1000)
        l = st.text_input("Lage")
        if st.form_submit_button("Speichern"):
            new = pd.DataFrame([{"Titel": t, "URL": u, "Bild-URL": b, "Kaufpreis": p, "Lage": l, "User": st.session_state.user_name}])
            save_data(pd.concat([df, new], ignore_index=True))
            st.success("Check!")

elif menu == "📅 Besichtigungs-Kalender":
    st.title("Kalender")
    df_cal = load_data("Kalender")
    edited = st.data_editor(df_cal, num_rows="dynamic", use_container_width=True)
    if st.button("Kalender speichern"):
        save_data(edited, sheet_name="Kalender")
        st.rerun()
