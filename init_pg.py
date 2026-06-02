"""
init_pg.py — one-time PostgreSQL setup.

Run once after connecting Neon in Vercel:
    DATABASE_URL=... python init_pg.py
"""

import json
import os
from pathlib import Path
from db import get_pg_connection

SCHEMA = Path(__file__).parent / "schema_pg.sql"

TOPICS = [
    {"name": "Математика", "icon": "➗", "sort_order": 1},
    {"name": "Логика",      "icon": "🧩", "sort_order": 2},
    {"name": "Английский",  "icon": "🇬🇧", "sort_order": 3},
]

TAGS = [
    ("Математика", "натуральные-числа"),
    ("Математика", "дроби"),
    ("Математика", "проценты"),
    ("Математика", "уравнения"),
    ("Математика", "геометрия-периметр"),
    ("Математика", "геометрия-площадь"),
    ("Логика", "логика-последовательности"),
    ("Логика", "логика-аналогии"),
    ("Логика", "логика-множества"),
    ("Логика", "логика-истина-ложь"),
    ("Английский", "en-vocabulary"),
    ("Английский", "en-grammar-tenses"),
    ("Английский", "en-grammar-articles"),
    ("Английский", "en-reading"),
]


def run_schema(conn):
    sql = SCHEMA.read_text(encoding="utf-8")
    # Execute each statement separately (psycopg2 doesn't have executescript)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    print("Schema applied.")


def seed_topics(conn) -> dict[str, int]:
    topic_ids: dict[str, int] = {}
    for t in TOPICS:
        row = conn.execute(
            """
            INSERT INTO topics (name, icon, sort_order)
            VALUES (?, ?, ?)
            ON CONFLICT (name) DO UPDATE SET icon = EXCLUDED.icon
            RETURNING id
            """,
            (t["name"], t["icon"], t["sort_order"]),
        ).fetchone()
        topic_ids[t["name"]] = row["id"]
    conn.commit()
    print(f"Topics: {topic_ids}")
    return topic_ids


def seed_tags(conn, topic_ids: dict[str, int]) -> dict[str, int]:
    tag_ids: dict[str, int] = {}
    for topic_name, tag_name in TAGS:
        row = conn.execute(
            """
            INSERT INTO tags (topic_id, name)
            VALUES (?, ?)
            ON CONFLICT (name) DO UPDATE SET topic_id = EXCLUDED.topic_id
            RETURNING id
            """,
            (topic_ids[topic_name], tag_name),
        ).fetchone()
        tag_ids[tag_name] = row["id"]
    conn.commit()
    print(f"Tags seeded: {len(tag_ids)}")
    return tag_ids


def seed_student(conn) -> int:
    row = conn.execute(
        """
        INSERT INTO students (name, grade)
        VALUES (?, 7)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        ("Алибек",),
    ).fetchone()
    if row is None:
        row = conn.execute("SELECT id FROM students WHERE name = ?", ("Алибек",)).fetchone()
    conn.commit()
    student_id = row["id"]
    print(f"Student id: {student_id}")
    return student_id


def load_lesson_json(conn, path: Path, topic_ids, tag_ids):
    data = json.loads(path.read_text(encoding="utf-8"))
    topic_name = data["topic"]
    topic_id = topic_ids.get(topic_name)
    if topic_id is None:
        print(f"  Unknown topic '{topic_name}', skipping {path.name}")
        return

    # Support both intro_content and intro_text field names
    intro = data.get("intro_content") or data.get("intro_text", "")

    row = conn.execute(
        """
        INSERT INTO lessons (topic_id, title, intro_content, difficulty)
        VALUES (?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (topic_id, data["title"], intro, data.get("difficulty", 1)),
    ).fetchone()
    if row is None:
        print(f"  Lesson '{data['title']}' already exists, skipping.")
        return
    lesson_id = row["id"]

    for q in data.get("questions", []):
        # Support both options formats:
        # dict: {"A": "text", "B": "text"} → list: ["A) text", "B) text"]
        # list: ["A) text", "B) text"]      → used as-is
        raw_opts = q.get("options", [])
        if isinstance(raw_opts, dict):
            options = [f"{k}) {v}" for k, v in raw_opts.items()]
        else:
            options = raw_opts

        # Support both correct_answer and correct field names
        correct = q.get("correct_answer") or q.get("correct", "")

        q_row = conn.execute(
            """
            INSERT INTO questions
                (lesson_id, text, question_type, options, correct_answer, explanation, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                lesson_id,
                q["text"],
                q.get("question_type", "multiple_choice"),
                json.dumps(options, ensure_ascii=False),
                correct,
                q.get("explanation", ""),
                q.get("difficulty", 1),
            ),
        ).fetchone()
        q_id = q_row["id"]

        for tag_name in q.get("tags", []):
            tid = tag_ids.get(tag_name)
            if tid:
                conn.execute(
                    "INSERT INTO question_tags (question_id, tag_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
                    (q_id, tid),
                )

    conn.commit()
    print(f"  Loaded lesson '{data['title']}' ({len(data.get('questions', []))} questions)")


def main():
    conn = get_pg_connection()
    try:
        run_schema(conn)
        topic_ids = seed_topics(conn)
        tag_ids = seed_tags(conn, topic_ids)
        seed_student(conn)

        lessons_dir = Path(__file__).parent / "lessons"
        for f in sorted(lessons_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue
            print(f"Loading {f.name}...")
            load_lesson_json(conn, f, topic_ids, tag_ids)

        # Also seed inline data from seed_data.py logic
        _seed_inline(conn, topic_ids, tag_ids)

    finally:
        conn.close()
    print("Done!")


def _seed_inline(conn, topic_ids, tag_ids):
    """Seed the sample lessons from seed_data.py inline content."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    # Import the LESSONS constant from seed_data without running its __main__
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_data", Path(__file__).parent / "seed_data.py")
    sd = importlib.util.module_from_spec(spec)
    # Monkey-patch to avoid sqlite3 import issues
    try:
        spec.loader.exec_module(sd)
        lessons = sd.LESSONS
    except Exception as e:
        print(f"  Could not load seed_data.py inline lessons: {e}")
        return

    for topic_name, title, intro_md, questions in lessons:
        topic_id = topic_ids.get(topic_name)
        if topic_id is None:
            continue
        row = conn.execute(
            """
            INSERT INTO lessons (topic_id, title, intro_content, difficulty)
            VALUES (?, ?, ?, 1)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (topic_id, title, intro_md),
        ).fetchone()
        if row is None:
            continue
        lesson_id = row["id"]

        for text, qtype, options, correct, explanation, difficulty, tags in questions:
            q_row = conn.execute(
                """
                INSERT INTO questions
                    (lesson_id, text, question_type, options, correct_answer, explanation, difficulty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    lesson_id, text, qtype,
                    json.dumps(options, ensure_ascii=False) if options else None,
                    correct, explanation, difficulty,
                ),
            ).fetchone()
            q_id = q_row["id"]
            for tag_name in tags:
                tid = tag_ids.get(tag_name)
                if tid:
                    conn.execute(
                        "INSERT INTO question_tags (question_id, tag_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
                        (q_id, tid),
                    )
        conn.commit()
        print(f"  Seeded lesson '{title}'")


if __name__ == "__main__":
    main()
