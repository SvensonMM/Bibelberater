from datetime import datetime
import json
import os
import time
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
          "Sei gegrüßt, liebe Brigitte! Ich begleite dich heute als dein"
          " persönlicher Bibelberater. Ganz egal, ob du eine Frage zu einem"
          " bestimmten Bibelvers hast, den historischen Hintergrund"
          " verstehen möchtest oder einen Impuls für deinen Alltag suchst –"
          " lass uns ins Gespräch kommen.\n\nZu welchem Thema oder"
          " Bibelabschnitt möchtest du heute sprechen?"
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


# Gemini Client initialisieren
@st.cache_resource
def get_gemini_client():
  api_key = st.secrets.get("GEMINI_API_KEY")
  return genai.Client(api_key=api_key)


client = get_gemini_client()


# Stabiler Modell-Test mit automatischem Fallback
@st.cache_resource
def get_best_available_model():
  candidate_models = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
  for model_name in candidate_models:
    try:
      client.models.generate_content(model=model_name, contents="Test")
      return model_name
    except Exception:
      continue
  return "gemini-3.6-flash"


ACTIVE_MODEL = get_best_available_model()

SYSTEM_INSTRUCTION = (
    "Du bist ein einfühlsamer, kluger und theologisch fundierter Bibelberater."
    " Die Person, mit der du sprichst, heißt Brigitte. Verwende ihren Namen"
    " gelegentlich ganz natürlich im Gespräch (z. B. zur Begrüßung, bei"
    " Ermutigungen oder passenden Übergängen), aber nicht in jedem Satz,"
    " damit es sich echt und herzlich anfühlt. Deine Aufgabe ist es, in einem"
    " lockeren, dialogorientierten Gespräch auf Fragen von Brigitte zu"
    " antworten. Antworte nicht nur mit Bibelversen, sondern erkläre den"
    " historischen und kulturellen Hintergrund. Wichtig: Stelle am Ende"
    " deiner Antwort *immer* eine passende Rückfrage, um das Gespräch"
    " vertiefend fortzuführen."
)

st.title("✝️ Bibelberater")
st.caption(
    "Dein persönlicher Begleiter in der Cloud – schnell, stabil & direkt."
)

# Session States für Audio-Optionen
if "voice_enabled" not in st.session_state:
  st.session_state.voice_enabled = False

# Sidebar für Verwaltung & Audio-Einstellungen
with st.sidebar:
  st.header("⚙️ Optionen & Verwaltung")
  st.session_state.voice_enabled = st.toggle(
      "🔊 Automatische Sprachausgabe (TTS)",
      value=st.session_state.voice_enabled,
      help="Liest die Antworten des Bibelberaters automatisch vor.",
  )
  st.caption(f"Aktives Modell: `{ACTIVE_MODEL}`")

  st.divider()
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

if "messages" not in st.session_state:
  st.session_state.messages = load_history()

if "chat_session" not in st.session_state:
  st.session_state.chat_session = client.chats.create(
      model=ACTIVE_MODEL,
      config=genai.types.GenerateContentConfig(
          system_instruction=SYSTEM_INSTRUCTION, temperature=0.7
      ),
  )

# Chatverlauf anzeigen
for i, message in enumerate(st.session_state.messages):
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

    if message["role"] == "assistant":
      if st.button(
          "🔊 Vorlesen", key=f"tts_btn_{i}", help="Diese Antwort vorlesen"
      ):
        clean_text = message["content"].replace('"', "'").replace("\n", " ")
        js_code = f"""
                <script>
                    var msg = new SpeechSynthesisUtterance("{clean_text}");
                    msg.lang = 'de-DE';
                    window.speechSynthesis.speak(msg);
                </script>
                """
        st.components.v1.html(js_code, height=0)


# Funktion mit automatischer Wiederholung bei Lastspitzen
def safe_send_message(chat_session, text):
  max_retries = 3
  for attempt in range(max_retries):
    try:
      return chat_session.send_message(text)
    except Exception as e:
      if "503" in str(e) and attempt < max_retries - 1:
        time.sleep(2)
        continue
      raise e


def process_user_input(text_to_process):
  if not text_to_process:
    return

  st.session_state.messages.append({"role": "user", "content": text_to_process})
  save_history(st.session_state.messages)

  with st.chat_message("user"):
    st.markdown(text_to_process)

  with st.chat_message("assistant"):
    with st.spinner("Der Bibelberater denkt nach..."):
      try:
        response = safe_send_message(
            st.session_state.chat_session, text_to_process
        )
        bot_reply = response.text
        st.markdown(bot_reply)

        st.session_state.messages.append(
            {"role": "assistant", "content": bot_reply}
        )
        save_history(st.session_state.messages)

        if st.session_state.voice_enabled:
          clean_reply = bot_reply.replace('"', "'").replace("\n", " ")
          tts_script = f"""
                    <script>
                        var msg = new SpeechSynthesisUtterance("{clean_reply}");
                        msg.lang = 'de-DE';
                        window.speechSynthesis.speak(msg);
                    </script>
                    """
          st.components.v1.html(tts_script, height=0)

      except Exception as e:
        st.error(
            "Der Server ist aktuell kurzzeitig ausgelastet. Bitte versuche es"
            " in einem Moment noch einmal."
        )


# Normale Chat-Eingabe (Tastatur & Samsung-Mikrofon-Taste unten links)
if user_input := st.chat_input("Schreibe oder frage etwas..."):
  process_user_input(user_input)
