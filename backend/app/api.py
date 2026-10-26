import difflib, json, re
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import hashlib
from . import config, db, batches, ai, reports, parsing

bp = Blueprint("api", __name__, url_prefix="/api")


def err(msg, status=400, code=None):
    return jsonify(error=dict(code=code or {400: "bad_request", 404: "not_found", 409: "conflict", 413: "too_large"}.get(status, "error"), message=msg)), status


def body():
    return request.get_json(silent=True) or {}


def skills_list(v):
    if isinstance(v, str):
        v = v.split(",")
    return [s.strip() for s in (v or []) if isinstance(s, str) and s.strip()][:50]


# ---------- helpers ----------
def load_cand(cid, full=False):
    r = db.q("SELECT * FROM candidates WHERE id=?", (cid,), one=True)
    if not r:
        return None
    r["result"] = json.loads(r["result"]) if r["result"] else None
    if not full:
        r.pop("text", None)
    return r


def summary(c):
    res = c.get("result") or {}
    bd = res.get("breakdown", {})
    return dict(id=c["id"], batch_id=c["batch_id"], job_id=c["job_id"], filename=c["filename"], status=c["status"], error=c["error"],
                retryable=bool(c["retryable"]), name=c["name"] or ("Not detected" if c["status"] == "completed" else None), score=c["score"],
                analyzed_at=c["analyzed_at"], duplicate_of=c["duplicate_of"], parsing=(res.get("parsing") or {}).get("label"),
                evidence=(res.get("evidence") or {}).get("label"), required_coverage=(bd.get("required") or {}).get("value"),
                preferred_coverage=(bd.get("preferred") or {}).get("value"),
                matched=[v["skill"] for v in res.get("required", []) + res.get("preferred", []) if v["status"] == "matched"],
                missing_required=res.get("missing_required", []), likely_duplicates=res.get("duplicates", []))


def cands_of(batch_id):
    return [load_cand(r["id"]) for r in db.q("SELECT id FROM candidates WHERE batch_id=? ORDER BY created_at, filename", (batch_id,))]


def make_report(kind, ref_id, title, data=None, writer=None):
    rid = db.uid()
    ext = "pdf" if kind == "candidate_pdf" else "csv"
    path = config.REPORTS / f"{rid}.{ext}"
    if writer:
        writer(path)
    else:
        path.write_bytes(data)
    db.run("INSERT INTO reports(id,kind,ref_id,title,filename,created_at) VALUES(?,?,?,?,?,?)", (rid, kind, ref_id, title, f"{rid}.{ext}", db.now()))
    return rid


def drop_reports(where, arg):
    for r in db.q(f"SELECT id, filename FROM reports WHERE {where}", (arg,)):
        try:
            (config.REPORTS / r["filename"]).unlink()
        except FileNotFoundError:
            pass
        db.run("DELETE FROM reports WHERE id=?", (r["id"],))


# ---------- health / settings ----------
@bp.get("/health")
def health():
    return jsonify(status="ok", time=db.now())


@bp.get("/settings")
def get_settings():
    return jsonify(settings=db.get_settings(), limits=config.HARD_LIMITS, supported_formats=list(config.SUPPORTED_EXT),
                   ai=ai.status(), ocr_available=parsing.ocr_available(), analysis_method="Skill taxonomy + synonyms + TF-IDF similarity",
                   weights=__import__("app.matching", fromlist=["x"]).WEIGHTS)


@bp.put("/settings")
def put_settings():
    d, out = body(), {}
    for k, (lo, hi) in config.HARD_LIMITS.items():
        if k in d:
            try:
                v = int(d[k])
            except (TypeError, ValueError):
                return err(f"{k} must be a whole number")
            if not lo <= v <= hi:
                return err(f"{k} must be between {lo} and {hi}")
            out[k] = v
    db.save_settings(out)
    if "retention_days" in out:
        batches.purge_older_than(out["retention_days"])
    return jsonify(settings=db.get_settings())


