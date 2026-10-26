"""Transparent resume<->job matching.

Score = weighted sum of six components (0..1 each), x100. Weights are in WEIGHTS and are
renormalised if a component is not applicable (e.g. a job lists no preferred skills).
This is an internal estimate. It is NOT an official ATS score or a hiring recommendation.
"""
import csv, re
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from . import config, parsing, ats

WEIGHTS = {"required": 0.40, "preferred": 0.10, "experience": 0.20, "project_edu": 0.10, "keywords": 0.10, "similarity": 0.10}
LABELS = {"required": "Required skill coverage", "preferred": "Preferred skill coverage", "experience": "Experience evidence",
          "project_edu": "Project / education evidence", "keywords": "Job keyword coverage", "similarity": "Overall text relevance"}
SEM_THRESHOLD = 0.35     # TF-IDF cosine for a 'semantic' (partial) match
PARTIAL_WEIGHT = 0.5     # partial credit for semantic matches
GENERIC = set("experience years year work team ability strong knowledge skills including required preferred requirements looking hiring join build maintain using etc good great role company candidate must should will need".split())
MARK = re.compile(r"^\W*(preferred|nice to have|bonus|good to have|plus points?)\b", re.I | re.M)


@lru_cache(maxsize=1)
def taxonomy():
    t = {}
    with open(config.TAXONOMY, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            syn = [s for s in r["synonyms"].split("|") if s]
            rel = [s for s in r["related"].split("|") if s]
            t[r["skill"]] = dict(category=r["category"], terms=[r["skill"]] + syn, related=rel)
    return t


@lru_cache(maxsize=4096)
def rx(term):
    return re.compile(r"(?<![A-Za-z0-9+#.])" + re.escape(term) + r"(?![A-Za-z0-9+#])", re.I)


def canon(s):
    s = s.strip().lower()
    for k, v in taxonomy().items():
        if s == k or s in [x.lower() for x in v["terms"]]:
            return k
    return s


def entry(skill):
    return taxonomy().get(skill) or dict(category="Custom", terms=[skill], related=[])


def detect_skills(text):
    return [k for k, v in taxonomy().items() if any(rx(t).search(text) for t in v["terms"])]


def jd_skills(job):
    desc = job.get("description") or ""
    req = [canon(s) for s in job.get("required_skills") or [] if s.strip()]
    pref = [canon(s) for s in job.get("preferred_skills") or [] if s.strip()]
    m = MARK.search(desc)
    head, tail = (desc[: m.start()], desc[m.start():]) if m else (desc, "")
    if not req:
        req = detect_skills(head)
    if not pref:
        pref = detect_skills(tail)
    pref = [s for s in pref if s not in req]
    return list(dict.fromkeys(req)), list(dict.fromkeys(pref))


def _snip(line):
    return line if len(line) <= 240 else line[:237] + "..."


def match_exact(skill, labelled):
    hits = []
    for term in entry(skill)["terms"]:
        r = rx(term)
        for sec, line in labelled:
            if r.search(line):
                hits.append(dict(section=sec, text=_snip(line), term=term, kind="exact" if term == skill else "synonym"))
    hits.sort(key=lambda h: h["section"] == "skills")
    seen, out = set(), []
    for h in hits:
        if h["text"] not in seen:
            seen.add(h["text"]); out.append(h)
    return out[:3]


def semantic_pass(skills, labelled):
    """Related-term and TF-IDF sentence similarity for skills with no exact/synonym match."""
    res = {}
    lines = [l for _, l in labelled]
    if not skills or not lines:
        return res
    desc = {s: " ".join([s] + entry(s)["terms"] + entry(s)["related"]) for s in skills}
    try:
        v = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        M = v.fit_transform(lines + list(desc.values()))
        sims = cosine_similarity(M[len(lines):], M[: len(lines)])
    except ValueError:
        sims = None
    for i, s in enumerate(skills):
        for rel in entry(s)["related"]:
            r = rx(rel)
            for sec, line in labelled:
                if r.search(line):
                    res[s] = dict(section=sec, text=_snip(line), term=rel, kind="semantic", reason=f"mentions related term '{rel}'")
                    break
            if s in res:
                break
        if s not in res and sims is not None:
            j = int(sims[i].argmax())
            if sims[i][j] >= SEM_THRESHOLD:
                res[s] = dict(section=labelled[j][0], text=_snip(lines[j]), term=None, kind="semantic", reason=f"text similarity {sims[i][j]:.2f}")
    return res


def keywords(desc, n=15):
    try:
        cv = CountVectorizer(stop_words="english", token_pattern=r"[A-Za-z][A-Za-z+#.]{3,}")
        X = cv.fit_transform([desc])
    except ValueError:
        return []
    counts = sorted(zip(cv.get_feature_names_out(), X.toarray()[0]), key=lambda x: -x[1])
    return [w for w, _ in counts if w.lower() not in GENERIC][:n]


def _cov(items):
    return None if not items else sum(1.0 if i["status"] == "matched" else PARTIAL_WEIGHT if i["status"] == "partial" else 0 for i in items) / len(items)


def analyze(p, job):
    req, pref = jd_skills(job)
    labelled = p["labelled"]
    skills = {}
    for s in req + pref:
        ev = match_exact(s, labelled)
        skills[s] = dict(skill=s, category=entry(s)["category"], status="matched" if ev else "not_found",
                         match_type=ev[0]["kind"] if ev else "not_found", evidence=ev,
                         listed_only=bool(ev) and all(e["section"] == "skills" for e in ev))
    missing = [s for s, v in skills.items() if v["status"] == "not_found"]
    for s, h in semantic_pass(missing, labelled).items():
        skills[s].update(status="partial", match_type="semantic", evidence=[h],
                         note="Related wording found; confirm the candidate really used this skill.")
    for s, v in skills.items():
        if v["status"] == "not_found":
            v["note"] = "Not found in the resume text; this does not prove the skill is absent."
    R = [skills[s] for s in req]; P = [skills[s] for s in pref]
    has_exp = "experience" in p["sections"]

    def in_secs(v, secs=None):
        return any((e["section"] in secs) if secs else (e["section"] != "skills") for e in v["evidence"]) if v["status"] == "matched" else False
    base = R or P
    comp = {
        "required": _cov(R), "preferred": _cov(P),
        "experience": (sum(in_secs(v, {"experience"} if has_exp else None) for v in base) / len(base)) if base else None,
        "project_edu": (sum(in_secs(v, {"projects", "education", "certifications"}) for v in R + P) / len(R + P)) if R + P else None,
    }
    kws = keywords(job["description"])
    low = p["text"].lower()
    covered = [k for k in kws if rx(k).search(low)]
    comp["keywords"] = len(covered) / len(kws) if kws else None
    try:
        M = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform([job["description"], p["text"]])
        comp["similarity"] = min(1.0, float(cosine_similarity(M[0], M[1])[0][0]) * 2)
    except ValueError:
        comp["similarity"] = None
    avail = {k: v for k, v in comp.items() if v is not None}
    tw = sum(WEIGHTS[k] for k in avail) or 1
    breakdown = {k: dict(label=LABELS[k], value=None if comp[k] is None else round(comp[k], 3),
                         weight=round(WEIGHTS[k] / tw, 3) if k in avail else 0,
                         points=round(comp[k] * WEIGHTS[k] / tw * 100, 1) if k in avail else None) for k in WEIGHTS}
    score = round(sum(c["points"] for c in breakdown.values() if c["points"] is not None), 1)

    matched = [v for v in skills.values() if v["status"] == "matched"]
    evid = [v for v in matched if not v["listed_only"]]
    ev_score = round(len(evid) / len(matched), 2) if matched else 0.0
    ev_label = "No matched skills to evidence" if not matched else "Strong evidence" if ev_score >= .7 else "Moderate evidence" if ev_score >= .4 else "Limited evidence (mostly listed, not demonstrated)"
    q = parsing.quality(p)
    obs, opp = [], []
    mr = [v for v in R if v["status"] == "matched"]
    if R:
        obs.append(f"{len(mr)} of {len(R)} required skills have direct evidence in the resume.")
    if evid:
        obs.append(f"{len(evid)} matched skills are supported by experience, project or education text, not only a skills list.")
    if [v for v in matched if v["listed_only"]]:
        opp.append("Some skills appear only in the skills list. Add a bullet showing where you used them.")
    for v in R:
        if v["status"] == "not_found":
            opp.append(f"Required skill '{v['skill']}' is not clearly evidenced. Add it only if you have real experience with it.")
        elif v["status"] == "partial":
            opp.append(f"'{v['skill']}' is only indirectly evidenced; consider naming it explicitly if accurate.")
    ex = {k: p[k] for k in ("name", "email", "phone", "summary", "education", "experience", "projects", "certifications", "skills_listed")}
    ex["date_ranges"] = p["date_ranges"]
    unc = [k for k in ("name", "email", "phone", "summary") if not ex[k]]
    highlights = sorted({e["term"] for v in skills.values() for e in v["evidence"] if e.get("term")}, key=len, reverse=True)
    return dict(
        score=score, breakdown=breakdown, required=R, preferred=P,
        missing_required=[v["skill"] for v in R if v["status"] == "not_found"],
        missing_preferred=[v["skill"] for v in P if v["status"] == "not_found"],
        keywords=dict(covered=covered, missing=[k for k in kws if k not in covered]),
        parsing=q, evidence=dict(score=ev_score, label=ev_label),
        ats=ats.audit(p), extracted=ex, uncertain_fields=unc, highlights=highlights,
        observations=obs, opportunities=opp, ocr_used=p["ocr_used"],
        method="Skill taxonomy + synonyms + TF-IDF similarity",
        disclaimer="Internal estimate of relevance to this job description. Not an official ATS score, not a hiring recommendation, and no guarantee of interview outcome.")
