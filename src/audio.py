import io
import base64

async def generate_audio(text: str, voice: str = "el-GR-NestorasNeural") -> str:
    """
    Generates audio from text using Microsoft Edge TTS and returns it as a Base64 string.
    """
    try:
        import edge_tts
    except ImportError:
        raise ImportError(
            "The 'edge_tts' module is required for audio generation. "
            "Please install it using 'pip install edge-tts'."
        )

    communicate = edge_tts.Communicate(text, voice)

    audio_data = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])

    # Reset pointer to beginning of the stream
    audio_data.seek(0)

    # Encode to base64
    base64_audio = base64.b64encode(audio_data.read()).decode("utf-8")

    return base64_audio
