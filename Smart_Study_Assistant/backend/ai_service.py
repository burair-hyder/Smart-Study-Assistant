import os
import json
import re
import random
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip().replace("models/", "")


def _fallback_answer(prompt: str) -> str:
    return (
        "## Gemini API Key Missing\n\n"
        "Add your Gemini API key in the `.env` file and restart the backend.\n\n"
        "```env\n"
        "GEMINI_API_KEY=your_key_here\n"
        "GEMINI_MODEL=gemini-2.0-flash\n"
        "```\n\n"
        f"### Request Preview\n\n{prompt[:800]}"
    )


def _parse_retry_seconds(error_text: str):
    match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", error_text)
    if match:
        return int(match.group(1))
    return None


def _is_quota_error(error_text: str) -> bool:
    lowered = error_text.lower()
    return "429" in error_text or "quota" in lowered or "resourceexhausted" in lowered


def _quota_error_message(error_text: str) -> str:
    retry_seconds = _parse_retry_seconds(error_text)
    retry_line = (
        f"Google says you can retry in about **{retry_seconds} seconds**.\n\n"
        if retry_seconds else ""
    )

    return (
        "## Daily AI Quota Reached\n\n"
        f"Your Gemini API key has hit its free-tier request limit for "
        f"`{GEMINI_MODEL}`. This is a limit on Google's side, not a bug in "
        "the app — it counts every request to that model across the whole "
        "project, regardless of how many documents are involved.\n\n"
        f"{retry_line}"
        "**Options:**\n"
        "- Wait for the daily quota to reset and try again later\n"
        f"- Switch to a different model with more daily headroom by setting "
        "`GEMINI_MODEL` in your `.env` file (e.g. a Flash-Lite variant)\n"
        "- Enable billing on your Google AI Studio / Cloud project for higher limits"
    )


def call_llm(system_prompt: str, user_prompt: str) -> str:
    if not GEMINI_API_KEY:
        return _fallback_answer(user_prompt)

    try:
        genai.configure(api_key=GEMINI_API_KEY)

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt
        )

        response = model.generate_content(
            user_prompt,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.9,
                "max_output_tokens": 8192
            }
        )

        return response.text or "No response generated."

    except Exception as exc:
        error_text = str(exc)

        if _is_quota_error(error_text):
            return _quota_error_message(error_text)

        return (
            "## Gemini Error\n\n"
            "Gemini could not generate a response.\n\n"
            f"**Error:** `{error_text}`"
        )


def answer_question(question: str, context: str = "") -> str:
    system_prompt = (
        "You are a Smart Study Assistant for university students. "
        "Answer clearly and completely. Use Markdown formatting. "
        "Keep the answer structured but not overly long."
    )

    user_prompt = f"""
Question:
{question}

Relevant Study Material:
{context if context else "No uploaded study material was provided."}

Give the answer in this format:

## Direct Answer
Write a clear answer.

## Explanation
Explain step by step.

## Example
Give one simple example.

## Exam Points
Give 5 bullet points.

## Quick Revision
Give a short 2-line revision.
"""

    return call_llm(system_prompt, user_prompt)


def summarize_notes(text: str) -> str:
    system_prompt = (
        "You are an academic summarization assistant. "
        "You must complete every requested section. "
        "Keep each section concise. Do not stop after the overview."
    )

    user_prompt = f"""
Summarize the following study material.

Rules:
- Complete ALL sections.
- Keep points short.
- Do not write very long paragraphs.
- Do not skip any section.

Use this exact format:

## Short Overview
Write 3 lines.

## Main Concepts
Give 7 concise bullet points.

## Important Terms
Create a short table with 6 terms only.

| Term | Meaning |
|---|---|

## Step-by-Step Understanding
Give 6 numbered steps.

## Exam-Focused Points
Give 6 bullet points.

## 5 Revision Questions
Give exactly 5 questions.

Study Material:
{text[:8000]}
"""

    return call_llm(system_prompt, user_prompt)


def generate_study_plan(topic: str, days: int) -> str:
    system_prompt = (
        "You are an academic planning assistant. "
        "You must generate a complete study plan for all requested days. "
        "Keep table cells short so the full plan is completed."
    )

    user_prompt = f"""
Create a complete {days}-day study plan for:

{topic}

Important rules:
- You MUST include all {days} days.
- Do not stop after Day 1.
- Keep every table cell short.
- Use only 1 short sentence per cell.
- Do not put long bullet lists inside table cells.

Use this exact format:

## Study Plan Overview
Write 2 to 3 lines.

## Daily Plan

| Day | Focus Area | What to Study | Practice Task | Revision Task |
|---|---|---|---|---|

Fill the table from Day 1 to Day {days}.

## Final Preparation Tips
Give 5 concise bullet points.
"""

    return call_llm(system_prompt, user_prompt)


# =====================================================================
# Flashcards & Quiz — return PARSED structured data (list of dicts),
# not raw LLM text, so the frontend can render them directly as JSON.
# =====================================================================

def _extract_json_array(raw: str):
    """Try hard to pull a valid JSON array out of an LLM response,
    even if it wrapped it in markdown fences or added commentary."""
    if not raw:
        return None

    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        snippet = cleaned[start:end + 1]
        try:
            data = json.loads(snippet)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return None

    return None


def _split_sentences(text: str):
    sentences = re.split(r"(?<=[.!?])\s+", text or "")
    return [s.strip() for s in sentences if len(s.strip()) > 25]


