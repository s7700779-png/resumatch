"""Optional Gemini integration (REST, no SDK) + deterministic fallback suggestions.
Key and model name come from env vars only (GEMINI_API_KEY, GEMINI_MODEL). Contact details are
stripped before any text leaves the server."""
import json, os, re, urllib.request, urllib.error

WEAK = [("responsible for", "Managed"), ("worked on", "Contributed to"), ("helped", "Supported"),
        ("assisted", "Supported"), ("involved in", "Contributed to"), ("participated in", "Contributed to"), ("tasked with", "Handled")]


class AIError(Exception):
    pass


def status():
    key, model = os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "")
    ok = bool(key and model and not key.startswith("your_"))
    msg = "Configured" if ok else ("Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env" if not (key and model) else "Replace the placeholder key")
    return {"configured": ok, "provider": "Google Gemini", "message": msg}


def redact(t):
    t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]", t)
    return re.sub(r"\+?\d[\d\s().-]{8,}\d", "[phone]", t)


def _call(prompt):
    if not status()["configured"]:
        raise AIError("AI provider is not configured.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{os.environ['GEMINI_MODEL']}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        raise AIError("AI provider rejected the request (quota, key or model problem)." if e.code in (400, 401, 403, 429) else f"AI provider error {e.code}.")
    except Exception:
        raise AIError("AI provider unavailable or timed out.")


def rule_suggestions(result, job):
    """Deterministic, explainable suggestions built only from the candidate's own text."""
    ex, out = result["extracted"], []
    top = [v["skill"] for v in result["required"] + result["preferred"] if v["status"] == "matched"][:4]
    if top:
        out.append(dict(id="summary", kind="summary", original=ex.get("summary") or "", source="rule",
            suggested=f"{job['title']} candidate with demonstrated experience in {', '.join(top)}. [Add your years of experience and one real achievement.]",
            rationale="Draft built from skills actually found in your resume; edit it so every statement is true."))
    n = 0
    for i, line in enumerate(ex.get("experience", []) + ex.get("projects", [])):
        low = line.lower()
        for weak, strong in WEAK:
            if low.startswith(weak):
                out.append(dict(id=f"b{i}", kind="bullet", original=line, source="rule", suggested=strong + line[len(weak):],
                    rationale=f"'{weak.title()}' is vague. Pick the verb that matches what you actually did.")); n += 1; break
        if n >= 8:
            break
    for v in result["required"] + result["preferred"]:
        if v["status"] != "matched":
            rel = [e["term"] for e in v["evidence"] if e.get("term")]
            out.append(dict(id=f"k-{v['skill']}", kind="keyword", original="", suggested=v["skill"], source="rule",
                rationale=f"'{v['skill']}' appears in the job description and is not clearly evidenced." + (f" Related wording found: {', '.join(rel)}." if rel else "") +
                " Add it only if you have real experience, ideally inside a bullet that shows where you used it."))
    return out


def ai_suggestions(result, job, text):
    ex = result["extracted"]
    prompt = ("You improve resumes without inventing facts. Using ONLY the resume text, return JSON "
              '{"summary":"...","bullets":[{"original":"exact bullet","suggested":"improved bullet"}]} with at most 6 bullets. '
              "Never add skills, employers, numbers or achievements that are not in the resume.\n"
              f"JOB TITLE: {job['title']}\nJOB DESCRIPTION: {job['description'][:2000]}\nRESUME: {redact(text)[:6000]}")
    try:
        d = json.loads(_call(prompt))
        assert isinstance(d, dict)
    except AIError:
        raise
    except Exception:
        raise AIError("AI returned an unusable response.")
    out = []
    if isinstance(d.get("summary"), str) and d["summary"].strip():
        out.append(dict(id="ai-summary", kind="summary", original=ex.get("summary") or "", suggested=d["summary"].strip(), source="ai",
                        rationale="AI-generated. Verify every statement before use."))
    for i, b in enumerate(d.get("bullets") or []):
        if isinstance(b, dict) and isinstance(b.get("original"), str) and isinstance(b.get("suggested"), str):
            out.append(dict(id=f"ai-b{i}", kind="bullet", original=b["original"], suggested=b["suggested"], source="ai",
                            rationale="AI-generated rewrite. Verify it still says what is true."))
    return out
