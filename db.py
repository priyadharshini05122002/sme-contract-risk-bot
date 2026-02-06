"""
db.py — Database-free version

This project now runs fully in memory.
No MySQL, no SQLite, no login storage, no embeddings storage.

All functions are kept as placeholders so the main app
does not crash when importing them.
"""

from typing import List, Dict, Any, Optional

# ────────────────────────────────────────────────
# Init (no database)
# ────────────────────────────────────────────────

def init_db():
    print("INFO: Running in NO-DATABASE mode")

def ensure_migrations():
    pass

# ────────────────────────────────────────────────
# Analyses (in-memory only)
# ────────────────────────────────────────────────

_ANALYSES = []
_ANALYSIS_COUNTER = 1

def list_analyses(owner_id: Optional[int] = None):
    return _ANALYSES


def save_analysis(name: str, language: str, raw_text: str, clauses: List[Dict[str, Any]], owner_id: Optional[int] = None):
    global _ANALYSIS_COUNTER
    
    analysis = {
        "id": _ANALYSIS_COUNTER,
        "name": name,
        "language": language,
        "total_clauses": len(clauses),
        "raw_text": raw_text,
        "owner_id": owner_id,
        "clauses": clauses
    }
    
    _ANALYSES.append(analysis)
    _ANALYSIS_COUNTER += 1
    
    return analysis["id"]


def load_analysis(analysis_id: int) -> Optional[Dict[str, Any]]:
    for a in _ANALYSES:
        if a["id"] == analysis_id:
            return a
    return None


def update_clause_comment(analysis_id: int, clause_number: int, comment: str):
    for a in _ANALYSES:
        if a["id"] == analysis_id:
            for c in a["clauses"]:
                if c.get("id") == clause_number:
                    c["comment"] = comment
                    return


def delete_analysis(analysis_id: int):
    global _ANALYSES
    _ANALYSES = [a for a in _ANALYSES if a["id"] != analysis_id]
    return True

# ────────────────────────────────────────────────
# Embeddings (memory only)
# ────────────────────────────────────────────────

_EMBEDDINGS = {}

def save_embedding(analysis_id: int, clause_number: int, model: str, vector: List[float]):
    key = (analysis_id, clause_number)
    _EMBEDDINGS[key] = {
        "model": model,
        "vector": vector
    }


def get_embeddings(analysis_id: int):
    results = []
    for (aid, clause_no), data in _EMBEDDINGS.items():
        if aid == analysis_id:
            results.append((clause_no, data["model"], data["vector"]))
    return results

# ────────────────────────────────────────────────
# Users (disabled)
# ────────────────────────────────────────────────

_USERS = []
_USER_COUNTER = 1

def list_users():
    return _USERS


def create_user(email: str, password: str):
    global _USER_COUNTER
    
    user = {
        "id": _USER_COUNTER,
        "email": email,
        "password": password,
        "is_admin": False
    }
    
    _USERS.append(user)
    _USER_COUNTER += 1
    return user["id"]


def verify_user(email: str, password: str):
    for u in _USERS:
        if u["email"] == email and u["password"] == password:
            return u["id"]
    return None


def delete_user(user_id: int):
    global _USERS
    _USERS = [u for u in _USERS if u["id"] != user_id]


def set_user_admin(user_id: int, is_admin: bool):
    for u in _USERS:
        if u["id"] == user_id:
            u["is_admin"] = is_admin


def get_user_by_email(email: str):
    for u in _USERS:
        if u["email"] == email:
            return u
    return None


def user_exists(email: str):
    return get_user_by_email(email) is not None


def register_user(email: str, password: str):
    if user_exists(email):
        return False, "Email already registered."
    
    create_user(email, password)
    return True, "Registration successful."
