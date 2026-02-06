# risk_engine.py
# Full updated Hindi + English contract risk engine

import re
from typing import Dict, List

# ---------- CLEANING ----------

def clean_hindi(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\u0900-\u097F\s0-9]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_english(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def is_hindi(text: str) -> bool:
    return bool(re.search(r'[\u0900-\u097F]', text))


def normalize_text(text: str) -> str:
    if not text:
        return ""
    if is_hindi(text):
        return clean_hindi(text)
    return clean_english(text)


# ---------- CONTRACT DETECTION ----------

def looks_like_contract(text: str) -> bool:
    """
    Detect whether uploaded file is likely a contract.
    Prevents false warning for Hindi documents.
    """

    if not text or len(text) < 120:
        return False

    text_norm = normalize_text(text)

    hindi_keywords = [
        "समझौता", "अनुबंध", "दायित्व", "भुगतान",
        "समाप्ति", "क्षतिपूर्ति", "विवाद", "पक्ष"
    ]

    english_keywords = [
        "agreement", "liability", "termination",
        "indemnity", "payment", "party", "breach"
    ]

    score = 0

    for kw in hindi_keywords:
        if kw in text_norm:
            score += 1

    for kw in english_keywords:
        if kw in text_norm:
            score += 1

    return score >= 2


# ---------- CLAUSE SPLITTING ----------

def split_clauses(text: str) -> List[str]:
    """
    Splits contract into clauses using numbering patterns.
    """

    if not text:
        return []

    clauses = re.split(r"\n\s*(?:\d+\.|clause\s+\d+|section\s+\d+)\s*", text, flags=re.IGNORECASE)
    return [c.strip() for c in clauses if len(c.strip()) > 40]


# ---------- RISK ANALYSIS ----------

def analyze_risk(clause: str) -> Dict:
    """
    Hindi + English clause-level risk scoring engine.
    """

    if not clause or len(clause.strip()) < 30:
        return {
            "risk_level": "Low",
            "explanation": "यह केवल शीर्षक या अधूरा क्लॉज है।"
        }

    normalized = normalize_text(clause)
    clause_clean_hi = clean_hindi(clause)
    clause_clean_en = clean_english(clause)

    risk_score = 0
    reasons = []

    # 🔴 HIGH RISK — Hindi
    if 'असीमित' in clause_clean_hi and 'दायित्व' in clause_clean_hi:
        risk_score += 4
        reasons.append("असीमित दायित्व")

    if 'क्षतिपूर्ति' in clause_clean_hi:
        risk_score += 4
        reasons.append("पूर्ण क्षतिपूर्ति")

    if 'एकतरफा' in clause_clean_hi and ('बिना' in clause_clean_hi or 'सूचना' in clause_clean_hi):
        risk_score += 4
        reasons.append("एकतरफा समाप्ति")

    if 'भुगतान' in clause_clean_hi and ('रोक' in clause_clean_hi or 'अस्वीकृत' in clause_clean_hi):
        risk_score += 4
        reasons.append("भुगतान रोका जाना")

    if 'दावा' in clause_clean_hi and ('परित्याग' in clause_clean_hi or 'नहीं' in clause_clean_hi):
        risk_score += 4
        reasons.append("भविष्य के दावों का परित्याग")

    # 🔴 HIGH RISK — English
    if 'unlimited liability' in clause_clean_en:
        risk_score += 4
        reasons.append("Unlimited liability")

    if 'indemnify' in clause_clean_en:
        risk_score += 4
        reasons.append("Broad indemnity obligation")

    if 'terminate at any time' in clause_clean_en:
        risk_score += 4
        reasons.append("Unilateral termination")

    if 'without notice' in clause_clean_en:
        risk_score += 3
        reasons.append("Termination without notice")

    if 'penalty' in clause_clean_en and 'breach' in clause_clean_en:
        risk_score += 3
        reasons.append("Penalty on breach")

    # 🟠 MEDIUM RISK
    if 'गोपनीय' in clause_clean_hi:
        risk_score += 2
        reasons.append("गोपनीयता दायित्व")

    if 'confidential' in clause_clean_en:
        risk_score += 2
        reasons.append("Confidentiality obligation")

    if 'विवाद' in clause_clean_hi:
        risk_score += 2
        reasons.append("विवाद समाधान क्लॉज")

    if 'dispute' in clause_clean_en:
        risk_score += 2
        reasons.append("Dispute resolution clause")

    # ---------- FINAL DECISION ----------

    if risk_score >= 6:
        return {
            "risk_level": "High",
            "explanation": "उच्च जोखिम: " + ", ".join(reasons)
        }

    if risk_score >= 3:
        return {
            "risk_level": "Medium",
            "explanation": "मध्यम जोखिम: समीक्षा आवश्यक।"
        }

    return {
        "risk_level": "Low",
        "explanation": "कोई गंभीर कानूनी जोखिम नहीं मिला।"
    }
