"""
Quick demo: shows how get_next_lesson and record_attempt work together.
Run: python demo.py
"""

from adaptive_engine import get_mastery_report, get_next_lesson, record_attempt
from seed_data import seed

STUDENT_ID = 1


def run_demo():
    # 1. Re-seed
    seed()

    # 2. Simulate a poor session on fractions (дроби)
    print("\n--- Simulating session 1: student struggles with drobi ---")
    plan = get_next_lesson(STUDENT_ID)
    print(f"Session {plan.session_id}  ({len(plan.questions)} questions)")

    for q in plan.questions[:5]:  # answer only first 5 to keep demo short
        # Deliberately give wrong answer for дроби questions
        wrong = q.options[2] if len(q.options) > 2 else "X"
        answer = wrong[0]  # just the letter
        result = record_attempt(STUDENT_ID, q.id, answer, plan.session_id)
        symbol = "+" if result.is_correct else "x"
        suffix = f"  (correct: {result.correct_answer})" if not result.is_correct else ""
        print(f"  {symbol} Q{q.id} [{', '.join(q.tags)}] -> gave '{answer}'{suffix}")

    # 3. Print mastery after session 1
    print("\n--- Mastery after session 1 ---")
    report = get_mastery_report(STUDENT_ID)
    for row in report:
        filled = int(row["mastery"] * 10)
        bar = "#" * filled + "." * (10 - filled)
        print(f"  [{row['topic']:12}] {row['tag']:35} {bar} {row['mastery']:.2f}  ({row['correct']}/{row['total_attempts']})")

    # 4. Get next lesson — should now favour weak tags
    print("\n--- Session 2: adaptive plan targets weak areas ---")
    plan2 = get_next_lesson(STUDENT_ID)
    print(f"Targeting weak tags: {plan2.weak_tags}")
    print("Questions selected:")
    for q in plan2.questions:
        tag_str = ', '.join(q.tags)
        safe_text = q.text[:60].encode('ascii', errors='replace').decode('ascii')
        print(f"  . [{tag_str:35}] {safe_text}")


if __name__ == "__main__":
    run_demo()
