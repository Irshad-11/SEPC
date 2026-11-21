"""
SEPC - Software Engineering Programming Community (backend)
===========================================================
Flask + SQLite. One file. Runs the same on your laptop and on PythonAnywhere.

    python app.py              -> dev server on http://localhost:5000
    python app.py sync         -> fetch every Codeforces/LeetCode/CodeChef account (PythonAnywhere scheduled task)
    python app.py demo         -> load demo (test) data
    python app.py add-user USERNAME PASSWORD [admin|developer]

Sync on PythonAnywhere:
    PythonAnywhere web apps cannot run background threads, so a sync is done in small
    steps: the frontend calls POST /api/sync/step again and again, each call fetches a
    few accounts and returns log lines. No queue, no worker, nothing to configure.

Data model (sepc.db):
    users      -> people who can log in (admin / developer)
    students   -> people on the leaderboard (role: student / developer)
    accounts   -> one row per student per platform with the LATEST numbers
    snapshots  -> one row per account per day (Dhaka date) = history
    sync_runs  -> every sync (server or local push) with its log lines
    meta       -> small key/value store

"Solved in a period" = total at the end of the latest day - total at the end of the day
before the period started. If the account has no snapshot that old, its first snapshot
is used, so old problems are never counted as new.
"""

import gzip
import io
import json
import os
import random
import re
import sqlite3
import sys
import time
import hashlib
import hmac
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_file
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # explicit path: PythonAnywhere's working dir is different

import platforms as fetchers  # noqa: E402  (after .env, so proxy vars are visible)

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
TZ = ZoneInfo("Asia/Dhaka")
DB_PATH = os.path.join(BASE_DIR, "sepc.db")
SECRET_KEY = os.getenv("SECRET_KEY") or "change-me-in-env"
INGEST_SECRET = os.getenv("INGEST_SECRET", "")
ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_ORIGINS", "*").split(",") if o.strip()]
PLATFORMS = ["codeforces", "leetcode", "codechef", "beecrowd"]
SERVER_PLATFORMS = [
    p.strip() for p in os.getenv(
        "SERVER_PLATFORMS", "codeforces,leetcode" if fetchers.ON_PYTHONANYWHERE else "codeforces,leetcode,codechef"
    ).split(",") if p.strip() in fetchers.FETCHERS
]
PROFILE_URL = {
    "codeforces": "https://codeforces.com/profile/{}",
    "leetcode": "https://leetcode.com/u/{}/",
    "codechef": "https://www.codechef.com/users/{}",
    "beecrowd": "https://judge.beecrowd.com/en/profile/{}",
}
WINDOWS = {"day": 1, "week": 7, "month": 30}
TOKEN_DAYS = 30
STEP_SECONDS = 5       # one /api/sync/step call works about this long (keeps the live log flowing)
STALE_SECONDS = 180    # a running sync with no step for 3 min is marked stopped

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.json.sort_keys = False
tokens = URLSafeTimedSerializer(SECRET_KEY, salt="sepc-login")

# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'developer',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    batch TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT 'Software Engineering',
    email TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NOT NULL DEFAULT '',
    github_url TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'student',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_pk INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    username TEXT NOT NULL,
    solved INTEGER,
    rating REAL,
    rank_text TEXT,
    avatar TEXT,
    last_synced TEXT,
    last_error TEXT,
    UNIQUE (student_pk, platform)
);
CREATE TABLE IF NOT EXISTS snapshots (
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    solved INTEGER NOT NULL,
    rating REAL,
    PRIMARY KEY (account_id, day)
);
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    started_by TEXT,
    queue TEXT NOT NULL DEFAULT '[]',
    pos INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    log TEXT NOT NULL DEFAULT '[]',
    started_at TEXT,
    finished_at TEXT,
    heartbeat REAL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        username = os.getenv("FIRST_USER", "se@uftb.com").strip().lower()
        password = os.getenv("FIRST_PASSWORD", "UFTB_SE@02")
        conn.execute("INSERT INTO users (username, name, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
                     (username, "SE Admin", generate_password_hash(password), now_str()))
        print(f"Default login created: {username}")
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def now():
    return datetime.now(TZ).replace(tzinfo=None)


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return now().date()


def error(message, status=400):
    return jsonify({"error": message}), status


def clean(value, limit=300):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()[:limit]


def to_num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(re.sub(r"[,\s]", "", str(value)))
    except ValueError:
        return None


def get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn, key, value):
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, value))


# ----------------------------------------------------------------------------
# CORS + gzip + errors (no extra package needed)
# ----------------------------------------------------------------------------
@app.before_request
def preflight():
    if request.method == "OPTIONS":
        return app.make_default_options_response()


@app.after_request
def after(response):
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if "*" in ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin in ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.vary.add("Origin")
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Timestamp, X-Signature"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "86400"

    if (response.status_code < 300 and response.mimetype == "application/json" and not response.direct_passthrough
            and "gzip" in request.headers.get("Accept-Encoding", "") and "Content-Encoding" not in response.headers):
        data = response.get_data()
        if len(data) > 2000:
            response.set_data(gzip.compress(data, 5))
            response.headers["Content-Encoding"] = "gzip"
            response.vary.add("Accept-Encoding")
    return response


