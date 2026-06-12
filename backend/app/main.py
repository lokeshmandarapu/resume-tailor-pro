"""FastAPI backend for Resume Tailor Pro.

Endpoints (all consumed by the Chrome extension side panel):
  GET  /health                 -> {ok, has_key}
  POST /import      (file)     -> master Resume JSON  (parse uploaded PDF/DOCX)
  POST /score       (resume,jd)-> Score JSON          (cheap: 1 extraction call + deterministic)
  POST /tailor      (resume,jd)-> TailorResult JSON   (full grounded pipeline)
  POST /render/docx (resume)   -> .docx download
  POST /render/pdf  (resume)   -> .pdf  download

The extension stores the master resume locally (chrome.storage); the backend is stateless."""
from __future__ import annotations
import os
from dotenv import load_dotenv
# Load .env from the backend folder no matter where the server is launched from,
# so GEMINI_API_KEY / OPENROUTER_API_KEY are always available.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import io

from .schema import Resume, TailorResult
from . import llm, extract, score as scoring, rewrite, resume_import, render_docx, render_pdf

app = FastAPI(title="Resume Tailor Pro")

# Chrome extensions call from an chrome-extension:// origin; allow all for a local personal tool.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)


class ScoreReq(BaseModel):
    resume: Resume
    jd: str


class RenderReq(BaseModel):
    resume: Resume
    filename: str = "resume"
    bold_terms: list[str] = []      # JD keywords to bold in bullets (matched skills)


@app.get("/health")
def health():
    return {"ok": True, "has_key": llm.have_any_key()}


@app.post("/import")
async def do_import(file: UploadFile = File(...)):
    try:
        data = await file.read()
        resume = resume_import.import_resume(file.filename, data)
        return JSONResponse(resume.model_dump())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Import failed: {e}")


@app.post("/score")
def do_score(req: ScoreReq):
    if not req.jd.strip():
        raise HTTPException(400, "No job description provided.")
    try:
        kw = extract.extract_jd(req.jd)
        sc = scoring.score(kw, req.resume)
        return JSONResponse({"keywords": kw.model_dump(), "score": sc.model_dump()})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Scoring failed: {e}")


@app.post("/tailor")
def do_tailor(req: ScoreReq):
    if not req.jd.strip():
        raise HTTPException(400, "No job description provided.")
    try:
        kw = extract.extract_jd(req.jd)
        before = scoring.score(kw, req.resume)
        tailored, flagged, _adj = rewrite.tailor(req.resume, kw, req.jd)
        after = scoring.score(kw, tailored)

        change_log = []
        no_change = tailored.model_dump() == req.resume.model_dump()
        if no_change:
            change_log.append("Tailoring produced no changes — either your resume already aligns "
                              "with this JD, or the rewrite engine was briefly unavailable (try again).")
        # never-lower guard: tailoring must never reduce your score
        if after.total < before.total:
            tailored, after = req.resume, before
            change_log.append("Kept your original wording — the rewrite would have lowered the score.")

        gained = sorted(set(after.matched) - set(before.matched))
        if gained:
            change_log.append("Surfaced JD skills you have that weren't reflected before: " + ", ".join(gained))
        if after.adjacent:
            change_log.append("Covered by related/transferable experience (truthful, partial credit): "
                              + "; ".join(after.adjacent))
        if after.total != before.total:
            change_log.append(f"Score {before.total} -> {after.total}.")
        elif not no_change:
            change_log.append(f"Score held at {after.total} (already covers this JD's required skills); "
                              "bullets were rephrased into the JD's language for human reviewers.")
        if flagged:
            change_log.append("Did not add skills you can't back up (kept you honest): " + ", ".join(flagged))

        result = TailorResult(resume=tailored, score_before=before, score_after=after,
                              change_log=change_log, flagged=flagged)
        return JSONResponse({"result": result.model_dump(), "keywords": kw.model_dump()})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Tailoring failed: {e}")


@app.post("/render/docx")
def do_docx(req: RenderReq):
    data = render_docx.render_docx(req.resume, req.bold_terms)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{req.filename}.docx"'})


@app.post("/render/pdf")
def do_pdf(req: RenderReq):
    data = render_pdf.render_pdf(req.resume, req.bold_terms)
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{req.filename}.pdf"'})
