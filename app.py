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
    save_audit_log,
    strip_html_tags
)

# ─── Database & Auth imports ──────────────────────────────────────────────
from db import (
    init_db,
    save_analysis, list_analyses, save_embedding, delete_analysis, get_conn,
    verify_user, get_user_by_email, register_user,
    q  # ← Import the q() helper for SQL placeholder conversion
)

# ────────────────────────────────────────────────
#  Page configuration
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="📄 SME Contract Analysis & Risk Bot",
    page_icon="📄",
    layout="wide"
)

# Initialize DB
init_db()
# try:
#     ensure_migrations()
# except Exception:
#     pass

# Cached models
@st.cache_resource
def load_spacy_model():
    import spacy
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return spacy.blank("en")

@st.cache_resource
def load_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None

nlp = load_spacy_model()
embed_model = load_embedding_model()

# ────────────────────────────────────────────────
#  Custom styles
# ────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f172a !important; }
    section[data-testid="stSidebar"] { background-color: #1e293b !important; }
    .header {
        background: linear-gradient(90deg, #1e40af, #60a5fa) !important;
        color: white !important;
        padding: 1.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .risk-card, .preview, div[data-testid="stMetric"] {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .stMetricValue { font-size: 2.4rem !important; font-weight: 700 !important; }
    .stMetricLabel { font-size: 1.1rem !important; color: #4b5563 !important; }
    .preview { color: #f1f5f9 !important; border-left: 5px solid #60a5fa !important; padding-left: 1rem; }
    .mark { background: #ca8a04 !important; color: #fefce8 !important; padding: 2px 4px; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header">
    <h1>📄 SME Contract Analysis & Risk Bot</h1>
    <p>Fast clause-level risk scanning for Indian SMEs</p>
</div>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
#  Authentication Logic
# ────────────────────────────────────────────────

if "user" not in st.session_state:
    st.session_state.user = None

def logout():
    st.session_state.user = None
    for key in list(st.session_state.keys()):
        if key not in ["user", "analyses_refresh"]:
            del st.session_state[key]
    st.rerun()

# ─── Sidebar – Auth + Upload ──────────────────────────────────────────────
with st.sidebar:

    st.title("👤 Account")

    if st.session_state.user is None:
        tab_login, tab_reg = st.tabs(["Login", "Register"])

        with tab_login:
            st.subheader("Login")
            login_email = st.text_input("Email", key="login_email_input")
            login_pw = st.text_input("Password", type="password", key="login_pw_input")

            if st.button("🔑 Login", type="primary", use_container_width=True):
                if not login_email.strip() or not login_pw.strip():
                    st.error("Please enter email and password")
                else:
                    user_id = verify_user(login_email.strip(), login_pw)
                    if user_id:
                        user = get_user_by_email(login_email.strip())
                        if user is not None:
                            st.session_state.user = user
                            st.success(f"Welcome, {user['email']}")
                            st.rerun()
                        else:
                            st.error("User record not found despite successful password check")
                    else:
                        st.error("Invalid email or password")

        with tab_reg:
            st.subheader("Register")
            reg_email = st.text_input("Email", key="reg_email_input")
            reg_pw = st.text_input("Password", type="password", key="reg_pw_input")
            reg_pw_confirm = st.text_input("Confirm password", type="password", key="reg_confirm_input")

            if st.button("Create Account", type="primary", use_container_width=True):
                email_clean = reg_email.strip()
                if not email_clean or not reg_pw:
                    st.error("Email and password are required")
                elif reg_pw != reg_pw_confirm:
                    st.error("Passwords do not match")
                elif len(reg_pw) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register_user(email_clean, reg_pw)
                    if success:
                        st.success(message)
                        st.info("You can now log in above →")
                    else:
                        st.error(message)

    else:
        # Logged in view
        st.success(f"Logged in as: **{st.session_state.user['email']}**")
        if st.button("Logout", type="secondary", use_container_width=True):
            logout()

        st.markdown("---")

        st.title("📤 Upload & Options")

        uploaded_file = st.sidebar.file_uploader(
            "Upload Contract (PDF / DOCX / TXT)",
            type=["pdf", "docx", "txt"]
        )

        advanced = st.sidebar.checkbox("Enable advanced NLP (NER, obligations)", value=True)
        export_json = st.sidebar.checkbox("Enable JSON export of audit log", value=True)

# ────────────────────────────────────────────────
#  Require login for main content
# ────────────────────────────────────────────────
if st.session_state.user is None:
    st.warning("🔐 Please log in or register to use the Contract Analysis tool.")
    st.stop()

# ────────────────────────────────────────────────
#  Main app – only shown when logged in
# ────────────────────────────────────────────────

# Load & process contract
contract_text: Optional[str] = None
if uploaded_file is not None:
    contract_text = load_contract_text(uploaded_file)

if not contract_text:
    st.info("Please upload a contract (PDF, DOCX or TXT) to begin analysis.")
    st.stop()

# Clean early
contract_text = strip_html_tags(contract_text)

# Language detection
lang = detect_language(contract_text)
st.sidebar.markdown(f"**Detected language:** {lang}")

normalized_text = contract_text
if lang.lower().startswith("hi"):
    normalized_text = normalize_to_english(contract_text)

# Clause extraction & analysis
clauses = extract_clauses(normalized_text)

rows = []
for i, clause in enumerate(clauses, start=1):
    clause = strip_html_tags(clause)
    ner_entities = []
    obligations = []

    if advanced and nlp:
        doc = nlp(clause)
        # Uncomment if you want NER and obligations extraction
        # ner_entities = [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
        # obligations = []
        # for sent in getattr(doc, "sents", []):
        #     if re.search(r'\bshall\b|\bmust\b|\bagree to\b|\bwill\b', sent.text, flags=re.I):
        #         obligations.append(sent.text)

    risk, reasons, risk_score = analyze_clause_risk(clause)
    suggestion = suggest_alternatives_for_clause(clause, risk, reasons)

    rows.append({
        "id": i,
        "clause": clause,
        "risk": risk,
        "risk_score": risk_score,
        "reasons": reasons,
        "entities": ner_entities,
        "obligations": obligations,
        "suggestion": suggestion,
        "comment": ""
    })

df = pd.DataFrame(rows)

# ────────────────────────────────────────────────
#  KPIs
# ────────────────────────────────────────────────
col_lang, col_total, col_high, col_medium, col_low = st.columns(5)

col_lang.markdown(
    f"<div style='text-align:center; padding:1rem; background:#1e293b; border-radius:6px;'>"
    f"🌐 Language: <b>{lang.upper()}</b>"
    f"</div>",
    unsafe_allow_html=True
)

col_total.metric("Total Clauses", len(df))

if not df.empty and "risk" in df.columns:
    high_count   = int((df["risk"] == "High").sum())
    medium_count = int((df["risk"] == "Medium").sum())
    low_count    = int((df["risk"] == "Low").sum())
    col_high.metric("🔴 High",   high_count)
    col_medium.metric("🟠 Medium", medium_count)
    col_low.metric("🟢 Low",    low_count)
else:
    col_high.metric("🔴 High",   0)
    col_medium.metric("🟠 Medium", 0)
    col_low.metric("🟢 Low",    0)

# ────────────────────────────────────────────────
#  Similarity Search
# ────────────────────────────────────────────────
st.markdown("### 🔍 Find similar clauses")

query = st.text_input("Enter text to find similar clauses", "")

if query and embed_model is not None and not df.empty:
    docs = df["clause"].tolist()

    if "clause_embeddings" not in st.session_state:
        with st.spinner("Computing embeddings..."):
            embeddings = embed_model.encode(docs, convert_to_numpy=True)
            st.session_state["clause_embeddings"] = embeddings

    q_emb = embed_model.encode(query, convert_to_numpy=True)
    import numpy as np
    from sentence_transformers import util

    similarities = util.cos_sim(q_emb, st.session_state["clause_embeddings"])[0]
    top_indices = similarities.argsort(descending=True)[:5]

    if len(top_indices) == 0:
        st.info("No similar clauses found.")
    else:
        st.markdown("**Top similar clauses:**")
        for rank, idx in enumerate(top_indices, 1):
            row = df.iloc[int(idx)]
            score = float(similarities[idx]) * 100
            clean_clause = html.escape(row['clause'][:600])

            if query.strip():
                for term in query.split():
                    if len(term.strip()) > 2:
                        clean_clause = re.sub(
                            re.escape(term),
                            f"<span style='background:#fef08a;color:#854d0e;padding:1px 4px;border-radius:3px;'>{term}</span>",
                            clean_clause,
                            flags=re.I
                        )

            st.markdown(
                f"""
                <div style="background:#1e293b; padding:1rem; border-radius:6px; margin-bottom:1rem;">
                    <div style="display:flex; justify-content:space-between;">
                        <strong>Rank {rank} — Clause {row['id']}</strong>
                        <span style="color:#9ca3af;">{score:.1f}% match</span>
                    </div>
                    <div style="margin-top:0.75rem; white-space:pre-wrap;">
                        {clean_clause}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ────────────────────────────────────────────────
#  Clause display
# ────────────────────────────────────────────────
st.markdown("### 📑 Risk Analysis by Clause")

for idx, row in df.iterrows():
    clause_num = row['id']
    full_text = row['clause'].strip()

    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
    title = "Clause Content"
    body = full_text
    if lines:
        title = re.sub(r'^\d+\.?\s*|Clause\s*\d+\s*[-—]?\s*', '', lines[0], flags=re.I).strip()
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else full_text

    risk_lower = row['risk'].lower()
    if risk_lower == 'high':
        badge = "🔴 HIGH RISK"
    elif risk_lower == 'medium':
        badge = "🟠 MEDIUM RISK"
    else:
        badge = "🟢 LOW RISK"

    reasons_list = [r.strip() for r in (row['reasons'] or '').split(',') if r.strip()]
    highlighted_body = body
    for term in reasons_list:
        if term and len(term) > 2:
            highlighted_body = re.sub(
                re.escape(term),
                f"<span style='background:#fef08a;color:#854d0e;padding:1px 4px;border-radius:3px;'>{term}</span>",
                highlighted_body,
                flags=re.I
            )

    body_with_breaks = highlighted_body.replace('\n', '  \n')

    main_reason = row.get('explanation', f"Key issues: {row['reasons'] or '—'}").strip()

    st.markdown(f"""
**Clause {clause_num} — {badge} {title}**

{body_with_breaks}

* **Risk Level**: {row['risk']} Risk
* **Main Reason**: {main_reason}

**Detected issues**: {', '.join(reasons_list) if reasons_list else '—'}
    """, unsafe_allow_html=True)

    if row.get('suggestion'):
        st.markdown(f"""
> 💡 **Suggested rewrite**  
> {row['suggestion'].strip()}
        """)

    st.markdown("---")

# ────────────────────────────────────────────────
#  Save / Export – now requires login
# ────────────────────────────────────────────────
st.sidebar.markdown("### 💾 Save / Export")
name = st.sidebar.text_input("Analysis name", f"My Analysis {datetime.now().date()}")

if st.sidebar.button("💾 Save analysis"):
    clauses_data = [{str(k): v for k, v in row.items()} for row in df.to_dict(orient="records")]

    analysis_id = save_analysis(
        name=name,
        language=lang,
        raw_text=contract_text,
        clauses=clauses_data,
        owner_id=st.session_state.user["id"]
    )

    if analysis_id is not None:
        if embed_model is not None:
            vectors = embed_model.encode(df["clause"].tolist(), convert_to_numpy=True).tolist()
            for r, vec in zip(df.to_dict(orient="records"), vectors):
                save_embedding(int(analysis_id), int(r["id"]), "all-MiniLM-L6-v2", vec)

        audit = {
            "analysis_id": analysis_id,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "language": lang,
            "total_clauses": len(df),
            "summary": summarize_contract_plain_english(contract_text, df),
            "clauses": clauses_data
        }
        save_audit_log(analysis_id, audit, export_json=export_json)

        st.sidebar.success(f"Analysis saved! (ID: {analysis_id})")
        st.session_state.pop("current_analyses", None)
        st.session_state["analyses_refresh"] = datetime.now().timestamp()
        st.rerun()
    else:
        st.sidebar.error("Save failed.")

# ────────────────────────────────────────────────
#  SME-friendly templates
# ────────────────────────────────────────────────
st.markdown("### 🧾 SME-friendly Templates & Suggested Rewrites")
templates = load_templates()
for t in templates[:6]:
    st.markdown(f"**{t['title']}** — {t['description']}")
    st.code(t['text'][:800] + ("..." if len(t['text']) > 800 else ""))

# ────────────────────────────────────────────────
#  Admin Tools – List + Delete (now per user)
# ────────────────────────────────────────────────
st.sidebar.markdown("### Admin Tools")

if "analyses_refresh" not in st.session_state:
    st.session_state["analyses_refresh"] = 0.0

if st.sidebar.button("📋 Refresh / Manage Analyses", key=f"list_{st.session_state['analyses_refresh']}"):
    analyses = list_analyses(owner_id=st.session_state.user["id"]) or []
    st.session_state["current_analyses"] = analyses
else:
    analyses = st.session_state.get("current_analyses", list_analyses(owner_id=st.session_state.user["id"]) or [])

if not analyses:
    st.sidebar.info("No saved analyses yet.")
else:
    st.sidebar.markdown(f"**Your Saved Analyses ({len(analyses)})**")

    hcols = st.sidebar.columns([1, 5, 3, 1, 1])
    hcols[0].markdown("**ID**")
    hcols[1].markdown("**Name**")
    hcols[2].markdown("**Date**")
    hcols[3].markdown("**Lang**")
    hcols[4].markdown("**Action**")

    st.sidebar.markdown("---")

    for item in analyses:
        row = item if isinstance(item, dict) else {
            "id": item[0],
            "name": item[1],
            "created_at": item[2],
            "language": item[3],
            "total_clauses": item[4] if len(item) > 4 else None
        }

        cols = st.sidebar.columns([1, 5, 3, 1, 1])
        cols[0].write(row["id"])
        cols[1].write(row["name"][:32] + "…" if len(row["name"]) > 32 else row["name"])
        created = row.get("created_at")
        date_str = (
            created.strftime("%Y-%m-%d") if isinstance(created, datetime) else
            (created[:10] if isinstance(created, str) and len(created) >= 10 else "-")
        )
        cols[2].write(date_str)
        cols[3].write(row.get("language", "?").upper())

        del_key = f"del_{row['id']}_{st.session_state['analyses_refresh']}"
        if cols[4].button("🗑", key=del_key):
            st.session_state["confirm_delete_id"] = row["id"]
            st.rerun()

# Confirmation dialog for delete
if "confirm_delete_id" in st.session_state:
    cid = st.session_state["confirm_delete_id"]
    analyses = st.session_state.get("current_analyses", list_analyses(owner_id=st.session_state.user["id"]) or [])
    name = "this analysis"
    for it in analyses:
        if (isinstance(it, tuple) and it[0] == cid) or (isinstance(it, dict) and it.get("id") == cid):
            name = it[1] if isinstance(it, tuple) else it.get("name", name)
            break

        st.sidebar.warning(f'**Delete #{cid}?**  \n"{name}" will be **permanently removed**.')

    c1, c2 = st.sidebar.columns(2)

    if c1.button("Yes – Delete", key=f"yes_{cid}"):
        try:
            delete_analysis(cid)
            st.sidebar.success(f"Deleted #{cid}")
            st.session_state.pop("confirm_delete_id", None)
            st.session_state["analyses_refresh"] += 1
            st.session_state.pop("current_analyses", None)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Delete failed: {str(e)}")
            st.session_state.pop("confirm_delete_id", None)
            st.rerun()

    if c2.button("Cancel", key=f"no_{cid}"):
        st.session_state.pop("confirm_delete_id", None)
        st.rerun()

# Final footer
if not looks_like_contract(contract_text):
    st.warning("⚠️ Uploaded document may not be a legal contract (low keyword density).")

st.markdown("---")
st.caption("Built for Indian SMEs • Clause-level risk scoring • Plain language explanations • Suggested alternatives • Audit trail")

# ─── Danger Zone - FIXED VERSION ──────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("**Danger Zone**")

if st.sidebar.button("🧹 Delete ALL **YOUR** Analyses", type="primary"):
    st.sidebar.error("**This will permanently delete ALL your saved analyses!**")
    st.sidebar.warning("This cannot be undone.")
    
    if st.sidebar.button("Yes – Delete All My Analyses", type="primary"):
        with st.sidebar.spinner("Deleting your analyses..."):
            try:
                conn = get_conn()
                cur = conn.cursor()
                user_id = st.session_state.user["id"]
                
                # Use q() to convert placeholders automatically for SQLite/MySQL compatibility
                cur.execute(q("DELETE FROM embeddings WHERE analysis_id IN (SELECT id FROM analyses WHERE owner_id = %s)"), (user_id,))
                cur.execute(q("DELETE FROM clauses WHERE analysis_id IN (SELECT id FROM analyses WHERE owner_id = %s)"), (user_id,))
                cur.execute(q("DELETE FROM analyses WHERE owner_id = %s"), (user_id,))
                
                conn.commit()
                conn.close()

                st.session_state.pop("current_analyses", None)
                st.session_state["analyses_refresh"] = datetime.now().timestamp()

                st.sidebar.success("**All your analyses have been deleted.**")
                st.rerun()
                
            except Exception as e:
                st.sidebar.error(f"Reset failed: {str(e)}")
                if 'conn' in locals() and hasattr(conn, 'close'):
                    try:
                        conn.close()
                    except:
                        pass