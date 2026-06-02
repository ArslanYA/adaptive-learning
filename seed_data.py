"""
Seed the DB with topics, tags, sample lessons and questions.
Run once: python seed_data.py
"""

import json
import sqlite3
from pathlib import Path

from adaptive_engine import DB_PATH, SCHEMA_PATH, get_connection

# ── Seed payload ──────────────────────────────────────────────

TOPICS = [
    {"name": "Математика", "icon": "➗", "sort_order": 1},
    {"name": "Логика",      "icon": "🧩", "sort_order": 2},
    {"name": "Английский",  "icon": "🇬🇧", "sort_order": 3},
]

TAGS = [
    # Математика
    ("Математика", "натуральные-числа"),
    ("Математика", "дроби"),
    ("Математика", "проценты"),
    ("Математика", "уравнения"),
    ("Математика", "геометрия-периметр"),
    ("Математика", "геометрия-площадь"),
    # Логика
    ("Логика", "логика-последовательности"),
    ("Логика", "логика-аналогии"),
    ("Логика", "логика-множества"),
    ("Логика", "логика-истина-ложь"),
    # Английский
    ("Английский", "en-vocabulary"),
    ("Английский", "en-grammar-tenses"),
    ("Английский", "en-grammar-articles"),
    ("Английский", "en-reading"),
]