def generate_flashcards(text: str, num_cards: int = 10):
    """Returns a list of {'id', 'question', 'answer'} dicts."""
    text = (text or "").strip()
    if not text:
        return []

    # No key configured: skip the LLM call entirely. Otherwise call_llm's
    # fallback echoes the prompt text back (which contains our own JSON
    # example), and that would get misread as a real AI response.
    if not GEMINI_API_KEY:
        cards = _fallback_flashcards(text, num_cards)
        final = cards[:num_cards]
        return [{"id": i + 1, **card} for i, card in enumerate(final)]

    system_prompt = (
        "You are a flashcard generator for students. "
        "Respond with ONLY a valid JSON array and no other text, markdown, or commentary."
    )
    user_prompt = f"""Create exactly {num_cards} study flashcards from the material below.

Return ONLY valid JSON in this exact shape (no markdown fences, no explanation):
[
  {{"question": "short question here", "answer": "concise answer here"}}
]

Study Material:
{text[:8000]}
"""

    raw = call_llm(system_prompt, user_prompt)
    parsed = _extract_json_array(raw)

    cards = []
    if parsed:
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            if question and answer:
                cards.append({"question": question, "answer": answer})

    if not cards:
        cards = _fallback_flashcards(text, num_cards)

    final = cards[:num_cards]
    return [{"id": i + 1, **card} for i, card in enumerate(final)]


def _fallback_flashcards(text: str, num_cards: int):
    """Used when no API key is set, or the model output couldn't be parsed.
    Builds simple but usable flashcards directly from the document text
    so the feature never just breaks."""
    cards = []

    if not GEMINI_API_KEY:
        cards.append({
            "question": "AI setup needed",
            "answer": "Add a valid GEMINI_API_KEY to your .env file to unlock "
                       "AI-generated flashcards. These are basic auto-generated "
                       "cards from your document in the meantime."
        })

    sentences = _split_sentences(text)
    remaining = max(num_cards - len(cards), 0)

    for sentence in sentences[:remaining]:
        preview = sentence[:90] + ("..." if len(sentence) > 90 else "")
        cards.append({
            "question": f"Explain this point from your notes: \"{preview}\"",
            "answer": sentence
        })

    if not cards:
        cards.append({
            "question": "No content available",
            "answer": "Upload a document with more readable text to generate flashcards."
        })

    return cards


def generate_quiz(text: str, num_questions: int = 5):
    """Returns a list of {'id', 'question', 'options', 'answer'} dicts."""
    text = (text or "").strip()
    if not text:
        return []

    # No key configured: skip the LLM call entirely (see note in
    # generate_flashcards above for why).
    if not GEMINI_API_KEY:
        questions = _fallback_quiz(text, num_questions)
        final = questions[:num_questions]
        return [{"id": i + 1, **q} for i, q in enumerate(final)]

    system_prompt = (
        "You are a multiple-choice quiz generator for students. "
        "Respond with ONLY a valid JSON array and no other text, markdown, or commentary."
    )
    user_prompt = f"""Create exactly {num_questions} multiple-choice quiz questions from the material below.

Return ONLY valid JSON in this exact shape (no markdown fences, no explanation):
[
  {{"question": "question text", "options": ["option A", "option B", "option C", "option D"], "answer": "the correct option, copied exactly from options"}}
]

Each question must have exactly 4 options and exactly one correct answer that
matches one of the option strings exactly.

Study Material:
{text[:8000]}
"""

    raw = call_llm(system_prompt, user_prompt)
    parsed = _extract_json_array(raw)

    questions = []
    if parsed:
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            options = item.get("options", [])
            answer = str(item.get("answer", "")).strip()

            if not (question and isinstance(options, list) and len(options) >= 2 and answer):
                continue

            clean_options = [str(o).strip() for o in options if str(o).strip()]
            if answer not in clean_options:
                continue

            questions.append({
                "question": question,
                "options": clean_options,
                "answer": answer
            })

    if not questions:
        questions = _fallback_quiz(text, num_questions)

    final = questions[:num_questions]
    return [{"id": i + 1, **q} for i, q in enumerate(final)]


def _fallback_quiz(text: str, num_questions: int):
    """Used when no API key is set, or the model output couldn't be parsed."""
    questions = []

    if not GEMINI_API_KEY:
        questions.append({
            "question": "AI setup needed — what should you do?",
            "options": [
                "Add a valid GEMINI_API_KEY to the .env file",
                "Restart your computer",
                "Delete the document",
                "Nothing, this is normal"
            ],
            "answer": "Add a valid GEMINI_API_KEY to the .env file"
        })

    sentences = _split_sentences(text)
    remaining = max(num_questions - len(questions), 0)

    for i in range(remaining):
        if i >= len(sentences):
            break

        correct = sentences[i][:90]
        distractor_pool = [s[:90] for j, s in enumerate(sentences) if j != i]
        random.shuffle(distractor_pool)
        distractors = distractor_pool[:3]
        while len(distractors) < 3:
            distractors.append("None of the above")

        options = distractors + [correct]
        random.shuffle(options)

        questions.append({
            "question": "Which statement accurately reflects your notes?",
            "options": options,
            "answer": correct
        })

    if not questions:
        questions.append({
            "question": "No content available",
            "options": ["Upload more text", "N/A", "N/A", "N/A"],
            "answer": "Upload more text"
        })

    return questions
