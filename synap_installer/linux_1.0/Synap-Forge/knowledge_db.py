#!/usr/bin/env python3
"""
KNOWLEDGE DB — SQLite error/fix learning database
Remembers every error, fix attempt, and outcome.
Gets smarter with every interaction.
"""

import sqlite3
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

logger = logging.getLogger("KnowledgeDB")

DB_PATH = Path("/home/aaron/Synap-Forge/mcp/knowledge.db")


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS errors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            signature   TEXT UNIQUE NOT NULL,
            message     TEXT NOT NULL,
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL,
            hit_count   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS fixes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            error_signature TEXT NOT NULL,
            action          TEXT NOT NULL,
            params          TEXT NOT NULL,
            success_count   INTEGER DEFAULT 0,
            failure_count   INTEGER DEFAULT 0,
            confidence      REAL DEFAULT 0.5,
            last_used       TEXT,
            FOREIGN KEY (error_signature) REFERENCES errors(signature)
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            error_signature TEXT NOT NULL,
            fix_id          INTEGER,
            action          TEXT NOT NULL,
            params          TEXT NOT NULL,
            success         INTEGER NOT NULL,
            execution_time  REAL,
            project_path    TEXT,
            timestamp       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            pattern     TEXT NOT NULL,
            action      TEXT NOT NULL,
            params      TEXT NOT NULL,
            confidence  REAL DEFAULT 0.8
        );

        CREATE INDEX IF NOT EXISTS idx_errors_sig ON errors(signature);
        CREATE INDEX IF NOT EXISTS idx_fixes_sig ON fixes(error_signature);
        """)
    _seed_templates()


def _sig(message: str) -> str:
    return hashlib.md5(message.strip().lower().encode()).hexdigest()


def _seed_templates():
    """Seed common Android/build error templates."""
    templates = [
        ("missing_manifest_package",
         "package attribute is missing",
         "merge_manifest",
         {"permissions": ["android.permission.INTERNET"]},
         0.9),
        ("missing_internet_permission",
         "internet permission",
         "merge_manifest",
         {"permissions": ["android.permission.INTERNET"]},
         0.95),
        ("missing_exported_flag",
         "android:exported",
         "inject_code",
         {"strategy": "append"},
         0.88),
        ("duplicate_class",
         "Duplicate class",
         "gradle_clean",
         {},
         0.75),
        ("gradle_namespace_missing",
         "namespace not specified",
         "inject_code",
         {"strategy": "overwrite"},
         0.85),
        ("out_of_memory_build",
         "OutOfMemoryError",
         "shell_exec",
         {"command": "./gradlew --stop"},
         0.7),
        ("manifest_merger_failed",
         "Manifest merger failed",
         "merge_manifest",
         {},
         0.8),
    ]
    with _get_conn() as conn:
        for name, pattern, action, params, confidence in templates:
            conn.execute("""
                INSERT OR IGNORE INTO templates (name, pattern, action, params, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (name, pattern, action, json.dumps(params), confidence))


def get_smart_fix(error_message: str) -> Optional[Dict]:
    """
    Find the best known fix for an error.
    Checks fix history first, then templates.
    Returns dict with action, params, confidence or None.
    """
    sig = _sig(error_message)
    with _get_conn() as conn:
        # Check learned fixes first
        row = conn.execute("""
            SELECT action, params, confidence
            FROM fixes
            WHERE error_signature = ?
            ORDER BY confidence DESC, success_count DESC
            LIMIT 1
        """, (sig,)).fetchone()

        if row and row["confidence"] >= 0.6:
            return {
                "action": row["action"],
                "params": json.loads(row["params"]),
                "confidence": row["confidence"],
                "source": "learned"
            }

        # Fall back to templates
        msg_lower = error_message.lower()
        rows = conn.execute("SELECT * FROM templates ORDER BY confidence DESC").fetchall()
        for t in rows:
            if t["pattern"].lower() in msg_lower:
                return {
                    "action": t["action"],
                    "params": json.loads(t["params"]),
                    "confidence": t["confidence"],
                    "source": "template",
                    "template_name": t["name"]
                }

    return None


def learn_from_error(error_message: str, action: str, params: dict,
                     success: bool, execution_time: float = 0.0,
                     project_path: str = None) -> Dict:
    """Record a fix attempt and update confidence scores."""
    sig = _sig(error_message)
    now = datetime.now().isoformat()

    with _get_conn() as conn:
        # Upsert error record
        conn.execute("""
            INSERT INTO errors (signature, message, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(signature) DO UPDATE SET
                last_seen = excluded.last_seen,
                hit_count = hit_count + 1
        """, (sig, error_message[:1000], now, now))

        # Find or create fix record
        fix_row = conn.execute("""
            SELECT id, success_count, failure_count, confidence
            FROM fixes
            WHERE error_signature = ? AND action = ?
        """, (sig, action)).fetchone()

        if fix_row:
            sc = fix_row["success_count"] + (1 if success else 0)
            fc = fix_row["failure_count"] + (0 if success else 1)
            total = sc + fc
            confidence = round(sc / total, 4) if total > 0 else 0.5
            conn.execute("""
                UPDATE fixes SET success_count=?, failure_count=?, confidence=?, last_used=?
                WHERE id=?
            """, (sc, fc, confidence, now, fix_row["id"]))
            fix_id = fix_row["id"]
        else:
            confidence = 0.8 if success else 0.2
            cur = conn.execute("""
                INSERT INTO fixes (error_signature, action, params, success_count, failure_count, confidence, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sig, action, json.dumps(params),
                  1 if success else 0,
                  0 if success else 1,
                  confidence, now))
            fix_id = cur.lastrowid

        # Log the attempt
        conn.execute("""
            INSERT INTO attempts (error_signature, fix_id, action, params, success, execution_time, project_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sig, fix_id, action, json.dumps(params), int(success), execution_time, project_path, now))

    return {"fix_id": fix_id, "confidence": confidence, "success": success}


def get_statistics() -> Dict:
    with _get_conn() as conn:
        total_errors = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        total_fixes = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        successful = conn.execute("SELECT COUNT(*) FROM attempts WHERE success=1").fetchone()[0]
        success_rate = round(successful / total_fixes, 4) if total_fixes > 0 else 0.0

        top_actions = conn.execute("""
            SELECT action, COUNT(*) as count,
                   AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as avg_confidence
            FROM attempts GROUP BY action ORDER BY count DESC LIMIT 5
        """).fetchall()

        return {
            "total_errors": total_errors,
            "total_fixes": total_fixes,
            "successful_fixes": successful,
            "success_rate": success_rate,
            "top_actions": [dict(r) for r in top_actions],
            "db_path": str(DB_PATH),
            "db_size": DB_PATH.stat().st_size if DB_PATH.exists() else 0
        }


def add_template(name: str, pattern: str, action: str, params: dict, confidence: float = 0.8):
    with _get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO templates (name, pattern, action, params, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (name, pattern, action, json.dumps(params), confidence))
    return {"success": True, "name": name}


# Initialize on import
_init_db()
