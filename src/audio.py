import os
import base64
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY"))

def generate_audio(text: str) -> str:
    try:
        # Synchronous generator
        audio_generator = client.text_to_speech.convert(
            voice_id="21m00Tcm4TlvDq8ikWAM",
            model_id="eleven_multilingual_v2",
            text=text
        )
        audio_bytes = b"".join(audio_generator)
        return base64.b64encode(audio_bytes).decode('utf-8')
    except Exception as e:
        print(f"Audio Error: {e}")
        raise e