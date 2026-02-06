import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import sqlite3
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# Database Configuration
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///contract_analysis.db")


# ============================================================
# Helper Functions
# ============================================================

def is_mysql():
    """Check if using MySQL database"""
    return DATABASE_URL.startswith("mysql")


def q(sql):
    """Convert MySQL placeholders (%s) to SQLite placeholders (?) automatically"""
    return sql if is_mysql() else sql.replace("%s", "?")


# ============================================================
# Connection
# ============================================================

def get_conn():
    """Get database connection - works for both SQLite and MySQL"""
    print(f"DEBUG: Connecting to database: {DATABASE_URL}")

    # ---------- SQLITE ----------
    if DATABASE_URL.startswith("sqlite"):
        path = DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        print("DEBUG: SQLite connection established")
        return conn

    # ---------- MYSQL ----------
    try:
        u = urlparse(DATABASE_URL)
        
        conn = pymysql.connect(
            host=u.hostname or "localhost",
            user=u.username or "root",
            password=u.password or "",
            database=u.path.lstrip('/') or "contract_analysis",
            port=u.port or 3306,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        print("DEBUG: MySQL connection established")
        return conn
    except Exception as e:
        raise RuntimeError(f"MySQL connection failed: {str(e)}")


# ============================================================
# Database Schema
# ============================================================

SQLITE_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        created_at TEXT,
        language TEXT,
        total_clauses INTEGER,
        raw_text TEXT,
        owner_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clauses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER,
        clause_number INTEGER,
        clause_text TEXT,
        risk TEXT,
        reasons TEXT,
        classification TEXT,
        entities TEXT,
        comment TEXT,
        FOREIGN KEY(analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        created_at TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER,
        clause_number INTEGER,
        model TEXT,
        vector_json TEXT,
        created_at TEXT,
        FOREIGN KEY(analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
    )
    """
]

MYSQL_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255),
        created_at VARCHAR(50),
        language VARCHAR(50),
        total_clauses INT,
        raw_text MEDIUMTEXT,
        owner_id INT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clauses (
        id INT PRIMARY KEY AUTO_INCREMENT,
        analysis_id INT,
        clause_number INT,
        clause_text TEXT,
        risk VARCHAR(50),
        reasons TEXT,
        classification TEXT,
        entities TEXT,
        comment TEXT,
        FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255),
        created_at VARCHAR(50),
        is_admin TINYINT DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        id INT PRIMARY KEY AUTO_INCREMENT,
        analysis_id INT,
        clause_number INT,
        model VARCHAR(100),
        vector_json TEXT,
        created_at VARCHAR(50),
        FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
    )
    """
]


# ============================================================
# Initialize Database
# ============================================================

def init_db():
    """Create tables if they don't exist"""
    conn = get_conn()
    cur = conn.cursor()

    schema = MYSQL_SCHEMA if is_mysql() else SQLITE_SCHEMA

    for stmt in schema:
        try:
            cur.execute(stmt)
            print(f"DEBUG: Schema statement executed successfully")
        except Exception as e:
            print(f"WARNING: Schema execution warning: {e}")

    conn.commit()
    conn.close()
    print("DEBUG: Database initialized successfully")


def ensure_migrations():
    """
    Run any necessary schema migrations.
    For MySQL: schema is already correct via init_db()
    For SQLite: checks and adds missing columns if needed
    """
    if is_mysql():
        return  # MySQL schema is already correct
    
    # SQLite-only migrations
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Check if 'is_admin' column exists in users table
        cur.execute("PRAGMA table_info(users)")
        columns = cur.fetchall()
        
        # Convert to list of column names
        column_names = [col['name'] if isinstance(col, dict) else col[1] for col in columns]
        
        if 'is_admin' not in column_names:
            cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            print("DEBUG: Added 'is_admin' column to users table (SQLite)")
        
        conn.commit()
        print("DEBUG: SQLite migrations completed")
        
    except Exception as e:
        print(f"WARNING: Migration check failed: {e}")
    finally:
        conn.close()


# ============================================================
# User Management
# ============================================================

def register_user(email: str, password: str) -> tuple[bool, str]:
    """Register a new user"""
    conn = get_conn()
    cur = conn.cursor()

    pw_hash = generate_password_hash(password)
    created_at = datetime.utcnow().isoformat()

    try:
        cur.execute(q(
            "INSERT INTO users (email, password_hash, created_at, is_admin) VALUES (%s, %s, %s, 0)"
        ), (email, pw_hash, created_at))
        conn.commit()
        return True, "Registration successful. You can now log in."
    except Exception as e:
        conn.rollback()
        return False, f"Registration failed: {str(e)}"
    finally:
        conn.close()


def verify_user(email: str, password: str) -> Optional[int]:
    """Verify user credentials and return user ID"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(q("SELECT id, password_hash FROM users WHERE email = %s"), (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    # Handle both dict (MySQL) and Row (SQLite) objects
    user_id = row["id"] if isinstance(row, dict) else row[0]
    pw_hash = row["password_hash"] if isinstance(row, dict) else row[1]

    if check_password_hash(pw_hash, password):
        return user_id

    return None


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user details by email"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(q("SELECT id, email, password_hash, is_admin FROM users WHERE email = %s"), (email,))
    user = cur.fetchone()
    conn.close()
    
    if user:
        # Convert to dict if it's a Row object
        if not isinstance(user, dict):
            user = dict(user)
    
    return user


def user_exists(email: str) -> bool:
    """Check if user exists"""
    return get_user_by_email(email) is not None


def list_users():
    """List all users"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT id, email, created_at, is_admin FROM users ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    
    # Convert Row objects to dicts for SQLite
    if rows and not isinstance(rows[0], dict):
        rows = [dict(row) for row in rows]
    
    return rows


def set_user_admin(user_id: int, is_admin: bool):
    """Set admin flag for a user"""
    conn = get_conn()
    cur = conn.cursor()
    
    val = 1 if is_admin else 0
    cur.execute(q("UPDATE users SET is_admin = %s WHERE id = %s"), (val, user_id))
    
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    """Delete a user"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(q("DELETE FROM users WHERE id = %s"), (user_id,))
    
    conn.commit()
    conn.close()


# ============================================================
# Analysis Management
# ============================================================

def save_analysis(name: str, language: str, raw_text: str, clauses: List[Dict[str, Any]], owner_id: Optional[int] = None):
    """Save contract analysis"""
    conn = get_conn()
    cur = conn.cursor()

    created_at = datetime.utcnow().isoformat()
    total = len(clauses)

    cur.execute(q(
        "INSERT INTO analyses (name, created_at, language, total_clauses, raw_text, owner_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    ), (name, created_at, language, total, raw_text, owner_id))

    analysis_id = cur.lastrowid

    for c in clauses:
        cur.execute(q(
            "INSERT INTO clauses (analysis_id, clause_number, clause_text, risk, reasons, classification, entities, comment) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        ), (
            analysis_id,
            c.get("id"),
            c.get("clause"),
            c.get("risk"),
            c.get("reasons"),
            c.get("classification"),
            json.dumps(c.get("entities")) if c.get("entities") else None,
            c.get("comment")
        ))

    conn.commit()
    conn.close()
    print(f"DEBUG: Saved analysis ID {analysis_id}")
    return analysis_id


def list_analyses(owner_id: Optional[int] = None):
    """List all analyses, optionally filtered by owner"""
    conn = get_conn()
    cur = conn.cursor()

    if owner_id:
        cur.execute(q(
            "SELECT id, name, created_at, language, total_clauses "
            "FROM analyses WHERE owner_id = %s ORDER BY created_at DESC"
        ), (owner_id,))
    else:
        cur.execute(
            "SELECT id, name, created_at, language, total_clauses "
            "FROM analyses ORDER BY created_at DESC"
        )

    rows = cur.fetchall()
    conn.close()
    
    # Convert Row objects to dicts for SQLite
    if rows and not isinstance(rows[0], dict):
        rows = [dict(row) for row in rows]
    
    return rows


def load_analysis(analysis_id: int) -> Optional[Dict[str, Any]]:
    """Load a saved analysis including all clauses"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(q(
        "SELECT id, name, created_at, language, total_clauses, raw_text, owner_id "
        "FROM analyses WHERE id = %s"
    ), (analysis_id,))
    
    meta = cur.fetchone()

    if not meta:
        conn.close()
        return None
    
    # Convert to dict if Row object
    if not isinstance(meta, dict):
        meta = dict(meta)

    cur.execute(q(
        "SELECT clause_number, clause_text, risk, reasons, classification, entities, comment "
        "FROM clauses WHERE analysis_id = %s ORDER BY clause_number"
    ), (analysis_id,))
    
    clauses_rows = cur.fetchall()
    conn.close()
    
    # Convert to dicts if Row objects
    if clauses_rows and not isinstance(clauses_rows[0], dict):
        clauses_rows = [dict(row) for row in clauses_rows]

    analysis = {
        "id": meta['id'],
        "name": meta['name'],
        "created_at": meta['created_at'],
        "language": meta['language'],
        "total_clauses": meta['total_clauses'],
        "raw_text": meta['raw_text'],
        "owner_id": meta['owner_id'],
        "clauses": []
    }

    for row in clauses_rows:
        entities = None
        if row['entities']:
            try:
                entities = json.loads(row['entities'])
            except json.JSONDecodeError:
                entities = row['entities']

        analysis["clauses"].append({
            "id": row['clause_number'],
            "clause": row['clause_text'],
            "risk": row['risk'],
            "reasons": row['reasons'],
            "classification": row['classification'],
            "entities": entities,
            "comment": row['comment'],
        })

    return analysis


