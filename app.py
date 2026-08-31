from datetime import datetime
import json
import os
import streamlit as st
from google import genai
from streamlit_mic_recorder import mic_recorder

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


# Gemini Client initialisieren (holt den Key aus den Streamlit Secrets)
@st.cache_resource
def get_gemini_client():
  api_key = st.secrets.get("GEMINI_API_KEY")
  return genai.Client(api_key=api_key)


client = get_gemini_client()

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
    "Dein persönlicher Begleiter in der Cloud – mit Sprach- & Textunterstützung."
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
      model="gemini-2.5-flash",
      config=genai.types.GenerateContentConfig(
          system_instruction=SYSTEM_INSTRUCTION, temperature=0.7
      ),
  )

# Chatverlauf anzeigen
for i, message in enumerate(st.session_state.messages):
  with st.chat_message(message["role"]):
    st.markdown(message["content"])

    # Option zum Vorlesen einzelner alten Antworten
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


# Funktion zur Verarbeitung von Texteingaben oder Sprachaufnahmen
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
        response = st.session_state.chat_session.send_message(text_to_process)
        bot_reply = response.text
        st.markdown(bot_reply)

        st.session_state.messages.append(
            {"role": "assistant", "content": bot_reply}
        )
        save_history(st.session_state.messages)

        # Automatische Sprachausgabe, falls in der Sidebar aktiviert
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
        st.error(f"Fehler bei der Verbindung: {str(e)}")


# Direkter Mikrofon-Button in der Oberfläche
col_mic, col_info = st.columns([1, 3])
with col_mic:
  audio_data = mic_recorder(
      start_prompt="🎙️ Sprechen",
      stop_prompt="⏹️ Stopp",
      just_once=True,
      key="mic",
  )

with col_info:
  st.caption(
      "Tippe auf 'Sprechen', um deine Frage direkt per Mikrofon aufzunehmen."
  )

# Wenn eine Sprachaufnahme gemacht wurde, korrekt als temporäre Datei an Gemini übergeben
if audio_data:
  audio_bytes = audio_data.get("bytes")
  if audio_bytes:
    with st.spinner("Verarbeite Sprache..."):
      temp_audio_path = "temp_audio.wav"
      try:
        # Audio vorübergehend lokal speichern
        with open(temp_audio_path, "wb") as f:
          f.write(audio_bytes)

        # Datei über die offizielle Files API hochladen
        audio_file_ref = client.files.upload(file=temp_audio_path)

        # Transkribieren lassen
        transcribe_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                (
                    "Wandle diese Audionachricht exakt auf Deutsch in Text"
                    " um. Gib nur den transkribierten Text zurück, ohne"
                    " Zusätze."
                ),
                audio_file_ref,
            ],
        )
        spoken_text = transcribe_response.text.strip()

        # Temporäre Datei aufräumen
        if os.path.exists(temp_audio_path):
          os.remove(temp_audio_path)

        if spoken_text:
          process_user_input(spoken_text)

      except Exception as e:
        if os.path.exists(temp_audio_path):
          os.remove(temp_audio_path)
        st.error(f"Fehler bei der Spracherkennung: {e}")

# Normale Chat-Eingabe (Tastatur)
if user_input := st.chat_input("Schreibe oder frage etwas..."):
  process_user_input(user_input)
