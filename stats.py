import os
from db import get_pg_connection

conn = get_pg_connection()

total = conn.execute("SELECT COUNT(*) as n FROM questions").fetchone()["n"]
print(f"Всего вопросов: {total}\n")

by_topic = conn.execute("""
    SELECT tp.name as topic, COUNT(q.id) as cnt,
           MIN(q.difficulty) as mn, MAX(q.difficulty) as mx
    FROM questions q
    JOIN lessons l ON l.id = q.lesson_id
    JOIN topics tp ON tp.id = l.topic_id
    GROUP BY tp.name, tp.sort_order ORDER BY tp.sort_order
""").fetchall()
for r in by_topic:
    print(f"  {r['topic']}: {r['cnt']} вопросов, difficulty {r['mn']}–{r['mx']}")

print()
by_lesson = conn.execute("""
    SELECT l.title, l.grade_level, l.difficulty, COUNT(q.id) as cnt
    FROM questions q JOIN lessons l ON l.id = q.lesson_id
    GROUP BY l.id, l.title, l.grade_level, l.difficulty
    ORDER BY l.grade_level, l.difficulty
""").fetchall()
for r in by_lesson:
    print(f"  [{r['grade_level']} кл, diff {r['difficulty']}] {r['title']}: {r['cnt']} вопр.")

conn.close()
