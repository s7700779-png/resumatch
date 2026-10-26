"""Generate SYNTHETIC resumes (no real people) + labels + edge-case files.
Usage: python generate_dataset.py   (needs reportlab, python-docx)"""
import csv, random, shutil
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from docx import Document

random.seed(42)
OUT = Path(__file__).parent / "synthetic_resumes"
shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir()

ROLES = {
 "backend": dict(title="Backend Developer", core=["python","flask","rest api","sql","postgresql","docker","git","unit testing"], pref=["redis","aws","microservices","ci/cd"],
   bullets=["Designed and built {0} and {1} services used by internal dashboards","Modelled schemas in {2} and tuned slow queries, cutting report time by 35%","Packaged services with {3} and kept history clean with {4}","Wrote {5} suites for critical business logic","Reviewed pull requests for a team of 5 developers"]),
 "frontend": dict(title="Frontend Developer", core=["javascript","html","css","react","redux","responsive design","accessibility","git","unit testing"], pref=["typescript","tailwind css","graphql"],
   bullets=["Built reusable {0} components with {1} and {2}","Implemented {3} layouts that work from phones to desktops","Improved {4} by adding keyboard navigation and labels, passing audits","Covered UI logic with {5} and tracked changes in {6}","Reduced bundle size by 20% through code splitting"]),
 "datascience": dict(title="Data Scientist", core=["python","pandas","numpy","machine learning","scikit-learn","statistics","feature engineering","sql","data visualization"], pref=["deep learning","tensorflow","nlp","a/b testing"],
   bullets=["Trained {0} models with {1} and {2} to predict customer churn","Engineered features using {3} and validated with {4}","Queried warehouse tables in {5} to assemble training sets","Presented results with {6} to non-technical stakeholders","Improved recall by 12% after tuning hyperparameters"]),
 "dataanalyst": dict(title="Data Analyst", core=["sql","excel","tableau","data analysis","statistics","communication","power bi"], pref=["python","etl","google analytics"],
   bullets=["Wrote {0} queries to answer weekly business questions","Built {1} and {2} dashboards used by regional managers","Performed {3} and {4} to find drivers of declining sales","Used {5} to explain findings to stakeholders","Automated a manual reporting task, saving 6 hours per week"]),
 "devops": dict(title="DevOps Engineer", core=["docker","kubernetes","ci/cd","jenkins","terraform","linux","bash","aws","infrastructure as code"], pref=["prometheus","grafana","ansible","python"],
   bullets=["Containerised services with {0} and deployed them to {1}","Maintained {2} pipelines in {3}, reducing release time from 2 hours to 25 minutes","Provisioned cloud resources on {4} using {5}","Wrote {6} scripts for routine maintenance on {7} hosts","Set up alerting so on-call engineers are paged only for real incidents"]),
 "marketing": dict(title="Digital Marketing Specialist", core=["seo","google analytics","content marketing","copywriting","social media marketing","campaign management","market research"], pref=["email marketing","google ads","crm"],
   bullets=["Grew organic traffic by 40% through {0} and keyword research","Tracked performance in {1} and reported weekly","Planned {2} calendars and wrote {3} for blog and landing pages","Ran {4} campaigns on LinkedIn and Instagram","Handled {5} budgets and timelines for three launches"]),
}
SYN = {"rest api":["RESTful services","REST APIs"],"postgresql":["Postgres"],"unit testing":["pytest","unit tests"],"docker":["containerization"],
       "kubernetes":["k8s"],"ci/cd":["continuous integration"],"scikit-learn":["sklearn"],"machine learning":["ML"],"javascript":["JS"],"aws":["Amazon Web Services"],
       "seo":["search engine optimization"],"infrastructure as code":["IaC"],"data analysis":["data analytics"]}
