"""Optional: load the 6 sample job descriptions from dataset/job_descriptions.csv into the database."""
import csv, json
from app import config, db
from app.factory import create_app

create_app(recover=False)
with open(config.ROOT / "dataset" / "job_descriptions.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if db.q("SELECT id FROM jobs WHERE title=?", (r["title"],), one=True):
            continue
        t = db.now()
        db.run("INSERT INTO jobs(id,title,department,description,required_skills,preferred_skills,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
               (db.uid(), r["title"], r["department"], r["description"], "[]", "[]", t, t))
        print("added", r["title"])
