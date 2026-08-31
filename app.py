from datetime import datetime
import json
import os
import time
import streamlit as st
from google import genai

# Streamlit Page Setup mit dem exakten Titel für den Browser & Startbildschirm
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
          " bestimmten Bibelvers hast oder einen Impuls für deinen Alltag"
          " suchst – lass uns ins Gespräch kommen.\n\nZu welchem Thema"
          " möchtest du heute sprechen?"
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


# Automatischer Test, welches Modell aktuell erreichbar ist
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
    "Du bist ein einfühlsamer und theologisch fundierter Bibelberater."
    " Die Person, mit der du sprichst, heißt Brigitte. Verwende ihren Namen"
    " gelegentlich ganz natürlich im Gespräch. Antworte anschaulich,"
    " verständlich, erkläre den Hintergrund und stelle am Ende *immer* eine"
    " kurze Rückfrage."
)

st.title("✝️ Bibelberater")
st.caption("Dein persönlicher Begleiter in der Cloud – blitzschnell.")

# Session States für Audio-Optionen
if "voice_enabled" not in st.session_state:
  st.session_state.voice_enabled = False

# Sidebar für Verwaltung & Audio-Einstellungen
with st.sidebar:
  st.header("⚙️ Optionen & Verwaltung")
  st.session_state.voice_enabled = st.toggle(
      "🔊 Automatische Sprachausgabe",
      value=st.session_state.voice_enabled,
      help="Liest die Antworten automatisch vor.",
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
                    var utterance = new SpeechSynthesisUtterance("{clean_text}");
                    utterance.lang = 'de-DE';
                    
                    var voices = window.speechSynthesis.getVoices();
                    var preferredVoice = voices.find(v => v.lang === 'de-DE' && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Online')));
                    if (!preferredVoice) {{
                        preferredVoice = voices.find(v => v.lang === 'de-DE' || v.lang === 'de_DE');
                    }}
                    if (preferredVoice) {{ utterance.voice = preferredVoice; }}
                    
                    window.speechSynthesis.cancel();
                    window.speechSynthesis.speak(utterance);
                </script>
                """
        st.components.v1.html(js_code, height=0)


# Ultraschnelle Abfrage im Direkt-Modus (ohne starre Token-Begrenzung)
def get_fast_response(messages_history, new_user_input):
  contents = [SYSTEM_INSTRUCTION]
  recent_msgs = messages_history[-6:]
  for msg in recent_msgs:
    role_prefix = "Nutzer: " if msg["role"] == "user" else "Assistent: "
    contents.append(role_prefix + msg["content"])

  contents.append("Nutzer: " + new_user_input)
  contents.append("Assistent:")

  max_retries = 3
  for attempt in range(max_retries):
    try:
      response = client.models.generate_content(
          model=ACTIVE_MODEL,
          contents=contents,
          config=genai.types.GenerateContentConfig(temperature=0.4),
      )
      return response.text
    except Exception as e:
      if "503" in str(e) and attempt < max_retries - 1:
        time.sleep(2)
        continue
      raise e


# Chat-Eingabe
if user_input := st.chat_input("Schreibe deine Nachricht..."):
  st.session_state.messages.append({"role": "user", "content": user_input})
  save_history(st.session_state.messages)

  with st.chat_message("user"):
    st.markdown(user_input)

  with st.chat_message("assistant"):
    with st.spinner("Der Bibelberater antwortet..."):
      try:
        bot_reply = get_fast_response(
            st.session_state.messages[:-1], user_input
        )
        st.markdown(bot_reply)

        st.session_state.messages.append(
            {"role": "assistant", "content": bot_reply}
        )
        save_history(st.session_state.messages)

        if st.session_state.voice_enabled:
          clean_reply = bot_reply.replace('"', "'").replace("\n", " ")
          tts_script = f"""
                    <script>
                        function playSpeech() {{
                            var utterance = new SpeechSynthesisUtterance("{clean_reply}");
                            utterance.lang = 'de-DE';
                            
                            var voices = window.speechSynthesis.getVoices();
                            var preferredVoice = voices.find(v => v.lang === 'de-DE' && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Online')));
                            if (!preferredVoice) {{
                                preferredVoice = voices.find(v => v.lang === 'de-DE' || v.lang === 'de_DE');
                            }}
                            if (preferredVoice) {{ utterance.voice = preferredVoice; }}
                            
                            window.speechSynthesis.cancel();
                            window.speechSynthesis.speak(utterance);
                        }}
                        if ('speechSynthesis' in window) {{
                            if (window.speechSynthesis.getVoices().length > 0) {{
                                playSpeech();
                            }} else {{
                                window.speechSynthesis.onvoiceschanged = playSpeech;
                                playSpeech();
                            }}
                        }}
                    </script>
                    """
          st.components.v1.html(tts_script, height=0)

      except Exception as e:
        st.error(f"Fehler bei der Antwortgenerierung: {e}")
