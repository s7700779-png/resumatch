"""Evaluate the matching engine on the SYNTHETIC dataset.
For each job description, every resume is scored; resumes written for that role (strong/medium) are the
'relevant' class. Reports ROC-AUC and precision@k per role. Run from the repo root:
    python ml/evaluate.py
NOTE: the dataset is synthetic and generated from the same skill taxonomy the engine uses, so this checks
that the pipeline behaves sensibly; it is NOT evidence of accuracy on real resumes."""
import csv, json, sys
from pathlib import Path
from statistics import mean
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sklearn.metrics import roc_auc_score
from app import parsing, matching

DS = ROOT / "dataset"
labels = list(csv.DictReader(open(DS / "labels.csv")))
jobs = list(csv.DictReader(open(DS / "job_descriptions.csv", encoding="utf-8")))
parsed = {r["file"]: parsing.extract(DS / "synthetic_resumes" / r["file"], r["file"].rsplit(".", 1)[1]) for r in labels}
out, aucs, pks = {}, [], []
for j in jobs:
    job = dict(title=j["title"], description=j["description"])
    sc = {f: matching.analyze(p, job)["score"] for f, p in parsed.items()}
    y = [int(r["role"] == j["role"] and r["level"] in ("strong", "medium")) for r in labels]
    s = [sc[r["file"]] for r in labels]
    k = sum(y)
    top = sorted(labels, key=lambda r: -sc[r["file"]])[:k]
    p_at_k = sum(r["role"] == j["role"] and r["level"] in ("strong", "medium") for r in top) / k
    by = lambda lv: round(mean(sc[r["file"]] for r in labels if r["role"] == j["role"] and r["level"] == lv), 1)
    off = round(mean(sc[r["file"]] for r in labels if r["role"] != j["role"]), 1)
    out[j["role"]] = dict(auc=round(roc_auc_score(y, s), 3), precision_at_k=round(p_at_k, 3), k=k,
                          mean_strong=by("strong"), mean_medium=by("medium"), mean_weak=by("weak"), mean_other_roles=off)
    aucs.append(out[j["role"]]["auc"]); pks.append(p_at_k)
out["_summary"] = dict(mean_auc=round(mean(aucs), 3), mean_precision_at_k=round(mean(pks), 3), n_resumes=len(labels), n_jobs=len(jobs))
json.dump(out, open(ROOT / "ml" / "results.json", "w"), indent=2)
print(json.dumps(out, indent=2))
