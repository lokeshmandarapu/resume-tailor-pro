// Scrapes the job description from the current page. Board-specific selectors first,
// then user-selected text, then a generic "largest text block" heuristic.

function textFrom(selectors) {
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) {
      const t = (el.innerText || "").trim();
      if (t.length > 120) return t;
    }
  }
  return "";
}

function selectedText() {
  const s = (window.getSelection && window.getSelection().toString()) || "";
  return s.trim().length > 120 ? s.trim() : "";
}

function genericBlock() {
  // pick the densest text container on the page
  const candidates = Array.from(document.querySelectorAll("main, article, [role=main], section, div"));
  let best = "", bestLen = 0;
  for (const el of candidates) {
    const t = (el.innerText || "").trim();
    // prefer blocks that look like a JD (mention responsibilities/requirements) and are substantial
    const score = t.length + (/responsibilit|requirement|qualificat|what you|you will|skills/i.test(t) ? 1500 : 0);
    if (t.length > 400 && score > bestLen) { best = t; bestLen = score; }
  }
  return best;
}

function scrapeJD() {
  const host = location.hostname;
  let jd = "";
  let source = "page";

  if (host.includes("linkedin.com")) {
    jd = textFrom([
      ".jobs-description__content",
      ".jobs-description-content__text",
      "#job-details",
      ".show-more-less-html__markup",
      ".description__text"
    ]);
    source = "LinkedIn";
  } else if (host.includes("greenhouse.io") || document.querySelector("#content #app_body")) {
    jd = textFrom(["#content", ".job__description", "#app_body", ".opening"]);
    source = "Greenhouse";
  } else if (host.includes("lever.co")) {
    jd = textFrom([".posting-page", ".section-wrapper.page-full-width", ".content"]);
    source = "Lever";
  } else if (host.includes("myworkdayjobs.com")) {
    jd = textFrom(['[data-automation-id="jobPostingDescription"]', '[data-automation-id="job-posting-details"]']);
    source = "Workday";
  } else if (host.includes("ashbyhq.com")) {
    jd = textFrom(['div[class*="_descriptionText"]', ".ashby-job-posting-right-pane", "main"]);
    source = "Ashby";
  } else if (host.includes("indeed.com")) {
    jd = textFrom(["#jobDescriptionText", ".jobsearch-JobComponent-description"]);
    source = "Indeed";
  }

  if (!jd) { const s = selectedText(); if (s) { jd = s; source = "selected text"; } }
  if (!jd) { jd = genericBlock(); source = "page (auto-detected)"; }

  const title =
    (document.querySelector("h1") && document.querySelector("h1").innerText.trim()) ||
    document.title || "";

  return { jd: jd.slice(0, 20000), title: title.slice(0, 200), source, url: location.href };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "GET_JD") {
    try { sendResponse(scrapeJD()); } catch (e) { sendResponse({ jd: "", error: String(e) }); }
  }
  return true; // keep channel open for async (defensive)
});
