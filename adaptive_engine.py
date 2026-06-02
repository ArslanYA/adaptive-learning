"""
Adaptive Learning Engine
========================
Core logic for selecting the next personalized lesson based on
a student's per-tag mastery history.
"""

from __future__ import annotations

import json
import math
import os
import random
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).parent / "adaptive_learning.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# How many days before an attempt's influence decays to ~37 % (1/e)
MASTERY_DECAY_DAYS = 21

# Questions with no history get this prior (slight uncertainty → revisit)
UNKNOWN_TAG_PRIOR = 0.5

# Exploration bonus multiplier for questions whose tags were never seen
EXPLORATION_BONUS = 1.4

# Minimum weight floor so every question has a non-zero chance
MIN_WEIGHT = 0.05

# 4 difficulty levels; level N+1 unlocks when mastery on level N >= this threshold
_UNLOCK_THRESHOLD = 0.9
# Minimum attempts on a level before it can unlock the next
_MIN_ATTEMPTS_TO_UNLOCK = 10


# ── Data classes ──────────────────────────────────────────────

@dataclass
class Question:
    id: int
    lesson_id: int
    lesson_title: str
    lesson_title_kz: str
    intro_content: str
    text: str
    text_kz: str
    question_type: str
    options: list[str]
    options_kz: list[str]
    correct_answer: str
    explanation: str
    explanation_kz: str
    difficulty: int
    tags: list[str] = field(default_factory=list)


@dataclass
class LessonPlan:
    session_id: str
    questions: list[Question]
    weak_tags: list[str]
    mastery_summary: dict[str, float]
    current_level: int = 1        # highest unlocked difficulty (1–4)


@dataclass
class AttemptResult:
    is_correct: bool
    correct_answer: str | None   # None when student was right
    explanation: str | None      # None when student was right


# ── DB helpers ────────────────────────────────────────────────

def get_connection(db_path: Path = DB_PATH):
    """Return a database connection.

    Uses PostgreSQL (via PGConn wrapper) when DATABASE_URL is set,
    otherwise falls back to local SQLite for development.
    """
    if os.environ.get("DATABASE_URL"):
        from db import get_pg_connection
        return get_pg_connection()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables if they don't exist yet (SQLite local dev only)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()


# ── Mastery calculation ───────────────────────────────────────

def compute_tag_mastery(
    conn: sqlite3.Connection,
    student_id: int,
    lookback_days: int = MASTERY_DECAY_DAYS * 6,
) -> dict[int, float]:
    """
    Compute per-tag mastery for a student using exponential time decay.

    Each attempt contributes weight = exp(-days_ago / MASTERY_DECAY_DAYS).
    mastery = Σ(weight * is_correct) / Σ(weight)

    This means a wrong answer from 3 weeks ago matters much less than
    one from yesterday — the student is rewarded for recent improvement.

    Returns:
        {tag_id: mastery_score}  — scores are in [0.0, 1.0]
    """
    # Pass as datetime so psycopg2 sends it typed; sqlite3 accepts datetime too
    cutoff = datetime.now() - timedelta(days=lookback_days)

    rows = conn.execute(
        """
        SELECT qt.tag_id, sa.is_correct, sa.attempted_at
        FROM   student_attempts sa
        JOIN   question_tags qt ON qt.question_id = sa.question_id
        WHERE  sa.student_id = ?
          AND  sa.attempted_at >= ?
        ORDER  BY sa.attempted_at DESC
        """,
        (student_id, cutoff),
    ).fetchall()

    if not rows:
        return {}

    now = datetime.now()
    weighted_correct: dict[int, float] = defaultdict(float)
    weighted_total: dict[int, float] = defaultdict(float)

    for row in rows:
        tag_id = row["tag_id"]
        is_correct = bool(row["is_correct"])
        # psycopg2 returns TIMESTAMP as datetime; sqlite3 returns str
        raw = row["attempted_at"]
        attempted_at = raw if isinstance(raw, datetime) else datetime.fromisoformat(raw)

        days_ago = (now - attempted_at).total_seconds() / 86_400
        weight = math.exp(-days_ago / MASTERY_DECAY_DAYS)

        weighted_total[tag_id] += weight
        if is_correct:
            weighted_correct[tag_id] += weight

    return {
        tag_id: weighted_correct[tag_id] / total
        for tag_id, total in weighted_total.items()
        if total > 0
    }


