def generate_summary(clauses):
    """
    Generates a simple business-friendly summary
    """
    if not clauses:
        return "No contract clauses detected."

    summary_lines = []
    for i, clause in enumerate(clauses[:5], start=1):
        summary_lines.append(f"{i}. {clause}")

    return "\n".join(summary_lines)
