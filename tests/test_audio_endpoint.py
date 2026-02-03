import sys
from unittest.mock import MagicMock

# Mock heavy dependencies to avoid import errors and slow loading
sys.modules["pandas"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# Mock src.kombyphantike module
mock_engine_module = MagicMock()
sys.modules["src.kombyphantike"] = mock_engine_module
mock_engine_module.KombyphantikeEngine = MagicMock()

# Now import app
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from src.api import app
import base64
import json
import pytest

client = TestClient(app)

@pytest.mark.asyncio
async def test_speak_endpoint():
    # Mock the generate_audio function to avoid network calls and verify contract
    with patch("src.api.generate_audio", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = "SGVsbG8gV29ybGQ=" # "Hello World" in base64

        # Define a sample text
        payload = {"text": "Καλημέρα κόσμε"}

        # Send POST request
        response = client.post("/speak", json=payload)

        # Assert status code
        assert response.status_code == 200

        # Assert JSON structure
        json_response = response.json()
        assert "audio_data" in json_response
        assert json_response["audio_data"].startswith("data:audio/mp3;base64,")

        # Extract base64 part
        b64_str = json_response["audio_data"].split(",")[1]

        # Assert expected mock value
        assert b64_str == "SGVsbG8gV29ybGQ="

        # Verify mock called
        mock_generate.assert_called_once_with("Καλημέρα κόσμε")
