import re
from utils import is_resume_section

def extract_clauses(text):
    raw_lines = re.split(r'\n+', text)
    clauses = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        if is_resume_section(line):
            continue
        if len(line) < 10:
            continue
        clauses.append(line)

    return clauses