def _update_mastery_cache(
    conn: sqlite3.Connection,
    student_id: int,
    tag_ids: list[int],
    is_correct: bool,
) -> None:
    """Fast incremental update of the mastery cache after one answer."""
    mastery = compute_tag_mastery(conn, student_id)
    for tag_id in tag_ids:
        score = mastery.get(tag_id, UNKNOWN_TAG_PRIOR)
        # Simple upsert — compute_tag_mastery already used full history
        conn.execute(
            """
            INSERT INTO student_tag_mastery
                   (student_id, tag_id, total_attempts, correct_count, mastery_score, last_updated)
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT (student_id, tag_id) DO UPDATE SET
                total_attempts = student_tag_mastery.total_attempts + 1,
                correct_count  = student_tag_mastery.correct_count  + excluded.correct_count,
                mastery_score  = excluded.mastery_score,
                last_updated   = excluded.last_updated
            """,
            (student_id, tag_id, int(is_correct), round(score, 4), datetime.now()),
        )


# ── Per-level mastery ─────────────────────────────────────────

def compute_level_mastery(
    conn,
    student_id: int,
    lookback_days: int = MASTERY_DECAY_DAYS * 6,
) -> dict[int, tuple[float, int]]:
    """
    Return time-weighted mastery and attempt count per difficulty level.
    Result: {1: (mastery, attempts), 2: ..., 3: ..., 4: ...}
    mastery is None when the student has never attempted that level.
    """
    cutoff = datetime.now() - timedelta(days=lookback_days)
    rows = conn.execute(
        """
        SELECT q.difficulty, sa.is_correct, sa.attempted_at
        FROM   student_attempts sa
        JOIN   questions q ON q.id = sa.question_id
        WHERE  sa.student_id = ?
          AND  sa.attempted_at >= ?
        """,
        (student_id, cutoff),
    ).fetchall()

    now = datetime.now()
    w_correct: dict[int, float] = defaultdict(float)
    w_total:   dict[int, float] = defaultdict(float)
    counts:    dict[int, int]   = defaultdict(int)

    for row in rows:
        diff = min(max(int(row["difficulty"]), 1), 4)
        raw = row["attempted_at"]
        attempted_at = raw if isinstance(raw, datetime) else datetime.fromisoformat(raw)
        days_ago = (now - attempted_at).total_seconds() / 86_400
        w = math.exp(-days_ago / MASTERY_DECAY_DAYS)
        w_total[diff] += w
        counts[diff] += 1
        if row["is_correct"]:
            w_correct[diff] += w

    result: dict[int, tuple] = {}
    for diff in range(1, 5):
        if w_total[diff] > 0:
            result[diff] = (w_correct[diff] / w_total[diff], counts[diff])
        else:
            result[diff] = (None, 0)
    return result


def get_max_unlocked_level(level_mastery: dict) -> int:
    """
    Return the highest difficulty level the student can access.
    Level N+1 unlocks when level N mastery >= 90% with >= 10 attempts.
    Always at least level 1.
    """
    max_level = 1
    for level in range(1, 4):
        mastery, attempts = level_mastery.get(level, (None, 0))
        if mastery is not None and mastery >= _UNLOCK_THRESHOLD and attempts >= _MIN_ATTEMPTS_TO_UNLOCK:
            max_level = level + 1
        else:
            break
    return max_level


# ── Question weighting ────────────────────────────────────────