@bp.post("/settings/purge")
def purge():
    d = body()
    if d.get("confirm") is not True:
        return err("Confirmation required")
    for r in db.q("SELECT stored_name FROM candidates"):
        batches.remove_file(r["stored_name"])
    for r in db.q("SELECT filename FROM reports"):
        try:
            (config.REPORTS / r["filename"]).unlink()
        except FileNotFoundError:
            pass
    db.run("DELETE FROM reports"); db.run("DELETE FROM candidates"); db.run("DELETE FROM batches")
    if d.get("include_jobs"):
        db.run("DELETE FROM jobs")
    return jsonify(ok=True)


# ---------- jobs ----------
def job_payload(d):
    title, desc = (d.get("title") or "").strip(), (d.get("description") or "").strip()
    if not title:
        return None, "Job title is required"
    if not desc:
        return None, "Job description cannot be empty"
    if len(desc) > 20000:
        return None, "Job description is too long (max 20,000 characters)"
    return dict(title=title[:200], department=(d.get("department") or "").strip()[:200], description=desc,
                required=json.dumps(skills_list(d.get("required_skills"))), preferred=json.dumps(skills_list(d.get("preferred_skills")))), None


@bp.get("/jobs")
def jobs_list():
    s = f"%{(request.args.get('q') or '').strip()}%"
    rows = db.q("""SELECT j.*, (SELECT COUNT(*) FROM batches b WHERE b.job_id=j.id) batch_count FROM jobs j
                   WHERE j.title LIKE ? OR j.description LIKE ? OR j.department LIKE ? ORDER BY j.updated_at DESC""", (s, s, s))
    return jsonify(jobs=[db.job_out(r) for r in rows])


@bp.post("/jobs")
def jobs_create():
    p, e = job_payload(body())
    if e:
        return err(e)
    jid, t = db.uid(), db.now()
    db.run("INSERT INTO jobs(id,title,department,description,required_skills,preferred_skills,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
           (jid, p["title"], p["department"], p["description"], p["required"], p["preferred"], t, t))
    return jsonify(job=db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (jid,), one=True))), 201


@bp.get("/jobs/<jid>")
def jobs_get(jid):
    j = db.q("SELECT * FROM jobs WHERE id=?", (jid,), one=True)
    if not j:
        return err("Job description not found", 404)
    bs = db.q("SELECT * FROM batches WHERE job_id=? ORDER BY created_at DESC", (jid,))
    return jsonify(job=db.job_out(j), batches=[dict(id=b["id"], created_at=b["created_at"], **batches.batch_summary(b)) for b in bs])


@bp.put("/jobs/<jid>")
def jobs_update(jid):
    if not db.q("SELECT id FROM jobs WHERE id=?", (jid,), one=True):
        return err("Job description not found", 404)
    p, e = job_payload(body())
    if e:
        return err(e)
    db.run("UPDATE jobs SET title=?,department=?,description=?,required_skills=?,preferred_skills=?,updated_at=? WHERE id=?",
           (p["title"], p["department"], p["description"], p["required"], p["preferred"], db.now(), jid))
    return jsonify(job=db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (jid,), one=True)))


@bp.delete("/jobs/<jid>")
def jobs_delete(jid):
    if not db.q("SELECT id FROM jobs WHERE id=?", (jid,), one=True):
        return err("Job description not found", 404)
    n = db.q("SELECT COUNT(*) n FROM batches WHERE job_id=?", (jid,), one=True)["n"]
    if n and request.args.get("with_batches") != "true":
        return err(f"This job has {n} analysis batch(es). Delete them first or confirm deleting them too.", 409)
    for b in db.q("SELECT id FROM batches WHERE job_id=?", (jid,)):
        delete_batch(b["id"])
    db.run("DELETE FROM jobs WHERE id=?", (jid,))
    return jsonify(ok=True)


# ---------- batches ----------
MAGIC = {"pdf": b"%PDF", "docx": b"PK"}


