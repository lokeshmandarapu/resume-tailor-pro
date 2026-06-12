# Resume Tailor Pro

A Chrome side-panel extension that detects the job description on the page (LinkedIn,
Greenhouse, Lever, Workday, Ashby, Indeed, or any page via text selection), scores your
resume against it with an **honest, explainable** model, tailors your resume truthfully,
and lets you **download PDF + Word** — all in the sidebar.

It is built on the research synthesis: it models what ATS + recruiters actually reward
(parse-safety, required-skill coverage, title alignment, quantified bullets), never
fabricates, and is transparent that the score is a **pre-submission diagnostic**, not a
real-ATS verdict.

## How it works (architecture)

```
Chrome extension (side panel + JD scraper)  ⇄  local Python backend (FastAPI)
        chrome.storage (your resume)              5-stage grounded pipeline:
                                                   extract → gap → rewrite → verify → score
                                                   renders ATS-safe DOCX + text-PDF
```

The backend runs **locally on your Mac** (free + private). You start it once when you sit
down to job-hunt; the extension talks to it at `http://127.0.0.1:8000`.

---

## One-time setup

### 1. Start the backend
1. Get a free **Gemini** API key (no card): https://aistudio.google.com/apikey
   (Optional, better rewrites: a free **OpenRouter** key: https://openrouter.ai/keys)
2. Double-click **`backend/launch.command`**.
   - First run creates a virtual env, installs dependencies, and makes a `.env` file.
   - It will print the path to `.env` — open it and paste your key(s):
     ```
     GEMINI_API_KEY=your_key
     OPENROUTER_API_KEY=your_key   # optional
     ```
   - Double-click `launch.command` again. When you see
     `Server starting at http://127.0.0.1:8000`, leave that window open.
   - (If macOS blocks the file: right-click → Open the first time, or run
     `chmod +x backend/launch.command`.)

### 2. Load the extension in Chrome
1. Go to `chrome://extensions`.
2. Toggle **Developer mode** (top right) ON.
3. Click **Load unpacked** and select the **`extension/`** folder.
4. Pin "Resume Tailor Pro" to your toolbar. Click the icon to open the side panel.

### 3. Store your resume (once)
In the side panel, click **Upload / update resume** and pick your PDF or DOCX. It's parsed
into a structured master resume and saved in the extension. Update it only when it changes.

---

## Daily use
1. Open a job posting (LinkedIn / a careers page).
2. Open the side panel → **Detect job on this page** (or select the JD text, or paste it).
3. **Score** — see your total, the five sub-scores, and matched vs missing JD keywords.
4. **Tailor resume** — runs the grounded rewrite, re-scores, shows a change log, and flags
   anything it refused to fabricate.
5. **Download PDF** / **Download Word** — ATS-safe, single-column, ready to submit.

---

## Honest notes
- **The score is a diagnostic, not a guarantee.** Real ATS rarely auto-reject on content;
  they parse + rank, and humans decide. Clean parsing + truthful, quantified, JD-aligned
  content is what actually earns callbacks. The tool never fabricates skills or metrics.
- **Free tiers:** Gemini Flash/Flash-Lite are free (daily caps). The rewrite uses free
  DeepSeek via OpenRouter if you add that key, else it falls back to Gemini.
- **The backend must be running** for scoring/tailoring/downloads. If the dot at the top of
  the panel is red, start `launch.command` and click Retry.
- **Sponsorship knockout:** if a JD says it won't sponsor visas, the score flags it — a
  real hard-stop for H-1B candidates.
- Your data stays on your machine; the backend is local and stateless.

## Project layout
```
resume-tailor-pro/
  backend/
    app/        schema, llm, taxonomy, extract, score, rewrite, render_docx, render_pdf, main
    launch.command   # double-click to run
    requirements.txt, .env.example
  extension/
    manifest.json, background.js, content.js
    sidepanel.html / .css / .js
    icons/
```
