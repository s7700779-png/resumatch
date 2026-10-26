import csv, io
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def safe(v):
    """CSV-injection guard + None handling."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in "=+-@\t\r" and s else s

def to_csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    w.writerow(header)
    for r in rows:
        w.writerow([safe(x) for x in r])
    return buf.getvalue().encode("utf-8-sig")

def skill_names(items, status):
    return "; ".join(i["skill"] for i in items if i["status"] == status)

def batch_rows(batch_id, cands):
    rows = []
    for c in cands:
        r = c.get("result") or {}
        bd = r.get("breakdown", {})
        rows.append([batch_id, c["filename"], c["status"], r.get("score"), (r.get("parsing") or {}).get("label"),
                     (bd.get("required") or {}).get("value"), (bd.get("preferred") or {}).get("value"),
                     skill_names(r.get("required", []) + r.get("preferred", []), "matched"),
                     "; ".join(r.get("missing_required", [])), c.get("analyzed_at") or "", c.get("error") or ""])
    return rows

BATCH_HEADER = ["batch_id", "file", "status", "estimated_match_score", "parsing_quality", "required_coverage", "preferred_coverage",
                "matched_skills", "missing_or_unobserved_required", "analysis_time", "error"]

def candidate_pdf(path, cand, job):
    r = cand["result"]; st = getSampleStyleSheet()
    P = lambda t, s="Normal": Paragraph(escape(str(t)), st[s])
    f = [P("ResuMatch Candidate Report", "Title"),
         P(f"File: {cand['filename']}   |   Target role: {job['title']}   |   Analysed: {cand.get('analyzed_at', '')}"), Spacer(1, 8),
         P(f"Estimated match score: {r['score']} / 100", "Heading2"),
         P(f"Parsing quality: {r['parsing']['label']}   |   Evidence: {r['evidence']['label']}"), Spacer(1, 6)]
    t = Table([["Component", "Value", "Weight", "Points"]] + [[b["label"], "n/a" if b["value"] is None else f"{b['value']:.0%}", f"{b['weight']:.0%}", "" if b["points"] is None else b["points"]] for b in r["breakdown"].values()])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
    f += [t, Spacer(1, 8), P("Skills", "Heading2")]
    for v in r["required"] + r["preferred"]:
        ev = v["evidence"][0]["text"] if v["evidence"] else "No supporting text found"
        f.append(P(f"[{v['status'].replace('_', ' ')} / {v['match_type']}] {v['skill']} - {ev}"))
    f += [Spacer(1, 6), P("ATS readability findings", "Heading2")] + [P(f"({a['kind']}) {a['title']}: {a['recommendation']}") for a in r["ats"]]
    f += [Spacer(1, 6), P("Improvement opportunities", "Heading2")] + [P("- " + o) for o in r["opportunities"]]
    f += [Spacer(1, 10), P("Limitations", "Heading2"), P(r["disclaimer"])]
    SimpleDocTemplate(str(path), pagesize=A4, title="ResuMatch report").build(f)
