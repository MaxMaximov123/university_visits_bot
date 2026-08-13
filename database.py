import sqlite3
import os
import datetime

DB_PATH = os.environ.get("DB_PATH", "./data/attendance.db")

DEFAULT_SETTINGS = {
    "mailing_enabled": "1",
    "content_weather": "1",
    "content_jokes": "1",
    "content_tips": "1",
    "content_facts": "1",
    "content_quotes": "1",
}


def _connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS polls (
            poll_id    TEXT PRIMARY KEY,
            message_id INTEGER,
            date       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS poll_answers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id    TEXT NOT NULL,
            user_id    INTEGER NOT NULL,
            username   TEXT,
            first_name TEXT,
            option_id  INTEGER,
            updated_at TEXT NOT NULL,
            UNIQUE(poll_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS members (
            user_id    INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            last_seen  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()


def save_poll(poll_id, message_id, date_str):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO polls (poll_id, message_id, date, created_at) VALUES (?, ?, ?, ?)",
        (poll_id, message_id, date_str, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def save_answer(poll_id, user_id, username, first_name, option_id):
    now = datetime.datetime.now().isoformat()
    today = datetime.date.today().isoformat()
    conn = _connect()
    conn.execute(
        """INSERT INTO poll_answers (poll_id, user_id, username, first_name, option_id, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(poll_id, user_id)
           DO UPDATE SET option_id=excluded.option_id, username=excluded.username,
                         first_name=excluded.first_name, updated_at=excluded.updated_at""",
        (poll_id, user_id, username, first_name, option_id, now),
    )
    conn.execute(
        """INSERT INTO members (user_id, username, first_name, last_seen)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id)
           DO UPDATE SET username=excluded.username, first_name=excluded.first_name,
                         last_seen=excluded.last_seen""",
        (user_id, username, first_name, today),
    )
    conn.commit()
    conn.close()


def retract_answer(poll_id, user_id):
    conn = _connect()
    conn.execute(
        "UPDATE poll_answers SET option_id=NULL, updated_at=? WHERE poll_id=? AND user_id=?",
        (datetime.datetime.now().isoformat(), poll_id, user_id),
    )
    conn.commit()
    conn.close()


def get_poll_by_date(date_str):
    conn = _connect()
    row = conn.execute("SELECT * FROM polls WHERE date=?", (date_str,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_answers_for_date(date_str):
    conn = _connect()
    rows = conn.execute(
        """SELECT pa.* FROM poll_answers pa
           JOIN polls p ON pa.poll_id = p.poll_id
           WHERE p.date = ? AND pa.option_id IS NOT NULL""",
        (date_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_members(days=30):
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM members WHERE last_seen >= ?", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_data(monday_iso):
    monday = datetime.date.fromisoformat(monday_iso)
    friday = monday + datetime.timedelta(days=4)
    conn = _connect()
    polls = conn.execute(
        "SELECT * FROM polls WHERE date >= ? AND date <= ? ORDER BY date",
        (monday_iso, friday.isoformat()),
    ).fetchall()
    result = []
    for poll in polls:
        answers = conn.execute(
            "SELECT * FROM poll_answers WHERE poll_id=? AND option_id IS NOT NULL",
            (poll["poll_id"],),
        ).fetchall()
        result.append({
            "date": poll["date"],
            "poll_id": poll["poll_id"],
            "answers": [dict(a) for a in answers],
        })
    conn.close()
    return result


def get_daily_attendance(days=30):
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    conn = _connect()
    rows = conn.execute(
        """SELECT p.date,
                  SUM(CASE WHEN pa.option_id IN (0, 1) THEN 1 ELSE 0 END) as attended,
                  COUNT(pa.id) as voted
           FROM polls p
           LEFT JOIN poll_answers pa ON p.poll_id = pa.poll_id AND pa.option_id IS NOT NULL
           WHERE p.date >= ?
           GROUP BY p.date
           ORDER BY p.date""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overall_stats():
    conn = _connect()
    rows = conn.execute(
        """SELECT m.user_id, m.username, m.first_name,
                  COALESCE(SUM(CASE WHEN pa.option_id IN (0, 1) THEN 1 ELSE 0 END), 0) as attended,
                  COALESCE(SUM(CASE WHEN pa.option_id = 2 THEN 1 ELSE 0 END), 0) as absent,
                  COUNT(pa.id) as total_votes
           FROM members m
           LEFT JOIN poll_answers pa ON m.user_id = pa.user_id AND pa.option_id IS NOT NULL
           GROUP BY m.user_id
           ORDER BY absent DESC, attended ASC""",
    ).fetchall()
    total_polls = conn.execute("SELECT COUNT(*) as cnt FROM polls").fetchone()["cnt"]
    conn.close()
    return [dict(r) for r in rows], total_polls


def get_setting(key):
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else DEFAULT_SETTINGS.get(key)


def set_setting(key, value):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()


def get_all_settings():
    conn = _connect()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    result = dict(DEFAULT_SETTINGS)
    for row in rows:
        result[row["key"]] = row["value"]
    return result
