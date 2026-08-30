from datetime import datetime
import json
import os
import streamlit as st
from google import genai

# Streamlit Page Setup mit Kreuz-Icon
st.set_page_config(
    page_title="Bibelberater", page_icon="✝️", layout="centered"
)

# Dateinamen & Ordner für die Cloud-Sitzung
HISTORY_FILE = "bibel_chat_history.json"
ARCHIVE_DIR = "bibel_chat_archives"

if not os.path.exists(ARCHIVE_DIR):
  os.makedirs(ARCHIVE_DIR)


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      pass
  return get_default_greeting()


def get_default_greeting():
  return [{
      "role":
          "assistant",
      "content": (
          "Sei gegrüßt! Ich begleite dich als dein persönlicher Bibelberater."
          " Ganz egal, ob du eine Frage zu einem bestimmten Bibelvers hast, den"
          " historischen Hintergrund verstehen möchtest oder einen Impuls für"
          " deinen Alltag suchst – lass uns ins Gespräch kommen.\n\nZu welchem"
          " Thema oder Bibelabschnitt möchtest du heute sprechen?"
      ),
  }]


def save_history(messages):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(messages, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"Fehler beim Speichern der Historie: {e}")


def archive_current_chat():
  if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
      messages = json.load(f)
    if len(messages) > 1:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
      first_user_msg = next(
          (m["content"] for m in messages if m["role"] == "user"), "Chat"
      )
      clean_title = "".join(
          c
          for c in first_user_msg[:25]
          if c.isalnum() or c in (" ", "_", "-")
      ).strip()
      archive_filename = f"{timestamp}_{clean_title}.json"
      archive_path = os.path.join(ARCHIVE_DIR, archive_filename)
      with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)


# Gemini Client initialisieren (holt den Key aus den Streamlit Secrets)
@st.cache_resource
def get_gemini_client():
  api_key = st.secrets.get("GEMINI_API_KEY")
  return genai.Client(api_key=api_key)


client = get_gemini_client()

SYSTEM_INSTRUCTION = (
    "Du bist ein einfühlsamer, kluger und theologisch fundierter Bibelberater."
    " Deine Aufgabe ist es, in einem lockeren, dialogorientierten Gespräch auf"
    " Fragen des Nutzers zu antworten. Antworte nicht nur mit Bibelversen,"
    " sondern erkläre den historischen und kulturellen Hintergrund. Wichtig:"
    " Stelle am Ende deiner Antwort *immer* eine passende Rückfrage, um das"
    " Gespräch vertiefend fortzuführen."
)

st.title("✝️ Bibelberater")
st.caption("Dein persönlicher Begleiter in der Cloud.")

if "messages" not in st.session_state:
  st.session_state.messages = load_history()

if "chat_session" not in st.session_state:
  st.session_state.chat_session = client.chats.create(
      model="gemini-2.5-flash",
      config=genai.types.GenerateContentConfig(
          system_instruction=SYSTEM_INSTRUCTION, temperature=0.7
      ),
  )

for message in st.session_state.messages:
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

if user_input := st.chat_input("Schreibe deine Nachricht..."):
  st.session_state.messages.append({"role": "user", "content": user_input})
  save_history(st.session_state.messages)

  with st.chat_message("user"):
    st.markdown(user_input)

  with st.chat_message("assistant"):
    with st.spinner("Der Bibelberater denkt nach..."):
      try:
        response = st.session_state.chat_session.send_message(user_input)
        bot_reply = response.text
        st.markdown(bot_reply)

        st.session_state.messages.append(
            {"role": "assistant", "content": bot_reply}
        )
        save_history(st.session_state.messages)
      except Exception as e:
        st.error(f"Fehler bei der Verbindung: {str(e)}")

# Sidebar für Verwaltung
with st.sidebar:
  st.header("🗂️ Chat-Verwaltung")
  if st.button("➕ Neuer Chat (Aktuellen archivieren)"):
    archive_current_chat()
    if os.path.exists(HISTORY_FILE):
      os.remove(HISTORY_FILE)
    st.session_state.messages = get_default_greeting()
    save_history(st.session_state.messages)
    st.rerun()

  st.divider()
  st.subheader("📚 Archivierte Gespräche")
  archives = sorted(
      [f for f in os.listdir(ARCHIVE_DIR) if f.endswith(".json")], reverse=True
  )

  if not archives:
    st.info("Noch keine alten Chats archiviert.")
  else:
    selected_archive = st.selectbox(
        "Wähle ein Archiv aus:", ["-- Auswählen --"] + archives
    )
    if selected_archive != "-- Auswählen --":
      col1, col2 = st.columns(2)
      archive_full_path = os.path.join(ARCHIVE_DIR, selected_archive)
      with col1:
        if st.button("📥 Laden"):
          archive_current_chat()
          with open(archive_full_path, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
          save_history(st.session_state.messages)
          st.rerun()
      with col2:
        if st.button("🗑️ Löschen", type="primary"):
          os.remove(archive_full_path)
          st.rerun()
