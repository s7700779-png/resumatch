import json, logging
from concurrent.futures import ThreadPoolExecutor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from . import config, db, parsing, matching

log = logging.getLogger("resumatch")
_pool = None

def pool():
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)
    return _pool

def reset_pool():
    global _pool
    if _pool:
        _pool.shutdown(wait=False)
    _pool = None

def submit(cid):
    pool().submit(process, cid)

def process(cid):
    c = db.q("SELECT * FROM candidates WHERE id=?", (cid,), one=True)
    if not c:
        return
    db.run("UPDATE candidates SET status='processing', error=NULL WHERE id=?", (cid,))
    try:
        path = config.UPLOADS / c["stored_name"]
        p = parsing.extract(path, c["ext"])
        job = db.job_out(db.q("SELECT * FROM jobs WHERE id=?", (c["job_id"],), one=True))
        res = matching.analyze(p, job)
        res["duplicates"] = near_duplicates(cid, c["job_id"], p["text"])
        db.run("UPDATE candidates SET status='completed', name=?, score=?, text=?, result=?, analyzed_at=?, retryable=0 WHERE id=?",
               (p["name"], res["score"], p["text"], json.dumps(res), db.now(), cid))
    except parsing.ParseError as e:
        db.run("UPDATE candidates SET status='failed', error=?, retryable=1 WHERE id=?", (str(e), cid))
    except Exception:
        log.exception("processing failed for %s", cid)   # no resume content is logged
        db.run("UPDATE candidates SET status='failed', error=?, retryable=1 WHERE id=?", ("Unexpected processing error. Try again.", cid))

def near_duplicates(cid, job_id, text, threshold=0.92):
    others = db.q("SELECT id, filename, text FROM candidates WHERE job_id=? AND id<>? AND status='completed' AND text IS NOT NULL LIMIT 200", (job_id, cid))
    if not others:
        return []
    try:
        M = TfidfVectorizer().fit_transform([text] + [o["text"] for o in others])
        sims = cosine_similarity(M[0], M[1:])[0]
    except ValueError:
        return []
    return [dict(candidate_id=o["id"], filename=o["filename"], similarity=round(float(s), 3)) for o, s in zip(others, sims) if s >= threshold]

def batch_status(counts):
    total = sum(counts.values())
    if not total:
        return "pending"
    active = counts.get("pending", 0) + counts.get("processing", 0)
    done, failed = counts.get("completed", 0), counts.get("failed", 0)
    if active:
        return "processing"
    if done == total or done + counts.get("skipped", 0) == total:
        return "completed"
    return "failed" if failed == total else "partially_completed"

def batch_summary(b):
    rows = db.q("SELECT status, COUNT(*) n FROM candidates WHERE batch_id=? GROUP BY status", (b["id"],))
    counts = {r["status"]: r["n"] for r in rows}
    total = sum(counts.values())
    finished = counts.get("completed", 0) + counts.get("failed", 0) + counts.get("skipped", 0)
    return dict(counts=counts, total=total, status=batch_status(counts), progress=round(100 * finished / total) if total else 0)

def recover():
    """After a restart, requeue unfinished work."""
    for r in db.q("SELECT id FROM candidates WHERE status IN ('pending','processing') AND stored_name IS NOT NULL"):
        submit(r["id"])

def purge_older_than(days):
    if not days:
        return 0
    old = db.q("SELECT id, stored_name FROM candidates WHERE created_at < datetime('now', ?)", (f"-{int(days)} days",))
    for o in old:
        remove_file(o["stored_name"])
    return db.run("DELETE FROM candidates WHERE created_at < datetime('now', ?)", (f"-{int(days)} days",))

def remove_file(stored):
    if stored:
        try:
            (config.UPLOADS / stored).unlink()
        except FileNotFoundError:
            pass