def _compute_question_weights(
    conn,
    student_id: int,
    topic_id: Optional[int],
    grade_level: Optional[int],
    mastery: dict[int, float],
    max_unlocked_level: int = 4,
) -> list[tuple[int, float]]:
    query = """
        SELECT DISTINCT q.id, q.difficulty
        FROM   questions q
        JOIN   lessons   l ON l.id = q.lesson_id
        WHERE  q.difficulty <= ?
    """
    params: list[Any] = [max_unlocked_level]
    if topic_id is not None:
        query += " AND l.topic_id = ?"
        params.append(topic_id)
    if grade_level is not None:
        query += " AND l.grade_level = ?"
        params.append(grade_level)

    rows = conn.execute(query, params).fetchall()
    question_data: list[tuple[int, int]] = [(r["id"], r["difficulty"]) for r in rows]
    if not question_data:
        return []

    question_ids = [qid for qid, _ in question_data]

    # Bulk-fetch tags for all questions in one query
    placeholders = ",".join("?" * len(question_ids))
    tag_rows = conn.execute(
        f"SELECT question_id, tag_id FROM question_tags WHERE question_id IN ({placeholders})",
        question_ids,
    ).fetchall()

    q_tags: dict[int, list[int]] = defaultdict(list)
    for row in tag_rows:
        q_tags[row["question_id"]].append(row["tag_id"])

    weights: list[tuple[int, float]] = []
    for q_id, q_diff in question_data:
        tags = q_tags.get(q_id, [])

        if not tags:
            weakness = 1.0
        else:
            weaknesses = [1.0 - mastery.get(t, UNKNOWN_TAG_PRIOR) for t in tags]
            weakness = sum(weaknesses) / len(weaknesses)
            if not any(t in mastery for t in tags):
                weakness *= EXPLORATION_BONUS

        # Boost newly-unlocked level questions to give student exposure to them
        diff_factor = 1.2 if q_diff == max_unlocked_level else 1.0

        weights.append((q_id, max(weakness * diff_factor, MIN_WEIGHT)))

    return weights


def _weighted_sample_no_replace(
    items: list[tuple[int, float]], k: int
) -> list[int]:
    """
    Sample k unique question IDs proportional to their weights.
    Falls back to the full list if fewer than k items exist.
    """
    if len(items) <= k:
        return [item[0] for item in items]

    selected: list[int] = []
    pool = list(items)

    for _ in range(k):
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        cumulative = 0.0
        for i, (q_id, w) in enumerate(pool):
            cumulative += w
            if r <= cumulative:
                selected.append(q_id)
                pool.pop(i)
                break

    return selected


# ── Public API ────────────────────────────────────────────────

