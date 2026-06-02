"""
api/index.py — FastAPI application for Adaptive Learning System.

All routes are prefixed /api/* so Vercel can route them here
while serving static HTML from the project root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

# Make sibling modules importable from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

TEMPLATES = Path(__file__).parent.parent / "templates"

def _html(name: str) -> HTMLResponse:
    return HTMLResponse(content=(TEMPLATES / name).read_text(encoding="utf-8"))

from adaptive_engine import (
    get_connection,
    get_next_lesson,
    record_attempt,
    get_mastery_report,
)
from explain_mistake import (
    QuestionContext,
    explain_mistake_stream_async,
    _MODEL,
    _system_block,
    _initial_context_text,
)

import anthropic

app = FastAPI(title="Adaptive Learning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ─────────────────────────────────────────────

class AttemptRequest(BaseModel):
    student_id: int = 1
    question_id: int
    answer_given: str
    lesson_session_id: str


class TutorStartRequest(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    user_answer: str
    explanation: str
    lesson_title: str = ""
    tags: List[str] = []


class TutorReplyRequest(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    user_answer: str
    explanation: str
    lesson_title: str = ""
    tags: List[str] = []
    history: List[dict]   # [{role, content}] — client holds the state
    student_message: str
    turn: int = 0         # how many tutor turns so far


# ── Routes ────────────────────────────────────────────────────

@app.get("/")
def serve_index():
    return _html("index.html")

@app.get("/lesson.html")
@app.get("/lesson")
def serve_lesson():
    return _html("lesson.html")

@app.get("/dashboard.html")
@app.get("/dashboard")
def serve_dashboard():
    return _html("dashboard.html")

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/lesson")
def lesson(student_id: int = 1, topic_id: Optional[int] = None, n: int = 10):
    conn = get_connection()
    try:
        plan = get_next_lesson(student_id, topic_id, n, conn=conn)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        conn.close()

    return {
        "session_id": plan.session_id,
        "weak_tags": plan.weak_tags,
        "mastery_summary": plan.mastery_summary,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "options": q.options,
                "question_type": q.question_type,
                "lesson_title": q.lesson_title,
                "intro_content": q.intro_content,
                "explanation": q.explanation,
                "difficulty": q.difficulty,
                "tags": q.tags,
            }
            for q in plan.questions
        ],
    }


@app.post("/api/attempt")
def attempt(data: AttemptRequest):
    conn = get_connection()
    try:
        result = record_attempt(
            data.student_id,
            data.question_id,
            data.answer_given,
            data.lesson_session_id,
            conn=conn,
        )
    finally:
        conn.close()

    return {
        "is_correct": result.is_correct,
        "correct_answer": result.correct_answer,
        "explanation": result.explanation,
    }


@app.get("/api/mastery")
def mastery(student_id: int = 1):
    conn = get_connection()
    try:
        report = get_mastery_report(student_id, conn=conn)
    finally:
        conn.close()
    return report


@app.post("/api/tutor/start")
async def tutor_start(data: TutorStartRequest):
    """Open Socratic dialogue — streams the tutor's first question token by token."""
    ctx = QuestionContext(
        text=data.question_text,
        options=data.options,
        correct_answer=data.correct_answer,
        user_answer=data.user_answer,
        explanation=data.explanation,
        lesson_title=data.lesson_title,
        tags=data.tags,
    )

    async def generate():
        try:
            async for token in explain_mistake_stream_async(ctx):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'token': f'[Ошибка: {e}]'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/tutor/reply")
async def tutor_reply(data: TutorReplyRequest):
    """Continue the Socratic dialogue with the student's reply."""
    ctx = QuestionContext(
        text=data.question_text,
        options=data.options,
        correct_answer=data.correct_answer,
        user_answer=data.user_answer,
        explanation=data.explanation,
        lesson_title=data.lesson_title,
        tags=data.tags,
    )

    async def generate():
        # After MAX_TURNS, reveal the answer directly (no LLM call)
        if data.turn >= 6:
            reveal = (
                f"Ничего страшного — давай разберём вместе!\n\n"
                f"Правильный ответ: {ctx.correct_answer}\n\n"
                f"{ctx.explanation}\n\n"
                f"Попробуй решить похожую задачу — и у тебя всё получится!"
            )
            yield f"data: {json.dumps({'token': reveal, 'revealed': True})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Build messages payload: initial context + conversation history + new reply
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _initial_context_text(ctx),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]
        for msg in data.history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": data.student_message})

        try:
            client = anthropic.AsyncAnthropic()
            async with client.messages.stream(
                model=_MODEL,
                max_tokens=512,
                system=_system_block(),
                messages=messages,
            ) as stream:
                async for token in stream.text_stream:
                    yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'token': f'[Ошибка: {e}]'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
