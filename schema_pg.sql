-- PostgreSQL schema for Adaptive Learning System

CREATE TABLE IF NOT EXISTS students (
    id         SERIAL PRIMARY KEY,
    name       TEXT    NOT NULL,
    grade      INTEGER NOT NULL DEFAULT 7,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topics (
    id         SERIAL PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    icon       TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
    id          SERIAL PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS lessons (
    id                SERIAL PRIMARY KEY,
    topic_id          INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title             TEXT    NOT NULL,
    title_kz          TEXT    NOT NULL DEFAULT '',
    intro_content     TEXT    NOT NULL DEFAULT '',
    intro_content_kz  TEXT    NOT NULL DEFAULT '',
    difficulty        INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    grade_level       INTEGER NOT NULL DEFAULT 7,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id              SERIAL PRIMARY KEY,
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    text            TEXT    NOT NULL,
    text_kz         TEXT    NOT NULL DEFAULT '',
    question_type   TEXT    NOT NULL DEFAULT 'multiple_choice',
    options         TEXT,
    options_kz      TEXT,
    correct_answer  TEXT    NOT NULL,
    explanation     TEXT,
    explanation_kz  TEXT    NOT NULL DEFAULT '',
    difficulty      INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS question_tags (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id)      ON DELETE CASCADE,
    PRIMARY KEY (question_id, tag_id)
);

CREATE TABLE IF NOT EXISTS student_attempts (
    id                SERIAL PRIMARY KEY,
    student_id        INTEGER   NOT NULL REFERENCES students(id),
    question_id       INTEGER   NOT NULL REFERENCES questions(id),
    lesson_session_id TEXT      NOT NULL,
    answer_given      TEXT      NOT NULL,
    is_correct        SMALLINT  NOT NULL CHECK (is_correct IN (0, 1)),
    attempted_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attempts_student
    ON student_attempts (student_id, attempted_at DESC);

CREATE TABLE IF NOT EXISTS student_tag_mastery (
    student_id     INTEGER   NOT NULL REFERENCES students(id),
    tag_id         INTEGER   NOT NULL REFERENCES tags(id),
    total_attempts INTEGER   NOT NULL DEFAULT 0,
    correct_count  INTEGER   NOT NULL DEFAULT 0,
    mastery_score  REAL      NOT NULL DEFAULT 0.5,
    last_updated   TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (student_id, tag_id)
);
