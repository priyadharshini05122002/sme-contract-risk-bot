import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import pymysql

# ────────────────────────────────────────────────
# Database Configuration
# ────────────────────────────────────────────────
DATABASE_URL = "mysql://root:root123@localhost:3306/contract_analysis"

# ────────────────────────────────────────────────
# MySQL Schema (only needed once – can be run manually if preferred)
# ────────────────────────────────────────────────

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

# ────────────────────────────────────────────────
# Connection function
# ────────────────────────────────────────────────

def get_conn():
    print(f"DEBUG: Connecting to: {DATABASE_URL}")
    
    if not DATABASE_URL or not DATABASE_URL.startswith("mysql"):
        raise RuntimeError("MySQL DATABASE_URL not set correctly")
    
    from urllib.parse import urlparse
    u = urlparse(DATABASE_URL)
    
    user = u.username or "root"
    password = u.password or ""
    host = u.hostname or "localhost"
    port = u.port or 3306
    dbname = u.path.lstrip('/') or "contract_analysis"
    
    print(f"DEBUG: MySQL → host={host}, user={user}, db={dbname}, port={port}")
    
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=dbname,
            port=port,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        print("DEBUG: MySQL connection SUCCESSFUL")
        return conn
    except pymysql.err.OperationalError as e:
        if "Access denied" in str(e):
            raise RuntimeError(
                "Access denied - wrong password or root login blocked.\n"
                f"Tried user: {user}, password length: {len(password)}\n"
                "Fix options:\n"
                "1. No password: DATABASE_URL = \"mysql://root@localhost:3306/contract_analysis\"\n"
                "2. Reset password: ALTER USER 'root'@'localhost' IDENTIFIED BY 'priya05122002@'; FLUSH PRIVILEGES;\n"
                "3. New user: CREATE USER 'app'@'localhost' IDENTIFIED BY 'app123'; GRANT ALL ON contract_analysis.* TO 'app'@'localhost';"
            )
        raise RuntimeError(f"MySQL connection failed: {str(e)}")

# ────────────────────────────────────────────────
# Initialize DB (run once or on startup)
# ────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    for stmt in MYSQL_SCHEMA:
        try:
            cur.execute(stmt.strip())
            print(f"DEBUG: Table created/verified")
        except Exception as e:
            print(f"Schema warning: {e}")
    
    conn.commit()
    conn.close()
    print("DEBUG: init_db completed")

def ensure_migrations():
    """
    Run any necessary schema migrations.
    For MySQL: assumes schema is already correct (handled by init_db)
    For SQLite: adds missing columns if needed
    """
    if is_mysql():
        return  # MySQL schema is already created correctly via init_db()

    # SQLite-only migrations
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if 'is_admin' column exists in users table
    cur.execute("PRAGMA table_info(users)")
    columns = cur.fetchall()
    
    # columns is list of sqlite3.Row → each row has 'name' field for column name
    column_names = [col['name'] for col in columns]
    
    if 'is_admin' not in column_names:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        print("DEBUG: Added 'is_admin' column to users table (SQLite)")
    
    # Ensure embeddings table exists (with correct SQLite syntax)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER,
            clause_number INTEGER,
            model TEXT,
            vector_json TEXT,
            created_at TEXT,
            FOREIGN KEY(analysis_id) REFERENCES analyses(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("DEBUG: SQLite migrations completed")


def is_mysql():
    """
    Helper to detect MySQL connection (used only in ensure_migrations)
    """
    return DATABASE_URL and DATABASE_URL.startswith("mysql")



# ────────────────────────────────────────────────
# List saved analyses
# ────────────────────────────────────────────────

def list_analyses(owner_id: Optional[int] = None):
    conn = get_conn()
    cur = conn.cursor()
    
    if owner_id:
        cur.execute(
            "SELECT id, name, created_at, language, total_clauses "
            "FROM analyses WHERE owner_id = %s ORDER BY created_at DESC",
            (owner_id,)
        )
    else:
        cur.execute(
            "SELECT id, name, created_at, language, total_clauses "
            "FROM analyses ORDER BY created_at DESC"
        )
    
    rows = cur.fetchall()
    conn.close()
    return rows

# ────────────────────────────────────────────────
# Save analysis
# ────────────────────────────────────────────────

def save_analysis(name: str, language: str, raw_text: str, clauses: List[Dict[str, Any]], owner_id: Optional[int] = None):
    conn = get_conn()
    cur = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    total = len(clauses)
    
    cur.execute(
        "INSERT INTO analyses (name, created_at, language, total_clauses, raw_text, owner_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (name, created_at, language, total, raw_text, owner_id)
    )
    analysis_id = cur.lastrowid

    for c in clauses:
        cur.execute(
            "INSERT INTO clauses (analysis_id, clause_number, clause_text, risk, reasons, classification, entities, comment) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                analysis_id,
                c.get("id"),
                c.get("clause"),
                c.get("risk"),
                c.get("reasons"),
                c.get("classification"),
                json.dumps(c.get("entities")) if c.get("entities") else None,
                c.get("comment"),
            )
        )

    conn.commit()
    conn.close()
    print(f"DEBUG: Saved analysis ID {analysis_id}")
    return analysis_id


