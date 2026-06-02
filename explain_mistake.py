"""
explain_mistake.py
==================
Socratic mistake explainer for the adaptive learning system.

Uses Claude claude-opus-4-8 to guide a 7th-grade student (Kazakhstan curriculum)
toward discovering their own logical error — never by stating the answer directly.

Public API
----------
explain_mistake(ctx)          → str          — one-shot Socratic opening question
explain_mistake_stream(ctx)   → Iterator[str]— same, token-by-token for UI streaming
SocraticTutor                               — stateful multi-turn dialogue class
AsyncSocraticTutor                          — async version for web frameworks

Caching
-------
The system prompt is marked cache_control="ephemeral" so it is re-used across
all calls (~90% token savings on the stable prefix). The initial question context
is also cached within multi-turn sessions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator

import anthropic

# ── Model ─────────────────────────────────────────────────────────────────────

_MODEL = "claude-opus-4-8"

# ── System prompt (cached — byte-stable across all sessions) ──────────────────

_SYSTEM_PROMPT = """\
Ты — Сократ-наставник для ученика 7 класса школы Казахстана.
Твоя ЕДИНСТВЕННАЯ задача — помочь ребёнку САМОМУ найти свою ошибку через вопросы.

═══ ЖЁСТКИЕ ЗАПРЕТЫ ═══
✗ Никогда не называй правильный ответ — ни прямо, ни косвенно.
✗ Не говори «ответ начинается на...», «это не А и не В», не давай подсказок типа «теплее/холоднее».
✗ Не задавай два вопроса сразу — только один.
✗ Не говори «Ты ошибся» — говори «Давай проверим вместе».

═══ СТРАТЕГИЯ (2–4 шага) ═══
Шаг 1 — Что понял из условия?
  «Что нам известно из этой задачи?»
Шаг 2 — Какое правило применил?
  «Какую формулу / правило ты использовал?»
Шаг 3 — Проверь свои вычисления.
  «Попробуй выполнить этот шаг ещё раз — что получается?»
Шаг 4 — Пусть сам скажет ответ.
  «Итак, если ..., то чему равно ...?»