def get_next_lesson(
    student_id: int,
    topic_id: Optional[int] = None,
    n_questions: int = 20,
    grade_level: Optional[int] = None,
    db_path: Path = DB_PATH,
    conn=None,
) -> LessonPlan:
    """Build the next adaptive lesson for *student_id*."""
    own_conn = conn is None
    if conn is None:
        conn = get_connection(db_path)
    try:
        mastery = compute_tag_mastery(conn, student_id)
        level_mastery = compute_level_mastery(conn, student_id)
        max_level = get_max_unlocked_level(level_mastery)
        weights = _compute_question_weights(conn, student_id, topic_id, grade_level, mastery, max_level)

        if not weights:
            raise ValueError(
                f"No questions found for student={student_id}, topic={topic_id}"
            )

        selected_ids = _weighted_sample_no_replace(weights, n_questions)

        # Fetch full question data including kz fields
        placeholders = ",".join("?" * len(selected_ids))
        rows = conn.execute(
            f"""
            SELECT q.id, q.lesson_id,
                   l.title AS lesson_title,
                   COALESCE(l.title_kz, '') AS lesson_title_kz,
                   l.intro_content,
                   q.text,
                   COALESCE(q.text_kz, '') AS text_kz,
                   q.question_type,
                   q.options,
                   q.options_kz,
                   q.correct_answer,
                   q.explanation,
                   COALESCE(q.explanation_kz, '') AS explanation_kz,
                   q.difficulty
            FROM   questions q
            JOIN   lessons   l ON l.id = q.lesson_id
            WHERE  q.id IN ({placeholders})
            """,
            selected_ids,
        ).fetchall()

        # Attach tag names
        tag_rows = conn.execute(
            f"""
            SELECT qt.question_id, t.name
            FROM   question_tags qt
            JOIN   tags t ON t.id = qt.tag_id
            WHERE  qt.question_id IN ({placeholders})
            """,
            selected_ids,
        ).fetchall()
        q_tag_names: dict[int, list[str]] = defaultdict(list)
        for r in tag_rows:
            q_tag_names[r["question_id"]].append(r["name"])

        questions = [
            Question(
                id=r["id"],
                lesson_id=r["lesson_id"],
                lesson_title=r["lesson_title"],
                lesson_title_kz=r["lesson_title_kz"],
                intro_content=r["intro_content"],
                text=r["text"],
                text_kz=r["text_kz"],
                question_type=r["question_type"],
                options=json.loads(r["options"] or "[]"),
                options_kz=json.loads(r["options_kz"] or "[]"),
                correct_answer=r["correct_answer"],
                explanation=r["explanation"] or "",
                explanation_kz=r["explanation_kz"],
                difficulty=r["difficulty"],
                tags=q_tag_names.get(r["id"], []),
            )
            for r in rows
        ]
        random.shuffle(questions)

        # Build mastery summary (tag_name → score)
        all_tags = conn.execute("SELECT id, name FROM tags").fetchall()
        tag_name_map = {r["id"]: r["name"] for r in all_tags}

        mastery_summary = {
            tag_name_map[tid]: round(score, 3)
            for tid, score in mastery.items()
            if tid in tag_name_map
        }

        # Weakest tags being targeted (top 3 by lowest mastery)
        weak_tags = [
            name
            for name, _ in sorted(mastery_summary.items(), key=lambda x: x[1])[:3]
        ]

        session_id = f"s{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return LessonPlan(
            session_id=session_id,
            questions=questions,
            weak_tags=weak_tags,
            mastery_summary=mastery_summary,
            current_level=max_level,
        )

    finally:
        if own_conn:
            conn.close()


def record_attempt(
    student_id: int,
    question_id: int,
    answer_given: str,
    lesson_session_id: str,
    db_path: Path = DB_PATH,
    conn=None,
) -> AttemptResult:
    """Persist one answer and refresh the mastery cache."""
    own_conn = conn is None
    if conn is None:
        conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT correct_answer, explanation FROM questions WHERE id = ?",
            (question_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Question {question_id} not found")

        is_correct = (
            answer_given.strip().lower() == row["correct_answer"].strip().lower()
        )

        with conn:
            conn.execute(
                """
                INSERT INTO student_attempts
                    (student_id, question_id, lesson_session_id, answer_given, is_correct)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, question_id, lesson_session_id, answer_given, int(is_correct)),
            )

            tag_ids = [
                r["tag_id"]
                for r in conn.execute(
                    "SELECT tag_id FROM question_tags WHERE question_id = ?",
                    (question_id,),
                ).fetchall()
            ]
            _update_mastery_cache(conn, student_id, tag_ids, is_correct)

        return AttemptResult(
            is_correct=is_correct,
            correct_answer=None if is_correct else row["correct_answer"],
            explanation=None if is_correct else row["explanation"],
        )
    finally:
        if own_conn:
            conn.close()


def get_mastery_report(
    student_id: int, db_path: Path = DB_PATH, conn=None
) -> list[dict]:
    """Return a sorted mastery report across all tags."""
    own_conn = conn is None
    if conn is None:
        conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT tp.name AS topic, t.name AS tag,
                   COALESCE(stm.mastery_score, 0.5) AS mastery,
                   COALESCE(stm.total_attempts, 0)  AS total_attempts,
                   COALESCE(stm.correct_count, 0)   AS correct
            FROM   tags t
            JOIN   topics tp ON tp.id = t.topic_id
            LEFT JOIN student_tag_mastery stm
                   ON stm.tag_id = t.id AND stm.student_id = ?
            ORDER  BY mastery ASC, tp.sort_order, t.name
            """,
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.close()
