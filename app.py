import streamlit as st
import re
import json
import html
import pandas as pd
from typing import Optional
from datetime import datetime

from file_loader import load_contract_text
from language_detector import detect_language, normalize_to_english
from clause_extractor import extract_clauses
from utils import (
    looks_like_contract,
    analyze_clause_risk,
    suggest_alternatives_for_clause,
    load_templates,
    summarize_contract_plain_english,
    strip_html_tags
)

# Page config
st.set_page_config(
    page_title="📄 SME Contract Analysis & Risk Bot",
    page_icon="📄",
    layout="wide"
)

# Load embedding model (local only)
@st.cache_resource
def load_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None

embed_model = load_embedding_model()

# UI Header
st.markdown("""
<div style="background: linear-gradient(90deg,#1e40af,#60a5fa);color:white;padding:1.5rem;border-radius:8px;margin-bottom:1.5rem;">
    <h1>📄 SME Contract Analysis & Risk Bot</h1>
    <p>Fast clause-level risk scanning for Indian SMEs</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title("📤 Upload Contract")
uploaded_file = st.sidebar.file_uploader(
    "Upload Contract (PDF / DOCX / TXT)",
    type=["pdf", "docx", "txt"]
)

advanced = st.sidebar.checkbox("Enable advanced NLP", value=True)

# Load contract
contract_text: Optional[str] = None
if uploaded_file is not None:
    contract_text = load_contract_text(uploaded_file)

if not contract_text:
    st.info("Please upload a contract to begin analysis.")
    st.stop()

contract_text = strip_html_tags(contract_text)

# Language detection
lang = detect_language(contract_text)
st.sidebar.markdown(f"**Detected language:** {lang}")

normalized_text = contract_text
if lang.lower().startswith("hi"):
    normalized_text = normalize_to_english(contract_text)

# Extract clauses
clauses = extract_clauses(normalized_text)

rows = []
for i, clause in enumerate(clauses, start=1):
    clause = strip_html_tags(clause)

    risk, reasons, risk_score = analyze_clause_risk(clause)
    suggestion = suggest_alternatives_for_clause(clause, risk, reasons)

    rows.append({
        "id": i,
        "clause": clause,
        "risk": risk,
        "risk_score": risk_score,
        "reasons": reasons,
        "suggestion": suggestion
    })

df = pd.DataFrame(rows)

# KPIs
col_total, col_high, col_medium, col_low = st.columns(4)
col_total.metric("Total Clauses", len(df))
col_high.metric("🔴 High", int((df["risk"] == "High").sum()))
col_medium.metric("🟠 Medium", int((df["risk"] == "Medium").sum()))
col_low.metric("🟢 Low", int((df["risk"] == "Low").sum()))

# Similarity search (in memory)
st.markdown("### 🔍 Find similar clauses")
query = st.text_input("Enter text")

if query and embed_model is not None and not df.empty:
    docs = df["clause"].tolist()

    if "embeddings" not in st.session_state:
        embeddings = embed_model.encode(docs, convert_to_numpy=True)
        st.session_state["embeddings"] = embeddings

    from sentence_transformers import util
    q_emb = embed_model.encode(query, convert_to_numpy=True)
    sims = util.cos_sim(q_emb, st.session_state["embeddings"])[0]
    top = sims.argsort(descending=True)[:5]

    for idx in top:
        row = df.iloc[int(idx)]
        st.markdown(f"**Clause {row['id']}** — {row['clause']}")

# Clause analysis
st.markdown("### 📑 Risk Analysis by Clause")

for _, row in df.iterrows():
    st.markdown(f"""
**Clause {row['id']}**

{row['clause']}

Risk: **{row['risk']}**

Reasons: {row['reasons']}
""")

    if row.get("suggestion"):
        st.markdown(f"> 💡 Suggested rewrite\n> {row['suggestion']}")

    st.markdown("---")

# Templates
st.markdown("### 🧾 SME-friendly Templates")
templates = load_templates()

for t in templates[:6]:
    st.markdown(f"**{t['title']}** — {t['description']}")
    st.code(t['text'][:800])

# Warning
if not looks_like_contract(contract_text):
    st.warning("⚠️ Uploaded document may not be a legal contract.")

st.caption("Clause-level risk scoring • Plain language explanations • Suggested alternatives")
