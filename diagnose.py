from db import get_pg_connection

conn = get_pg_connection()

print("=== Students ===")
for s in conn.execute("SELECT id, name, grade FROM students ORDER BY id").fetchall():
    print(f"  id={s['id']} name={s['name']} grade={s['grade']}")

print("\n=== Lessons by grade_level ===")
for g in conn.execute("SELECT grade_level, COUNT(*) as cnt FROM lessons GROUP BY grade_level ORDER BY grade_level").fetchall():
    print(f"  grade_level={g['grade_level']}: {g['cnt']} lessons")

print("\n=== Questions per grade ===")
for g in conn.execute("""
    SELECT l.grade_level, COUNT(q.id) as cnt
    FROM questions q JOIN lessons l ON l.id = q.lesson_id
    GROUP BY l.grade_level ORDER BY l.grade_level
""").fetchall():
    print(f"  grade {g['grade_level']}: {g['cnt']} questions")

conn.close()
