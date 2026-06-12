"""Stage 1: extract structured keywords from a raw JD.

LLM does the semantic lifting (required vs preferred, title, company values, sponsorship flag);
a deterministic taxonomy pass then guarantees obvious hard skills present in the text are never
missed, even if the LLM omits them."""
from __future__ import annotations
import re
from .schema import JDKeywords
from .taxonomy import ALIASES, term_present
from . import llm

_SYS = (
    "You extract structured hiring signals from a job description for resume tailoring. "
    "Return ONLY JSON with keys: target_title (string), required_hard (array of concrete hard "
    "skills/tools/languages explicitly required), preferred (array of nice-to-have/bonus/preferred "
    "skills), soft (array of soft skills/competencies), company (string, or empty), values (array of "
    "culture/leadership cues, e.g. 'ownership', 'customer obsession'), requires_no_sponsorship "
    "(boolean: true ONLY if the JD explicitly says it will NOT sponsor visas). "
    "Use the JD's exact surface terms for skills. Do not invent skills not in the JD."
)

_NO_SPONSOR = re.compile(
    r"(no(t)?\s+(able\s+to\s+)?(provide|offer)\s+sponsor|will\s+not\s+sponsor|"
    r"unable\s+to\s+sponsor|without\s+sponsor|no\s+visa\s+sponsor|"
    r"must\s+be\s+(a\s+)?(us|u\.s\.)\s+citizen|us\s+citizens?\s+only)", re.I)


def extract_jd(jd_text: str) -> JDKeywords:
    jd_text = (jd_text or "").strip()
    try:
        data = llm.call_json(_SYS, f"JOB DESCRIPTION:\n{jd_text}", heavy=False, temperature=0.0)
        kw = JDKeywords(**{k: data.get(k) for k in JDKeywords.model_fields if k in data})
    except Exception:
        kw = JDKeywords()

    # deterministic backstop: scan for any known hard skill literally present in the JD
    low = jd_text.lower()
    have = {s.lower() for s in (kw.required_hard + kw.preferred)}
    for canon_key in ALIASES:
        if term_present(canon_key, low) and canon_key not in have:
            kw.required_hard.append(canon_key)
            have.add(canon_key)

    # sponsorship knockout — regex is authoritative (don't rely on the model alone)
    if _NO_SPONSOR.search(jd_text):
        kw.requires_no_sponsorship = True

    # de-dupe, keep order, drop empties
    def dedupe(xs):
        seen, out = set(), []
        for x in xs:
            c = (x or "").strip()
            if c and c.lower() not in seen:
                seen.add(c.lower()); out.append(c)
        return out

    kw.required_hard = dedupe(kw.required_hard)
    kw.preferred = dedupe([p for p in kw.preferred if p.lower() not in {r.lower() for r in kw.required_hard}])
    kw.soft = dedupe(kw.soft)
    kw.values = dedupe(kw.values)
    return kw