@bp.post("/batches")
def batches_create():
    st = db.get_settings()
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return err("Upload at least one resume (PDF or DOCX)")
    if len(files) > st["max_files"]:
        return err(f"Too many files: the limit is {st['max_files']} per batch")
    form = request.form
    if form.get("job_id"):
        job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (form["job_id"],), one=True))
        if not job:
            return err("Selected job description not found", 404)
    else:
        p, e = job_payload(form)
        if e:
            return err(e)
        jid, t = db.uid(), db.now()
        db.run("INSERT INTO jobs(id,title,department,description,required_skills,preferred_skills,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
               (jid, p["title"], p["department"], p["description"], p["required"], p["preferred"], t, t))
        job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (jid,), one=True))
    skip = form.get("skip_duplicates") in ("true", "1", "on")
    bid = db.uid()
    db.run("INSERT INTO batches(id,job_id,created_at,skip_duplicates) VALUES(?,?,?,?)", (bid, job["id"], db.now(), int(skip)))
    queue, seen = [], {}
    for f in files:
        cid, name = db.uid(), secure_filename(f.filename) or "resume"
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        data = f.read(st["max_size_mb"] * 1024 * 1024 + 1)
        row = dict(id=cid, batch_id=bid, job_id=job["id"], filename=name, stored_name=None, ext=ext, size=len(data),
                   file_hash=hashlib.sha256(data).hexdigest(), status="pending", error=None, retryable=0, duplicate_of=None)
        if ext not in config.SUPPORTED_EXT:
            row.update(status="failed", error="Unsupported file type. Only PDF and DOCX are accepted.")
        elif len(data) > st["max_size_mb"] * 1024 * 1024:
            row.update(status="failed", error=f"File is larger than the {st['max_size_mb']} MB limit.")
        elif not data:
            row.update(status="failed", error="File is empty.")
        elif not data.startswith(MAGIC[ext]):
            row.update(status="failed", error=f"File content does not look like a real {ext.upper()} file.")
        else:
            dup = seen.get(row["file_hash"]) or (db.q("SELECT id FROM candidates WHERE job_id=? AND file_hash=? AND status<>'failed' LIMIT 1", (job["id"], row["file_hash"]), one=True) or {}).get("id")
            row["duplicate_of"] = dup
            seen.setdefault(row["file_hash"], cid)
            if dup and skip:
                row.update(status="skipped", error="Identical file already analysed for this job (skipped at your request).")
            else:
                row["stored_name"] = f"{cid}.{ext}"
                (config.UPLOADS / row["stored_name"]).write_bytes(data)
                queue.append(cid)
        db.run("INSERT INTO candidates(id,batch_id,job_id,filename,stored_name,ext,size,file_hash,status,error,retryable,duplicate_of,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (row["id"], bid, job["id"], name, row["stored_name"], ext, row["size"], row["file_hash"], row["status"], row["error"], row["retryable"], row["duplicate_of"], db.now()))
    for cid in queue:
        batches.submit(cid)
    return jsonify(batch_id=bid, job_id=job["id"], files=len(files)), 201


def get_batch(bid):
    return db.q("SELECT * FROM batches WHERE id=?", (bid,), one=True)


@bp.get("/batches/<bid>")
def batches_get(bid):
    b = get_batch(bid)
    if not b:
        return err("Batch not found", 404)
    job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (b["job_id"],), one=True))
    return jsonify(batch=dict(id=b["id"], created_at=b["created_at"], job=dict(id=job["id"], title=job["title"], department=job["department"]), **batches.batch_summary(b)),
                   candidates=[summary(c) for c in cands_of(bid)])


@bp.get("/batches/<bid>/results")
def batches_results(bid):
    if not get_batch(bid):
        return err("Batch not found", 404)
    rows = [summary(c) for c in cands_of(bid) if c["status"] == "completed"]
    s = (request.args.get("q") or "").lower()
    if s:
        rows = [r for r in rows if s in (r["filename"] or "").lower() or s in (r["name"] or "").lower() or any(s in m for m in r["matched"])]
    key = request.args.get("sort", "score")
    rows.sort(key=lambda r: (r.get(key) is None, -(r.get(key) or 0)) if key in ("score", "required_coverage", "preferred_coverage") else (r.get(key) or ""))
    return jsonify(results=rows)


@bp.post("/batches/<bid>/retry")
def batches_retry(bid):
    if not get_batch(bid):
        return err("Batch not found", 404)
    ids = [r["id"] for r in db.q("SELECT id FROM candidates WHERE batch_id=? AND status='failed' AND retryable=1", (bid,))]
    for cid in ids:
        db.run("UPDATE candidates SET status='pending', error=NULL WHERE id=?", (cid,))
        batches.submit(cid)
    return jsonify(retried=len(ids))


