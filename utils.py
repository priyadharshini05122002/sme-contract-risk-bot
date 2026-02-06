# =============================
# utils.py (FULLY UPDATED – HINDI + ENGLISH + STABLE CONTRACT DETECTION)
# =============================

import re
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from language_detector import detect_language, normalize_text

# -----------------------------
# Heuristic keywords
# -----------------------------

CONTRACT_KEYWORDS_EN = [
    "party", "agreement", "term", "terminate", "liability", "indemnify",
    "governing law", "jurisdiction", "confidential", "warranty", "payment",
    "deliverable", "service", "termination", "notice", "compensation", "contract"
]

CONTRACT_KEYWORDS_HI = [
    "अनुबंध", "समझौता", "दायित्व", "क्षतिपूर्ति",
    "समाप्ति", "उल्लंघन", "पक्ष", "भुगतान",
    "गोपनीयता", "न्यायालय", "कानूनी", "समझौता अवधि"
]

RESUME_MARKERS = [
    "experience", "education", "skills", "objective", "linkedin", "curriculum vitae"
]

# -----------------------------
# Risk keywords
# -----------------------------

HIGH_RISK_KEYWORDS_EN = [
    "unlimited liability", "without limitation", "terminate at any time",
    "without notice", "no compensation", "indemnify", "hold harmless",
    "assign all rights", "sole discretion", "irrevocable"
]

MEDIUM_RISK_KEYWORDS_EN = [
    "governing law", "jurisdiction", "terminate", "liability",
    "compensation", "penalty", "liquidated damages",
    "auto-renew", "renewal", "lock-in"
]

HIGH_RISK_KEYWORDS_HI = [
    "असीमित दायित्व", "पूर्ण क्षतिपूर्ति", "एकतरफा समाप्ति",
    "भुगतान रोका", "भविष्य के दावों का परित्याग"
]

MEDIUM_RISK_KEYWORDS_HI = [
    "विवाद", "न्यायालय", "गोपनीयता", "दंड", "कानूनी"
]

# -----------------------------
# Paths
# -----------------------------

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(TEMPLATES_PATH, exist_ok=True)

# -----------------------------
# Contract heuristics (FIXED)
# -----------------------------

def looks_like_contract(text: str) -> bool:
    """
    Improved detection for Hindi + English contracts.
    Avoids false 'not contract' warnings.
    """

    if not text or len(text.strip()) < 80:
        return False

    lang = detect_language(text)
    t = text.lower()

    keywords = CONTRACT_KEYWORDS_HI if lang.startswith("hi") else CONTRACT_KEYWORDS_EN

    score = 0
    for k in keywords:
        if k.lower() in t:
            score += 1

    # structure signals
    if re.search(r"\\d+\\.", t):
        score += 1
    if re.search(r"\\bclause\\b|\\bsection\\b", t):
        score += 1
    if re.search(r"\\bparty\\b|\\bparties\\b", t):
        score += 1

    return score >= 2


# -----------------------------
# Resume detection
# -----------------------------

def is_resume_section(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in RESUME_MARKERS)


# -----------------------------
# Risk analysis (STABLE ENGINE)
# -----------------------------

def analyze_clause_risk(clause: str) -> Tuple[str, str, int]:
    """
    Hindi + English unified clause risk analysis
    """

    c = normalize_text(clause)
    score = 0
    reasons: List[str] = []

    # English high risk
    for w in HIGH_RISK_KEYWORDS_EN:
        if w in c:
            score += 3
            reasons.append(w)

    # English medium risk
    for w in MEDIUM_RISK_KEYWORDS_EN:
        if w in c:
            score += 1
            reasons.append(w)

    # Hindi high risk
    for w in HIGH_RISK_KEYWORDS_HI:
        if w in clause:
            score += 3
            reasons.append(w)

    # Hindi medium risk
    for w in MEDIUM_RISK_KEYWORDS_HI:
        if w in clause:
            score += 1
            reasons.append(w)

    # obligation pattern
    obligations = re.findall(r'\\bshall\\b|\\bmust\\b|\\bagree to\\b', c)
    if len(obligations) >= 3 and "payment" not in c:
        score += 1
        reasons.append("many obligations without payment")

    # scoring
    if score >= 5:
        label = "High"
    elif score >= 2:
        label = "Medium"
    else:
        label = "Low"

    reasons_csv = ", ".join(reasons) if reasons else "No strong risk indicators detected."
    return label, reasons_csv, score


