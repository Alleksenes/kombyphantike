import io
import base64
import os
from elevenlabs.client import AsyncElevenLabs

async def generate_audio(text: str, voice: str = "Clyde") -> str:
    """
    Generates audio from text using ElevenLabs and returns it as a Base64 string.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
         raise ValueError("ELEVENLABS_API_KEY environment variable not set")

    client = AsyncElevenLabs(api_key=api_key)

    # Generate audio
    # The return type of client.generate is an AsyncIterator[bytes] when stream=True
    audio_stream = await client.generate(
        text=text,
        voice=voice,
        model="eleven_multilingual_v2",
        stream=True
    )

    # Collect bytes
    audio_data = io.BytesIO()
    async for chunk in audio_stream:
        audio_data.write(chunk)

    # Reset pointer
    audio_data.seek(0)

    # Encode to base64
    base64_audio = base64.b64encode(audio_data.read()).decode("utf-8")

    return base64_audio