def update_clause_comment(analysis_id: int, clause_number: int, comment: str):
    """Update comment for a specific clause"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(q(
        "UPDATE clauses SET comment = %s WHERE analysis_id = %s AND clause_number = %s"
    ), (comment, analysis_id, clause_number))

    conn.commit()
    conn.close()


def delete_analysis(analysis_id: int):
    """Delete an analysis and all related data"""
    conn = get_conn()
    cur = conn.cursor()

    try:
        # Delete in order to respect foreign keys
        cur.execute(q("DELETE FROM embeddings WHERE analysis_id = %s"), (analysis_id,))
        cur.execute(q("DELETE FROM clauses WHERE analysis_id = %s"), (analysis_id,))
        cur.execute(q("DELETE FROM analyses WHERE id = %s"), (analysis_id,))

        conn.commit()

        # Check if table is empty and reset auto-increment if MySQL
        if is_mysql():
            cur.execute("SELECT COUNT(*) AS cnt FROM analyses")
            count_row = cur.fetchone()
            count = count_row['cnt'] if count_row else 0

            if count == 0:
                cur.execute("ALTER TABLE analyses AUTO_INCREMENT = 1")
                conn.commit()
                print("DEBUG: Auto-increment reset")

        print(f"DEBUG: Deleted analysis {analysis_id}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Delete error: {str(e)}")
        raise Exception(f"Database delete error: {str(e)}")
    finally:
        conn.close()


# ============================================================
# Embeddings Management
# ============================================================

def save_embedding(analysis_id: int, clause_number: int, model: str, vector: List[float]):
    """Save embedding vector for a clause"""
    conn = get_conn()
    cur = conn.cursor()

    created_at = datetime.utcnow().isoformat()
    vec_json = json.dumps(vector)

    cur.execute(q(
        "INSERT INTO embeddings (analysis_id, clause_number, model, vector_json, created_at) "
        "VALUES (%s, %s, %s, %s, %s)"
    ), (analysis_id, clause_number, model, vec_json, created_at))

    conn.commit()
    conn.close()


def get_embeddings(analysis_id: int):
    """Retrieve all embeddings for an analysis"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(q(
        "SELECT clause_number, model, vector_json FROM embeddings "
        "WHERE analysis_id = %s ORDER BY clause_number"
    ), (analysis_id,))

    rows = cur.fetchall()
    conn.close()
    
    # Convert to dicts if Row objects
    if rows and not isinstance(rows[0], dict):
        rows = [dict(row) for row in rows]

    results = []
    for row in rows:
        clause_number = row['clause_number']
        model = row['model']
        vec = json.loads(row['vector_json'] or '[]')
        results.append((clause_number, model, vec))

    return results