# -----------------------------
# Highlight terms
# -----------------------------

def highlight_terms(text: str, terms: List[str]) -> str:
    if not terms:
        return text
    for t in sorted(set([t.strip() for t in terms if t]), key=len, reverse=True):
        try:
            text = re.sub(re.escape(t), f"<span class='mark'>{t}</span>", text, flags=re.I)
        except re.error:
            continue
    return text


# -----------------------------
# Alternative suggestions
# -----------------------------

def suggest_alternatives_for_clause(clause: str, risk_label: str, reasons: str) -> Optional[str]:
    c = clause.lower()

    if risk_label == "High":
        if "indemnif" in c or "hold harmless" in c or "क्षतिपूर्ति" in clause:
            return "Limit indemnity to direct damages and cap liability to contract value."
        if "unlimited liability" in c or "असीमित दायित्व" in clause:
            return "Add a liability cap and exclude indirect damages."
        if "terminate at any time" in c or "एकतरफा समाप्ति" in clause:
            return "Add notice period and cure period."

    if risk_label == "Medium":
        if "jurisdiction" in c or "न्यायालय" in clause:
            return "Specify neutral arbitration location within India."

    return None


# -----------------------------
# Templates loader
# -----------------------------

def load_templates() -> List[Dict[str, str]]:
    default = [
        {
            "title": "Limited Liability Clause (SME-friendly)",
            "description": "Caps liability to contract value and excludes indirect damages.",
            "text": "Except for liability arising from gross negligence or willful misconduct, each party's aggregate liability shall not exceed the total fees paid under this Agreement."
        },
        {
            "title": "Mutual Indemnity (Balanced)",
            "description": "Mutual indemnity limited to direct damages.",
            "text": "Each party shall indemnify the other only for direct losses caused by breach."
        }
    ]

    path = os.path.join(TEMPLATES_PATH, "sme_templates.json")

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_templates = json.load(f)
                return user_templates + default
        except Exception:
            return default

    return default


# -----------------------------
# Contract summary
# -----------------------------

def summarize_contract_plain_english(raw_text: str, clauses_df) -> str:
    total = len(clauses_df)
    high = int((clauses_df["risk"] == "High").sum()) if "risk" in clauses_df else 0
    medium = int((clauses_df["risk"] == "Medium").sum()) if "risk" in clauses_df else 0

    summary = f"This contract contains {total} clauses. {high} high risk and {medium} medium risk found."
    return summary


# -----------------------------
# Audit log saving
# -----------------------------

def save_audit_log(analysis_id: int, audit: Dict[str, Any], export_json: bool = True):
    audit_dir = os.path.join(os.path.dirname(__file__), "audit_logs")
    os.makedirs(audit_dir, exist_ok=True)

    audit_file = os.path.join(audit_dir, f"{analysis_id}.json")

    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    if export_json:
        export_dir = os.path.join(os.path.dirname(__file__), "exports")
        os.makedirs(export_dir, exist_ok=True)

        export_file = os.path.join(export_dir, f"analysis_{analysis_id}.json")
        with open(export_file, "w", encoding="utf-8") as ef:
            json.dump(audit, ef, indent=2, ensure_ascii=False)


# utils.py (add this)

def strip_html_tags(text: str) -> str:
    """
    Aggressively remove anything that looks like HTML tags
    AND also remove common literal closing div texts that leak through
    """
    if not text:
        return ""

    # Step 1: Remove actual HTML tags (<anything>)
    text = re.sub(r'<[^>]*>', '', text)

    # Step 2: Remove common leaked literal closing tags
    text = re.sub(r'(?i)(</?div>|</?span>|</?p>|</?section>|</?article>)\b', '', text)

    # Step 3: Remove any remaining stray angle-bracket-like fragments
    text = re.sub(r'</?[^>]*', '', text)

    # Step 4: Clean up multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text).strip()

    return text