# Format: (topic, lesson_title, intro_md, questions_list)
# Each question: (text, type, options_list|None, correct_answer, explanation, difficulty, tag_names)
LESSONS = [
    (
        "Математика",
        "Обыкновенные дроби",
        """## Дроби — краткое повторение

**Дробь** записывается как числитель / знаменатель.

Правила:
- Чтобы **сложить** дроби с одним знаменателем, сложи числители: 1/5 + 2/5 = 3/5
- Чтобы **сложить** дроби с разными знаменателями, найди НОК, приведи к нему.
- Сокращение: 4/6 → 2/3 (делим обе части на 2).
- **Смешанная дробь**: 1½ = 3/2

> Быстрая проверка: умножь числитель первой на знаменатель второй и наоборот.
""",
        [
            (
                "Сколько будет 1/4 + 2/4?",
                "multiple_choice",
                ["A) 3/8", "B) 3/4", "C) 1/2", "D) 2/4"],
                "B",
                "Знаменатели одинаковые — складываем числители: 1+2=3, итого 3/4.",
                1,
                ["дроби"],
            ),
            (
                "Сократите дробь 8/12.",
                "multiple_choice",
                ["A) 4/6", "B) 2/3", "C) 3/4", "D) 1/2"],
                "B",
                "НОД(8,12)=4. 8÷4=2, 12÷4=3. Ответ: 2/3.",
                1,
                ["дроби"],
            ),
            (
                "Чему равно 3/5 − 1/5?",
                "multiple_choice",
                ["A) 2/5", "B) 2/10", "C) 4/5", "D) 1/5"],
                "A",
                "Знаменатели равны: 3−1=2, итого 2/5.",
                1,
                ["дроби"],
            ),
            (
                "Переведите смешанную дробь 2¾ в неправильную.",
                "multiple_choice",
                ["A) 9/4", "B) 11/4", "C) 8/4", "D) 10/4"],
                "B",
                "2×4 + 3 = 11. Ответ: 11/4.",
                2,
                ["дроби"],
            ),
            (
                "1/3 + 1/4 = ?",
                "multiple_choice",
                ["A) 2/7", "B) 7/12", "C) 1/6", "D) 5/12"],
                "B",
                "НОК(3,4)=12. 4/12 + 3/12 = 7/12.",
                2,
                ["дроби"],
            ),
        ],
    ),
    (
        "Математика",
        "Проценты",
        """## Проценты — краткое повторение

**Процент** — сотая часть числа.

Формулы:
- Найти X% от числа N: N × X / 100
- Сколько % составляет A от B: (A / B) × 100
- Число N составляет X% от неизвестного M: M = N × 100 / X
""",
        [
            (
                "Сколько составляет 20% от 150?",
                "multiple_choice",
                ["A) 20", "B) 25", "C) 30", "D) 35"],
                "C",
                "150 × 20 / 100 = 30.",
                1,
                ["проценты"],
            ),
            (
                "Цена товара 400 тенге. Скидка 25%. Сколько стоит товар?",
                "multiple_choice",
                ["A) 100", "B) 300", "C) 350", "D) 375"],
                "B",
                "25% от 400 = 100. 400 − 100 = 300.",
                2,
                ["проценты"],
            ),
            (
                "40 — это сколько % от 200?",
                "multiple_choice",
                ["A) 10%", "B) 15%", "C) 20%", "D) 25%"],
                "C",
                "(40 / 200) × 100 = 20%.",
                2,
                ["проценты"],
            ),
        ],
    ),
    (
        "Логика",
        "Числовые последовательности",
        """## Числовые последовательности

Найди закономерность и продолжи ряд.

Типичные закономерности:
- Арифметическая прогрессия (каждый раз прибавляем одно число): 2, 5, 8, 11 → +3
- Геометрическая прогрессия (умножаем): 3, 6, 12, 24 → ×2
- Чередование двух правил: 1, 2, 4, 5, 7, 8, … → +1, +2, +1, +2…
""",
        [
            (
                "Продолжите ряд: 3, 7, 11, 15, __",
                "multiple_choice",
                ["A) 17", "B) 18", "C) 19", "D) 20"],
                "C",
                "Каждый раз прибавляем 4: 15 + 4 = 19.",
                1,
                ["логика-последовательности"],
            ),
            (
                "Продолжите ряд: 2, 4, 8, 16, __",
                "multiple_choice",
                ["A) 24", "B) 28", "C) 32", "D) 36"],
                "C",
                "Каждый раз умножаем на 2: 16 × 2 = 32.",
                1,
                ["логика-последовательности"],
            ),
            (
                "Найди пропущенное число: 1, 4, 9, __, 25",
                "multiple_choice",
                ["A) 12", "B) 14", "C) 16", "D) 18"],
                "C",
                "Это квадраты: 1², 2², 3², 4²=16, 5²=25.",
                2,
                ["логика-последовательности"],
            ),
            (
                "Ряд: 100, 50, 25, __. Что дальше?",
                "multiple_choice",
                ["A) 10", "B) 12.5", "C) 15", "D) 20"],
                "B",
                "Делим на 2: 25 ÷ 2 = 12.5.",
                2,
                ["логика-последовательности"],
            ),
        ],
    ),
    (
        "Логика",
        "Логические высказывания",
        """## Истина и ложь в логике

В логике высказывание — это утверждение, которое может быть **истинным** или **ложным**.

Основные операции:
| Знак | Смысл | Истина, если… |
|------|-------|----------------|
| И (AND) | оба верны | оба истинны |
| ИЛИ (OR) | хотя бы одно | хотя бы одно истинно |
| НЕ (NOT) | отрицание | исходное ложно |
""",
        [
            (
                "«7 > 5» И «3 < 2». Это высказывание...",
                "multiple_choice",
                ["A) Истинно", "B) Ложно"],
                "B",
                "«7 > 5» — истина, «3 < 2» — ложь. Истина И Ложь = Ложь.",
                1,
                ["логика-истина-ложь"],
            ),
            (
                "«4 = 4» ИЛИ «10 < 0». Это высказывание...",
                "multiple_choice",
                ["A) Истинно", "B) Ложно"],
                "A",
                "«4=4» истинно. Истина ИЛИ что угодно = Истина.",
                1,
                ["логика-истина-ложь"],
            ),
        ],
    ),
    (
        "Английский",
        "Present Simple vs Present Continuous",
        """## Present Simple vs Present Continuous

**Present Simple** — регулярные действия, факты.
> She *works* every day.

**Present Continuous** — действие происходит прямо сейчас.
> She *is working* right now.

Слова-подсказки:
- always, usually, every day → Simple
- now, at the moment, look! → Continuous
""",
        [
            (
                "Choose the correct form: 'He ___ (play) football every Saturday.'",
                "multiple_choice",
                ["A) plays", "B) is playing", "C) play", "D) played"],
                "A",
                "Every Saturday = регулярное действие → Present Simple: he plays.",
                1,
                ["en-grammar-tenses"],
            ),
            (
                "Choose: 'Look! The dog ___ (run) in the garden.'",
                "multiple_choice",
                ["A) runs", "B) is running", "C) run", "D) ran"],
                "B",
                "Look! = прямо сейчас → Present Continuous: is running.",
                1,
                ["en-grammar-tenses"],
            ),
            (
                "Which sentence is correct?",
                "multiple_choice",
                [
                    "A) I am usually eating breakfast at 7.",
                    "B) I usually eat breakfast at 7.",
                    "C) I usually eating breakfast at 7.",
                    "D) I am usually eat breakfast at 7.",
                ],
                "B",
                "Usually → Present Simple. Правильно: I usually eat.",
                1,
                ["en-grammar-tenses"],
            ),
            (
                "She ___ (not/like) coffee.",
                "multiple_choice",
                ["A) doesn't likes", "B) don't like", "C) doesn't like", "D) isn't like"],
                "C",
                "She → does/doesn't + V1 (без -s). Doesn't like.",
                2,
                ["en-grammar-tenses"],
            ),
            (
                "___ they ___ (watch) TV now?",
                "multiple_choice",
                ["A) Do / watch", "B) Are / watching", "C) Is / watching", "D) Do / watching"],
                "B",
                "Now → Continuous. They → are + V-ing. Are they watching?",
                2,
                ["en-grammar-tenses"],
            ),
        ],
    ),
    (
        "Английский",
        "Articles: a / an / the / —",
        """## Артикли в английском

| Артикль | Когда используем |
|---------|-----------------|
| **a**   | первое упоминание, перед согласным звуком |
| **an**  | первое упоминание, перед гласным звуком |
| **the** | конкретный предмет, уже упомянутый |
| **—**   | множественное число неопределённо / имена / города |

Примеры: *a cat, an apple, the sun, — dogs are friendly*
""",
        [
            (
                "I saw ___ elephant at the zoo.",
                "multiple_choice",
                ["A) a", "B) an", "C) the", "D) —"],
                "B",
                "Elephant начинается с гласного звука → an elephant.",
                1,
                ["en-grammar-articles"],
            ),
            (
                "___ Moon is very bright tonight.",
                "multiple_choice",
                ["A) A", "B) An", "C) The", "D) —"],
                "C",
                "Moon — единственный объект, конкретный → the Moon.",
                1,
                ["en-grammar-articles"],
            ),
            (
                "She is ___ doctor.",
                "multiple_choice",
                ["A) a", "B) an", "C) the", "D) —"],
                "A",
                "Doctor начинается с согласного → a doctor (профессия, первое упоминание).",
                1,
                ["en-grammar-articles"],
            ),
        ],
    ),
]