═══ ТОН ═══
• Тёплый, ободряющий — ты разговариваешь с 12-13-летним ребёнком.
• Хвали усилие, а не результат: «Хорошая попытка! А теперь посмотрим...»
• Язык: отвечай на том языке, на котором написан вопрос ученика — русский, қазақша или English.
• Длина ответа: 2–4 предложения максимум — один вопрос в конце.\
"""


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class QuestionContext:
    """
    All information about a question where the student made a mistake.
    Passed to the tutor so it knows what error to guide the student through.
    """
    text: str                           # the question text
    options: list[str]                  # ["A) ...", "B) ...", ...]
    correct_answer: str                 # letter: 'A', 'B', 'C', or 'D'
    user_answer: str                    # letter the student chose (wrong)
    explanation: str                    # DB explanation — used only as last resort
    lesson_title: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class TutorMessage:
    """Single turn in the Socratic dialogue."""
    role: str       # 'user' | 'assistant'
    content: str


# ── Prompt builders ────────────────────────────────────────────────────────────

def _initial_context_text(ctx: QuestionContext) -> str:
    """
    Craft the hidden context block given to the LLM only.
    The student never sees this — it tells the tutor what mistake was made
    and instructs it to start questioning, not explaining.
    """
    options_block = "\n".join(f"  {o}" for o in ctx.options)
    tags_block = ", ".join(ctx.tags) if ctx.tags else "—"
    return (
        f"Ученик допустил ошибку. Ты должен начать Сократовский диалог.\n\n"
        f"━━━ ВОПРОС ━━━\n{ctx.text}\n\n"
        f"━━━ ВАРИАНТЫ ━━━\n{options_block}\n\n"
        f"━━━ СЕКРЕТНАЯ ИНФОРМАЦИЯ (только для тебя) ━━━\n"
        f"Правильный ответ: {ctx.correct_answer}\n"
        f"Ответ ученика:    {ctx.user_answer}  ← НЕВЕРНО\n\n"
        f"━━━ КОНТЕКСТ ━━━\n"
        f"Урок: {ctx.lesson_title or '—'} | Темы: {tags_block}\n\n"
        f"Начни диалог. Задай первый направляющий вопрос ученику. "
        f"НЕ раскрывай ответ — пусть ребёнок сам его найдёт."
    )


def _system_block() -> list[dict]:
    """System prompt as a cached content block."""
    return [
        {
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _extract_text(content: list) -> str:
    """Pull text from a content block list (skips thinking blocks)."""
    for block in content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


# ── One-shot functions ─────────────────────────────────────────────────────────

def explain_mistake(
    ctx: QuestionContext,
    client: anthropic.Anthropic | None = None,
) -> str:
    """
    Generate the tutor's opening Socratic question for a wrong answer.

    Returns a short string (2-4 sentences + 1 guiding question).
    Uses streaming internally to prevent HTTP timeouts on slow networks.

    Args:
        ctx:    QuestionContext describing the question and the mistake.
        client: Optional pre-built Anthropic client (reads ANTHROPIC_API_KEY
                from environment if omitted).
    """
    client = client or anthropic.Anthropic()
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _initial_context_text(ctx),
                    # Cache the context too — stable for repeated calls
                    # on the same question in a multi-turn session.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    with client.messages.stream(
        model=_MODEL,
        max_tokens=512,
        system=_system_block(),
        messages=messages,
    ) as stream:
        return _extract_text(stream.get_final_message().content)


def explain_mistake_stream(
    ctx: QuestionContext,
    client: anthropic.Anthropic | None = None,
) -> Iterator[str]:
    """
    Streaming variant — yields text tokens as they arrive.
    Ideal for word-by-word display in a frontend UI.

    Usage::
        for token in explain_mistake_stream(ctx):
            print(token, end="", flush=True)
    """
    client = client or anthropic.Anthropic()
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

    with client.messages.stream(
        model=_MODEL,
        max_tokens=512,
        system=_system_block(),
        messages=messages,
    ) as stream:
        for token in stream.text_stream:
            yield token


# ── Stateful multi-turn tutor ─────────────────────────────────────────────────

class SocraticTutor:
    """
    Multi-turn Socratic tutor for a single mistake.

    The tutor maintains conversation history and guides the student through
    2-4 Socratic steps. If the student still cannot find the answer after
    MAX_TURNS, call ``reveal()`` to show the direct explanation.

    Example::

        tutor = SocraticTutor(ctx)

        print(tutor.start())                    # tutor's opening question
        print(tutor.reply("Не знаю..."))        # student's response → next question
        print(tutor.reply("Это 2x = 8?"))       # another student attempt

        if tutor.should_give_up():
            print(tutor.reveal())               # direct explanation as last resort
    """

    MAX_TURNS = 6   # give up and reveal after this many tutor responses

    def __init__(
        self,
        ctx: QuestionContext,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.ctx = ctx
        self.client = client or anthropic.Anthropic()
        self._history: list[TutorMessage] = []
        self._tutor_turns = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> str:
        """Open the dialogue. Returns the tutor's first Socratic question."""
        response = explain_mistake(self.ctx, client=self.client)
        self._history.append(TutorMessage("assistant", response))
        self._tutor_turns += 1
        return response

    def start_stream(self) -> Iterator[str]:
        """Streaming version of ``start()`` — yields tokens."""
        chunks: list[str] = []
        for token in explain_mistake_stream(self.ctx, client=self.client):
            chunks.append(token)
            yield token
        self._history.append(TutorMessage("assistant", "".join(chunks)))
        self._tutor_turns += 1

    def reply(self, student_text: str) -> str:
        """
        Accept the student's response and return the tutor's next question.
        Each call counts as one turn toward ``MAX_TURNS``.
        """
        self._history.append(TutorMessage("user", student_text))
        response = self._call_claude()
        self._history.append(TutorMessage("assistant", response))
        self._tutor_turns += 1
        return response

    def reply_stream(self, student_text: str) -> Iterator[str]:
        """Streaming version of ``reply()``."""
        self._history.append(TutorMessage("user", student_text))
        chunks: list[str] = []
        for token in self._call_claude_stream():
            chunks.append(token)
            yield token
        self._history.append(TutorMessage("assistant", "".join(chunks)))
        self._tutor_turns += 1

    def should_give_up(self) -> bool:
        """True when MAX_TURNS is reached — caller should switch to ``reveal()``."""
        return self._tutor_turns >= self.MAX_TURNS

    def reveal(self) -> str:
        """
        Last-resort direct explanation. Uses the pre-written DB explanation,
        NOT the LLM — so it's instant, cheap, and deterministic.
        """
        return (
            f"Ничего страшного — давай разберём вместе! 🌟\n\n"
            f"Правильный ответ: **{self.ctx.correct_answer}**\n\n"
            f"{self.ctx.explanation}\n\n"
            f"Попробуй решить похожую задачу — и у тебя всё получится!"
        )

    def history(self) -> list[TutorMessage]:
        """Read-only view of the conversation so far."""
        return list(self._history)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _messages_payload(self) -> list[dict]:
        """
        Build the full messages array for the next Claude call.

        Layout:
            1. Initial context (user turn, cached)   — stable across all turns
            2. History turns (assistant / user)       — grows each round
        """
        payload: list[dict] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _initial_context_text(self.ctx),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]
        for msg in self._history:
            payload.append({"role": msg.role, "content": msg.content})
        return payload

    def _call_claude(self) -> str:
        response = self.client.messages.create(
            model=_MODEL,
            max_tokens=512,
                system=_system_block(),
            messages=self._messages_payload(),
        )
        return _extract_text(response.content)

    def _call_claude_stream(self) -> Iterator[str]:
        with self.client.messages.stream(
            model=_MODEL,
            max_tokens=512,
                system=_system_block(),
            messages=self._messages_payload(),
        ) as stream:
            yield from stream.text_stream


