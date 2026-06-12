"""Stages 2 & 5: deterministic gap analysis and the honest, explainable score.

The score models what ATS + recruiters actually reward (from the research):
  required hard-skill coverage 35 | title alignment 20 | parse-safety 20 |
  evidence-backed bullet quality 15 | preferred & values 10
It is a PRE-SUBMISSION DIAGNOSTIC, not a real-ATS verdict, and it never rewards stuffing."""
from __future__ import annotations
import re
from typing import List, Tuple
from .schema import Resume, JDKeywords, Score, SubScore
from .taxonomy import term_present, adjacent_held

_METRIC = re.compile(r"\d|%|\bms\b|\brps\b|\btps\b|million|billion|thousand|\bk\b|x\b", re.I)
_WEAK = re.compile(r"\b(helped|worked on|responsible for|assisted|involved in|various|several)\b", re.I)
_STRONG_START = re.compile(r"^\s*(led|built|designed|architected|reduced|cut|achieved|engineered|"
                           r"implemented|optimized|scaled|automated|delivered|launched|migrated|"
                           r"improved|increased|decreased|drove|shipped|created|developed|deployed)\b", re.I)


def resume_text(r: Resume) -> str:
    parts = [r.name, r.contact, r.summary]
    for e in r.experience:
        parts += [e.company, e.title, e.stack] + e.bullets
    for p in r.projects:
        parts += [p.name, p.stack] + p.bullets
    parts += r.skills
    for ed in r.education:
        parts += [ed.school, ed.degree, ed.coursework]
    parts += r.achievements
    return "\n".join(x for x in parts if x)


def gap(kw: JDKeywords, r: Resume):
    """Return (matched, missing_required, missing_preferred, adjacent).
    adjacent = list of 'MySQL -> you have PostgreSQL (relational databases)' style strings, for
    required skills the candidate doesn't have verbatim but holds a genuine same-family sibling."""
    low = resume_text(r).lower()
    matched, missing_req, adjacent = [], [], []
    for s in kw.required_hard:
        if term_present(s, low):
            matched.append(s)
        else:
            adj = adjacent_held(s, low)
            if adj:
                label, held = adj
                adjacent.append(f"{s} -> you have {held} ({label})")
            else:
                missing_req.append(s)
    matched_pref, missing_pref = [], []
    for s in kw.preferred:
        (matched_pref if term_present(s, low) else missing_pref).append(s)
    return matched + matched_pref, missing_req, missing_pref, adjacent


def _title_alignment(kw: JDKeywords, r: Resume) -> Tuple[float, str]:
    target = (kw.target_title or "").lower()
    if not target:
        return 70.0, "No target title detected in JD."
    hay = " ".join([r.summary] + [e.title for e in r.experience]).lower()
    tokens = [t for t in re.findall(r"[a-z]+", target) if len(t) > 2
              and t not in {"the", "and", "for", "with", "our", "you", "team"}]
    if not tokens:
        return 70.0, ""
    hits = sum(1 for t in tokens if t in hay)
    val = round(100 * hits / len(tokens))
    return float(val), f"{hits}/{len(tokens)} title words present (target: '{kw.target_title}')."


def parse_safety(r: Resume) -> Tuple[float, List[str]]:
    """Deterministic parse-readiness lint. Our renderers are ATS-safe by construction, so this
    mostly validates content completeness — the part most 'ATS scores' ignore."""
    warns, penalty = [], 0
    if not r.contact or "@" not in r.contact:
        warns.append("Contact line is missing an email."); penalty += 20
    if not r.experience:
        warns.append("No work experience parsed."); penalty += 25
    if not r.skills:
        warns.append("No skills section parsed."); penalty += 15
    if not r.education:
        warns.append("No education parsed."); penalty += 10
    for e in r.experience:
        if not e.dates:
            warns.append(f"Missing dates for role at {e.company or 'a company'}."); penalty += 5
    if len(r.skills) > 6:
        warns.append("More than 6 skill groups — dense; recruiters skim poorly."); penalty += 8
    return max(0.0, 100 - penalty), warns