FIRST = ["Aarav","Meera","Kabir","Ananya","Rohan","Isha","Vikram","Sana","Dev","Nisha","Arjun","Tara","Neil","Priya","Zoya","Karan","Leela","Omar","Riya","Sam","Anika","Yash","Mira","Tejas"]
LAST = ["Verma","Nair","Singh","Rao","Kapoor","Iyer","Mehta","Das","Bose","Khan","Sethi","Joshi"]
EDU = ["B.Tech in Computer Science, Sample Institute of Technology, 2019 - 2023","B.Sc in Information Technology, Demo University, 2018 - 2021","BBA in Marketing, Example College, 2018 - 2021","M.Sc in Statistics, Test University, 2020 - 2022"]
CERT = ["Cloud Practitioner (sample certification), 2022","Data Analytics Certificate (sample), 2021","Google Analytics Certification (sample), 2022","Scrum Fundamentals (sample), 2023"]

def disp(s):
    return random.choice(SYN[s]) if s in SYN and random.random() < .35 else s.upper() if s in ("sql","css","seo","aws") else s

def build(role, level, i):
    r = ROLES[role]; core = r["core"][:]; random.shuffle(core)
    noise = [s for k, v in ROLES.items() if k != role for s in v["core"]]
    n = {"strong": len(core), "medium": max(3, int(len(core)*.6)), "weak": max(1, int(len(core)*.25))}[level]
    sk = core[:n]
    if level == "weak": sk += random.sample(noise, 4)
    pref = random.sample(r["pref"], {"strong": 2, "medium": 1, "weak": 0}[level])
    pool = sk + pref
    b = [t.format(*[disp(pool[j % len(pool)]) for j in range(8)]) for t in r["bullets"][: (5 if level != "weak" else 3)]]
    name = f"{FIRST[(i*5) % len(FIRST)]} {random.choice(LAST)}"
    slug = name.lower().replace(" ", ".")
    lines = [name, f"{slug}@example.test | +91 90000 {random.randint(10000,99999)} | Sample City", "",
      "SUMMARY", f"{r['title'] if level!='weak' else 'Recent graduate'} with {random.randint(1,6)} years of combined study and project work.", "",
      "SKILLS", ", ".join(disp(s) for s in pool), "",
      "EXPERIENCE", f"{r['title'] if level!='weak' else 'Intern'}, Northwind Labs (fictional)   Jan {2021+i%3} - Present"] + ["- " + x for x in b] + ["",
      "PROJECTS", f"Portfolio project: built a small application using {disp(pool[0])}.", "",
      "EDUCATION", random.choice(EDU), "", "CERTIFICATIONS", random.choice(CERT)]
    return name, lines

def write_pdf(path, lines):
    st = getSampleStyleSheet()["Normal"]
    doc = SimpleDocTemplate(str(path), pagesize=A4); flow = []
    for l in lines: flow.append(Paragraph(l.replace("&", "&amp;") or "&nbsp;", st)); flow.append(Spacer(1, 3))
    doc.build(flow)

def write_docx(path, lines):
    d = Document()
    for l in lines: d.add_paragraph(l)
    d.save(path)

rows = []; k = 0
for role in ROLES:
    for level in ["strong", "strong", "medium", "weak"]:
        k += 1; name, lines = build(role, level, k)
        fn = f"{role}_{level}_{k:02d}." + ("pdf" if k % 2 else "docx")
        (write_pdf if k % 2 else write_docx)(OUT / fn, lines)
        rows.append([fn, role, level, 1 if level in ("strong", "medium") else 0])
with open(Path(__file__).parent / "labels.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["file", "role", "level", "relevant_to_own_role"]); w.writerows(rows)

# edge cases (for testing failure handling & duplicates; not part of labels.csv)
E = OUT.parent / "edge_cases"; shutil.rmtree(E, ignore_errors=True); E.mkdir()
shutil.copy(OUT / rows[0][0], E / ("duplicate_of_" + rows[0][0]))
write_pdf(E / "no_text.pdf", [""])
(E / "corrupt.docx").write_bytes(b"this is not a real docx file")
(E / "fake.pdf").write_text("plain text pretending to be a PDF")
(E / "empty.pdf").write_bytes(b"")
print(f"Wrote {len(rows)} resumes + edge cases")
