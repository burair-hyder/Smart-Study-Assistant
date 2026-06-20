from backend.storage import load_documents
from backend.ai_service import generate_flashcards


def generate_flashcards_from_doc(document_id: int, num_cards: int = 10):
    docs = load_documents()
    doc = next((d for d in docs if d["id"] == document_id), None)

    if not doc:
        return {"error": "Document not found. Please select a valid uploaded document."}

    text = doc.get("text", "")
    if not text.strip():
        return {"error": "The selected document has no readable text to generate flashcards from."}

    cards = generate_flashcards(text, num_cards)

    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "flashcards": cards
    }
