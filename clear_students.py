"""Очистка всех данных студентов. Уроки и вопросы не трогаем."""
from db import get_pg_connection

conn = get_pg_connection()

conn.execute("DELETE FROM student_attempts")
conn.execute("DELETE FROM student_tag_mastery")
conn.execute("DELETE FROM students")
# Сброс счётчика — следующий студент получит id=1
conn.execute("ALTER SEQUENCE students_id_seq RESTART WITH 1")
conn.commit()
conn.close()
print("Done — all student records cleared, sequence reset to 1.")
