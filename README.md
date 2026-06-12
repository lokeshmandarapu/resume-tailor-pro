Resume Tailor Pro

A free, private resume-tailoring tool. A Chrome side-panel extension detects the job description on a careers page, scores your resume against it, rewrites your bullets to match the job's language, and exports a clean, ATS-safe PDF and Word file — one page, with your real skills and metrics bolded.

Everything runs on your own machine with your own free API keys. Nothing is uploaded to a server, and the tool never invents skills, metrics, or experience you don't have.


What you need (all free)


A Mac or Windows/Linux computer
Python 3.10 or newer
Google Chrome
A free Google Gemini API key (no credit card required)
(Optional but recommended) a free OpenRouter API key (no credit card required) — used for the higher-quality rewrite step



Step 1 — Get the code

If you have git:

git clone https://github.com/lokeshmandarapu/resume-tailor-pro.git
cd resume-tailor-pro

Or download the ZIP from the green Code -> Download ZIP button on GitHub, unzip it, and cd into the folder.


Step 2 — Get your free API keys

Gemini key (required)


Go to https://aistudio.google.com/apikey
Sign in with a Google account
Click Create API key
Copy the key (a long string starting with AIza...)


OpenRouter key (optional, recommended)


Go to https://openrouter.ai/keys
Sign in (Google/GitHub login works)
Click Create Key, give it any name
Copy the key (starts with sk-or-...)



If you skip the OpenRouter key, the tool still works — it just uses Gemini for everything.




Step 3 — Add your keys (create the .env file)

The project ships with a template called .env.example. You make your own private copy named .env and paste your keys in.

Mac / Linux:

cd backend
cp .env.example .env
nano .env

Windows (PowerShell):

cd backend
copy .env.example .env
notepad .env

In the editor, replace the placeholder values with your real keys so it looks like this:

GEMINI_API_KEY=AIza...your_real_gemini_key...
OPENROUTER_API_KEY=sk-or-...your_real_openrouter_key...

Save and close (in nano: press Ctrl+O, Enter, then Ctrl+X).


Your .env is private and is never uploaded to GitHub — it is listed in .gitignore. Only .env.example (with no real keys) lives in the repo.




Step 4 — Install and run the backend

From inside the backend folder:

Mac / Linux:

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Windows (PowerShell):

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

When it is ready you will see:

Uvicorn running on http://127.0.0.1:8000

Leave this terminal window open — it is the running server. To check it is healthy, open a new terminal and run:

curl http://127.0.0.1:8000/health

You want: {"ok":true,"has_key":true}
(If has_key is false, your .env keys are not set correctly — recheck Step 3.)


Step 5 — Load the Chrome extension


Open Chrome and go to chrome://extensions
Turn on Developer mode (toggle, top-right)
Click Load unpacked
Select the extension folder inside the project
The Resume Tailor Pro icon appears in your toolbar (pin it for easy access)



Step 6 — Use it


Add your resume once: click the extension icon to open the side panel, then paste/import your resume (it is stored locally in your browser).
Open any job posting (LinkedIn, Greenhouse, Lever, Workday, Ashby, Indeed, or any careers page).
In the side panel:

Detect — pulls the job description off the page
Score — shows how your resume matches: skills you have, skills missing, and skills covered by related experience
Tailor — rewrites your bullets to match the job (honestly — it never adds skills you do not have)
Download PDF / Word — exports a clean, one-page, ATS-safe file





The backend must be running (Step 4) whenever you use the extension.


Restarting later

Next time, you only need to start the backend again:

Mac / Linux:

cd resume-tailor-pro/backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Windows:

cd resume-tailor-pro\backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

The extension stays loaded in Chrome between sessions.


Changing or updating your keys

If a key's free daily limit runs out, or you want to swap keys, just edit backend/.env, replace the value, and restart the backend. Nothing else changes.

Free-tier daily limits are generous for personal use (tailoring a handful of jobs a day). If you hit them, wait for the daily reset or generate a fresh key.


Troubleshooting

ProblemFixhas_key: false at /healthYour .env keys are missing or misnamed. Recheck Step 3; the file must be named .env (not .env.txt) and sit inside backend/.Extension buttons do nothingThe backend is not running, or it is on a different port. Make sure Step 4's terminal shows "Uvicorn running" and the health check returns ok:true.command not found: pythonTry python3 instead of python. Install Python from https://www.python.org if needed.Tailor says "engine briefly unavailable"The free AI providers were momentarily overloaded. Just click Tailor again.Score did not change after TailorYour resume may already cover the job's required skills (nothing honest to add) — check the gap list and "covered via related experience" instead.


How it works (honest by design)


Never fabricates. It will not add a skill, tool, metric, or experience you do not have. Skills you are missing show up in a gap list so you know what to genuinely learn.
Truthful adjacent skills. If a job wants MySQL and you have PostgreSQL, it recognizes the transferable relational-database experience and tells you — without claiming MySQL.
Cannot lose your content. The rewrite preserves every job, company, date, and number exactly; it only improves bullet wording.
ATS-safe output. Single column, standard headings, real bullets, one page, standard fonts — the formatting parsers handle reliably.
Private. Your resume and keys stay on your machine. There is no server collecting anything.



Tech


Backend: Python, FastAPI, Gemini + OpenRouter (DeepSeek), python-docx, reportlab
Extension: Chrome Manifest V3 side panel
License: personal/educational use



Built for honest, fast, job-specific resume tailoring. Bring your own keys, keep your data, and never put a skill on paper you cannot defend in the interview.
