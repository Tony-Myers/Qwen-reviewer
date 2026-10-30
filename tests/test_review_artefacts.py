"""Behavioural regressions for the per-review artefacts.

The review worker is run with every model-facing stage replaced by a test
double, on synthetic text. No model, backend or network is used.

Covered:
- the extraction evidence appendix and the Human Evidence Appendix are both
  produced, are separate, and each has its own endpoint and status flag;
- Development mode ON and OFF give identical model-stage inputs, report and
  appendices; only completed-job trace retention and the trace endpoint
  differ.
"""
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import review_pipeline as rp
import server

PRIMARY = "The primary outcome was measured after twelve weeks of treatment."
SUPPLEMENT = "The sensitivity analysis used complete cases and robust standard errors."
REPORT = (
    "# Overall synopsis\nA primary manuscript with supporting evidence.\n"
    "# Major strengths\nClear reporting.\n# Directly supported concerns\n"
    "* Concern: Check the sensitivity analysis,\n"
    "  which was restricted to complete cases.\n"
    f'* Evidence: "{SUPPLEMENT}"\n'
    "# Verification prompts\n- Check: whether follow-up was complete.\n"
    "  Reason: Attrition is not reported.\n"
    "\nCheck the design.\n"
    "# Extraction limits\nText only.\n# Overall confidence\nModerate.\n"
)


def _describe(value):
    """A stable description of a call argument for comparison across runs."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_describe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _describe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    for attribute in ("source_name", "text"):
        if not hasattr(value, attribute):
            break
    else:
        return {"type": type(value).__name__, "source_name": value.source_name, "text": value.text}
    if hasattr(value, "summary_text"):
        return {"type": type(value).__name__, "summary": value.summary_text()}
    return type(value).__name__


class ReviewArtefacts(unittest.TestCase):
    def setUp(self):
        self.jobs = patch.object(server, "review_jobs", {})
        self.jobs.start()
        self.addCleanup(self.jobs.stop)

    def run_worker(self, job_id, *, development_mode, supplements=0):
        root = Path(tempfile.mkdtemp())
        path = root / "upload.txt"
        path.write_text(PRIMARY)
        extra = []
        for i in range(supplements):
            p = root / f"s{i}.txt"
            p.write_text(SUPPLEMENT + f" Source marker {i}.")
            extra.append({"path": str(p), "name": "supp.txt"})
        job = dict(status="running", progress=[], filename="main.txt", supplements=extra,
                   cancel_requested=False, thinking=None, thinking_scope="review",
                   development_mode=development_mode)
        server.review_jobs[job_id] = job
        calls = []

        def recorder(name, result):
            def record(*args, **kwargs):
                calls.append((name, _describe(list(args[2:])), _describe(kwargs)))
                return result(*args, **kwargs)
            return record

        with ExitStack() as stack:
            for name, result in [
                ("review_chunk", lambda m, t, chunk, **kw: chunk.text),
                ("synthesize_file_review", lambda m, t, name, combined, **kw: combined),
                ("synthesize_report", lambda m, t, files, **kw: REPORT),
                ("validate_report_against_evidence", lambda m, t, d, f, **kw: d),
            ]:
                stack.enter_context(patch.object(rp, name, side_effect=recorder(name, result)))
            stack.enter_context(patch.object(rp, "REVIEW_PASSES", 1))
            server._run_review_inner(job_id, path, "general", root)
        self.assertFalse(root.exists())
        self.assertEqual(job["status"], "complete", job.get("error"))
        return job, calls

    @staticmethod
    def without_timestamp(text):
        return "\n".join(line for line in text.splitlines() if not line.startswith("Generated:"))

    def test_both_appendices_are_produced_and_separate(self):
        for supplements in (0, 1):
            with self.subTest(supplements=supplements):
                job, _ = self.run_worker(f"both-{supplements}", development_mode=False,
                                         supplements=supplements)
                extraction = job["appendix"]
                human = job["human_appendix"]
                # Extraction evidence appendix: the earlier public content.
                self.assertEqual(extraction.count("# Evidence appendix"), 1)
                self.assertIn("## Evidence manifest", extraction)
                self.assertIn("## Chunk previews", extraction)
                self.assertIn("Automated extraction can be incomplete or wrong.", extraction)
                self.assertIn(PRIMARY[:40], extraction)
                if supplements:
                    self.assertIn("## Source: Supplement 1: supp.txt", extraction)
                    self.assertIn("Source marker 0", extraction)
                self.assertNotIn("# Human Evidence Appendix", extraction)
                # Human Evidence Appendix: cards from the final report.
                self.assertEqual(human.count("# Human Evidence Appendix"), 1)
                self.assertNotIn("# Evidence appendix", human)
                self.assertIn("## C1 — Concern", human)
                self.assertIn("which was restricted to complete cases", human)
                evidence_line = [line for line in human.splitlines()
                                 if line.startswith("**Evidence reported in the review:**")]
                self.assertEqual(len(evidence_line), 1)
                self.assertIn(SUPPLEMENT[:-1], evidence_line[0])
                self.assertIn("## Q1 — Verification question", human)
                self.assertIn("**Reviewer interpretation:** Attrition", human)
                self.assertIn("Not established — human verification required", human)
                self.assertNotIn("**Verified manuscript evidence:**", human)
                self.assertIn("## Report content not converted into cards", human)
                self.assertIn("Check the design.", human)

    def test_endpoints_and_status_flags(self):
        on, _ = self.run_worker("job-on", development_mode=True)
        off, _ = self.run_worker("job-off", development_mode=False)
        with patch.object(server, "ensure_model"), TestClient(server.app) as client:
            for job_id, job in (("job-on", on), ("job-off", off)):
                with self.subTest(job=job_id):
                    r = client.get(f"/api/review/appendix/{job_id}")
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r.json(), {"appendix": job["appendix"]})
                    r = client.get(f"/api/review/human-appendix/{job_id}")
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r.json(), {"human_appendix": job["human_appendix"]})
                    with client.stream("GET", f"/api/review/status/{job_id}") as stream:
                        events = [json.loads(line[6:]) for line in stream.iter_lines()
                                  if line.startswith("data: ")]
                    complete = [e for e in events if e["type"] == "complete"][0]
                    self.assertTrue(complete["has_appendix"])
                    self.assertTrue(complete["has_human_appendix"])
                    self.assertEqual(complete["has_development_trace"], job_id == "job-on")
            r = client.get("/api/review/trace/job-on")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(set(r.json()), {"trace", "filename"})
            self.assertEqual(r.json()["trace"]["job_id"], "job-on")
            self.assertEqual(client.get("/api/review/trace/job-off").status_code, 404)
            self.assertEqual(client.get("/api/review/human-appendix/unknown").status_code, 404)

    def test_development_mode_changes_only_trace_retention(self):
        on, calls_on = self.run_worker("same", development_mode=True, supplements=1)
        self.jobs.stop()
        self.jobs = patch.object(server, "review_jobs", {})
        self.jobs.start()
        off, calls_off = self.run_worker("same", development_mode=False, supplements=1)

        self.assertTrue(calls_on)
        self.assertEqual(calls_on, calls_off)
        self.assertEqual(on["report"], off["report"])
        self.assertEqual(self.without_timestamp(on["appendix"]),
                         self.without_timestamp(off["appendix"]))
        self.assertEqual(on["human_appendix"], off["human_appendix"])
        self.assertIsInstance(on.get("trace"), dict)
        self.assertIsNone(off.get("trace"))


if __name__ == "__main__":
    unittest.main()
