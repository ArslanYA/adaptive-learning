"""
generate_questions.py — Generates 500 questions per subject (grade 7) using Claude API.
Creates JSON files in lessons/, then calls init_pg.py to load them into PostgreSQL.

Run: python generate_questions.py
Requires: ANTHROPIC_API_KEY and DATABASE_URL environment variables
"""

import json
import os
import time
from pathlib import Path
import anthropic

client = anthropic.Anthropic()
LESSONS_DIR = Path(__file__).parent / "lessons"

# 20 topic groups × 25 questions = 500 per subject
# Format: (difficulty_level, topic_description, tags)
PLAN = {
    "Математика": [
        (1, "натуральные числа: НОД, НОК, делимость, простые числа", ["натуральные-числа"]),
        (1, "обыкновенные дроби: сложение, вычитание, умножение, деление", ["дроби"]),
        (1, "десятичные дроби: 4 действия и перевод в обыкновенные", ["дроби"]),
        (1, "проценты: нахождение процента от числа и числа по проценту", ["проценты"]),
        (1, "пропорции: составление и решение", ["натуральные-числа"]),
        (2, "линейные уравнения с одной переменной (ax + b = c)", ["уравнения"]),
        (2, "целые и рациональные числа: действия с отрицательными", ["натуральные-числа"]),
        (2, "задачи на проценты: скидки, наценки, смеси", ["проценты"]),
        (2, "степени натуральных чисел (a в степени n)", ["степени"]),
        (2, "прямоугольная система координат: точки и расстояния", ["геометрия-площадь"]),
        (3, "системы двух линейных уравнений: метод подстановки и сложения", ["уравнения"]),
        (3, "площадь и периметр: треугольник, четырёхугольники, окружность", ["геометрия-площадь", "геометрия-периметр"]),
        (3, "линейная функция y=kx+b: построение и свойства", ["уравнения"]),
        (3, "арифметический и геометрический квадратный корень", ["степени"]),
        (3, "составные текстовые задачи: движение, работа, концентрация", ["уравнения"]),
        (4, "неравенства и системы неравенств на числовой прямой", ["уравнения"]),
        (4, "описательная статистика: среднее, медиана, мода, размах", ["натуральные-числа"]),
        (4, "элементарная теория вероятностей: классическое определение", ["натуральные-числа"]),
        (4, "многошаговые комбинированные задачи повышенной сложности", ["уравнения"]),
        (4, "олимпиадные задачи 7 класса: нестандартные методы", ["уравнения"]),
    ],
    "Логика": [
        (1, "арифметические последовательности: найти следующий элемент или пропущенное число", ["логика-последовательности"]),
        (1, "простые аналогии вида A:B = C:? с числами и словами", ["логика-аналогии"]),
        (1, "найди лишнее в ряду: числа, фигуры, понятия", ["логика-аналогии"]),
        (1, "таблицы истинности: И (AND), ИЛИ (OR), НЕ (NOT)", ["логика-истина-ложь"]),
        (1, "числовые паттерны и закономерности: +, -, ×", ["логика-последовательности"]),
        (2, "геометрические прогрессии (умножение/деление на константу)", ["логика-последовательности"]),
        (2, "логические высказывания ЕСЛИ...ТО и их отрицание", ["логика-истина-ложь"]),
        (2, "диаграммы Венна: объединение, пересечение, разность множеств", ["логика-множества"]),
        (2, "задачи на упорядочивание: кто старше/быстрее/дальше", ["логика-аналогии"]),
        (2, "двухшаговые числовые паттерны (+a, ×b чередование)", ["логика-последовательности"]),
        (3, "сложные числовые последовательности с несколькими правилами", ["логика-последовательности"]),
        (3, "силлогизмы: все A есть B, некоторые B есть C → вывод", ["логика-истина-ложь"]),
        (3, "задачи на отрицание и контрпримеры к высказываниям", ["логика-истина-ложь"]),
        (3, "логические сетки 3×3: кто живёт в каком доме (метод исключения)", ["логика-множества"]),
        (3, "пространственная логика: развёртки, повороты, зеркала", ["логика-аналогии"]),
        (4, "комбинаторика: перестановки, сочетания без повторений", ["логика-комбинаторика"]),
        (4, "сложные задачи на дедукцию с 4+ условиями", ["логика-истина-ложь"]),
        (4, "многоуровневые цепочки логических умозаключений", ["логика-последовательности"]),
        (4, "задачи типа рыцари-и-лжецы (все говорят правду или лгут)", ["логика-истина-ложь"]),
        (4, "нестандартные олимпиадные задачи: парадоксы и ловушки", ["логика-комбинаторика"]),
    ],
    "Английский": [
        (1, "Present Simple: утвердительные, отрицательные, вопросительные предложения", ["en-grammar-tenses"]),
        (1, "Past Simple с правильными глаголами (-ed forms)", ["en-grammar-tenses"]),
        (1, "артикли a / an / the / без артикля: правила выбора", ["en-grammar-articles"]),
        (1, "базовая лексика: дом, школа, еда, одежда, числа от 1 до 1000", ["en-vocabulary"]),
        (1, "специальные вопросы: What, Where, When, Who, How", ["en-grammar-tenses"]),
        (2, "Present Continuous: действие происходит прямо сейчас или запланировано", ["en-grammar-tenses"]),
        (2, "Past Simple неправильные глаголы (go-went, see-saw, take-took и др.)", ["en-grammar-tenses"]),
        (2, "Future Simple (will / won't) и going to: планы и предсказания", ["en-grammar-tenses"]),
        (2, "лексика средней сложности: хобби, спорт, путешествия, природа", ["en-vocabulary"]),
        (2, "предлоги времени (in/on/at) и места (in/on/at/under/next to)", ["en-grammar-articles"]),
        (3, "Present Perfect: have/has + V3 (just, already, yet, ever, never)", ["en-grammar-tenses"]),
        (3, "модальные глаголы: can/can't (способность), must/mustn't (обязательство), should/shouldn't (совет)", ["en-grammar-modals"]),
        (3, "First Conditional: If + Present Simple, will + V", ["en-conditionals"]),
        (3, "лексика: профессии, город и инфраструктура, технологии", ["en-vocabulary"]),
        (3, "Past Continuous: was/were + V-ing и разница с Past Simple", ["en-grammar-tenses"]),
        (4, "Second Conditional: If + Past Simple, would + V (нереальные ситуации)", ["en-conditionals"]),
        (4, "Passive Voice: Present Simple Passive и Past Simple Passive", ["en-grammar-tenses"]),
        (4, "фразовые глаголы: look (up/out/after/for), make (up/out/sure), get (on/off/up)", ["en-grammar-modals"]),
        (4, "понимание письменного текста: 4-6 предложений + 5 вопросов по содержанию", ["en-reading"]),
        (4, "смешанные задачи: определи время, исправь ошибку, выбери правильную форму", ["en-grammar-tenses"]),
    ],
}

