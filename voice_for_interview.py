import streamlit as st
from google.cloud import speech_v1 as speech
from google.cloud import texttospeech
from google.oauth2 import service_account
import json
import os
from audio_recorder_streamlit import audio_recorder
import tempfile

st.set_page_config(page_title="Voice API Test", layout="wide")

# Load credentials from JSON (for local testing)
def load_credentials():
    # Try to get from Streamlit secrets first
    if "google_credentials" in st.secrets:
        return service_account.Credentials.from_service_account_info(
            st.secrets["google_credentials"]
        )
    
    # Otherwise load from local file
    creds_file = st.text_input(
        "Path to credentials JSON file:",
        value="credentials.json" if os.path.exists("credentials.json") else ""
    )
    
    if not os.path.exists(creds_file):
        st.warning(f"Credentials file not found: {creds_file}")
        st.info("Either upload a file or enter credentials manually below")
        return None
    
    with open(creds_file, "r") as f:
        return service_account.Credentials.from_service_account_info(json.load(f))

# Function to transcribe audio
def transcribe_audio(audio_bytes, credentials):
    # Save audio bytes to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_file_path = tmp_file.name
    
    # Create speech client
    client = speech.SpeechClient(credentials=credentials)
    
    # Load the audio file
    with open(tmp_file_path, "rb") as audio_file:
        content = audio_file.read()
    
    # Configure the speech recognition request
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=48000,
        language_code="en-GB",
    )
    
    # Perform speech recognition
    response = client.recognize(config=config, audio=audio)
    
    # Delete the temporary file
    os.unlink(tmp_file_path)
    
    # Extract and return the transcript
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript
    
    return transcript

# Function for text to speech
def text_to_speech(text, credentials):
    # Create TTS client
    client = texttospeech.TextToSpeechClient(credentials=credentials)
    
    # Set up the input text
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    # Configure the voice
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-GB",
        name="en-GB-Neural2-B",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    
    # Configure the audio output
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    # Generate the speech
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    # Return the audio content
    return response.audio_content

def main():
    st.title("Google Cloud Voice API Tester")
    
    # Set up tabs
    tab1, tab2, tab3 = st.tabs(["Setup", "Speech-to-Text", "Text-to-Speech"])
    
    with tab1:
        st.header("Credentials Setup")
        
        # Manual credentials entry option
        st.subheader("Enter Credentials Manually")
        use_manual = st.checkbox("Enter credentials manually instead of using a file")
        
        credentials = None
        
        if use_manual:
            project_id = st.text_input("Project ID")
            private_key_id = st.text_input("Private Key ID")
            private_key = st.text_area("Private Key (Entire key including BEGIN/END lines)")
            client_email = st.text_input("Client Email")
            
            if st.button("Save Manual Credentials"):
                creds_dict = {
                    "type": "service_account",
                    "project_id": project_id,
                    "private_key_id": private_key_id,
                    "private_key": private_key,
                    "client_email": client_email,
                    "client_id": "",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@', '%40')}"
                }
                
                credentials = service_account.Credentials.from_service_account_info(creds_dict)
                st.session_state["credentials"] = credentials
                st.success("Credentials saved!")
        else:
            credentials = load_credentials()
            if credentials:
                st.session_state["credentials"] = credentials
                st.success("Credentials loaded successfully!")
        
        st.header("Set Up Billing Alerts")
        st.markdown("""
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Select your project
        3. Navigate to Billing > Budgets & alerts
        4. Click "Create Budget"
        5. Set a budget name and amount (e.g., $10)
        6. Configure alerts at 50%, 90%, and 100% of your budget
        7. Save your budget
        """)
        
        st.header("Estimated Costs")
        st.markdown("""
        - Speech-to-Text: $0.006 per 15 seconds (free tier: 60 minutes/month)
        - Text-to-Speech: $4 per million characters (free tier: 4 million characters/month)
        """)
    
    with tab2:
        st.header("Speech-to-Text Test")
        
        if "credentials" not in st.session_state:
            st.warning("Please set up credentials in the Setup tab first")
        else:
            st.write("Click the microphone button and speak to record audio:")
            
            # Record audio
            audio_bytes = audio_recorder()
            
            if audio_bytes:
                with st.spinner("Transcribing..."):
                    try:
                        transcript = transcribe_audio(audio_bytes, st.session_state["credentials"])
                        st.success("Transcription complete!")
                        st.write(f"**Transcribed Text:** {transcript}")
                        
                        # Save to session state for easy access in TTS tab
                        st.session_state["last_transcript"] = transcript
                    except Exception as e:
                        st.error(f"Error during transcription: {str(e)}")
    
    with tab3:
        st.header("Text-to-Speech Test")
        
        if "credentials" not in st.session_state:
            st.warning("Please set up credentials in the Setup tab first")
        else:
            # Text input
            default_text = st.session_state.get("last_transcript", "Hello, this is a test of the Google Text-to-Speech API.")
            text_to_convert = st.text_area("Text to convert to speech:", value=default_text)
            
            if st.button("Convert to Speech"):
                with st.spinner("Converting text to speech..."):
                    try:
                        audio_content = text_to_speech(text_to_convert, st.session_state["credentials"])
                        st.success("Conversion complete!")
                        st.audio(audio_content, format="audio/mp3")
                    except Exception as e:
                        st.error(f"Error during text-to-speech conversion: {str(e)}")

if __name__ == "__main__":
    main()
