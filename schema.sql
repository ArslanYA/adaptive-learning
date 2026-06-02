-- ============================================================
-- Adaptive Learning System — SQLite Schema
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Core reference tables ────────────────────────────────────

CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    grade       INTEGER NOT NULL DEFAULT 7,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,   -- 'Математика', 'Логика', 'Английский'
    icon        TEXT,                      -- emoji or SVG id for UI
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- Fine-grained skill tags; each belongs to one topic
CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL UNIQUE,   -- 'дроби', 'алгебра', 'логика-последовательности'
    description TEXT
);

-- ── Content tables ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lessons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id      INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL,
    -- Markdown/HTML intro shown before the 20 questions
    intro_content TEXT    NOT NULL DEFAULT '',
    difficulty    INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    text            TEXT    NOT NULL,
    -- 'multiple_choice' | 'fill_blank' | 'true_false'
    question_type   TEXT    NOT NULL DEFAULT 'multiple_choice',
    -- JSON array of strings, e.g. ["A) 1/2", "B) 2/3", "C) 3/4", "D) 5/6"]
    options         TEXT,
    -- Index into options (0-based) for MC; plain text for fill_blank
    correct_answer  TEXT    NOT NULL,
    -- Shown after a wrong answer to explain the concept
    explanation     TEXT,
    difficulty      INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5)
);

-- Many-to-many: one question can belong to several tags
CREATE TABLE IF NOT EXISTS question_tags (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id)      ON DELETE CASCADE,
    PRIMARY KEY (question_id, tag_id)
);

-- ── Tracking tables ──────────────────────────────────────────

-- Every answer a student gives is recorded here (never deleted)
CREATE TABLE IF NOT EXISTS student_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        INTEGER NOT NULL REFERENCES students(id),
    question_id       INTEGER NOT NULL REFERENCES questions(id),
    lesson_session_id TEXT    NOT NULL,   -- groups one 20-question run
    answer_given      TEXT    NOT NULL,
    is_correct        INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    attempted_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attempts_student
    ON student_attempts (student_id, attempted_at DESC);

-- ── Mastery cache ─────────────────────────────────────────────
-- Recomputed after every session; fast lookup for the scheduler.
-- mastery_score: 0.0 = never correct, 1.0 = always correct (time-weighted)
CREATE TABLE IF NOT EXISTS student_tag_mastery (
    student_id     INTEGER NOT NULL REFERENCES students(id),
    tag_id         INTEGER NOT NULL REFERENCES tags(id),
    total_attempts INTEGER NOT NULL DEFAULT 0,
    correct_count  INTEGER NOT NULL DEFAULT 0,
    -- Exponentially time-weighted success rate (see Python logic)
    mastery_score  REAL    NOT NULL DEFAULT 0.5,
    last_updated   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (student_id, tag_id)
);
