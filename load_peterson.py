"""One-time script to add Peterson topic and load trial questions."""
import json
from pathlib import Path
from db import get_pg_connection

conn = get_pg_connection()

# Add Peterson topic
row = conn.execute(
    "INSERT INTO topics (name, icon, sort_order) VALUES (?, ?, ?) "
    "ON CONFLICT (name) DO UPDATE SET icon = EXCLUDED.icon RETURNING id",
    ("Петерсон", "📖", 4),
).fetchone()
topic_id = row["id"]
conn.commit()
print(f"Topic 'Петерсон' id={topic_id}")

# Add peterson tag
conn.execute(
    "INSERT INTO tags (topic_id, name) VALUES (?, ?) "
    "ON CONFLICT (name) DO UPDATE SET topic_id = EXCLUDED.topic_id",
    (topic_id, "петерсон"),
)
conn.commit()
tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", ("петерсон",)).fetchone()
tag_id = tag_row["id"]
print(f"Tag 'петерсон' id={tag_id}")

# Load lesson
data = json.loads(Path("lessons/grade4_peterson_trial.json").read_text(encoding="utf-8"))
lesson_row = conn.execute(
    "INSERT INTO lessons (topic_id, title, intro_content, difficulty, grade_level) "
    "VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING RETURNING id",
    (topic_id, data["title"], "", 1, 4),
).fetchone()

if lesson_row is None:
    print("Lesson already exists — skipping questions")
else:
    lesson_id = lesson_row["id"]
    count = 0
    for q in data["questions"]:
        q_row = conn.execute(
            "INSERT INTO questions (lesson_id, text, question_type, options, correct_answer, explanation, difficulty) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (lesson_id, q["text"], "multiple_choice",
             json.dumps(q["options"], ensure_ascii=False),
             q["correct_answer"], q["explanation"], q["difficulty"]),
        ).fetchone()
        conn.execute(
            "INSERT INTO question_tags (question_id, tag_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (q_row["id"], tag_id),
        )
        count += 1
    conn.commit()
    print(f"Loaded {count} questions. topic_id={topic_id}")

conn.close()
print("Done!")
