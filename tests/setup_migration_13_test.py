import sqlite3
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import KAIKKI_EL_FILE, PROCESSED_DIR, DICT_DIR

def setup_test_data():
    # Ensure directories exist
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DICT_DIR.mkdir(parents=True, exist_ok=True)

    # 0. Create Beta Code Mappings (Minimal)
    beta_to_uni = {
        "a": "α", "b": "β", "g": "γ", "d": "δ", "e": "ε", "z": "ζ", "h": "η", "q": "θ",
        "i": "ι", "k": "κ", "l": "λ", "m": "μ", "n": "ν", "c": "ξ", "o": "ο", "p": "π",
        "r": "ρ", "s": "σ", "t": "τ", "u": "υ", "f": "φ", "x": "χ", "y": "ψ", "w": "ω",
        "j": "ς",
        ")": "\u0313", "/": "\u0301", "(": "\u0314", "\\": "\u0300", "=": "\u0342", "|": "\u0345"
    }
    # Inverse mapping
    uni_to_beta = {v: k for k, v in beta_to_uni.items()}
    # Add pre-composed chars for test if needed
    uni_to_beta.update({
        "ά": "a/", "έ": "e/", "ή": "h/", "ί": "i/", "ό": "o/", "ύ": "u/", "ώ": "w/",
        "ἄ": "a)/", "ἀ": "a)/", # Minimal approximation
    })

    with open(DICT_DIR / "beta_code_to_unicode.json", "w", encoding="utf-8") as f:
        json.dump(beta_to_uni, f)

    with open(DICT_DIR / "unicode_to_beta_code.json", "w", encoding="utf-8") as f:
        json.dump(uni_to_beta, f)

    print(f"Created Beta Code mappings in {DICT_DIR}")

    # 1. Create Mock LSJ Entries in DB
    db_path = PROCESSED_DIR / "kombyphantike_v2.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create lsj_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lsj_entries (
            id INTEGER PRIMARY KEY,
            canonical_key TEXT UNIQUE,
            headword TEXT,
            entry_json TEXT
        )
    """)

    # Sample LSJ Entry: Anthropos
    # Beta code for ἄνθρωπος is a)/nqrwpos
    # Canonical: anqrwpoj (using j for final sigma)
    anthropos_entry = {
        "headword": "ἄνθρωπος",
        "senses": [
            {
                "id": "1",
                "definition": "man, human being",
                "citations": [
                    {
                        "author": "Hom.",
                        "work": "Il.",
                        "greek": "ἄνθρωπος",
                        "translation": "man",
                        "tier": 1
                    },
                    {
                        "author": "Pl.",
                        "work": "Rep.",
                        "greek": "ὁ ἄνθρωπος",
                        "translation": "the human",
                        "tier": 2
                    },
                    {
                         "author": "X.",
                         "work": "An.",
                         "greek": "τις ἄνθρωπος",
                         "translation": "", # No translation, should be lower priority
                         "tier": 2
                    }
                ]
            }
        ]
    }

    # Insert Anthropos
    cursor.execute("""
        INSERT OR REPLACE INTO lsj_entries (canonical_key, headword, entry_json)
        VALUES (?, ?, ?)
    """, ("anqrwpoj", "ἄνθρωπος", json.dumps(anthropos_entry, ensure_ascii=False)))

    # Sample LSJ Entry: Theos (God)
    # Beta: qeo/s -> qeos -> qeoj
    theos_entry = {
        "headword": "θεός",
        "senses": [
            {
                "id": "1",
                "definition": "god",
                "citations": [
                    {
                        "author": "Soph.",
                        "work": "Ant.",
                        "greek": "θεός",
                        "translation": "god",
                        "tier": 1
                    }
                ]
            }
        ]
    }
    cursor.execute("""
        INSERT OR REPLACE INTO lsj_entries (canonical_key, headword, entry_json)
        VALUES (?, ?, ?)
    """, ("qeoj", "θεός", json.dumps(theos_entry, ensure_ascii=False)))

    conn.commit()
    conn.close()
    print(f"Created/Updated DB at {db_path} with lsj_entries.")

    # 2. Create Mock Kaikki File
    # Entry 1: Anthropos (Modern) -> Etymology Link to ancient 'ἄνθρωπος'
    # Entry 2: Theos (Modern) -> No Etymology Link, but Fuzzy Link should work (Modern 'θεός' -> 'θεός' Ancient)
    # Entry 3: Unknown -> No link

    kaikki_data = [
        {
            "word": "άνθρωπος",
            "pos": "noun",
            "senses": [{"glosses": ["human"]}],
            "etymology_text": "From αρχαία ελληνική ἄνθρωπος.",
            "forms": [{"form": "άνθρωποι", "tags": ["plural"]}]
        },
        {
            "word": "θεός",
            "pos": "noun",
            "senses": [{"glosses": ["god"]}],
            "etymology_text": "Inherited from ancient Greek.", # No explicit word, so fuzzy match should kick in
            "forms": [{"form": "θεοί", "tags": ["plural"]}]
        },
        {
            "word": "διαδίκτυο",
            "pos": "noun",
            "senses": [{"glosses": ["internet"]}],
            "etymology_text": "Modern compound.",
            "forms": []
        }
    ]

    with open(KAIKKI_EL_FILE, "w", encoding="utf-8") as f:
        for entry in kaikki_data:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Created Mock Kaikki file at {KAIKKI_EL_FILE}")

if __name__ == "__main__":
    setup_test_data()
