import json
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_FILE = DATA_DIR / "uploaded_docs.json"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
if not DB_FILE.exists():
    DB_FILE.write_text("[]", encoding="utf-8")

def load_documents() -> List[Dict]:
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

def save_document(filename: str, text: str) -> Dict:
    docs = load_documents()
    doc = {"id": len(docs) + 1, "filename": filename, "text": text}
    docs.append(doc)
    DB_FILE.write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")
    return doc

def clear_documents() -> None:
    DB_FILE.write_text("[]", encoding="utf-8")
