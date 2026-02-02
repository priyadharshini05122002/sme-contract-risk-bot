from langdetect import detect

def detect_language(text):
    try:
        lang = detect(text)
        if lang == "hi":
            return "Hindi"
        return "English"
    except:
        return "Unknown"
