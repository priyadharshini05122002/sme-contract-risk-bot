LEGAL_KEYWORDS = [
    "agreement", "party", "parties", "shall", "liability",
    "indemnity", "terminate", "termination", "jurisdiction",
    "governing law", "confidential", "arbitration", "penalty"
]

NON_CONTRACT_HEADINGS = [
    "education", "skills", "projects", "experience",
    "summary", "certifications", "languages", "technical"
]

def looks_like_contract(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in LEGAL_KEYWORDS)

def is_resume_section(line: str) -> bool:
    return line.strip().lower() in NON_CONTRACT_HEADINGS
