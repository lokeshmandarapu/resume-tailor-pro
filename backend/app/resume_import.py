"""Parse an uploaded resume (PDF or DOCX) into the structured master Resume.
Raw text extraction is deterministic; the LLM only structures it (no invention)."""
from __future__ import annotations
import io
from .schema import Resume
from . import llm

_SYS = (
    "You convert raw resume text into structured JSON. Return ONLY JSON with keys: name, contact "
    "(one line: location | email | phone | links), work_authorization (empty unless stated), summary "
    "(empty unless the resume has one), experience[company,title,location,dates,stack,bullets[]], "
    "projects[name,stack,bullets[]], skills[] (each 'Category: a, b, c'), education[school,location,"
    "dates,degree,coursework], achievements[]. COPY the content faithfully — do NOT invent, embellish, "
    "summarize, or drop anything. Keep bullets verbatim. Keep experience in the original order."
)


def _pdf_text(data: bytes) -> str:
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)


def _docx_text(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def import_resume(filename: str, data: bytes) -> Resume:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        raw = _pdf_text(data)
    elif name.endswith(".docx"):
        raw = _docx_text(data)
    else:
        raw = data.decode("utf-8", errors="ignore")
    raw = raw.strip()
    if not raw:
        raise ValueError("Could not extract any text from the uploaded file.")
    data_json = llm.call_json(_SYS, f"RAW RESUME TEXT:\n{raw}", heavy=False, temperature=0.0)
    data_json.pop("section_order", None)
    return Resume(**{k: data_json.get(k, getattr(Resume(), k)) for k in Resume.model_fields})