def load_analysis(analysis_id: int) -> Optional[Dict[str, Any]]:
    """
    Load a saved analysis from MySQL, including all its clauses.
    Returns dict with analysis metadata + list of clauses, or None if not found.
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Get analysis metadata
    cur.execute(
        """
        SELECT id, name, created_at, language, total_clauses, raw_text, owner_id 
        FROM analyses 
        WHERE id = %s
        """,
        (analysis_id,)
    )
    meta = cur.fetchone()
    
    if not meta:
        conn.close()
        return None
    
    # Get all clauses for this analysis
    cur.execute(
        """
        SELECT clause_number, clause_text, risk, reasons, classification, entities, comment 
        FROM clauses 
        WHERE analysis_id = %s 
        ORDER BY clause_number
        """,
        (analysis_id,)
    )
    clauses_rows = cur.fetchall()
    
    conn.close()
    
    # Build result dict
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
                entities = row['entities']  # fallback to raw string if invalid JSON
        
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
    """
    Update the comment field for a specific clause in MySQL
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        "UPDATE clauses SET comment = %s WHERE analysis_id = %s AND clause_number = %s",
        (comment, analysis_id, clause_number)
    )
    
    conn.commit()
    conn.close()


# ────────────────────────────────────────────────
# Delete analysis
# ────────────────────────────────────────────────
def delete_analysis(analysis_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Delete related data (in correct order to respect foreign keys)
        cur.execute("DELETE FROM embeddings WHERE analysis_id = %s", (analysis_id,))
        cur.execute("DELETE FROM clauses WHERE analysis_id = %s", (analysis_id,))
        cur.execute("DELETE FROM analyses WHERE id = %s", (analysis_id,))
        
        conn.commit()

        # Check if table is now empty
        cur.execute("SELECT COUNT(*) AS cnt FROM analyses")
        count_row = cur.fetchone()
        count = count_row['cnt'] if count_row else 0

        if count == 0:
            # Reset AUTO_INCREMENT to 1
            cur.execute("ALTER TABLE analyses AUTO_INCREMENT = 1")
            conn.commit()
            print("DEBUG: All analyses deleted → AUTO_INCREMENT reset to 1")

        print(f"DEBUG: Deleted analysis {analysis_id}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Delete error: {str(e)}")
        raise Exception(f"Database delete error: {str(e)}")
    finally:
        conn.close()

        
def save_embedding(analysis_id: int, clause_number: int, model: str, vector: List[float]):
    conn = get_conn()
    cur = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    vec_json = json.dumps(vector)
    
    cur.execute(
        "INSERT INTO embeddings (analysis_id, clause_number, model, vector_json, created_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (analysis_id, clause_number, model, vec_json, created_at)
    )
    
    conn.commit()
    conn.close()


def get_embeddings(analysis_id: int):
    """
    Retrieve all embeddings for a given analysis_id (MySQL only)
    Returns list of tuples: (clause_number, model, vector)
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT clause_number, model, vector_json FROM embeddings "
        "WHERE analysis_id = %s ORDER BY clause_number",
        (analysis_id,)
    )
    
    rows = cur.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        # row is dict because we use DictCursor
        clause_number = row['clause_number']
        model = row['model']
        vec = json.loads(row['vector_json'] or '[]')
        results.append((clause_number, model, vec))
    
    return results

# ---------------- User management ----------------
def list_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, email, created_at, is_admin FROM users ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def set_user_admin(user_id: int, is_admin: bool):
    """
    Set admin flag for a user in MySQL
    """
    conn = get_conn()
    cur = conn.cursor()
    val = 1 if is_admin else 0
    
    cur.execute(
        "UPDATE users SET is_admin = %s WHERE id = %s",
        (val, user_id)
    )
    
    conn.commit()
    conn.close()

def delete_user(user_id: int):
    """
    Delete a user from MySQL
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    
    conn.commit()
    conn.close()


# ---------------- User auth ----------------
try:
    from werkzeug.security import generate_password_hash, check_password_hash
    _use_werkzeug = True
except Exception:
    _use_werkzeug = False


def create_user(email: str, password: str) -> Optional[int]:
    """
    Create a new user in MySQL
    Returns user ID on success, None on failure
    """
    conn = get_conn()
    cur = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    
    # Hash password
    pw_hash = generate_password_hash(password)  # assuming werkzeug is used
    
    try:
        cur.execute(
            "INSERT INTO users (email, password_hash, created_at) "
            "VALUES (%s, %s, %s)",
            (email, pw_hash, created_at)
        )
        uid = cur.lastrowid
        conn.commit()
        return uid
    except pymysql.err.IntegrityError:
        # Email already exists
        return None
    finally:
        conn.close()


def verify_user(email: str, password: str) -> Optional[int]:
    """
    Verify user credentials in MySQL
    Returns user ID if valid, None otherwise
    """
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT id, password_hash FROM users WHERE email = %s",
        (email,)
    )
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    uid = row['id']
    pw_hash = row['password_hash']
    
    if check_password_hash(pw_hash, password):
        return uid
    
    return None

# ─── Authentication helpers ───────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, password_hash, is_admin FROM users WHERE email = %s",
        (email,)
    )
    user = cur.fetchone()
    conn.close()
    return user


def user_exists(email: str) -> bool:
    return get_user_by_email(email) is not None


def register_user(email: str, password: str) -> tuple[bool, str]:
    if user_exists(email):
        return False, "Email already registered."
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        pw_hash = generate_password_hash(password)
        created_at = datetime.utcnow().isoformat()
        
        cur.execute(
            "INSERT INTO users (email, password_hash, created_at, is_admin) "
            "VALUES (%s, %s, %s, 0)",
            (email, pw_hash, created_at)
        )
        conn.commit()
        return True, "Registration successful. You can now log in."
    except Exception as e:
        conn.rollback()
        return False, f"Registration failed: {str(e)}"
    finally:
        conn.close()