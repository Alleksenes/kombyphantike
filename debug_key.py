import os
from pathlib import Path
from dotenv import load_dotenv

print("--- DIAGNOSTIC MODE ---")
print(f"Current Working Directory: {os.getcwd()}")

# 1. Check if file exists
env_path = Path(".env")
if env_path.exists():
    print(f"✅ .env file FOUND at: {env_path.absolute()}")

    # 2. Check content (First 20 chars to verify format)
    try:
        content = env_path.read_text(encoding="utf-8")
        print("--- CONTENT PREVIEW ---")
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "GOOGLE_API_KEY" in line:
                print(f"Line {i+1}: {line[:20]}... (Key hidden)")
            else:
                print(f"Line {i+1}: {line}")
        print("-----------------------")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
else:
    print(f"❌ .env file NOT FOUND in {os.getcwd()}")

# 3. Load it
print("Attempting load_dotenv()...")
load_dotenv()

# 4. Check Variable
key = os.getenv("GOOGLE_API_KEY")
if key:
    print(f"✅ SUCCESS: Variable loaded! Value starts with: {key[:5]}...")
else:
    print("❌ FAILURE: .env loaded, but GOOGLE_API_KEY is None.")
    print("Possible causes:")
    print("1. Syntax error in .env (spaces around =?)")
    print("2. File encoding issue (UTF-8 with BOM?)")