@app.errorhandler(HTTPException)
def http_error(exc):
    return error({404: "Not found", 405: "Method not allowed", 413: "File too large (max 5 MB)"}.get(
        exc.code, exc.description), exc.code)


@app.errorhandler(Exception)
def server_error(exc):
    app.logger.exception(exc)
    return error(f"Server error: {type(exc).__name__}: {str(exc)[:200]}", 500)


# ----------------------------------------------------------------------------
# Auth (Bearer token, no cookies -> works across vercel.app / pythonanywhere.com)
# ----------------------------------------------------------------------------
_failed_logins = {}


def make_token(user):
    return tokens.dumps({"uid": user["id"], "pv": user["password_hash"][-10:]})


def current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        data = tokens.loads(header[7:], max_age=TOKEN_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return None
    user = db().execute("SELECT * FROM users WHERE id = ?", (data.get("uid"),)).fetchone()
    if not user or user["password_hash"][-10:] != data.get("pv"):
        return None  # password changed -> old tokens die
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user = current_user()
        if g.user is None:
            return error("Please log in", 401)
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            return error("Only an admin can do this", 403)
        return view(*args, **kwargs)
    return wrapper


def user_dict(u):
    return {"id": u["id"], "username": u["username"], "name": u["name"], "role": u["role"], "created_at": u["created_at"]}


def signed_required(view):
    """For local_sync.py (no login). Headers: X-Timestamp, X-Signature = HMAC(INGEST_SECRET, ts + '.' + body)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not INGEST_SECRET:
            return error("INGEST_SECRET is not set in backend .env", 503)
        ts = request.headers.get("X-Timestamp", "")
        if not ts.isdigit() or abs(time.time() - int(ts)) > 300:
            return error("Missing/expired X-Timestamp (check your computer clock)", 401)
        expected = hmac.new(INGEST_SECRET.encode(), ts.encode() + b"." + request.get_data(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request.headers.get("X-Signature", "")):
            return error("Bad signature (INGEST_SECRET differs between local .env and server .env)", 401)
        return view(*args, **kwargs)
    return wrapper


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = clean(body.get("username")).lower()
    ip = request.headers.get("X-Real-IP") or request.remote_addr or "?"
    fails = [t for t in _failed_logins.get(ip, []) if t > time.time() - 900]
    if len(fails) >= 10:
        return error("Too many wrong attempts. Wait 15 minutes.", 429)
    user = db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], body.get("password") or ""):
        _failed_logins[ip] = fails + [time.time()]
        return error("Wrong username or password", 401)
    _failed_logins.pop(ip, None)
    return jsonify({"token": make_token(user), "user": user_dict(user)})


@app.get("/api/auth/me")
@login_required
def me():
    return jsonify({"user": user_dict(g.user)})


@app.post("/api/auth/password")
@login_required
def change_password():
    body = request.get_json(silent=True) or {}
    if not check_password_hash(g.user["password_hash"], body.get("current") or ""):
        return error("Current password is wrong")
    new = body.get("new") or ""
    if len(new) < 6:
        return error("New password must be at least 6 characters")
    db().execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), g.user["id"]))
    db().commit()
    user = db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return jsonify({"message": "Password changed", "token": make_token(user)})


@app.get("/api/users")
@login_required
def list_users():
    return jsonify([user_dict(u) for u in db().execute("SELECT * FROM users ORDER BY id")])


@app.post("/api/users")
@admin_required
def add_user():
    body = request.get_json(silent=True) or {}
    username = clean(body.get("username"), 100).lower()
    password = body.get("password") or ""
    role = clean(body.get("role")).lower() or "developer"
    if not username or len(password) < 6 or role not in ("admin", "developer"):
        return error("username, password (6+ chars) and role (admin/developer) are required")
    if db().execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        return error("This username already exists", 409)
    db().execute("INSERT INTO users (username, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                 (username, clean(body.get("name"), 100), generate_password_hash(password), role, now_str()))
    db().commit()
    return jsonify({"message": "User added"}), 201


@app.delete("/api/users/<int:uid>")
@admin_required
def delete_user(uid):
    if uid == g.user["id"]:
        return error("You cannot delete yourself")
    db().execute("DELETE FROM users WHERE id = ?", (uid,))
    db().commit()
    return jsonify({"message": "User deleted"})


# ----------------------------------------------------------------------------
# Students
# ----------------------------------------------------------------------------
TEXT_FIELDS = ["student_id", "name", "batch", "department", "email", "avatar_url", "github_url", "linkedin_url", "role"]
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def normalize_username(value):
    """'tourist', '@tourist' or a pasted profile link -> 'tourist'."""
    text = clean(value)
    if "/" in text:
        parts = [p for p in re.sub(r"^https?://", "", text).split("?")[0].split("/") if p]
        text = parts[-1] if len(parts) > 1 else ""
    return text.lstrip("@")


def validate_student(data, partial=False):
    out, problems = {}, []
    for field in TEXT_FIELDS:
        if field in data:
            out[field] = clean(data[field])
    if "role" in out:
        out["role"] = "developer" if out["role"].lower().startswith("dev") else "student"
    for field in ("avatar_url", "github_url", "linkedin_url"):
        if out.get(field) and not re.match(r"^https?://\S+$", out[field]):
            if field == "github_url" and re.fullmatch(r"[A-Za-z0-9-]{1,39}", out[field]):
                out[field] = "https://github.com/" + out[field]
            else:
                problems.append(f"{field} must be a full http(s) link")
    for p in PLATFORMS:
        if p in data:
            out[p] = normalize_username(data[p])
            if out[p] and not USERNAME_RE.match(out[p]):
                problems.append(f"{p} username has invalid characters")
    for field in ("student_id", "name"):
        if (not partial or field in out) and not out.get(field):
            problems.append(f"{field} is required")
    return out, problems


def save_student(conn, data, pk=None):
    """Insert (pk=None) or update. Platform usernames: empty = remove, changed = history reset."""
    fields = [f for f in TEXT_FIELDS if f in data]
    if pk is None:
        cur = conn.execute(
            f"INSERT INTO students ({', '.join(fields + ['is_demo', 'created_at', 'updated_at'])}) "
            f"VALUES ({', '.join('?' * (len(fields) + 3))})",
            [data[f] for f in fields] + [int(data.get("is_demo", 0)), now_str(), now_str()])
        pk = cur.lastrowid
    elif fields:
        conn.execute(f"UPDATE students SET {', '.join(f + ' = ?' for f in fields)}, updated_at = ? WHERE id = ?",
                     [data[f] for f in fields] + [now_str(), pk])
    for p in PLATFORMS:
        if p not in data:
            continue
        old = conn.execute("SELECT id, username FROM accounts WHERE student_pk = ? AND platform = ?", (pk, p)).fetchone()
        if old and old["username"] == data[p]:
            continue
        if old:
            conn.execute("DELETE FROM accounts WHERE id = ?", (old["id"],))
        if data[p]:
            conn.execute("INSERT INTO accounts (student_pk, platform, username) VALUES (?, ?, ?)", (pk, p, data[p]))
    return pk


def student_dict(conn, row):
    out = {k: row[k] for k in ["id"] + TEXT_FIELDS + ["is_demo"]}
    for p in PLATFORMS:
        out[p] = ""
    for acc in conn.execute("SELECT platform, username FROM accounts WHERE student_pk = ?", (row["id"],)):
        out[acc["platform"]] = acc["username"]
    return out


@app.get("/api/students")
@login_required
def list_students():
    conn = db()
    return jsonify([student_dict(conn, r) for r in conn.execute("SELECT * FROM students ORDER BY name")])


@app.post("/api/students")
@login_required
def add_student():
    data, problems = validate_student(request.get_json(silent=True) or {})
    if problems:
        return error("; ".join(problems))
    conn = db()
    if conn.execute("SELECT 1 FROM students WHERE student_id = ?", (data["student_id"],)).fetchone():
        return error("This Student ID already exists", 409)
    pk = save_student(conn, data)
    conn.commit()
    return jsonify(student_dict(conn, conn.execute("SELECT * FROM students WHERE id = ?", (pk,)).fetchone())), 201


@app.put("/api/students/<int:pk>")
@login_required
def edit_student(pk):
    conn = db()
    if not conn.execute("SELECT 1 FROM students WHERE id = ?", (pk,)).fetchone():
        return error("Student not found", 404)
    data, problems = validate_student(request.get_json(silent=True) or {}, partial=True)
    if problems:
        return error("; ".join(problems))
    if "student_id" in data and conn.execute("SELECT 1 FROM students WHERE student_id = ? AND id != ?",
                                             (data["student_id"], pk)).fetchone():
        return error("This Student ID already exists", 409)
    save_student(conn, data, pk)
    conn.commit()
    return jsonify(student_dict(conn, conn.execute("SELECT * FROM students WHERE id = ?", (pk,)).fetchone()))


@app.delete("/api/students/<int:pk>")
@login_required
def delete_student(pk):
    db().execute("DELETE FROM students WHERE id = ?", (pk,))
    db().commit()
    return jsonify({"message": "Student deleted"})


# ---- Excel import ----------------------------------------------------------
HEADER_ALIASES = {
    "id": "student_id", "roll": "student_id", "studentid": "student_id", "student_name": "name", "full_name": "name",
    "dept": "department", "mail": "email", "photo": "avatar_url", "avatar": "avatar_url", "image": "avatar_url",
    "picture": "avatar_url", "github": "github_url", "linkedin": "linkedin_url", "special_role": "role",
    "cf": "codeforces", "codeforce": "codeforces", "codeforces_id": "codeforces", "lc": "leetcode",
    "leetcode_id": "leetcode", "cc": "codechef", "codechef_id": "codechef", "beecrowed": "beecrowd",
    "beecrowd_id": "beecrowd", "beecrowed_id": "beecrowd", "uri": "beecrowd",
}
IMPORT_COLUMNS = TEXT_FIELDS + PLATFORMS


@app.get("/api/students/template")
def excel_template():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(IMPORT_COLUMNS)
    ws.append(["2303030", "Irshad Hossain", "2023-24", "Software Engineering", "", "", "https://github.com/username",
               "", "developer", "cf_handle", "lc_username", "cc_handle", "1072467"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="sepc_students_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/students/import")
@login_required
def excel_import():
    """multipart: file=.xlsx, dry_run=1 (preview) or 0 (save). Existing Student ID = update."""
    from openpyxl import load_workbook
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".xlsx"):
        return error("Please choose an .xlsx file")
    try:
        rows = list(load_workbook(file, read_only=True, data_only=True).active.iter_rows(values_only=True))
    except Exception:
        return error("Could not read this Excel file")
    if len(rows) < 2:
        return error("The file has no data rows")
    header = []
    for h in rows[0]:
        key = re.sub(r"[^a-z0-9]+", "_", clean(h).lower()).strip("_")
        header.append(HEADER_ALIASES.get(key, key))
    if "student_id" not in header or "name" not in header:
        return error("Columns 'student_id' and 'name' are required")

    conn = db()
    existing = {r["student_id"]: r["id"] for r in conn.execute("SELECT id, student_id FROM students")}
    dry_run = request.form.get("dry_run", "1") != "0"
    preview, seen, saved = [], set(), 0
    for number, cells in enumerate(rows[1:], start=2):
        raw = {col: clean(cells[i]) for i, col in enumerate(header) if col in IMPORT_COLUMNS and i < len(cells)}
        if not any(raw.values()):
            continue
        sid = raw.get("student_id", "")
        pk = existing.get(sid)
        data, problems = validate_student({k: v for k, v in raw.items() if v or pk is None}, partial=pk is not None)
        if sid in seen:
            problems.append("duplicate Student ID in file")
        seen.add(sid)
        preview.append({"row": number, "action": "update" if pk else "add", "student_id": sid,
                        "name": raw.get("name", ""), "errors": problems})
        if not problems and not dry_run:
            save_student(conn, data, pk)
            saved += 1
    if not dry_run:
        conn.commit()
    return jsonify({"dry_run": dry_run, "rows": preview, "saved": saved,
                    "valid": sum(1 for r in preview if not r["errors"])})


# ----------------------------------------------------------------------------
# Stats engine (leaderboard + profile read from here)
# ----------------------------------------------------------------------------
_cache = {"key": None, "value": None}


def data_version(conn):
    return get_meta(conn, "version") or "0"


def bump(conn):
    set_meta(conn, "version", str(int(data_version(conn)) + 1))


def compute_board(conn):
    key = (data_version(conn), today().isoformat())
    if _cache["key"] == key:
        return _cache["value"]

    ref_row = conn.execute("SELECT MAX(day) FROM snapshots WHERE day <= ?", (today().isoformat(),)).fetchone()[0]
    ref = date.fromisoformat(ref_row) if ref_row else today()
    snaps = {}
    for s in conn.execute("SELECT account_id, day, solved, rating FROM snapshots ORDER BY account_id, day"):
        snaps.setdefault(s["account_id"], []).append((s["day"], s["solved"], s["rating"]))

    def at(series, day_str, index):
        """Last value on or before day_str (None if the account started later)."""
        value = None
        for d, solved, rating in series:
            if d > day_str:
                break
            item = (solved, rating)[index]
            if item is not None:
                value = item
        return value

    def first(series, index):
        return next((s[index + 1] for s in series if s[index + 1] is not None), None)

    rows = {}
    for s in conn.execute("SELECT * FROM students"):
        rows[s["id"]] = {
            "id": s["id"], "student_id": s["student_id"], "name": s["name"], "batch": s["batch"],
            "department": s["department"], "role": s["role"], "avatar": s["avatar_url"],
            "github": s["github_url"], "linkedin": s["linkedin_url"], "is_demo": s["is_demo"],
            "solved": {"day": 0, "week": 0, "month": 0, "all": 0},
            "prev": {"day": 0, "week": 0, "month": 0, "all": 0},
            "rating": 0, "rating_delta": {"day": 0, "week": 0, "month": 0, "all": 0},
            "p": {},
        }
    for a in conn.execute("SELECT * FROM accounts"):
        row = rows.get(a["student_pk"])
        if row is None:
            continue
        series = snaps.get(a["id"], [])
        item = {"username": a["username"], "url": PROFILE_URL[a["platform"]].format(a["username"]),
                "solved": {"day": 0, "week": 0, "month": 0, "all": a["solved"] or 0},
                "prev": {"day": 0, "week": 0, "month": 0},
                "rating": a["rating"], "rating_delta": {"day": 0, "week": 0, "month": 0, "all": 0},
                "rank": a["rank_text"], "synced": a["last_synced"], "error": a["last_error"]}
        if not row["avatar"] and a["avatar"] and a["platform"] in ("codeforces", "leetcode"):
            row["avatar"] = a["avatar"]
        if series:
            first_solved, first_rating = first(series, 0), first(series, 1)
            current = at(series, ref.isoformat(), 0)
            for period, n in WINDOWS.items():
                base = at(series, (ref - timedelta(days=n)).isoformat(), 0)
                base = first_solved if base is None else base
                before = at(series, (ref - timedelta(days=2 * n)).isoformat(), 0)
                before = first_solved if before is None else before
                item["solved"][period] = max(0, current - base)
                item["prev"][period] = max(0, base - before)
                if a["rating"] is not None and a["platform"] != "beecrowd":
                    old = at(series, (ref - timedelta(days=n)).isoformat(), 1)
                    old = first_rating if old is None else old
                    if old is not None:
                        item["rating_delta"][period] = round(a["rating"] - old)
            if a["rating"] is not None and first_rating is not None and a["platform"] != "beecrowd":
                item["rating_delta"]["all"] = round(a["rating"] - first_rating)
            month_base = at(series, (ref - timedelta(days=30)).isoformat(), 0)
            row["prev"]["all"] += first_solved if month_base is None else month_base
        for period in ("day", "week", "month"):
            row["solved"][period] += item["solved"][period]
            row["prev"][period] += item["prev"][period]
        row["solved"]["all"] += item["solved"]["all"]
        if a["platform"] != "beecrowd" and a["rating"]:
            row["rating"] += round(a["rating"])
            for period in item["rating_delta"]:
                row["rating_delta"][period] += item["rating_delta"][period]
        row["p"][a["platform"]] = item

    value = {"as_of": ref.isoformat(), "generated_at": now_str(), "rows": list(rows.values())}
    _cache.update(key=key, value=value)
    return value


@app.get("/api/board")
def board():
    """Everything the leaderboard needs. Ranking/sorting is done in the browser (instant filter switch)."""
    conn = db()
    data = dict(compute_board(conn))
    data["last_sync"] = last_sync(conn)
    return jsonify(data)


@app.get("/api/students/<int:pk>/public")
def public_student(pk):
    row = next((r for r in compute_board(db())["rows"] if r["id"] == pk), None)
    return jsonify(row) if row else error("Student not found", 404)


@app.get("/api/history")
def history():
    """Daily series for graphs. /api/history?ids=3,1&days=30  (days=0 -> all history)"""
    conn = db()
    ids = [int(i) for i in request.args.get("ids", "").split(",") if i.strip().isdigit()][:5]
    days = max(0, min(400, int(request.args.get("days", "30") or 30)))
    end = today()
    if days == 0:
        first_day = conn.execute("SELECT MIN(day) FROM snapshots").fetchone()[0]
        start = date.fromisoformat(first_day) if first_day else end - timedelta(days=29)
        start = max(start, end - timedelta(days=399))
    else:
        start = end - timedelta(days=days - 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    out = {}
    for pk in ids:
        per = {}
        for acc in conn.execute("SELECT id, platform FROM accounts WHERE student_pk = ?", (pk,)):
            snaps = conn.execute("SELECT day, solved, rating FROM snapshots WHERE account_id = ? ORDER BY day",
                                 (acc["id"],)).fetchall()
            solved, rating, i, last_s, last_r = [], [], 0, None, None
            for d in dates:
                while i < len(snaps) and snaps[i]["day"] <= d:
                    last_s = snaps[i]["solved"]
                    last_r = snaps[i]["rating"] if snaps[i]["rating"] is not None else last_r
                    i += 1
                solved.append(last_s)
                rating.append(last_r if acc["platform"] != "beecrowd" else None)
            per[acc["platform"]] = {"solved": solved, "rating": rating}
        out[str(pk)] = per
    return jsonify({"dates": dates, "series": out})


# ----------------------------------------------------------------------------
# Sync
# ----------------------------------------------------------------------------
def record(conn, account_id, result, day=None):
    solved = int(result["solved"])
    rating = to_num(result.get("rating"))
    conn.execute("INSERT INTO snapshots (account_id, day, solved, rating) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(account_id, day) DO UPDATE SET solved = excluded.solved, rating = excluded.rating",
                 (account_id, day or today().isoformat(), solved, rating))
    conn.execute("UPDATE accounts SET solved = ?, rating = ?, rank_text = ?, avatar = COALESCE(?, avatar), "
                 "last_synced = ?, last_error = NULL WHERE id = ?",
                 (solved, rating, clean(result.get("rank"), 40) or None, result.get("avatar") or None,
                  now_str(), account_id))


def run_dict(r, with_log=True):
    if r is None:
        return None
    out = {k: r[k] for k in ("id", "status", "source", "started_by", "total", "done", "ok", "failed",
                             "started_at", "finished_at")}
    if with_log:
        out["log"] = json.loads(r["log"])
    return out


def last_sync(conn):
    out = {}
    for p in PLATFORMS:
        out[p] = conn.execute("SELECT MAX(last_synced) FROM accounts WHERE platform = ?", (p,)).fetchone()[0]
    return out


def expire_stale(conn):
    conn.execute("UPDATE sync_runs SET status = 'stopped', finished_at = ? WHERE status = 'running' AND heartbeat < ?",
                 (now_str(), time.time() - STALE_SECONDS))


def start_run(conn, who, only=None):
    """Create a sync run (or return the one already running)."""
    conn.execute("BEGIN IMMEDIATE")
    expire_stale(conn)
    running = conn.execute("SELECT * FROM sync_runs WHERE status = 'running' ORDER BY id DESC LIMIT 1").fetchone()
    if running:
        conn.commit()
        return running, False
    plats = [p for p in (only or SERVER_PLATFORMS) if p in SERVER_PLATFORMS]
    accounts = conn.execute(
        f"SELECT id, platform FROM accounts WHERE platform IN ({','.join('?' * len(plats))}) ORDER BY id", plats
    ).fetchall() if plats else []
    groups = {p: [a["id"] for a in accounts if a["platform"] == p] for p in plats}
    queue = [ids[i] for i in range(max([len(v) for v in groups.values()] or [0])) for ids in groups.values()
             if i < len(ids)]  # cf, lc, cf, lc ... mixed so one slow site does not block the start
    cur = conn.execute("INSERT INTO sync_runs (status, source, started_by, queue, total, started_at, heartbeat) "
                       "VALUES ('running', 'server', ?, ?, ?, ?, ?)",
                       (who, json.dumps(queue), len(queue), now_str(), time.time()))
    conn.commit()
    return conn.execute("SELECT * FROM sync_runs WHERE id = ?", (cur.lastrowid,)).fetchone(), True


def step_run(conn, run_id, seconds=STEP_SECONDS):
    """Fetch accounts of this run for about `seconds`. Returns (run_row, new_log_lines)."""
    lines = []
    started = time.time()
    while time.time() - started < seconds:
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute("SELECT * FROM sync_runs WHERE id = ?", (run_id,)).fetchone()
        if run is None or run["status"] != "running":
            conn.commit()
            break
        queue = json.loads(run["queue"])
        if run["pos"] >= len(queue):
            conn.commit()
            break
        account_id = queue[run["pos"]]
        conn.execute("UPDATE sync_runs SET pos = pos + 1, heartbeat = ? WHERE id = ?", (time.time(), run_id))
        conn.commit()

        acc = conn.execute("SELECT a.*, s.name, s.student_id FROM accounts a JOIN students s ON s.id = a.student_pk "
                           "WHERE a.id = ?", (account_id,)).fetchone()
        if acc is None:
            conn.execute("UPDATE sync_runs SET done = done + 1 WHERE id = ?", (run_id,))
            conn.commit()
            continue
        t0 = time.time()
        result, reason = fetchers.fetch(acc["platform"], acc["username"])
        line = {"t": now().strftime("%H:%M:%S"), "platform": acc["platform"], "username": acc["username"],
                "student": f"{acc['name']} ({acc['student_id']})", "ok": result is not None,
                "ms": int((time.time() - t0) * 1000)}
        if result:
            record(conn, acc["id"], result)
            line["msg"] = f"{result['solved']} solved" + (f", rating {round(result['rating'])}"
                                                          if to_num(result.get("rating")) else "")
        else:
            conn.execute("UPDATE accounts SET last_error = ? WHERE id = ?", (reason, acc["id"]))
            line["msg"] = reason
        lines.append(line)
        run = conn.execute("SELECT log FROM sync_runs WHERE id = ?", (run_id,)).fetchone()
        log = (json.loads(run["log"]) + [line])[-400:]
        conn.execute(f"UPDATE sync_runs SET done = done + 1, {'ok' if result else 'failed'} = "
                     f"{'ok' if result else 'failed'} + 1, log = ?, heartbeat = ? WHERE id = ?",
                     (json.dumps(log, ensure_ascii=False), time.time(), run_id))
        bump(conn)
        conn.commit()

    run = conn.execute("SELECT * FROM sync_runs WHERE id = ?", (run_id,)).fetchone()
    if run and run["status"] == "running" and run["done"] >= run["total"]:
        conn.execute("UPDATE sync_runs SET status = 'finished', finished_at = ? WHERE id = ?", (now_str(), run_id))
        bump(conn)
        conn.commit()
        run = conn.execute("SELECT * FROM sync_runs WHERE id = ?", (run_id,)).fetchone()
    return run, lines


@app.post("/api/sync/start")
@login_required
def sync_start():
    body = request.get_json(silent=True) or {}
    run, created = start_run(db(), g.user["username"], body.get("platforms"))
    return jsonify({"run": run_dict(run), "created": created, "server_platforms": SERVER_PLATFORMS})


@app.post("/api/sync/step")
@login_required
def sync_step():
    run_id = int((request.get_json(silent=True) or {}).get("run_id") or 0)
    run, lines = step_run(db(), run_id)
    if run is None:
        return error("Sync run not found", 404)
    return jsonify({"run": run_dict(run, with_log=False), "lines": lines})


@app.post("/api/sync/stop")
@login_required
def sync_stop():
    db().execute("UPDATE sync_runs SET status = 'stopped', finished_at = ? WHERE status = 'running'", (now_str(),))
    db().commit()
    return jsonify({"message": "Stopped"})


@app.get("/api/sync/status")
def sync_status():
    conn = db()
    expire_stale(conn)
    conn.commit()
    runs = conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 15").fetchall()
    summary = {}
    for p in PLATFORMS:
        r = conn.execute("SELECT COUNT(*) AS n, SUM(last_error IS NULL AND solved IS NOT NULL) AS ok, "
                         "SUM(last_error IS NOT NULL) AS bad, MAX(last_synced) AS at FROM accounts WHERE platform = ?",
                         (p,)).fetchone()
        summary[p] = {"accounts": r["n"], "ok": r["ok"] or 0, "errors": r["bad"] or 0, "last_synced": r["at"],
                      "on_server": p in SERVER_PLATFORMS}
    errors = [dict(e) for e in conn.execute(
        "SELECT a.platform, a.username, a.last_error, s.name FROM accounts a JOIN students s ON s.id = a.student_pk "
        "WHERE a.last_error IS NOT NULL ORDER BY a.platform LIMIT 200")]
    return jsonify({
        "latest": run_dict(runs[0]) if runs else None,
        "runs": [run_dict(r, with_log=False) for r in runs],
        "platforms": summary,
        "errors": errors,
        "server_platforms": SERVER_PLATFORMS,
        "on_pythonanywhere": fetchers.ON_PYTHONANYWHERE,
        "curl_cffi": fetchers.curl_requests is not None,
    })


# ---- local_sync.py endpoints (signed) --------------------------------------
@app.get("/api/ingest/accounts")
@signed_required
def ingest_accounts():
    out = {p: [] for p in PLATFORMS}
    for a in db().execute("SELECT DISTINCT platform, username FROM accounts ORDER BY platform, username"):
        out[a["platform"]].append(a["username"])
    return jsonify(out)


@app.post("/api/ingest/<platform>")
@signed_required
def ingest(platform):
    """Body: {"users": {"username": {"solved": 12, "rating": 1500, "rank": "...", "avatar": "..."}}}
    (beecrowd.py's JSON works as is: it has "points" instead of "rating")."""
    if platform not in PLATFORMS:
        return error("Unknown platform", 404)
    try:
        payload = json.loads(request.get_data() or b"{}")
    except ValueError:
        return error("Body must be JSON")
    users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(users, dict):
        return error("'users' must be an object")
    conn = db()
    by_name = {}
    for a in conn.execute("SELECT id, username FROM accounts WHERE platform = ?", (platform,)):
        by_name.setdefault(a["username"].lower(), []).append(a["id"])
    lines, ok, failed, unknown = [], 0, 0, []
    for username, stats in users.items():
        ids = by_name.get(clean(username).lower())
        if not ids:
            unknown.append(username)
            continue
        stats = stats if isinstance(stats, dict) else {}
        solved = to_num(stats.get("solved"))
        line = {"t": now().strftime("%H:%M:%S"), "platform": platform, "username": username, "student": "",
                "ms": 0, "ok": solved is not None}
        if solved is None:
            reason = clean(stats.get("error") or stats.get("solved")) or "no data"
            for i in ids:
                conn.execute("UPDATE accounts SET last_error = ? WHERE id = ?", (f"local: {reason}", i))
            line["msg"] = reason
            failed += 1
        else:
            result = {"solved": int(solved), "rating": stats.get("rating", stats.get("points")),
                      "rank": stats.get("rank"), "avatar": stats.get("avatar")}
            for i in ids:
                record(conn, i, result)
            line["msg"] = f"{int(solved)} solved"
            ok += 1
        lines.append(line)
    conn.execute("INSERT INTO sync_runs (status, source, started_by, total, done, ok, failed, log, started_at, "
                 "finished_at, heartbeat) VALUES ('finished', ?, 'local_sync.py', ?, ?, ?, ?, ?, ?, ?, ?)",
                 (f"local:{platform}", len(lines), len(lines), ok, failed, json.dumps(lines[-400:]),
                  now_str(), now_str(), time.time()))
    bump(conn)
    conn.commit()
    return jsonify({"platform": platform, "ok": ok, "failed": failed, "unknown": unknown})


# ----------------------------------------------------------------------------
# Demo (test) data: real public accounts + 60 days of generated history
# ----------------------------------------------------------------------------
DEMO_STUDENTS = [
    # (student_id, name, batch, role, codeforces, leetcode, codechef, beecrowd)
    ("2303030", "Irshad Hossain", "2023-24", "developer", "", "", "", "1072467"),
    ("2403016", "Mahbub Tanmay", "2024-25", "developer", "MdMahbubTanmay", "", "", "1072468"),
    ("2303028", "Mahbubur Rahman Sifat", "2023-24", "developer", "", "", "covey_spark_88", "1072469"),
    ("2403019", "Ramjan Ali", "2024-25", "developer", "", "Md_Ramzan_Ali", "", "1072470"),
    ("D-1001", "Gennady Korotkevich", "2022-23", "student", "tourist", "", "gennady.korotkevich", ""),
    ("D-1002", "Jiang Ly", "2022-23", "student", "jiangly", "", "", ""),
    ("D-1003", "Benjamin Qi", "2023-24", "student", "Benq", "", "", "1072471"),
    ("D-1004", "Neal Wu", "2023-24", "student", "neal", "neal_wu", "", ""),
    ("D-1005", "Petr Mitrichev", "2022-23", "student", "Petr", "", "", "1072472"),
    ("D-1006", "Andrew He", "2024-25", "student", "ecnerwala", "", "", ""),
    ("D-1007", "Lee Hsien", "2024-25", "student", "", "lee215", "", "1072473"),
    ("D-1008", "Votrubac", "2023-24", "student", "", "votrubac", "", ""),
    ("D-1009", "Kamil Debowski", "2022-23", "student", "Errichto", "", "", "1072474"),
    ("D-1010", "David Harmeyer", "2024-25", "student", "SecondThread", "uwi", "", "1072475"),
    ("D-1011", "Alex Danilyuk", "2023-24", "student", "Um_nik", "", "", ""),
    ("D-1012", "Rahim Uddin", "2024-25", "student", "", "", "", "1072476"),
]
DEMO_SIZE = {"codeforces": (150, 2600, 1100, 3600), "leetcode": (80, 2400, 1400, 3200),
             "codechef": (40, 700, 1300, 3400), "beecrowd": (20, 400, 40, 900)}


def demo_rank(platform, rating, rng):
    if platform == "codeforces":
        for limit, name in ((3000, "Legendary Grandmaster"), (2600, "International Grandmaster"), (2400, "Grandmaster"),
                            (2300, "International Master"), (2100, "Master"), (1900, "Candidate Master"),
                            (1600, "Expert"), (1400, "Specialist"), (1200, "Pupil")):
            if rating >= limit:
                return name
        return "Newbie"
    if platform == "leetcode":
        return "Guardian" if rating >= 2200 else "Knight" if rating >= 1850 else "Contestant"
    if platform == "codechef":
        return fetchers._cc_stars(rating)
    return f"{rng.randint(800, 90000):,}"


def load_demo(conn):
    clear_demo(conn)
    rng = random.Random(2026)
    end = today()
    for sid, name, batch, role, cf, lc, cc, bee in DEMO_STUDENTS:
        if conn.execute("SELECT 1 FROM students WHERE student_id = ?", (sid,)).fetchone():
            continue  # a real student with this ID exists -> keep it
        pk = save_student(conn, {"student_id": sid, "name": name, "batch": batch, "role": role,
                                 "department": "Software Engineering", "is_demo": 1,
                                 "github_url": "https://github.com/" if role == "developer" else "",
                                 "codeforces": cf, "leetcode": lc, "codechef": cc, "beecrowd": bee})
        activity = rng.uniform(0.2, 1.6)
        for acc in conn.execute("SELECT id, platform FROM accounts WHERE student_pk = ?", (pk,)).fetchall():
            lo, hi, rlo, rhi = DEMO_SIZE[acc["platform"]]
            solved = rng.randint(lo, hi)
            rating = rng.randint(rlo, rhi) if rlo else None
            for back in range(59, -1, -1):
                day = (end - timedelta(days=back)).isoformat()
                solved += int(rng.random() < 0.55 * min(1, activity)) * rng.randint(0, int(4 * activity) + 1)
                if rating is not None and back % 7 == 3:
                    rating += rng.randint(-60, 90)
                conn.execute("INSERT INTO snapshots (account_id, day, solved, rating) VALUES (?, ?, ?, ?)",
                             (acc["id"], day, solved, rating))
            conn.execute("UPDATE accounts SET solved = ?, rating = ?, rank_text = ?, last_synced = ? WHERE id = ?",
                         (solved, rating, demo_rank(acc["platform"], rating, rng), now_str() + " (demo)", acc["id"]))
    bump(conn)
    conn.commit()


def clear_demo(conn):
    conn.execute("DELETE FROM students WHERE is_demo = 1")
    bump(conn)
    conn.commit()


@app.post("/api/demo/load")
@login_required
def demo_load():
    load_demo(db())
    return jsonify({"message": "Test data loaded"})


@app.post("/api/demo/clear")
@login_required
def demo_clear():
    clear_demo(db())
    return jsonify({"message": "Test data cleared"})


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "time": now_str(), "on_pythonanywhere": fetchers.ON_PYTHONANYWHERE,
                    "server_platforms": SERVER_PLATFORMS, "curl_cffi": fetchers.curl_requests is not None,
                    "students": db().execute("SELECT COUNT(*) FROM students").fetchone()[0]})


