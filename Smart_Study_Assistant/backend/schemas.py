from pydantic import BaseModel, Field
from typing import List, Optional


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2)
    use_uploaded_docs: bool = True


class AskResponse(BaseModel):
    answer: str
    context_used: Optional[str] = None


class SummaryResponse(BaseModel):
    summary: str


class TaskRequest(BaseModel):
    topic: str = Field(..., min_length=2)
    days: int = Field(default=7, ge=1, le=30)


class TaskResponse(BaseModel):
    study_plan: str


# ---------------- Flashcards ----------------

class Flashcard(BaseModel):
    id: int
    question: str
    answer: str


class FlashcardsResponse(BaseModel):
    document_id: int
    filename: str
    flashcards: List[Flashcard]


# ---------------- Quiz ----------------

class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[str]
    answer: str


class QuizResponse(BaseModel):
    document_id: int
    filename: str
    quiz: List[QuizQuestion]