def bullet_quality(r: Resume) -> Tuple[float, str]:
    bullets = [b for e in r.experience for b in e.bullets] + [b for p in r.projects for b in p.bullets]
    if not bullets:
        return 0.0, "No bullets to evaluate."
    good = 0
    for b in bullets:
        has_metric = bool(_METRIC.search(b))
        strong = bool(_STRONG_START.search(b))
        weak = bool(_WEAK.search(b))
        wc = len(b.split())
        if has_metric and strong and not weak and 8 <= wc <= 34:
            good += 1
    val = round(100 * good / len(bullets))
    return float(val), f"{good}/{len(bullets)} bullets are quantified + strong-verb + right-length."


def _values_cov(kw: JDKeywords, r: Resume) -> float:
    targets = kw.preferred + kw.values
    if not targets:
        return 75.0
    low = resume_text(r).lower()
    hits = sum(1 for s in targets if term_present(s, low) or any(w in low for w in s.lower().split()))
    return round(100 * hits / len(targets))


def _bullet_text(r: Resume) -> str:
    parts = []
    for e in r.experience:
        parts += e.bullets
    for p in r.projects:
        parts += p.bullets
    if r.summary:
        parts.append(r.summary)
    return "\n".join(parts).lower()


def score(kw: JDKeywords, r: Resume) -> Score:
    matched, miss_req, miss_pref, adjacent = gap(kw, r)
    req_total = len(kw.required_hard)
    full = resume_text(r).lower()
    bullets = _bullet_text(r)
    adj_skills = {a.split(" ->")[0].split(":")[0].strip() for a in adjacent}

    # Graded coverage (research: a skill DEMONSTRATED in a bullet beats one merely listed).
    # in a bullet/summary = 1.0 | present only in skills list / stack / title = 0.7
    # genuine same-family adjacency = 0.5 | absent = 0. This gives honest tailoring a real lever:
    # weaving a held JD skill into a bullet raises the score.
    held = 0.0
    in_bullet = 0
    for s in kw.required_hard:
        if s in adj_skills:
            held += 0.5
        elif term_present(s, bullets):
            held += 1.0; in_bullet += 1
        elif term_present(s, full):
            held += 0.7
        # else: missing, 0
    req_cov = min(100, round(100 * held / req_total)) if req_total else 75.0

    title_val, title_detail = _title_alignment(kw, r)
    parse_val, parse_warns = parse_safety(r)
    bq_val, bq_detail = bullet_quality(r)
    val_cov = _values_cov(kw, r)

    subs = [
        SubScore(name="Required hard-skill coverage", weight=0.35, value=float(req_cov),
                 detail=(f"{in_bullet}/{req_total} shown in experience bullets"
                         + (f", {len(adjacent)} via related skills" if adjacent else "")
                         + "." if req_total else "No explicit required skills detected in JD.")),
        SubScore(name="Title / seniority alignment", weight=0.20, value=title_val, detail=title_detail),
        SubScore(name="Parse-safety & completeness", weight=0.20, value=parse_val,
                 detail="; ".join(parse_warns) or "Clean, complete, single-column structure."),
        SubScore(name="Evidence-backed bullet quality", weight=0.15, value=bq_val, detail=bq_detail),
        SubScore(name="Preferred quals & values", weight=0.10, value=float(val_cov),
                 detail="Nice-to-haves and culture cues reflected truthfully."),
    ]
    total = round(sum(s.weight * s.value for s in subs))

    notes = []
    if kw.requires_no_sponsorship:
        notes.append("⚠️ This JD appears to state it will NOT sponsor visas — likely a hard knockout "
                     "for candidates needing H-1B sponsorship.")
    if adjacent:
        notes.append("Adjacent coverage (partial credit): " + "; ".join(adjacent)
                     + ". These are surfaced truthfully via the umbrella skill you hold — you can speak "
                     "to the transferable concept, but don't claim the specific tool you haven't used.")
    if total >= 85:
        notes.append("Score is high — stop optimizing for the number and prioritize readability. "
                     "Past ~80% returns diminish and stuffing hurts.")
    if req_total == 0:
        notes.append("This JD lists few hard technical keywords, so keyword match is a weak signal "
                     "here — judge fit by the responsibilities.")

    return Score(total=total, subscores=subs, matched=matched, missing_required=miss_req,
                 missing_preferred=miss_pref, adjacent=adjacent, parse_warnings=parse_warns, notes=notes)
