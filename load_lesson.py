"""
Load a lesson JSON file into the adaptive learning database.

Usage:
    python load_lesson.py lessons/math_linear_equations.json
    python load_lesson.py lessons/logic_patterns.json
    python load_lesson.py lessons/*.json        # bulk load
"""

import json
import sys
from pathlib import Path
from adaptive_engine import DB_PATH, SCHEMA_PATH, get_connection


def load_lesson(path: Path, conn) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))

    # ── 1. Ensure topic exists ──────────────────────────────────
    topic_name = data["topic"]
    conn.execute(
        "INSERT OR IGNORE INTO topics (name) VALUES (?)", (topic_name,)
    )
    topic_id = conn.execute(
        "SELECT id FROM topics WHERE name = ?", (topic_name,)
    ).fetchone()["id"]

    # ── 2. Ensure all tags exist ────────────────────────────────
    all_tags: set[str] = set(data.get("tags", []))
    for q in data["questions"]:
        all_tags.update(q.get("tags", []))

    tag_id_map: dict[str, int] = {}
    for tag_name in all_tags:
        conn.execute(
            "INSERT OR IGNORE INTO tags (topic_id, name) VALUES (?, ?)",
            (topic_id, tag_name),
        )
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (tag_name,)
        ).fetchone()
        tag_id_map[tag_name] = row["id"]

    # ── 3. Insert lesson ────────────────────────────────────────
    cur = conn.execute(
        """
        INSERT INTO lessons (topic_id, title, intro_content, difficulty)
        VALUES (?, ?, ?, ?)
        """,
        (topic_id, data["title"], data["intro_text"], data["difficulty"]),
    )
    lesson_id = cur.lastrowid

    # ── 4. Insert questions ─────────────────────────────────────
    inserted_questions = 0
    for q in data["questions"]:
        options_json = json.dumps(
            [f"{k}) {v}" for k, v in q["options"].items()],
            ensure_ascii=False,
        )
        cur = conn.execute(
            """
            INSERT INTO questions
                (lesson_id, text, question_type, options,
                 correct_answer, explanation, difficulty)
            VALUES (?, ?, 'multiple_choice', ?, ?, ?, ?)
            """,
            (
                lesson_id,
                q["text"],
                options_json,
                q["correct"],          # stores the letter: 'A','B','C','D'
                q["explanation"],
                q["difficulty"],
            ),
        )
        q_id = cur.lastrowid
        inserted_questions += 1

        # Lesson-level tags + question-specific tags
        q_tags = set(data.get("tags", [])) | set(q.get("tags", []))
        for tag_name in q_tags:
            conn.execute(
                "INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?, ?)",
                (q_id, tag_id_map[tag_name]),
            )

    return {
        "lesson_id": lesson_id,
        "title": data["title"],
        "topic": topic_name,
        "questions": inserted_questions,
        "tags": list(all_tags),
    }


def main(paths: list[Path]) -> None:
    conn = get_connection(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    results = []
    with conn:
        for p in paths:
            result = load_lesson(p, conn)
            results.append(result)

    print(f"\nLoaded {len(results)} lesson(s) into {DB_PATH}\n")
    for r in results:
        print(f"  [{r['topic']}] '{r['title']}'")
        print(f"    lesson_id={r['lesson_id']}, questions={r['questions']}")
        print(f"    tags: {', '.join(sorted(r['tags']))}")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_lesson.py <lesson.json> [lesson2.json ...]")
        sys.exit(1)

    lesson_paths = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            lesson_paths.extend(sorted(p.glob("*.json")))
        elif p.exists():
            lesson_paths.append(p)
        else:
            print(f"Warning: {arg} not found, skipping")

    lesson_paths = [p for p in lesson_paths if not p.name.startswith("_")]
    main(lesson_paths)
