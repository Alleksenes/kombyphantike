import base64
from google.cloud import texttospeech

_client = None

def get_client():
    global _client
    if _client is None:
        _client = texttospeech.TextToSpeechAsyncClient()
    return _client

async def generate_audio(text: str, voice: str = "el-GR-Wavenet-A") -> str:
    """
    Generates audio from text using Google Cloud Text-to-Speech (Async) and returns it as a Base64 string.
    """
    client = get_client()

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code and the specific voice
    voice_params = texttospeech.VoiceSelectionParams(
        language_code="el-GR",
        name=voice
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = await client.synthesize_speech(
        input=synthesis_input, voice=voice_params, audio_config=audio_config
    )

    # Encode to base64
    base64_audio = base64.b64encode(response.audio_content).decode("utf-8")

    return base64_audio
