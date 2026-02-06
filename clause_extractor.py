import re
from typing import List
from utils import is_resume_section, looks_like_contract

def extract_clauses(text: str) -> List[str]:
    """
    Improved splitter that handles:
    - Numbered lists (1., 2., 3., ...)
    - Hindi + English mixed text
    - PDF extraction artifacts (extra spaces, no line breaks)
    """
    if not text or len(text.strip()) < 50:
        return []

    # Normalize: fix line endings + reduce multiple blanks
    t = re.sub(r'\r\n?', '\n', text)
    t = re.sub(r'\s*\n\s*\n\s*', '\n\n', t)          # normalize paragraph breaks
    t = re.sub(r'([।।])\s*', r'\1\n', t)            # Hindi danda → new line

    # Try to find numbered items (very common in risk analysis docs)
    # Look for patterns like:   1.   2)   3 –   etc.
    numbered_split = r'(?=(?:^|\s)(?:\d{1,2}|[IVXLCDM]+)[.)–—-]\s+)'
  

    parts = re.split(numbered_split, t)

    clauses = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        # Skip very short fragments
        if len(cleaned) < 60:
            continue
        # Optional: require contract-like keywords in non-Hindi parts
        if not looks_like_contract(cleaned):
            if not re.search(r'\b(sh all|must|liability|terminate|indemn|payment|party|breach|confidential|unlimited|sole discretion)\b', cleaned, re.I):
                if not re.search(r'(दायित्व|क्षतिपूर्ति|समाप्ति|भुगतान|गोपनीयता|अनुबंध|पक्ष|उत्तरदायी|दंड|विवाद)', cleaned):
                    continue
        clauses.append(cleaned)

    # Fallback: if still one big block → split on double newlines or strong separators
    if len(clauses) <= 1:
        fallback_parts = re.split(r'\n{2,}(?=\d+[.)]|\s*[A-Z][.)]\s)', t)
        clauses = [p.strip() for p in fallback_parts if len(p.strip()) > 80]

    # Final cleanup
    final = []
    for c in clauses:
        # Remove leftover HTML junk if any
        c = re.sub(r'<[^>]+>', '', c)
        c = re.sub(r'</?[^>]*', '', c)
        c = re.sub(r'\s+', ' ', c).strip()
        if len(c) > 70:
            final.append(c)

    # If nothing usable → return whole text as single clause
    return final if final else [t.strip()]