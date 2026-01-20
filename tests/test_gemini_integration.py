import sys
import os
import json
from unittest.mock import MagicMock, patch

# Set dummy environment variable before import
os.environ["GOOGLE_API_KEY"] = "dummy"

# Patch KombyphantikeEngine to prevent it from running __init__ and exiting due to missing data
# We must patch it where it is defined or where it is imported.
# Since src.api imports it from src.kombyphantike, patching src.kombyphantike.KombyphantikeEngine is correct
# IF we do it before importing src.api
with patch("src.kombyphantike.KombyphantikeEngine") as MockEngine:
    # We mock the instance created
    MockEngine.return_value = MagicMock()

    # Import src.api inside the patch context doesn't work well because the module is cached.
    # But if this is the first import, it might work.
    # However, to be safe, we rely on sys.modules manipulation or just try importing.
    # The patch won't affect the import line inside src.api if src.api does `from src.kombyphantike import KombyphantikeEngine`
    # because that import statement gets the class object.
    # But when `engine = KombyphantikeEngine()` is called in src.api, it calls the class.
    # So if we patch the class in `src.kombyphantike`, it should work for the instantiation in `src.api`.

    from src.api import app, generate_with_gemini

from fastapi.testclient import TestClient

client = TestClient(app)

def test_generate_with_gemini_success():
    # Mock genai
    with patch("src.api.genai") as mock_genai:
        # Mock environment variable context if needed
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake_key"}):
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            # Mock response
            mock_response = MagicMock()
            mock_response.text = '```json\n[{"id": 1, "text": "result"}]\n```'
            mock_model.generate_content.return_value = mock_response

            result = generate_with_gemini("Test prompt")

            assert result == [{"id": 1, "text": "result"}]
            mock_genai.configure.assert_called_with(api_key="fake_key")
            mock_model.generate_content.assert_called_once()
            args, _ = mock_model.generate_content.call_args
            assert "Output the result strictly as a JSON list" in args[0]

def test_generate_worksheet_with_ai():
    # The global `engine` in `src.api` is already our mocked instance (or None if init failed differently).
    # But wait, inside the `with patch... import` block, `src.api` executed.
    # `src.api` executed `engine = KombyphantikeEngine()`.
    # Since `KombyphantikeEngine` was patched, `engine` in `src.api` should be a Mock.

    # Let's double check if we can access/configure it.
    from src.api import engine as api_engine

    # We want to configure the mock for this test
    # api_engine is the instance returned by MockEngine()

    if api_engine is None:
        # If it failed to init and ended up None (caught exception), we can patch it in src.api directly
        pass
    else:
        api_engine.compile_curriculum.return_value = {
            "worksheet_data": [{"id": 1, "text": "original"}],
            "instruction_text": "Do this."
        }

    # We can also patch src.api.engine directly to be sure
    mock_engine = MagicMock()
    mock_engine.compile_curriculum.return_value = {
        "worksheet_data": [{"id": 1, "text": "original"}],
        "instruction_text": "Do this."
    }

    with patch("src.api.engine", mock_engine):
        # Patch generate_with_gemini to avoid actual call
        with patch("src.api.generate_with_gemini") as mock_generate:
            mock_generate.return_value = [{"id": 1, "text": "ai_filled"}]

            response = client.post("/generate_worksheet", json={
                "theme": "war",
                "count": 5,
                "complete_with_ai": True
            })

            assert response.status_code == 200
            data = response.json()
            assert data["worksheet"] == [{"id": 1, "text": "ai_filled"}]

            # Verify generate_with_gemini was called with correct prompt structure
            mock_generate.assert_called_once()
            prompt_arg = mock_generate.call_args[0][0]
            assert "Do this." in prompt_arg
            assert "### DATA TO COMPLETE ###" in prompt_arg
            assert '"id": 1' in prompt_arg

def test_generate_worksheet_without_ai():
    mock_engine = MagicMock()
    mock_engine.compile_curriculum.return_value = {
        "worksheet_data": [{"id": 1, "text": "original"}],
        "instruction_text": "Do this."
    }

    with patch("src.api.engine", mock_engine):
        with patch("src.api.generate_with_gemini") as mock_generate:
            response = client.post("/generate_worksheet", json={
                "theme": "war",
                "count": 5,
                "complete_with_ai": False
            })

            assert response.status_code == 200
            data = response.json()
            assert data["worksheet"] == [{"id": 1, "text": "original"}]
            mock_generate.assert_not_called()

if __name__ == "__main__":
    try:
        test_generate_with_gemini_success()
        print("test_generate_with_gemini_success passed")
        test_generate_worksheet_with_ai()
        print("test_generate_worksheet_with_ai passed")
        test_generate_worksheet_without_ai()
        print("test_generate_worksheet_without_ai passed")
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
