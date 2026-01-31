import spacy
import sys

print(f"Python Executable: {sys.executable}")
try:
    print("Attempting to load 'el_core_news_lg' via shortcut...")
    nlp = spacy.load("el_core_news_lg")
    print("✅ Success via shortcut.")
except Exception as e:
    print(f"❌ Failed via shortcut: {e}")

    try:
        print("Attempting to import as module...")
        import el_core_news_lg

        print(f"✅ Module found at: {el_core_news_lg.__file__}")
        nlp = el_core_news_lg.load()
        print("✅ Success via module load.")
    except Exception as e2:
        print(f"❌ Failed via module: {e2}")