# ── Async variants ─────────────────────────────────────────────────────────────

async def explain_mistake_async(
    ctx: QuestionContext,
    client: anthropic.AsyncAnthropic | None = None,
) -> str:
    """Async version of ``explain_mistake`` — for FastAPI / asyncio frameworks."""
    client = client or anthropic.AsyncAnthropic()
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
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=512,
        system=_system_block(),
        messages=messages,
    ) as stream:
        msg = await stream.get_final_message()
        return _extract_text(msg.content)


async def explain_mistake_stream_async(
    ctx: QuestionContext,
    client: anthropic.AsyncAnthropic | None = None,
) -> AsyncIterator[str]:
    """Async streaming generator — yields tokens for Server-Sent Events."""
    client = client or anthropic.AsyncAnthropic()
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
    async with client.messages.stream(
        model=_MODEL,
        max_tokens=512,
        system=_system_block(),
        messages=messages,
    ) as stream:
        async for token in stream.text_stream:
            yield token


class AsyncSocraticTutor:
    """
    Async multi-turn Socratic tutor — drop-in replacement for ``SocraticTutor``
    for use inside ``async def`` handlers (FastAPI, aiohttp, etc.).
    """

    MAX_TURNS = 6

    def __init__(
        self,
        ctx: QuestionContext,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self.ctx = ctx
        self.client = client or anthropic.AsyncAnthropic()
        self._history: list[TutorMessage] = []
        self._tutor_turns = 0

    async def start(self) -> str:
        response = await explain_mistake_async(self.ctx, client=self.client)
        self._history.append(TutorMessage("assistant", response))
        self._tutor_turns += 1
        return response

    async def start_stream(self) -> AsyncIterator[str]:
        chunks: list[str] = []
        async for token in explain_mistake_stream_async(self.ctx, client=self.client):
            chunks.append(token)
            yield token
        self._history.append(TutorMessage("assistant", "".join(chunks)))
        self._tutor_turns += 1

    async def reply(self, student_text: str) -> str:
        self._history.append(TutorMessage("user", student_text))
        response = await self._call_claude()
        self._history.append(TutorMessage("assistant", response))
        self._tutor_turns += 1
        return response

    async def reply_stream(self, student_text: str) -> AsyncIterator[str]:
        self._history.append(TutorMessage("user", student_text))
        chunks: list[str] = []
        async with self.client.messages.stream(
            model=_MODEL,
            max_tokens=512,
                system=_system_block(),
            messages=self._messages_payload(),
        ) as stream:
            async for token in stream.text_stream:
                chunks.append(token)
                yield token
        self._history.append(TutorMessage("assistant", "".join(chunks)))
        self._tutor_turns += 1

    def should_give_up(self) -> bool:
        return self._tutor_turns >= self.MAX_TURNS

    def reveal(self) -> str:
        return (
            f"Ничего страшного — давай разберём вместе! 🌟\n\n"
            f"Правильный ответ: **{self.ctx.correct_answer}**\n\n"
            f"{self.ctx.explanation}\n\n"
            f"Попробуй решить похожую задачу — и у тебя всё получится!"
        )

    def _messages_payload(self) -> list[dict]:
        payload: list[dict] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _initial_context_text(self.ctx),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ]
        for msg in self._history:
            payload.append({"role": msg.role, "content": msg.content})
        return payload

    async def _call_claude(self) -> str:
        async with self.client.messages.stream(
            model=_MODEL,
            max_tokens=512,
                system=_system_block(),
            messages=self._messages_payload(),
        ) as stream:
            msg = await stream.get_final_message()
            return _extract_text(msg.content)
