from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start = max(end - overlap, start + 1)

    return chunks


def retrieve_relevant_context(question: str, documents: List[Dict], top_k: int = 4) -> str:
    chunks = []

    for doc in documents:
        for chunk in chunk_text(doc.get("text", "")):
            chunks.append({
                "filename": doc.get("filename", "Unknown"),
                "text": chunk
            })

    if not chunks:
        return ""

    corpus = [item["text"] for item in chunks]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000
    )

    matrix = vectorizer.fit_transform(corpus + [question])

    question_vector = matrix[-1]
    doc_vectors = matrix[:-1]

    scores = cosine_similarity(question_vector, doc_vectors).flatten()
    ranked_indices = scores.argsort()[::-1][:top_k]

    selected = []

    for idx in ranked_indices:
        if scores[idx] > 0:
            selected.append(
                f"Source: {chunks[idx]['filename']}\n"
                f"Relevance score: {scores[idx]:.3f}\n"
                f"{chunks[idx]['text']}"
            )

    return "\n\n---\n\n".join(selected)