def delete_batch(bid):
    for c in db.q("SELECT id, stored_name FROM candidates WHERE batch_id=?", (bid,)):
        batches.remove_file(c["stored_name"]); drop_reports("ref_id=?", c["id"])
    drop_reports("ref_id=?", bid)
    db.run("DELETE FROM batches WHERE id=?", (bid,))


@bp.delete("/batches/<bid>")
def batches_delete(bid):
    if not get_batch(bid):
        return err("Batch not found", 404)
    delete_batch(bid)
    return jsonify(ok=True)


@bp.get("/batches/<bid>/export.csv")
def batches_export(bid):
    if not get_batch(bid):
        return err("Batch not found", 404)
    data = reports.to_csv(reports.BATCH_HEADER, reports.batch_rows(bid, cands_of(bid)))
    rid = make_report("batch_csv", bid, f"Batch {bid} results (CSV)", data=data)
    return send_file(config.REPORTS / f"{rid}.csv", as_attachment=True, download_name=f"batch_{bid}.csv", mimetype="text/csv")


# ---------- candidates ----------
@bp.get("/candidates")
def cand_list():
    sql, args = "SELECT id FROM candidates WHERE status='completed'", []
    if request.args.get("job_id"):
        sql += " AND job_id=?"; args.append(request.args["job_id"])
    if request.args.get("ids"):
        ids = request.args["ids"].split(",")[:50]
        sql += f" AND id IN ({','.join('?' * len(ids))})"; args += ids
    rows = [summary(load_cand(r["id"])) for r in db.q(sql + " ORDER BY score DESC LIMIT 500", tuple(args))]
    s = (request.args.get("q") or "").lower()
    if s:
        rows = [r for r in rows if s in (r["filename"] or "").lower() or s in (r["name"] or "").lower()]
    return jsonify(candidates=rows)


@bp.get("/candidates/<cid>")
def cand_get(cid):
    c = load_cand(cid, full=True)
    if not c:
        return err("Candidate not found", 404)
    job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (c["job_id"],), one=True))
    c["job"] = dict(id=job["id"], title=job["title"])
    c.pop("stored_name", None); c.pop("file_hash", None)
    return jsonify(candidate=c)


@bp.delete("/candidates/<cid>")
def cand_delete(cid):
    c = db.q("SELECT stored_name FROM candidates WHERE id=?", (cid,), one=True)
    if not c:
        return err("Candidate not found", 404)
    batches.remove_file(c["stored_name"]); drop_reports("ref_id=?", cid)
    db.run("DELETE FROM candidates WHERE id=?", (cid,))
    return jsonify(ok=True)


@bp.get("/candidates/<cid>/file")
def cand_file(cid):
    c = db.q("SELECT stored_name, filename FROM candidates WHERE id=?", (cid,), one=True)
    if not c or not c["stored_name"] or not (config.UPLOADS / c["stored_name"]).exists():
        return err("Original file is not available", 404)
    return send_file(config.UPLOADS / c["stored_name"], download_name=c["filename"])


@bp.post("/candidates/<cid>/report")
def cand_report(cid):
    c = load_cand(cid)
    if not c or c["status"] != "completed":
        return err("Only completed analyses have reports", 404)
    job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (c["job_id"],), one=True))
    rid = make_report("candidate_pdf", cid, f"{c['filename']} - {job['title']}", writer=lambda p: reports.candidate_pdf(p, c, job))
    return jsonify(report_id=rid), 201


@bp.post("/candidates/<cid>/improve")
def cand_improve(cid):
    c = load_cand(cid, full=True)
    if not c or c["status"] != "completed":
        return err("Candidate not found or not analysed", 404)
    job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (c["job_id"],), one=True))
    sug, ai_error = ai.rule_suggestions(c["result"], job), None
    if body().get("use_ai"):
        try:
            sug = ai.ai_suggestions(c["result"], job, c["text"]) + sug
        except ai.AIError as e:
            ai_error = str(e)
    return jsonify(suggestions=sug, ai=ai.status(), ai_error=ai_error,
                   note="Suggestions never change the original file. Rule-based and AI suggestions are labelled; verify every statement is true.")