# ── DB init & seeding ─────────────────────────────────────────

def seed():
    conn = get_connection(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # Clear content tables so re-seeding is idempotent
    conn.execute("DELETE FROM student_tag_mastery")
    conn.execute("DELETE FROM student_attempts")
    conn.execute("DELETE FROM question_tags")
    conn.execute("DELETE FROM questions")
    conn.execute("DELETE FROM lessons")
    conn.execute("DELETE FROM tags")
    conn.execute("DELETE FROM topics")
    conn.execute("DELETE FROM students")

    # Topics
    topic_id_map: dict[str, int] = {}
    for t in TOPICS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO topics (name, icon, sort_order) VALUES (?,?,?)",
            (t["name"], t["icon"], t["sort_order"]),
        )
        row = conn.execute("SELECT id FROM topics WHERE name=?", (t["name"],)).fetchone()
        topic_id_map[t["name"]] = row["id"]

    # Tags
    tag_id_map: dict[str, int] = {}
    for topic_name, tag_name in TAGS:
        conn.execute(
            "INSERT OR IGNORE INTO tags (topic_id, name) VALUES (?,?)",
            (topic_id_map[topic_name], tag_name),
        )
        row = conn.execute("SELECT id FROM tags WHERE name=?", (tag_name,)).fetchone()
        tag_id_map[tag_name] = row["id"]

    # Lessons + Questions
    for topic_name, lesson_title, intro, questions in LESSONS:
        cur = conn.execute(
            "INSERT INTO lessons (topic_id, title, intro_content) VALUES (?,?,?)",
            (topic_id_map[topic_name], lesson_title, intro),
        )
        lesson_id = cur.lastrowid

        for text, qtype, options, answer, explanation, diff, tag_names in questions:
            cur = conn.execute(
                """INSERT INTO questions
                   (lesson_id, text, question_type, options, correct_answer, explanation, difficulty)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    lesson_id, text, qtype,
                    json.dumps(options, ensure_ascii=False) if options else None,
                    answer, explanation, diff,
                ),
            )
            q_id = cur.lastrowid
            for tag_name in tag_names:
                conn.execute(
                    "INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?,?)",
                    (q_id, tag_id_map[tag_name]),
                )

    # Demo student
    conn.execute(
        "INSERT OR IGNORE INTO students (id, name, grade) VALUES (1,'Алибек',7)"
    )

    conn.commit()
    conn.close()
    print(f"[OK] Database seeded at {DB_PATH}")
    print(f"  Topics: {list(topic_id_map.keys())}")
    print(f"  Tags:   {list(tag_id_map.keys())}")


if __name__ == "__main__":
    seed()
