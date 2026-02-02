import json
from src.config import PROCESSED_DIR

PARADIGMS_PATH = PROCESSED_DIR / "paradigms.json"

print("--- PARADIGM FILE AUDIT ---")

if not PARADIGMS_PATH.exists():
    print(f"❌ ERROR: File not found at {PARADIGMS_PATH}")
else:
    try:
        with open(PARADIGMS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        data_type = type(data)
        print(f"File loaded successfully. Data type is: {data_type}")

        if isinstance(data, dict):
            print("✅ SUCCESS: The paradigm file is a Dictionary (Correct Structure).")
            print(f"Total lemmas indexed: {len(data)}")
            # Check a sample
            if "λέξη" in data:
                print("Sample 'λέξη' found.")
            else:
                 print("Sample 'λέξη' NOT found.")
        elif isinstance(data, list):
            print("❌ CRITICAL ERROR: The paradigm file is a List (Old Structure).")
            print("You must regenerate the file.")
        else:
            print(f"❓ UNKNOWN ERROR: The file contains an unexpected data type: {data_type}")

    except Exception as e:
        print(f"❌ ERROR: Failed to read or parse the JSON file: {e}")