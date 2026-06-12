"""Stages 3 & 4: grounded, deletion-proof tailoring + verification.

Design (per the research):
- The LLM is an EDITOR, not an author. Factual fields (name, contact, company, title, dates,
  education) are locked from the original and never pass through generation.
- Experience and projects are rebuilt BY INDEX from the original, so a role/project can never be
  dropped, merged, or reordered out of existence — only its bullets are improved.
- Low temperature + explicit preservation guardrails reduce variance.
- A fabrication check removes any skill not grounded in the master resume.
- Truthful adjacent surfacing: if a JD wants a sibling skill the candidate lacks but holds another
  member of the same family, we surface the UMBRELLA term with the real tool in parentheses.
"""
from __future__ import annotations
from typing import List, Tuple
from .schema import Resume, JDKeywords, Experience, Project
from .taxonomy import term_present, NON_SKILL_CONCEPTS, adjacent_held
from .score import resume_text
from . import llm

_SYS = (
    "You are an expert software-engineering resume EDITOR tailoring a candidate's REAL resume to one "
    "job. You improve and reorder existing content and weave in truthful keywords. You are an editor, "
    "not an author. Return ONLY JSON matching the resume schema.\n"
    "HARD CONSTRAINTS (constraints, not suggestions):\n"
    "1. The output `experience` array MUST contain EXACTLY the same number of entries as the input, "
    "in the same order. NEVER remove, merge, drop, or reorder a role, project, or section.\n"
    "2. Preserve every job title, company, employment date, and numeric metric EXACTLY. Do not alter, "
    "round, or invent any number.\n"
    "3. Do NOT add any skill, tool, technology, role, achievement, or responsibility not present in "
    "the input resume. If the candidate lacks a JD skill, do NOT add it.\n"
    "4. You MAY rephrase bullet prose (active voice, action-verb first, XYZ: result+metric+how), "
    "reorder bullets WITHIN a role, and lead with the most JD-relevant bullet. Keep specific named "
    "systems and scale; never genericize. ~13-30 words per bullet, one line. No lead verb reused >2x.\n"
    "5. For each REQUIRED skill the candidate genuinely has, make sure it appears IN AN EXPERIENCE OR "
    "PROJECT BULLET (in context, describing real work) — not only in the skills list — wherever their "
    "real work supports it. A skill shown in a bullet is stronger than one merely listed. Use the JD's "
    "exact terminology. At most ~3 mentions of any term across the whole resume. No keyword stuffing.\n"
    "6. SKILLS: at most 5 grouped lines, hard tech only (languages, frameworks, tools, platforms, "
    "databases). Exclude concepts/traits (idempotency, fault tolerance, scalability, leadership). "
    "Use the JD's exact strings for skills the candidate genuinely has.\n"
    "7. Keep every experience entry you were given. This is a hard constraint, not a suggestion."
)


def _tailor_bullets(resume: Resume, kw: JDKeywords, jd_text: str) -> Resume | None:
    payload = (
        f"TARGET TITLE: {kw.target_title}\nCOMPANY: {kw.company}\n"
        f"REQUIRED SKILLS: {', '.join(kw.required_hard)}\n"
        f"PREFERRED: {', '.join(kw.preferred)}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"CANDIDATE MASTER RESUME (JSON):\n{resume.model_dump_json()}\n\n"
        f"Return the tailored resume as JSON with EXACTLY {len(resume.experience)} experience "
        f"entries and {len(resume.projects)} project entries, same order. Invent nothing."
    )
    try:
        data = llm.call_json(_SYS, payload, heavy=True, temperature=0.1)
        data.pop("section_order", None)
        return Resume(**{k: data.get(k, getattr(resume, k)) for k in Resume.model_fields})
    except Exception:
        return None


def tailor(resume: Resume, kw: JDKeywords, jd_text: str) -> Tuple[Resume, List[str], List[str]]:
    """Return (tailored_resume, flagged_skills, adjacent_notes)."""
    gen = _tailor_bullets(resume, kw, jd_text)
    if gen is None:
        return resume, [], []   # safe fallback: original untouched

    # ---- deletion-proof reconstruction: lock facts from ORIGINAL, take only improved bullets ----
    out = Resume(
        name=resume.name, contact=resume.contact, work_authorization=resume.work_authorization,
        summary=(gen.summary if (resume.summary or "").strip() else ""),  # follow uploaded resume
        education=resume.education, achievements=resume.achievements or gen.achievements,
    )

    new_exp = []
    for i, orig in enumerate(resume.experience):
        g = gen.experience[i] if i < len(gen.experience) else None
        bullets = g.bullets if (g and g.bullets) else orig.bullets   # never empty
        new_exp.append(Experience(company=orig.company, title=orig.title, location=orig.location,
                                  dates=orig.dates, stack=orig.stack, bullets=bullets))
    out.experience = new_exp     # exactly len(original), same order, facts verbatim

    new_proj = []
    for i, orig in enumerate(resume.projects):
        g = gen.projects[i] if i < len(gen.projects) else None
        bullets = g.bullets if (g and g.bullets) else orig.bullets
        new_proj.append(Project(name=orig.name, stack=orig.stack, bullets=bullets))
    out.projects = new_proj

    # ---- skills: take the model's, but drop anything not grounded in the master (anti-fabrication)
    master_low = resume_text(resume).lower()
    flagged, clean = [], []
    for line in (gen.skills or resume.skills):
        if ":" in line:
            cat, items = line.split(":", 1)
            kept = []
            for item in items.split(","):
                it = item.strip()
                if not it or it.lower() in NON_SKILL_CONCEPTS:
                    continue
                if term_present(it, master_low):
                    kept.append(it)
                else:
                    flagged.append(it)
            if kept:
                clean.append(f"{cat.strip()}: {', '.join(kept)}")
        else:
            clean.append(line)
    out.skills = clean[:5] or resume.skills

    # ---- coverage guard: re-add owned JD-required skills that got dropped ----
    out_low = resume_text(out).lower()
    readd = [s for s in kw.required_hard if term_present(s, master_low) and not term_present(s, out_low)]
    if readd and out.skills:
        out.skills[-1] = out.skills[-1].rstrip(", ") + ", " + ", ".join(readd)
    elif readd:
        out.skills = ["Skills: " + ", ".join(readd)]

    # ---- truthful adjacent detection: JD wants a sibling the candidate lacks but holds a family member.
    # We do NOT inject umbrella terms into the resume (keeps it clean / avoids padding); instead we
    # report it so the score gives partial credit and the user knows what to speak to in interviews.
    out_low = resume_text(out).lower()
    adjacent = []
    for s in kw.required_hard + kw.preferred:
        if term_present(s, out_low):
            continue
        hit = adjacent_held(s, master_low)
        if hit:
            umbrella, held = hit
            adjacent.append(f"{s}: covered via related experience — {umbrella} (you have {held})")

    return out, sorted(set(flagged)), adjacent
