import sys
from unittest.mock import MagicMock, AsyncMock, patch
import base64
import json

# Mock heavy dependencies to avoid import errors and slow loading
sys.modules["pandas"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["elevenlabs"] = MagicMock()
sys.modules["elevenlabs.client"] = MagicMock()

# Mock src.kombyphantike module
mock_engine_module = MagicMock()
sys.modules["src.kombyphantike"] = mock_engine_module
mock_engine_module.KombyphantikeEngine = MagicMock()

# Now import app
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

@patch("src.api.generate_audio", new_callable=AsyncMock)
def test_speak_endpoint(mock_generate_audio):
    # Setup mock
    # Return a valid base64 string (e.g., of "dummy mp3")
    mock_generate_audio.return_value = base64.b64encode(b"dummy mp3 content").decode("utf-8")

    # Define a sample text
    payload = {"text": "Καλημέρα κόσμε"}

    # Send POST request
    response = client.post("/speak", json=payload)

    # Assert status code
    assert response.status_code == 200

    # Assert JSON structure
    json_response = response.json()
    assert "audio_data" in json_response

    # Assert Base64 validity
    data_uri = json_response["audio_data"]
    assert isinstance(data_uri, str)
    assert data_uri.startswith("data:audio/mp3;base64,")

    b64_str = data_uri.split(",")[1]
    assert len(b64_str) > 0

    # Try decoding to check if it's valid base64
    try:
        decoded = base64.b64decode(b64_str)
        # Check if it looks like an MP3 (or our dummy content)
        assert len(decoded) > 0
        assert decoded == b"dummy mp3 content"
    except Exception as e:
        assert False, f"Failed to decode base64 audio: {e}"
