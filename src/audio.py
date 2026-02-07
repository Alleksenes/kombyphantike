import os
import logging
import base64
from elevenlabs.client import ElevenLabs

logger = logging.getLogger("audio")


def generate_audio(text: str) -> str:
    """
    Generates audio using the ElevenLabs v1.0+ SDK and returns a Base64 Data URI.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not found in environment variables.")
        raise ValueError("ElevenLabs API Key is missing.")

    try:
        # Initialize Client
        client = ElevenLabs(api_key=api_key)

        # Generate Audio (Returns an iterator)
        audio_stream = client.text_to_speech.convert(
            text=text,
            voice_id="21m00Tcm4TlvDq8ikWAM",  # "Rachel" (Default) - Change to a Greek voice ID if you have one
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        # Consume stream
        audio_bytes = b"".join(audio_stream)

        # Encode
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return f"data:audio/mp3;base64,{audio_base64}"

    except Exception as e:
        logger.error(f"ElevenLabs generation failed: {e}")
        # Detailed logging for debugging
        if hasattr(e, "body"):
            logger.error(f"API Response: {e.body}")
        raise e
