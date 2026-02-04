import sys
from unittest.mock import MagicMock, AsyncMock

# Mock heavy dependencies
sys.modules["pandas"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()

# Mock google.cloud.texttospeech specifically
mock_tts = MagicMock()
mock_cloud = MagicMock()
mock_cloud.texttospeech = mock_tts
sys.modules["google.cloud"] = mock_cloud
sys.modules["google.cloud.texttospeech"] = mock_tts
sys.modules["google"] = MagicMock()

# Setup the Client mock to return a response with bytes
mock_client_instance = MagicMock()
mock_tts.TextToSpeechAsyncClient.return_value = mock_client_instance

mock_response = MagicMock()
mock_response.audio_content = b"fake_mp3_bytes"

# Async method needs AsyncMock
mock_client_instance.synthesize_speech = AsyncMock(return_value=mock_response)

# Setup constants
mock_tts.SynthesisInput = MagicMock()
mock_tts.VoiceSelectionParams = MagicMock()
mock_tts.AudioConfig = MagicMock()
mock_tts.AudioEncoding.MP3 = "MP3"

# Mock src.kombyphantike module
mock_engine_module = MagicMock()
sys.modules["src.kombyphantike"] = mock_engine_module
mock_engine_module.KombyphantikeEngine = MagicMock()

# Now import app
from fastapi.testclient import TestClient
from src.api import app
import base64
import json

client = TestClient(app)

def test_speak_endpoint():
    # Define a sample text
    payload = {"text": "Καλημέρα κόσμε"}

    # Send POST request
    response = client.post("/speak", json=payload)

    # Assert status code
    assert response.status_code == 200

    # Assert JSON structure
    json_response = response.json()
    assert "audio_data" in json_response

    # Verify call arguments
    # Note: since get_client is global, it might be called multiple times or cached.
    # We verify that synthesize_speech was called on our mock instance.
    mock_client_instance.synthesize_speech.assert_called_once()

    # Check that the voice param was set correctly
    call_args = mock_client_instance.synthesize_speech.call_args
    _, kwargs = call_args

    # Let's check VoiceSelectionParams call
    mock_tts.VoiceSelectionParams.assert_called_with(
        language_code="el-GR",
        name="el-GR-Wavenet-A"
    )

    # Assert Base64 validity of the returned fake data
    data_uri = json_response["audio_data"]
    b64_str = data_uri.split(",")[1]
    decoded = base64.b64decode(b64_str)
    assert decoded == b"fake_mp3_bytes"
