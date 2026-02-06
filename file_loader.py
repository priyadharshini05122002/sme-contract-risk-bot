# file_loader.py
from typing import Optional
from io import BytesIO


def load_contract_text(uploaded_file) -> Optional[str]:
    """
    Extract text from uploaded contract files.
    Supports: PDF, DOCX, TXT.
    Returns cleaned string or None.
    """
    if not uploaded_file:
        return None

    name = uploaded_file.name.lower()

    try:
        # ---------- TXT ----------
        if name.endswith(".txt"):
            content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
            return content.strip() if content else None

        # ---------- PDF ----------
        elif name.endswith(".pdf"):
            from PyPDF2 import PdfReader

            data = uploaded_file.read()
            reader = PdfReader(BytesIO(data))

            pages = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        pages.append(text.strip())
                except Exception:
                    continue

            full_text = "\n\n".join(pages)
            return full_text if full_text else None

        # ---------- DOCX ----------
        elif name.endswith(".docx"):
            import docx

            data = uploaded_file.read()
            doc = docx.Document(BytesIO(data))

            paragraphs = []
            for p in doc.paragraphs:
                if p.text and p.text.strip():
                    paragraphs.append(p.text.strip())

            full_text = "\n\n".join(paragraphs)
            return full_text if full_text else None

        # ---------- FALLBACK ----------
        else:
            content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
            return content.strip() if content else None

    except Exception:
        # Prevent Streamlit crash if parsing fails
        return None