import streamlit as st
import re
from file_loader import load_contract_text
from language_detector import detect_language
from utils import looks_like_contract

# ---------------- Page Config ----------------
st.set_page_config(page_title="📄 SME Contract Risk Bot")

st.title("📄 SME Contract Analysis & Risk Bot")

# ---------------- HIGH-RISK KEYWORDS ----------------
HIGH_RISK_KEYWORDS = [
    "unlimited liability",
    "without limitation",
    "terminate at any time",
    "without notice",
    "no compensation",
    "sole discretion",
    "withheld",
    "exclusive property",
    "without additional compensation",
    "indemnify",
    "hold harmless",
    "own negligence"
]

MEDIUM_RISK_KEYWORDS = [
    "governing law",
    "jurisdiction",
    "terminate",
    "liability",
    "compensation"
]

# ---------------- Clause Splitter ----------------
def extract_clauses(text):
    pattern = r"\n(?=\d+\.)"
    clauses = re.split(pattern, text)
    return [c.strip() for c in clauses if len(c.strip()) > 30]

# ---------------- Risk Analyzer ----------------
def analyze_risk(clause):
    clause_lower = clause.lower()
    score = 0

    for word in HIGH_RISK_KEYWORDS:
        if word in clause_lower:
            score += 2

    for word in MEDIUM_RISK_KEYWORDS:
        if word in clause_lower:
            score += 1

    if score >= 4:
        return {
            "risk_level": "High",
            "explanation": "Contains strong unfavorable legal obligations."
        }
    elif score >= 2:
        return {
            "risk_level": "Medium",
            "explanation": "Contains potentially risky legal terms."
        }
    else:
        return {
            "risk_level": "Low",
            "explanation": "No strong risk indicators detected."
        }

# ---------------- File Upload ----------------
uploaded_file = st.file_uploader(
    "Upload Contract (PDF / DOCX / TXT)",
    type=["pdf", "docx", "txt"]
)

# ---------------- Main Logic ----------------
if uploaded_file:
    contract_text = load_contract_text(uploaded_file)

    st.subheader("📜 Extracted Contract Text")
    st.text_area("Contract Content", contract_text, height=200)

    lang = detect_language(contract_text)
    st.write(f"🌐 Detected Language: **{lang}**")

    if not looks_like_contract(contract_text):
        st.warning("⚠️ The uploaded document does not appear to be a legal contract.")

    clauses = extract_clauses(contract_text)
    st.subheader("🧩 Clause-level Risk Analysis")

    high_risk_count = 0
    medium_risk_count = 0

    for clause in clauses:
        result = analyze_risk(clause)
        risk = result["risk_level"]
        explanation = result["explanation"]

        if risk == "High":
            st.markdown(
                f"<span style='color:red'>**Clause:** {clause}</span>",
                unsafe_allow_html=True
            )
            st.markdown(
                "<span style='color:red'>⚠️ Risk Level: High</span>",
                unsafe_allow_html=True
            )
            high_risk_count += 1

        elif risk == "Medium":
            st.markdown(
                f"<span style='color:orange'>**Clause:** {clause}</span>",
                unsafe_allow_html=True
            )
            st.markdown(
                "<span style='color:orange'>⚠️ Risk Level: Medium</span>",
                unsafe_allow_html=True
            )
            medium_risk_count += 1

        else:
            st.markdown(f"**Clause:** {clause}")
            st.write("⚠️ Risk Level: Low")

        st.write(f"💡 Explanation: {explanation}")
        st.divider()

    # ---------------- Summary ----------------
    st.subheader("📝 Contract Summary")
    st.write(f"Total Clauses: {len(clauses)}")
    st.write(f"🔴 High Risk Clauses: {high_risk_count}")
    st.write(f"🟠 Medium Risk Clauses: {medium_risk_count}")
