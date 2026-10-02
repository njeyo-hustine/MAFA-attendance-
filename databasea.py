import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).with_name("mafa_attendance.db")

DEFAULT_SUBJECTS = [
    "Mathematics",
    "Further Mathematics",
    "Chemistry",
    "Physics",
    "Computer Science",
    "ICT",
]

DEFAULT_SUPER_ADMIN_USERNAME = "mafa_admin"
DEFAULT_SUPER_ADMIN_PASSWORD = "change-this-password"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database():
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS subjects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE COLLATE NOCASE NOT NULL)""")

        conn.execute("""CREATE TABLE IF NOT EXISTS admins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE COLLATE NOCASE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            subject_id INTEGER,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE SET NULL)""")

        conn.execute("""CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            school TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            attendance_time TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
            UNIQUE(student_name COLLATE NOCASE, school COLLATE NOCASE,
                   subject_id, attendance_date))""")

        for name in DEFAULT_SUBJECTS:
            conn.execute(
                "INSERT OR IGNORE INTO subjects(name) VALUES(?)", (name,)
            )

        exists = conn.execute(
            "SELECT id FROM admins WHERE username=?",
            (DEFAULT_SUPER_ADMIN_USERNAME,),
        ).fetchone()

        if not exists:
            conn.execute(
                "INSERT INTO admins(username,password_hash,role) VALUES(?,?,?)",
                (
                    DEFAULT_SUPER_ADMIN_USERNAME,
                    generate_password_hash(DEFAULT_SUPER_ADMIN_PASSWORD),
                    "super_admin",
                ),
            )


def clean(value):
    return " ".join((value or "").strip().split())


# ---------- Subjects ----------

def get_subjects():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM subjects ORDER BY name COLLATE NOCASE"
        ).fetchall()


def get_subject(subject_id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM subjects WHERE id=?", (subject_id,)
        ).fetchone()


def add_subject(name):
    with get_connection() as conn:
        conn.execute("INSERT INTO subjects(name) VALUES(?)", (name,))


def get_subjects_with_counts():
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.*, COUNT(a.id) AS count
            FROM subjects s
            LEFT JOIN attendance a ON a.subject_id = s.id
            GROUP BY s.id
            ORDER BY s.name COLLATE NOCASE
        """).fetchall()


# ---------- Admins ----------

def get_admin_by_username(username):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM admins WHERE username=?", (username,)
        ).fetchone()


def create_admin(username, password, role, subject_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO admins(username,password_hash,role,subject_id) VALUES(?,?,?,?)",
            (username, generate_password_hash(password), role, subject_id),
        )


def get_all_admins():
    with get_connection() as conn:
        return conn.execute("""
            SELECT a.*, s.name AS subject_name
            FROM admins a
            LEFT JOIN subjects s ON s.id = a.subject_id
            ORDER BY a.username COLLATE NOCASE
        """).fetchall()


# ---------- Attendance ----------

def mark_attendance(student_name, school, subject_id):
    now = datetime.now()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO attendance
            (student_name, school, subject_id, attendance_date, attendance_time)
            VALUES(?,?,?,?,?)
        """, (
            student_name, school, subject_id,
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
        ))


def get_attendance(subject_id=None, school=None, date=None, search=None, sort="newest"):
    query = """SELECT x.*, s.name AS subject_name
               FROM attendance x JOIN subjects s ON s.id = x.subject_id
               WHERE 1=1"""
    params = []

    if subject_id:
        query += " AND x.subject_id=?"
        params.append(subject_id)
    if school:
        query += " AND x.school=?"
        params.append(school)
    if date:
        query += " AND x.attendance_date=?"
        params.append(str(date))
    if search:
        query += " AND x.student_name LIKE ?"
        params.append(f"%{search}%")

    order = {
        "name": "x.student_name COLLATE NOCASE ASC",
        "school": "x.school COLLATE NOCASE ASC, x.student_name COLLATE NOCASE ASC",
        "subject": "s.name COLLATE NOCASE ASC, x.student_name COLLATE NOCASE ASC",
        "oldest": "x.attendance_date ASC, x.attendance_time ASC",
    }.get(sort, "x.attendance_date DESC, x.attendance_time DESC")

    query += " ORDER BY " + order

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_schools(subject_id=None):
    query = "SELECT DISTINCT school FROM attendance"
    params = []
    if subject_id:
        query += " WHERE subject_id=?"
        params.append(subject_id)
    query += " ORDER BY school COLLATE NOCASE"
    with get_connection() as conn:
        return [row["school"] for row in conn.execute(query, params).fetchall()]


def get_totals(subject_id=None):
    today = datetime.now().strftime("%Y-%m-%d")
    base = "SELECT COUNT(*) AS n FROM attendance WHERE 1=1"
    params = []
    if subject_id:
        base += " AND subject_id=?"
        params.append(subject_id)

    with get_connection() as conn:
        total = conn.execute(base, params).fetchone()["n"]
        today_total = conn.execute(
            base + " AND attendance_date=?", params + [today]
        ).fetchone()["n"]

    return total, today_total
