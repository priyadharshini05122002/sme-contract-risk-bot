import re
from typing import List

def extract_clauses(text: str) -> List[str]:
    """
    Robust clause extractor that works for:
    - PDF text
    - paragraph contracts
    - numbered agreements
    - badly formatted files
    """

    if not text or len(text.strip()) < 40:
        return []

    # Normalize spacing
    t = re.sub(r'\r\n?', '\n', text)
    t = re.sub(r'\n+', '\n', t)
    t = re.sub(r'\s+', ' ', t)

    # 1️⃣ Try numbered clauses first
    numbered = re.split(r'(?=\d+\.\s+)', t)
    clauses = [c.strip() for c in numbered if len(c.strip()) > 60]

    # 2️⃣ If numbering not found → split by sentences
    if len(clauses) < 2:
        sentences = re.split(r'(?<=[.!?]) +', t)
        clauses = [s.strip() for s in sentences if len(s.strip()) > 80]

    # 3️⃣ If still empty → split by paragraphs
    if not clauses:
        paragraphs = text.split("\n")
        clauses = [p.strip() for p in paragraphs if len(p.strip()) > 100]

    # 4️⃣ Last fallback → return full contract
    if not clauses:
        return [text.strip()]

    return clauses