TOPIC_TITLES = {
    "Математика": {1: "Математика — Уровень 1", 2: "Математика — Уровень 2",
                   3: "Математика — Уровень 3", 4: "Математика — Уровень 4"},
    "Логика":     {1: "Логика — Уровень 1", 2: "Логика — Уровень 2",
                   3: "Логика — Уровень 3", 4: "Логика — Уровень 4"},
    "Английский": {1: "Английский — Уровень 1", 2: "Английский — Уровень 2",
                   3: "Английский — Уровень 3", 4: "Английский — Уровень 4"},
}

FILENAME_MAP = {
    ("Математика", 1): "grade7_math_lvl1.json",
    ("Математика", 2): "grade7_math_lvl2.json",
    ("Математика", 3): "grade7_math_lvl3.json",
    ("Математика", 4): "grade7_math_lvl4.json",
    ("Логика",     1): "grade7_logic_lvl1.json",
    ("Логика",     2): "grade7_logic_lvl2.json",
    ("Логика",     3): "grade7_logic_lvl3.json",
    ("Логика",     4): "grade7_logic_lvl4.json",
    ("Английский", 1): "grade7_english_lvl1.json",
    ("Английский", 2): "grade7_english_lvl2.json",
    ("Английский", 3): "grade7_english_lvl3.json",
    ("Английский", 4): "grade7_english_lvl4.json",
}


