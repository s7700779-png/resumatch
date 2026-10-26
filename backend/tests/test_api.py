"""Run: python -m unittest discover -s tests -v   (from the backend folder)"""
import io, json, os, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.factory import create_app
from app import parsing, matching

DS = Path(__file__).resolve().parents[2] / "dataset"
RES, EDGE = DS / "synthetic_resumes", DS / "edge_cases"
JD = ("Backend Developer needed.\nRequirements:\n- Python and Flask REST API services\n- SQL and PostgreSQL\n- Docker, Git and unit testing\n\n"
      "Preferred:\n- Redis\n- AWS\n- CI/CD")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = create_app(cls.tmp.name, recover=False)
        cls.c = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def upload(self, paths, **form):
        data = {"files": [(io.BytesIO(Path(p).read_bytes()), Path(p).name) for p in paths], **form}
        return self.c.post("/api/batches", data=data, content_type="multipart/form-data")

    def wait(self, bid, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            b = self.c.get(f"/api/batches/{bid}").get_json()
            if b["batch"]["status"] not in ("pending", "processing"):
                return b
            time.sleep(0.3)
        self.fail("batch did not finish")

    def job(self):
        return self.c.post("/api/jobs", json=dict(title="Backend Developer", description=JD)).get_json()["job"]["id"]


class TestParsingMatching(unittest.TestCase):
    def test_pdf_and_docx_parse(self):
        for f in ("backend_strong_01.pdf", "backend_strong_02.docx"):
            p = parsing.extract(RES / f, f.split(".")[-1])
            self.assertTrue(p["email"] and p["name"] and "experience" in p["sections"], f)

    def test_invalid_files(self):
        for f, ext in (("corrupt.docx", "docx"), ("fake.pdf", "pdf"), ("empty.pdf", "pdf"), ("no_text.pdf", "pdf")):
            with self.assertRaises(parsing.ParseError, msg=f):
                parsing.extract(EDGE / f, ext)

    def test_matching_ranks_relevant_higher(self):
        job = dict(title="Backend", description=JD)
        sc = lambda f: matching.analyze(parsing.extract(RES / f, f.split(".")[-1]), job)
        strong, weak, other = sc("backend_strong_01.pdf"), sc("backend_weak_04.docx"), sc("marketing_strong_21.pdf")
        self.assertGreater(strong["score"], weak["score"])
        self.assertGreater(weak["score"], other["score"])
        self.assertIn("docker", other["missing_required"])
        self.assertEqual(strong["missing_required"], [])
        self.assertAlmostEqual(sum(b["weight"] for b in strong["breakdown"].values()), 1, places=2)

    def test_semantic_is_partial_not_confirmed(self):
        text = "Jane Doe\nEXPERIENCE\nBuilt services with Spring Boot for the billing team.\nSKILLS\nJava"
        p = dict(labelled=[("header", "Jane Doe"), ("experience", "Built services with Spring Boot for the billing team."), ("skills", "Java")],
                 sections={"experience": "x"}, text=text, ocr_used=False, tables=0, pages=1, headings=[], unknown_headings=[], date_ranges=[],
                 name="Jane Doe", email=None, phone=None, summary=None, education=[], experience=[], projects=[], certifications=[], skills_listed=[])
        r = matching.analyze(p, dict(title="Dev", description="Requirements: REST API development"))
        v = r["required"][0]
        self.assertEqual((v["status"], v["match_type"]), ("partial", "semantic"))

    def test_synonym_match(self):
        p = dict(labelled=[("experience", "Deployed on k8s clusters")], sections={"experience": "x"}, text="Deployed on k8s clusters", ocr_used=False,
                 tables=0, pages=1, headings=[], unknown_headings=[], date_ranges=[], name=None, email=None, phone=None, summary=None,
                 education=[], experience=[], projects=[], certifications=[], skills_listed=[])
        r = matching.analyze(p, dict(title="x", description="Requirements: Kubernetes"))
        self.assertEqual(r["required"][0]["match_type"], "synonym")


class TestApi(Base):
    def test_health(self):
        self.assertEqual(self.c.get("/api/health").get_json()["status"], "ok")

    def test_job_crud_and_validation(self):
        self.assertEqual(self.c.post("/api/jobs", json=dict(title="x", description="  ")).status_code, 400)
        self.assertEqual(self.c.post("/api/jobs", json=dict(description="d")).status_code, 400)
        jid = self.c.post("/api/jobs", json=dict(title="QA", description="Selenium testing", required_skills="selenium, jira")).get_json()["job"]["id"]
        self.assertEqual(self.c.get(f"/api/jobs/{jid}").get_json()["job"]["required_skills"], ["selenium", "jira"])
        self.assertEqual(self.c.put(f"/api/jobs/{jid}", json=dict(title="QA2", description="d")).get_json()["job"]["title"], "QA2")
        self.assertEqual(len(self.c.get("/api/jobs?q=QA2").get_json()["jobs"]), 1)
        self.assertEqual(self.c.delete(f"/api/jobs/{jid}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/jobs/{jid}").status_code, 404)

    def test_batch_validation(self):
        self.assertEqual(self.c.post("/api/batches", data={}, content_type="multipart/form-data").status_code, 400)
        r = self.upload([RES / "backend_strong_01.pdf"], title="x", description="")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.upload([RES / "backend_strong_01.pdf"], job_id="nope").status_code, 404)

    def test_full_workflow_failure_retry_persistence_reports(self):
        jid = self.job()
        trunc = Path(self.tmp.name) / "truncated.pdf"
        trunc.write_bytes(b"%PDF-1.4\n%%garbage, truncated file")   # valid header, unreadable body -> stored, retryable failure
        files = [RES / "backend_strong_01.pdf", RES / "backend_strong_02.docx", RES / "backend_weak_04.docx", EDGE / "corrupt.docx", EDGE / "fake.pdf", EDGE / "duplicate_of_backend_strong_01.pdf", trunc]
        r = self.upload(files, job_id=jid)
        self.assertEqual(r.status_code, 201)
        bid = r.get_json()["batch_id"]
        b = self.wait(bid)
        self.assertEqual(b["batch"]["status"], "partially_completed")
        self.assertEqual(b["batch"]["counts"]["completed"], 4)
        self.assertEqual(b["batch"]["counts"]["failed"], 3)
        failed = [c for c in b["candidates"] if c["status"] == "failed"]
        self.assertTrue(all(c["error"] for c in failed))
        dup = [c for c in b["candidates"] if c["filename"].startswith("duplicate_of")][0]
        self.assertTrue(dup["duplicate_of"] and dup["likely_duplicates"])
        res = self.c.get(f"/api/batches/{bid}/results").get_json()["results"]
        self.assertEqual([x["score"] for x in res], sorted([x["score"] for x in res], reverse=True))
        # retry re-queues only failed files that were stored (invalid/magic-mismatch files are not retryable); completed untouched
        before = {c["id"]: c["analyzed_at"] for c in b["candidates"] if c["status"] == "completed"}
        self.assertEqual(self.c.post(f"/api/batches/{bid}/retry").get_json()["retried"], 1)
        b2 = self.wait(bid)
        self.assertEqual({c["id"]: c["analyzed_at"] for c in b2["candidates"] if c["status"] == "completed"}, before)
        # candidate details, compare, improve, versions
        ids = [x["id"] for x in res[:2]]
        cd = self.c.get(f"/api/candidates/{ids[0]}").get_json()["candidate"]
        self.assertIn("breakdown", cd["result"]); self.assertTrue(cd["text"])
        cmp = self.c.post("/api/compare", json=dict(candidate_ids=ids)).get_json()
        self.assertEqual(len(cmp["candidates"]), 2)
        self.assertEqual(self.c.post("/api/compare", json=dict(candidate_ids=ids[:1])).status_code, 400)
        csvr = self.c.post("/api/compare/export", json=dict(candidate_ids=ids))
        self.assertIn(b"estimated_match_score", csvr.data)
        imp = self.c.post(f"/api/candidates/{ids[0]}/improve", json=dict(use_ai=True)).get_json()
        self.assertTrue(imp["ai_error"] is None or "configured" in imp["ai_error"])   # Gemini unavailable -> graceful
        self.assertIsInstance(imp["suggestions"], list)
        ver = self.c.post("/api/versions/compare", json=dict(old_id=ids[1], new_id=ids[0])).get_json()
        self.assertIn("score_change", ver)
        # reports
        rid = self.c.post(f"/api/candidates/{ids[0]}/report").get_json()["report_id"]
        dl = self.c.get(f"/api/reports/{rid}/download")
        self.assertTrue(dl.data.startswith(b"%PDF"))
        ex = self.c.get(f"/api/batches/{bid}/export.csv")
        self.assertIn(b"batch_id", ex.data); self.assertEqual(ex.data.count(b"\n"), 8)
        self.assertEqual(self.c.delete(f"/api/reports/{rid}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/reports/{rid}").status_code, 404)
        # history + dashboard are derived from stored records
        h = self.c.get("/api/history?q=Backend&status=partially_completed").get_json()
        self.assertTrue(any(i["id"] == bid for i in h["items"]))
        d = self.c.get("/api/dashboard").get_json()
        self.assertGreaterEqual(d["totals"]["completed"], 4)
        # persistence across app restart
        app2 = create_app(self.tmp.name, recover=False)
        self.assertEqual(app2.test_client().get(f"/api/batches/{bid}").get_json()["batch"]["counts"]["completed"], 4)
        # delete candidate
        self.assertEqual(self.c.delete(f"/api/candidates/{ids[1]}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/candidates/{ids[1]}").status_code, 404)

    def test_skip_duplicates_and_size_limit(self):
        jid = self.job()
        f = RES / "devops_strong_17.pdf" if (RES / "devops_strong_17.pdf").exists() else RES / "backend_strong_01.pdf"
        self.wait(self.upload([f], job_id=jid).get_json()["batch_id"])
        b = self.wait(self.upload([f], job_id=jid, skip_duplicates="true").get_json()["batch_id"])
        self.assertEqual(b["batch"]["counts"].get("skipped"), 1)
        self.c.put("/api/settings", json=dict(max_size_mb=1, max_files=2))
        big = io.BytesIO(b"%PDF" + b"0" * (1024 * 1024 + 10))
        r = self.c.post("/api/batches", data={"files": [(big, "big.pdf")], "job_id": jid}, content_type="multipart/form-data")
        bid = r.get_json()["batch_id"]
        self.assertIn("larger", self.c.get(f"/api/batches/{bid}").get_json()["candidates"][0]["error"])
        self.assertEqual(self.upload([f, f, f], job_id=jid).status_code, 400)       # exceeds max_files
        self.assertEqual(self.c.put("/api/settings", json=dict(max_files=999)).status_code, 400)
        self.c.put("/api/settings", json=dict(max_size_mb=10, max_files=20))

    def test_settings_do_not_expose_secrets(self):
        os.environ["GEMINI_API_KEY"] = "SECRET-TEST-KEY"; os.environ["GEMINI_MODEL"] = ""
        txt = self.c.get("/api/settings").get_data(as_text=True)
        self.assertNotIn("SECRET-TEST-KEY", txt)
        self.assertFalse(json.loads(txt)["ai"]["configured"])
        del os.environ["GEMINI_API_KEY"]

    def test_unknown_route_json(self):
        r = self.c.get("/api/nope")
        self.assertEqual(r.status_code, 404); self.assertIn("error", r.get_json())


if __name__ == "__main__":
    unittest.main()