# ---------- compare ----------
def compare_rows(ids):
    cs = [load_cand(i) for i in ids]
    if any(c is None or c["status"] != "completed" for c in cs):
        return None, ("One or more candidates were not found or not analysed", 404)
    if len({c["job_id"] for c in cs}) != 1:
        return None, ("Candidates must be analysed against the same job description", 400)
    rows = []
    for c in cs:
        r, s = c["result"], summary(c)
        bd = r["breakdown"]
        s.update(breakdown={k: v["value"] for k, v in bd.items()},
                 strengths=[v["skill"] for v in r["required"] if v["status"] == "matched"][:6],
                 review_areas=[f"'{x}' not clearly evidenced" for x in r["missing_required"]] + [f"'{v['skill']}' only indirectly evidenced" for v in r["required"] if v["status"] == "partial"],
                 parsing_score=r["parsing"]["score"])
        rows.append(s)
    return rows, None


@bp.post("/compare")
def compare():
    ids = list(dict.fromkeys(body().get("candidate_ids") or []))
    if len(ids) < 2:
        return err("Select at least two candidates")
    rows, e = compare_rows(ids)
    return err(*e) if e else jsonify(candidates=rows, note="Evidence for human review. This is not a hiring or rejection decision.")


@bp.post("/compare/export")
def compare_export():
    ids = list(dict.fromkeys(body().get("candidate_ids") or []))
    if len(ids) < 2:
        return err("Select at least two candidates")
    rows, e = compare_rows(ids)
    if e:
        return err(*e)
    keys = ["required", "preferred", "experience", "project_edu", "keywords", "similarity"]
    data = reports.to_csv(["file", "estimated_match_score"] + keys + ["parsing_quality", "strengths", "review_areas"],
                          [[r["filename"], r["score"]] + [r["breakdown"][k] for k in keys] + [r["parsing"], "; ".join(r["strengths"]), "; ".join(r["review_areas"])] for r in rows])
    rid = make_report("compare_csv", ",".join(ids)[:200], f"Comparison of {len(ids)} candidates (CSV)", data=data)
    return send_file(config.REPORTS / f"{rid}.csv", as_attachment=True, download_name="comparison.csv", mimetype="text/csv")


