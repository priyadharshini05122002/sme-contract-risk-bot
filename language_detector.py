# language_detector.py
from typing import Optional
import re

# -----------------------------
# Optional dependencies
# -----------------------------
try:
    from langdetect import detect
except Exception:
    detect = None

try:
    from googletrans import Translator
    _translator = Translator()
except Exception:
    _translator = None


# -----------------------------
# Language detection
# -----------------------------
def detect_language(text: str) -> str:
    """
    Detect language of the given text.
    Returns: 'hindi', 'english', or 'unknown'
    """

    if not text or len(text.strip()) == 0:
        return "unknown"

    # 1️⃣ Try langdetect (best)
    if detect:
        try:
            lang = detect(text)
            if lang:
                return lang
        except Exception:
            pass

    # 2️⃣ Fallback — Hindi Unicode detection
    if re.search(r'[\u0900-\u097F]', text):
        return "hindi"

    # 3️⃣ Default
    return "english"


# -----------------------------
# Normalize text to English
# -----------------------------
def normalize_to_english(text: str) -> str:
    """
    If Hindi detected and googletrans available, translate to English.
    Otherwise return original text.

    Used for:
    - keyword matching
    - risk engine support
    """

    if not text:
        return text

    lang = detect_language(text)

    # translate Hindi → English
    if lang.startswith("hindi") and _translator:
        try:
            translated = _translator.translate(text, src="hi", dest="en")
            return translated.text if translated and translated.text else text
        except Exception:
            return text

    return text


# -----------------------------
# Cleaners for NLP
# -----------------------------
def clean_hindi(text: str) -> str:
    """
    Remove punctuation + normalize Hindi text.
    """
    text = text.lower()
    text = re.sub(r'[^\u0900-\u097F\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_english(text: str) -> str:
    """
    Remove punctuation + normalize English text.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_text(text: str) -> str:
    """
    Auto normalize based on language.
    """
    lang = detect_language(text)

    if lang.startswith("hindi"):
        return clean_hindi(text)
    else:
        return clean_english(text)
