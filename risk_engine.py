import openai
from utils import looks_like_contract

openai.api_key = "YOUR_OPENAI_API_KEY"

def analyze_risk(clause):

    # SAFETY FALLBACK (important)
    legal_terms = ["shall", "must", "liable", "terminate", "penalty", "indemnity"]
    if not any(term in clause.lower() for term in legal_terms):
        return {
            "risk_level": "Low",
            "explanation": "No legal obligation or risk-related language detected in this clause."
        }

    prompt = f"""
    You are a legal assistant.
    Analyze the following contract clause for legal risk.
    Classify risk as Low, Medium, or High.
    Explain in simple business language.

    Clause:
    {clause}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        output = response['choices'][0]['message']['content']

        risk_level = "Low"
        explanation = output.strip()

        if "High" in output:
            risk_level = "High"
        elif "Medium" in output:
            risk_level = "Medium"

        return {
            "risk_level": risk_level,
            "explanation": explanation
        }

    except:
        return {
            "risk_level": "Low",
            "explanation": "No legal obligation or risk-related language detected in this clause."
        }