@bp.post("/versions/compare")
def versions():
    d = body()
    a, b = load_cand(d.get("old_id"), True), load_cand(d.get("new_id"), True)
    if not a or not b or a["status"] != "completed" or b["status"] != "completed":
        return err("Select two analysed resumes", 404)
    if a["job_id"] != b["job_id"]:
        return err("Both versions must be analysed against the same job description")
    la, lb = [l.strip() for l in a["text"].splitlines() if l.strip()], [l.strip() for l in b["text"].splitlines() if l.strip()]
    added, removed, modified = [], [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes():
        if op == "insert": added += lb[j1:j2]
        elif op == "delete": removed += la[i1:i2]
        elif op == "replace":
            n = min(i2 - i1, j2 - j1)
            modified += [dict(before=la[i1 + k], after=lb[j1 + k]) for k in range(n)]
            removed += la[i1 + n:i2]; added += lb[j1 + n:j2]
    ms = lambda c: {v["skill"] for v in c["result"]["required"] + c["result"]["preferred"] if v["status"] == "matched"}
    ra, rb = a["result"], b["result"]
    return jsonify(old=summary(a), new=summary(b), added=added[:100], removed=removed[:100], modified=modified[:100],
                   score_change=round(rb["score"] - ra["score"], 1), parsing_change=rb["parsing"]["score"] - ra["parsing"]["score"],
                   keyword_coverage_change=round(len(rb["keywords"]["covered"]) - len(ra["keywords"]["covered"]), 0),
                   newly_evidenced=sorted(ms(b) - ms(a)), no_longer_evidenced=sorted(ms(a) - ms(b)),
                   note="A higher estimated score does not guarantee a better chance of employment.")


# ---------- history / dashboard / reports ----------
@bp.get("/history")
def history():
    s, status = f"%{(request.args.get('q') or '').strip()}%", request.args.get("status") or ""
    page, per = max(int(request.args.get("page", 1) or 1), 1), min(max(int(request.args.get("per_page", 10) or 10), 1), 50)
    rows = db.q("SELECT b.*, j.title job_title FROM batches b JOIN jobs j ON j.id=b.job_id WHERE j.title LIKE ? OR b.id LIKE ? ORDER BY b.created_at DESC", (s, s))
    items = [dict(id=b["id"], job_id=b["job_id"], job_title=b["job_title"], created_at=b["created_at"], **batches.batch_summary(b)) for b in rows]
    if status:
        items = [i for i in items if i["status"] == status]
    return jsonify(items=items[(page - 1) * per: page * per], total=len(items), page=page, per_page=per)


@bp.get("/dashboard")
def dashboard():
    c = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) n FROM candidates GROUP BY status")}
    avg = db.q("SELECT AVG(score) a FROM candidates WHERE status='completed'", one=True)["a"]
    scores = [r["score"] for r in db.q("SELECT score FROM candidates WHERE status='completed'")]
    dist = [dict(range=f"{i}-{i + 19 if i < 80 else 100}", count=sum(1 for s in scores if i <= s < i + 20 or (i == 80 and s == 100))) for i in range(0, 100, 20)]
    act = db.q("SELECT substr(analyzed_at,1,10) day, COUNT(*) n FROM candidates WHERE status='completed' AND analyzed_at IS NOT NULL GROUP BY day ORDER BY day DESC LIMIT 14")[::-1]
    rb = db.q("SELECT b.*, j.title job_title FROM batches b JOIN jobs j ON j.id=b.job_id ORDER BY b.created_at DESC LIMIT 5")
    return jsonify(
        totals=dict(total=sum(c.values()), completed=c.get("completed", 0), failed=c.get("failed", 0), average_score=None if avg is None else round(avg, 1)),
        recent_batches=[dict(id=b["id"], job_title=b["job_title"], created_at=b["created_at"], **batches.batch_summary(b)) for b in rb],
        recent_candidates=[summary(load_cand(r["id"])) for r in db.q("SELECT id FROM candidates WHERE status='completed' ORDER BY analyzed_at DESC LIMIT 6")],
        frequent_jobs=db.q("SELECT j.id, j.title, COUNT(b.id) batches FROM jobs j JOIN batches b ON b.job_id=j.id GROUP BY j.id ORDER BY batches DESC LIMIT 5"),
        recent_reports=db.q("SELECT id, kind, title, created_at FROM reports ORDER BY created_at DESC LIMIT 5"),
        score_distribution=dist, activity=[dict(day=a["day"], count=a["n"]) for a in act])


@bp.get("/reports")
def reports_list():
    return jsonify(reports=db.q("SELECT id, kind, ref_id, title, created_at FROM reports ORDER BY created_at DESC LIMIT 200"))


@bp.get("/reports/<rid>")
def reports_get(rid):
    r = db.q("SELECT id, kind, ref_id, title, created_at FROM reports WHERE id=?", (rid,), one=True)
    if not r:
        return err("Report not found", 404)
    out = dict(report=r)
    if r["kind"] == "candidate_pdf":
        c = load_cand(r["ref_id"])
        out["candidate"] = summary(c) if c else None
    return jsonify(out)


@bp.get("/reports/<rid>/download")
def reports_download(rid):
    r = db.q("SELECT * FROM reports WHERE id=?", (rid,), one=True)
    if not r or not (config.REPORTS / r["filename"]).exists():
        return err("Report file not found", 404)
    return send_file(config.REPORTS / r["filename"], as_attachment=True, download_name=re.sub(r"[^\w.-]+", "_", r["title"])[:80] + "." + r["filename"].rsplit(".", 1)[-1])


@bp.delete("/reports/<rid>")
def reports_delete(rid):
    if not db.q("SELECT id FROM reports WHERE id=?", (rid,), one=True):
        return err("Report not found", 404)
    drop_reports("id=?", rid)
    return jsonify(ok=True)
