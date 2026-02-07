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
def test_speak_single_word(mock_generate_audio):
    # Setup mock
    mock_generate_audio.return_value = base64.b64encode(b"dummy mp3 content").decode("utf-8")

    # Define a sample text (single word)
    payload = {"text": "άνθρωπος"}

    # Send POST request
    response = client.post("/speak", json=payload)

    # Assert status code
    assert response.status_code == 200

    # Assert JSON structure
    json_response = response.json()
    assert "audio_data" in json_response

    # Verify mock was called correctly
    mock_generate_audio.assert_called_once_with("άνθρωπος")

@patch("src.api.generate_audio", new_callable=AsyncMock)
def test_speak_sentence(mock_generate_audio):
    # Setup mock
    mock_generate_audio.return_value = base64.b64encode(b"dummy mp3 content").decode("utf-8")

    # Define a sample text (sentence)
    payload = {"text": "Καλημέρα κόσμε, τι κάνεις;"}

    # Send POST request
    response = client.post("/speak", json=payload)

    # Assert status code
    assert response.status_code == 200

    # Verify mock was called correctly
    mock_generate_audio.assert_called_once_with("Καλημέρα κόσμε, τι κάνεις;")

def test_speak_empty_string():
    # Define a sample text (empty)
    payload = {"text": ""}

    # Send POST request
    response = client.post("/speak", json=payload)

    # Assert status code - expecting 400 Bad Request
    assert response.status_code == 400
    assert response.json()["detail"] == "Text cannot be empty"

def test_speak_whitespace_string():
    # Define a sample text (whitespace)
    payload = {"text": "   "}

    # Send POST request
    response = client.post("/speak", json=payload)

    # Assert status code - expecting 400 Bad Request
    assert response.status_code == 400
    assert response.json()["detail"] == "Text cannot be empty"
