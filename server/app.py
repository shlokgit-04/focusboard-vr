"""FocusBoard VR sync API: accounts and sticky-note boards.
SQLite + bcrypt + HMAC-signed tokens, CORS locked to the app's origins.
The VR app (GitHub Pages) and the web companion both talk to this."""
import os
import re
import sqlite3
import time
from datetime import datetime, timezone

import bcrypt
from flask import Flask, jsonify, request
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

DATA_DIR = os.environ.get("FOCUSBOARD_DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "focusboard.db")
SECRET = os.environ.get("FOCUSBOARD_SECRET_KEY", "")
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days
NOTE_COLORS = {"amber", "sage", "sky", "rose"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024
if not SECRET:
    app.logger.warning("FOCUSBOARD_SECRET_KEY not set; tokens will not survive restarts")
    SECRET = os.urandom(32)
serializer = URLSafeTimedSerializer(SECRET, salt="focusboard-auth")

# GitHub Pages (project page + custom domain) and local dev.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "FOCUSBOARD_ALLOWED_ORIGINS",
        "https://shlokgit-04.github.io,https://shlok.is-a.dev,http://localhost:8081,http://127.0.0.1:8081",
    ).split(",") if o.strip()
]
CORS(app, origins=ALLOWED_ORIGINS,
     allow_headers=["Authorization", "Content-Type"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

_conn = None


def db():
    global _conn
    if _conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, text TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT 'amber',
                pos_x REAL NOT NULL DEFAULT 0, pos_y REAL NOT NULL DEFAULT 0, pos_z REAL NOT NULL DEFAULT 0,
                rot_y REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS rate_limits (
                scope TEXT NOT NULL, window_start INTEGER NOT NULL, count INTEGER NOT NULL,
                PRIMARY KEY (scope, window_start));
            """
        )
        _conn.commit()
    return _conn


def limited(key, scope, limit, window_seconds):
    c = db()
    now = int(time.time())
    window_start = now - (now % window_seconds)
    row = c.execute("SELECT count FROM rate_limits WHERE scope=? AND window_start=?",
                    (f"{scope}:{key}", window_start)).fetchone()
    if row is None:
        c.execute("INSERT INTO rate_limits VALUES (?,?,1)", (f"{scope}:{key}", window_start))
        c.commit()
        return False
    if row["count"] >= limit:
        return True
    c.execute("UPDATE rate_limits SET count=count+1 WHERE scope=? AND window_start=?",
              (f"{scope}:{key}", window_start))
    c.commit()
    return False


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def issue(user_id):
    return serializer.dumps({"uid": user_id})


def current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        data = serializer.loads(header[7:], max_age=TOKEN_TTL)
    except (BadSignature, SignatureExpired):
        return None
    row = db().execute("SELECT id, email, name, created_at FROM users WHERE id=?",
                       (data.get("uid", ""),)).fetchone()
    return dict(row) if row else None


def require_user():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Sign in first."}), 401)
    return user, None


def client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr or "unknown")


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/auth/register", methods=["POST"])
def register():
    if limited(client_ip(), "register", 10, 3600):
        return jsonify({"error": "Too many sign-ups from this network. Try later."}), 429
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify({"error": "Enter a valid email address."}), 400
    if not name or len(name) > 80:
        return jsonify({"error": "Enter a name (up to 80 characters)."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    c = db()
    if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        return jsonify({"error": "That email is already registered. Sign in instead."}), 409
    uid = os.urandom(16).hex()
    c.execute("INSERT INTO users VALUES (?,?,?,?,?)",
              (uid, email, name, bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode(), now_iso()))
    c.commit()
    return jsonify({"user": {"id": uid, "email": email, "name": name}, "token": issue(uid)}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    if limited(f"{client_ip()}:{email[:120]}", "auth", 30, 900):
        return jsonify({"error": "Too many sign-in attempts. Try again in a few minutes."}), 429
    row = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not bcrypt.checkpw((body.get("password") or "").encode(), row["password_hash"].encode()):
        return jsonify({"error": "Wrong email or password."}), 401
    return jsonify({"user": {"id": row["id"], "email": row["email"], "name": row["name"]},
                    "token": issue(row["id"])}), 200


@app.route("/api/auth/me")
def me():
    user, err = require_user()
    if err:
        return err
    return jsonify({"user": user}), 200


@app.route("/api/notes", methods=["GET"])
def list_notes():
    user, err = require_user()
    if err:
        return err
    rows = db().execute(
        "SELECT id, text, color, pos_x, pos_y, pos_z, rot_y, created_at, updated_at"
        " FROM notes WHERE user_id=? ORDER BY created_at", (user["id"],)).fetchall()
    return jsonify({"notes": [dict(r) for r in rows]}), 200


@app.route("/api/notes", methods=["POST"])
def create_note():
    user, err = require_user()
    if err:
        return err
    if limited(user["id"], "notes_write", 120, 3600):
        return jsonify({"error": "Too many note changes this hour."}), 429
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()[:140]
    color = body.get("color") if body.get("color") in NOTE_COLORS else "amber"
    try:
        pos = [float(body.get(k, 0)) for k in ("x", "y", "z")]
        rot = float(body.get("rot_y", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Position must be numbers."}), 400
    if any(abs(v) > 50 for v in pos) or abs(rot) > 360:
        return jsonify({"error": "Position out of range."}), 400
    nid = os.urandom(12).hex()
    c = db()
    c.execute(
        "INSERT INTO notes (id, user_id, text, color, pos_x, pos_y, pos_z, rot_y, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (nid, user["id"], text, color, *pos, rot, now_iso(), now_iso()))
    c.commit()
    row = c.execute("SELECT id, text, color, pos_x, pos_y, pos_z, rot_y, created_at, updated_at"
                    " FROM notes WHERE id=?", (nid,)).fetchone()
    return jsonify({"note": dict(row)}), 201


@app.route("/api/notes/<note_id>", methods=["PUT"])
def update_note(note_id):
    user, err = require_user()
    if err:
        return err
    if limited(user["id"], "notes_write", 240, 3600):
        return jsonify({"error": "Too many note changes this hour."}), 429
    c = db()
    row = c.execute("SELECT * FROM notes WHERE id=? AND user_id=?", (note_id, user["id"])).fetchone()
    if not row:
        return jsonify({"error": "Note not found."}), 404
    body = request.get_json(silent=True) or {}
    text = (body.get("text", row["text"]) or "").strip()[:140]
    color = body.get("color") if body.get("color") in NOTE_COLORS else row["color"]
    try:
        pos = [float(body.get(k, row["pos_" + k])) for k in ("x", "y", "z")]
        rot = float(body.get("rot_y", row["rot_y"]))
    except (TypeError, ValueError):
        return jsonify({"error": "Position must be numbers."}), 400
    if any(abs(v) > 50 for v in pos) or abs(rot) > 360:
        return jsonify({"error": "Position out of range."}), 400
    c.execute("UPDATE notes SET text=?, color=?, pos_x=?, pos_y=?, pos_z=?, rot_y=?, updated_at=? WHERE id=?",
              (text, color, *pos, rot, now_iso(), note_id))
    c.commit()
    out = c.execute("SELECT id, text, color, pos_x, pos_y, pos_z, rot_y, created_at, updated_at"
                    " FROM notes WHERE id=?", (note_id,)).fetchone()
    return jsonify({"note": dict(out)}), 200


@app.route("/api/notes/<note_id>", methods=["DELETE"])
def delete_note(note_id):
    user, err = require_user()
    if err:
        return err
    c = db()
    cur = c.execute("DELETE FROM notes WHERE id=? AND user_id=?", (note_id, user["id"]))
    c.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Note not found."}), 404
    return jsonify({"ok": True}), 200


@app.route("/api/auth/export")
def export_data():
    user, err = require_user()
    if err:
        return err
    rows = db().execute("SELECT * FROM notes WHERE user_id=? ORDER BY created_at", (user["id"],)).fetchall()
    return jsonify({"account": user, "notes": [dict(r) for r in rows]}), 200


@app.route("/api/auth/me", methods=["DELETE"])
def delete_account():
    user, err = require_user()
    if err:
        return err
    c = db()
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("DELETE FROM notes WHERE user_id=?", (user["id"],))
    c.execute("DELETE FROM users WHERE id=?", (user["id"],))
    c.commit()
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
