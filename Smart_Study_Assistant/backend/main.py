from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import (
    AskRequest, AskResponse,
    SummaryResponse,
    TaskRequest, TaskResponse,
    FlashcardsResponse,
    QuizResponse,
)
from backend.storage import save_document, load_documents, clear_documents, UPLOAD_DIR
from backend.document_service import save_uploaded_file, extract_text, clean_text
from backend.retrieval_service import retrieve_relevant_context
from backend.ai_service import answer_question, summarize_notes, generate_study_plan
from backend.flashcard_service import generate_flashcards_from_doc
from backend.quiz_service import generate_quiz_from_doc


app = FastAPI(
    title="AI-Powered Smart Study Assistant",
    description="LLM-based study assistant with document summarization, Q&A, study planning, flashcards, and quizzes.",
    version="2.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "AI-Powered Smart Study Assistant API is running.",
        "version": "2.1.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed = [".txt", ".pdf", ".docx"]

    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail="Only .txt, .pdf, and .docx files are supported."
        )

    try:
        path = await save_uploaded_file(file, UPLOAD_DIR)
        text = clean_text(extract_text(path))

        if not text:
            raise HTTPException(
                status_code=400,
                detail="No readable text found in document."
            )

        doc = save_document(file.filename, text)

        return {
            "message": "Document uploaded and processed successfully.",
            "document_id": doc["id"],
            "filename": doc["filename"],
            "characters_extracted": len(text)
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/documents")
def list_documents():
    docs = load_documents()
    return [
        {
            "id": doc["id"],
            "filename": doc["filename"],
            "characters": len(doc.get("text", ""))
        }
        for doc in docs
    ]


@app.delete("/documents")
def delete_all_documents():
    clear_documents()
    return {"message": "All uploaded document records have been cleared."}


# ---------------------------------------------------------------------
# Q&A / Summary / Study Plan (unchanged behavior)
# ---------------------------------------------------------------------

@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest):
    docs = load_documents()
    context = ""

    if payload.use_uploaded_docs and docs:
        context = retrieve_relevant_context(payload.question, docs)

    answer = answer_question(payload.question, context)

    return AskResponse(
        answer=answer,
        context_used=context[:1800] if context else None
    )


@app.post("/summarize", response_model=SummaryResponse)
def summarize_all_documents():
    docs = load_documents()

    if not docs:
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded yet."
        )

    combined_text = "\n\n".join([doc["text"] for doc in docs])
    summary = summarize_notes(combined_text)

    return SummaryResponse(summary=summary)


@app.post("/tasks", response_model=TaskResponse)
def create_tasks(payload: TaskRequest):
    plan = generate_study_plan(payload.topic, payload.days)
    return TaskResponse(study_plan=plan)


# ---------------------------------------------------------------------
# Flashcards & Quiz
# GET + query params, matching the frontend's fetch calls and
# returning fully parsed JSON (not raw LLM text).
# ---------------------------------------------------------------------

@app.get("/flashcards", response_model=FlashcardsResponse)
def get_flashcards(
    document_id: int = Query(..., description="ID of the uploaded document to generate flashcards from"),
    num_cards: int = Query(10, ge=1, le=30, description="Number of flashcards to generate")
):
    result = generate_flashcards_from_doc(document_id, num_cards)

    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@app.get("/quiz", response_model=QuizResponse)
def get_quiz(
    document_id: int = Query(..., description="ID of the uploaded document to generate a quiz from"),
    num_questions: int = Query(5, ge=1, le=20, description="Number of quiz questions to generate")
):
    result = generate_quiz_from_doc(document_id, num_questions)

    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    return result