@app.get("/")
def index():
    return jsonify({"name": "SEPC API", "health": "/api/health"})


# ----------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------
def cli_sync():
    conn = connect()
    run, created = start_run(conn, "scheduled-task")
    print(f"Sync #{run['id']} {'started' if created else 'resumed'}: {run['total']} accounts "
          f"({', '.join(SERVER_PLATFORMS)})")
    while True:
        run, lines = step_run(conn, run["id"], seconds=60)
        for ln in lines:
            print(f"[{ln['t']}] {'OK ' if ln['ok'] else 'ERR'} {ln['platform']:<10} {ln['username']:<22} {ln['msg']}")
        if run["status"] != "running" or not lines:
            break
    print(f"Done: {run['ok']} ok, {run['failed']} failed, status={run['status']}")
    conn.close()


init_db()  # runs on import too (PythonAnywhere WSGI imports this file)

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "sync":
        cli_sync()
    elif command == "demo":
        c = connect()
        load_demo(c)
        c.close()
        print("Demo data loaded")
    elif command == "add-user" and len(sys.argv) >= 4:
        c = connect()
        c.execute("INSERT INTO users (username, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                  (sys.argv[2].lower(), "", generate_password_hash(sys.argv[3]),
                   sys.argv[4] if len(sys.argv) > 4 else "developer", now_str()))
        c.commit()
        c.close()
        print("User added")
    else:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