def make_prompt(subject: str, level: int, topic: str, tags: list, count: int = 25) -> str:
    level_desc = {
        1: "БАЗОВЫЙ (уровень 1/4) — простые одношаговые задачи, прямое применение правила",
        2: "СРЕДНИЙ (уровень 2/4) — 2–3 шага, требует понимания темы",
        3: "СЛОЖНЫЙ (уровень 3/4) — многошаговые задачи, анализ и синтез",
        4: "ЭКСПЕРТ (уровень 4/4) — олимпиадный уровень, нестандартные методы",
    }
    english_note = (
        "\nВАЖНО: Текст вопросов на РУССКОМ языке. Английский только внутри условия (предложения/тексты для анализа)."
        if subject == "Английский" else ""
    )
    return f"""Создай ровно {count} вопросов с множественным выбором.

Предмет: {subject} | Класс: 7 | Страна: Казахстан
Тема: {topic}
Уровень сложности: {level_desc[level]}{english_note}

Требования:
• Ровно 4 варианта: A) ... B) ... C) ... D) ...
• Один правильный ответ
• Неправильные варианты — правдоподобные ловушки (не очевидно неверные)
• Объяснение — краткий разбор решения (1–2 предложения)
• Все вопросы разные, покрывают разные аспекты темы

Верни ТОЛЬКО валидный JSON-массив (без текста до/после):
[
  {{
    "text": "Текст вопроса",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_answer": "A",
    "explanation": "Объяснение",
    "difficulty": {level},
    "tags": {json.dumps(tags, ensure_ascii=False)}
  }}
]"""


def generate_batch(subject: str, level: int, topic: str, tags: list, count: int = 25, retries: int = 3) -> list:
    prompt = make_prompt(subject, level, topic, tags, count)
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            start, end = text.find("["), text.rfind("]") + 1
            if start == -1 or end <= 0:
                raise ValueError("JSON массив не найден")
            questions = json.loads(text[start:end])
            valid = [
                q for q in questions
                if isinstance(q, dict)
                and all(k in q for k in ["text", "options", "correct_answer", "explanation", "difficulty", "tags"])
                and len(q["options"]) == 4
                and q["correct_answer"] in ["A", "B", "C", "D"]
            ]
            if len(valid) < count // 2:
                raise ValueError(f"Только {len(valid)} валидных вопросов из {len(questions)}")
            return valid
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                print(f"      Попытка {attempt + 2}/{retries}: {e}")
                time.sleep(3)
    raise RuntimeError(f"Не удалось сгенерировать после {retries} попыток: {last_err}")


def main():
    total_generated = 0

    for subject, topic_groups in PLAN.items():
        print(f"\n{'='*60}")
        print(f"  {subject}")
        print(f"{'='*60}")

        # Group by level
        by_level: dict[int, list] = {1: [], 2: [], 3: [], 4: []}
        for level, topic, tags in topic_groups:
            by_level[level].append((topic, tags))

        for level in range(1, 5):
            level_questions = []
            out_file = LESSONS_DIR / FILENAME_MAP[(subject, level)]

            # Skip if file already has questions
            if out_file.exists():
                existing = json.loads(out_file.read_text(encoding="utf-8"))
                if len(existing.get("questions", [])) >= 100:
                    print(f"  Уровень {level}: уже есть {len(existing['questions'])} вопросов, пропускаю")
                    continue

            print(f"\n  Уровень {level}:")
            for topic, tags in by_level[level]:
                print(f"    Тема: {topic[:55]}...")
                try:
                    qs = generate_batch(subject, level, topic, tags, count=25)
                    level_questions.extend(qs)
                    print(f"      ✓ {len(qs)} вопросов")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"      ✗ Ошибка: {e}")

            if not level_questions:
                print(f"  Уровень {level}: нет вопросов, пропускаю")
                continue

            lesson_data = {
                "topic": subject,
                "title": TOPIC_TITLES[subject][level],
                "grade_level": 7,
                "difficulty": level,
                "intro_content": "",
                "questions": level_questions,
            }
            out_file.write_text(json.dumps(lesson_data, ensure_ascii=False, indent=2), encoding="utf-8")
            total_generated += len(level_questions)
            print(f"  Уровень {level}: сохранено {len(level_questions)} вопросов → {out_file.name}")

    print(f"\n{'='*60}")
    print(f"Итого сгенерировано: {total_generated} вопросов")
    print(f"{'='*60}")

    # Load into DB
    print("\nЗагружаю в базу данных...")
    import subprocess
    result = subprocess.run(["python", "init_pg.py"], capture_output=True, text=True,
                            cwd=str(Path(__file__).parent))
    print(result.stdout)
    if result.returncode != 0:
        print(f"Ошибка init_pg.py:\n{result.stderr}")
    else:
        print("База данных обновлена!")


if __name__ == "__main__":
    main()
