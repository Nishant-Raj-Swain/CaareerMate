"""
Lightweight SQLite persistence.

Tables:
  users        - one row per WhatsApp user (phone number) + their applicant
                 profile (name/email/phone), needed to fill applications
  resumes      - resume versions (base + tailored copies), linked to a user
  applications - the application tracker; also stores which apply channel
                 was used (email / greenhouse / manual) and its target
                 (an email address or a job posting URL)
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,        -- WhatsApp phone number
    display_name TEXT,
    full_name TEXT,                  -- applicant profile, used to fill forms/emails
    email TEXT,
    phone TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,              -- 'base' or 'tailored'
    content TEXT NOT NULL,
    score REAL,
    score_feedback TEXT,
    job_description TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    job_title TEXT NOT NULL,
    company TEXT,
    job_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft',   -- draft -> ready -> applied -> failed/interview/offer/rejected
    apply_channel TEXT,               -- 'email' | 'greenhouse' | 'manual'
    apply_target TEXT,                -- recruiter email OR greenhouse job URL
    resume_id INTEGER,
    cover_letter TEXT,
    notes TEXT,                       -- e.g. failure reason
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _now():
    return datetime.now(timezone.utc).isoformat()


def upsert_user(user_id: str, display_name: str | None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (user_id, display_name, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name""",
            (user_id, display_name, _now()),
        )


def get_user(user_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def update_user_profile(user_id: str, full_name: str | None = None,
                         email: str | None = None, phone: str | None = None):
    with get_conn() as conn:
        if full_name is not None:
            conn.execute("UPDATE users SET full_name=? WHERE user_id=?", (full_name, user_id))
        if email is not None:
            conn.execute("UPDATE users SET email=? WHERE user_id=?", (email, user_id))
        if phone is not None:
            conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))


def save_resume(user_id: str, content: str, kind: str = "base",
                 score: float | None = None, score_feedback: dict | None = None,
                 job_description: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO resumes
               (user_id, kind, content, score, score_feedback, job_description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, kind, content, score,
             json.dumps(score_feedback) if score_feedback else None,
             job_description, _now()),
        )
        return cur.lastrowid


def get_latest_base_resume(user_id: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM resumes WHERE user_id=? AND kind='base'
               ORDER BY created_at DESC LIMIT 1""",
            (user_id,),
        ).fetchone()


def get_resume(resume_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()


def create_application(user_id: str, job_title: str, company: str | None,
                        job_url: str | None, resume_id: int | None = None,
                        cover_letter: str | None = None, status: str = "draft") -> int:
    with get_conn() as conn:
        now = _now()
        cur = conn.execute(
            """INSERT INTO applications
               (user_id, job_title, company, job_url, status, resume_id, cover_letter,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, job_title, company, job_url, status, resume_id, cover_letter, now, now),
        )
        return cur.lastrowid


def get_application(application_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()


def update_application(application_id: int, **fields):
    """Generic partial update, e.g. update_application(id, status='applied', apply_channel='email')."""
    if not fields:
        return
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE applications SET {set_clause} WHERE id=?",
            (*fields.values(), application_id),
        )


def list_applications(user_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM applications WHERE user_id=?
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()