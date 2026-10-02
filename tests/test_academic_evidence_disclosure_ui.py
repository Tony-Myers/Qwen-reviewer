#!/usr/bin/env python3
"""
Progressive disclosure of the evidence assessment in the chat page.

    python3 tests/test_academic_evidence_disclosure_ui.py

Level 1, always visible, is the compact evidence statement. Level 2, behind
"View evidence and sources" ("View checking details" when there are no
sources), is the curated further reading, with full
references and the points not established by the local guidance check behind
toggles of their own. Level 3, behind "Technical checking details", holds the diagnostics and
the existing verification panel. The structural checks always run; the
rendering checks run the page's own functions under Node when it is installed.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


def function_source(name):
    match = re.search(r"function " + name + r"\(.*?\n}\n", HTML, re.S)
    return match.group(0) if match else ""


print("\n[structure] the page builds three levels")
renderer = function_source("renderAcademicCheckFurther")
evidence = function_source("renderAcademicEvidence")
check(bool(renderer) and bool(evidence), "the evidence renderers exist")
check("'View evidence and sources'" in renderer and "'View checking details'" in renderer,
      "level two is labelled by what it holds")
check("Show the points not settled by the guidance" not in HTML,
      "the old wording, which credited the guidance rather than the check, is gone")
check("<summary>Show points not established by the local guidance check</summary>" in renderer,
      "the points sit behind their own toggle, labelled without a count")
check("<summary>Technical checking details</summary>" in renderer,
      "level three sits behind 'Technical checking details'")
check(renderer.index("Technical checking details") < renderer.index("h += auditHtml"),
      "the existing verification panel is inside level three")
check("diagnostics" not in renderer[:renderer.index("hasSources")]
      .replace("renderCheckFurtherDiagnostics", ""),
      "level one reads nothing from the diagnostics")
check("your notes" not in HTML.lower(),
      "nothing in the page addresses the reader as the owner of the notes")
audit = HTML[HTML.index("function renderAcademicAudit"):HTML.index("function renderAcademicEvidence")]
check("checkFurther" not in audit and "evidence-check" not in audit,
      "the existing audit renderer is untouched by the evidence layer")


print("\n[rendering] what each level actually shows")
node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run. "
          "Install Node to run them; the structural checks above still apply.")
else:
    names = ["esc", "checkFurtherAttr", "checkFurtherLink", "checkFurtherReference",
             "checkFurtherFullReference", "checkFurtherPoint",
             "renderCheckFurtherDiagnostics", "renderAcademicCheckFurther"]
    sources = [function_source(n) for n in names]
    check(all(sources), "every renderer function can be extracted")
    payload = {
        "state": "further_reading",
        "title": "Further reading available",
        "summary": "Parts of this answer align with the local methodological guidance, "
                   "while some details go beyond what that guidance covers.",
        "secondary": "Relevant curated sources are listed for further reading and independent checking.",
        "worth_checking": [],
        "citation_notice": None,
        "source_count": 1,
        "about": "Academic Chat compares parts of its answer with locally curated guidance.",
        "further_reading": [{
            "topic": "Are all 95% credible intervals the same?",
            "references": [{
                "author_year": "Hyndman (1996)", "short": "highest-density regions",
                "type": "Journal article", "access_label": "May need institutional access",
                "read_link": "https://doi.org/10.1080/00031305.1996.10474359",
                "link": "https://doi.org/10.1080/00031305.1996.10474359",
                "doi": "10.1080/00031305.1996.10474359",
                "cite": "Hyndman, R. J. (1996). Computing and graphing highest density regions.",
            }],
            "points": [{"text": "POINT-SENTENCE", "kind": "answer_sentence"}],
        }],
        "diagnostics": {"rules_version": "2", "counts": {"judgements": 31},
                        "routing": [{"statement": "ROUTED-STATEMENT", "routed_to": "x", "reason": "y"}],
                        "lost_conditions": [{"answer_sentence": "LOST-SENTENCE",
                                             "atomic_claim": "ATOMIC-CLAIM",
                                             "contextual_status": "s"}]},
    }
    script = "\n".join(sources) + f"""
const out = renderAcademicCheckFurther({json.dumps(payload)}, '<section>REFERENCES-HTML</section>',
  '<section>Evidence status: AUDIT-HTML</section>');
process.stdout.write(out);
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    html = subprocess.run([node, f.name], capture_output=True, text=True, timeout=30).stdout
    Path(f.name).unlink()

    level2_at = html.find("View evidence and sources")
    level3_at = html.find("Technical checking details")
    points_at = html.find("Show points not established by the local guidance check")
    level1 = html[:level2_at]
    check(level2_at > 0 and level3_at > level2_at and points_at > level2_at,
          "the three levels render in order")
    check("Further reading available" in level1 and "Parts of this answer align" in level1,
          "level one carries the state and its summary")
    check("1 relevant source available" in level1,
          "level one offers the number of sources, the only number it shows")
    check("31" not in level1 and "POINT-SENTENCE" not in level1 and "Hyndman" not in level1,
          "level one shows no claim counts, no points and no references")
    check(html.find("Hyndman (1996)") > level2_at and html.find("Hyndman (1996)") < level3_at,
          "references appear at level two in compact form")
    check(html.find("POINT-SENTENCE") > points_at,
          "points appear only behind their own toggle")
    check("“POINT-SENTENCE”" in html,
          "an answer sentence is shown in quotation marks, as the answer's words")
    for marker in ("AUDIT-HTML", "ROUTED-STATEMENT", "LOST-SENTENCE", "ATOMIC-CLAIM", "judgements"):
        check(html.find(marker) > level3_at, f"{marker} appears only in the technical details")
    check(html.find("REFERENCES-HTML") > level2_at and html.find("REFERENCES-HTML") < level3_at,
          "sources cited by the answer are listed at level two")


print("\n[incomplete] the reader is told once; the older notice is technical detail")
if not node:
    print("SKIP: Node is not installed, so the incomplete-state rendering did not run.")
else:
    # Every top-level function in the page, so renderAcademicEvidence runs as
    # it does in the browser (declarations only; nothing touches the DOM).
    page_functions = re.findall(r"^function \w+\(.*?\n}\n", HTML, re.S | re.M)
    incomplete = {
        "answer_draft": "ANSWER",
        "release": {"status": "checking_incomplete", "safe_to_present": False,
                    "reasons": ["RELEASE-REASON"]},
        "claim_coverage": {"status": "coverage_assessment_unavailable",
                           "reasons": ["COVERAGE-REASON"]},
        "check_further": {
            "state": "incomplete", "title": "Evidence check incomplete",
            "summary": "INCOMPLETE-SUMMARY", "secondary": "INCOMPLETE-SECONDARY",
            "worth_checking": [], "citation_notice": None, "further_reading": [],
            "source_count": 0, "about": "ABOUT", "diagnostics": {"rules_version": "2"},
        },
    }
    script = "\n".join(page_functions) + (
        f"\nprocess.stdout.write(renderAcademicEvidence({json.dumps(incomplete)}));")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    run = subprocess.run([node, f.name], capture_output=True, text=True, timeout=30)
    Path(f.name).unlink()
    out = run.stdout
    level3_at = out.find("Technical checking details")
    check(run.returncode == 0 and level3_at > 0, "the incomplete state renders")
    check(out.count("Evidence check incomplete") == 1,
          "'Evidence check incomplete' is shown once")
    check(0 <= out.find("INCOMPLETE-SECONDARY") < level3_at,
          "with its reassurance in the normal view")
    check(out.count("Checking incomplete.") == 1
          and out.find("Checking incomplete.") > level3_at,
          "the older technical-claim coverage notice appears only in the technical details")
    check(out.find("COVERAGE-REASON") > level3_at,
          "the coverage failure reason stays in the technical details")
    check("View checking details" in out and "View evidence and sources" not in out,
          "with no sources, level two is labelled 'View checking details'")

    # The same state with a source cited by the answer is labelled for sources.
    cited = dict(incomplete, references=[{"reference": {"author": "Altman", "year": 1995,
                                                      "title": "Absence of evidence"}}],
                 source_claims=[{"claim": {"claim": "c", "reference_index": 0}}])
    script = "\n".join(page_functions) + (
        f"\nprocess.stdout.write(renderAcademicEvidence({json.dumps(cited)}));")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    run = subprocess.run([node, f.name], capture_output=True, text=True, timeout=30)
    Path(f.name).unlink()
    check(run.returncode == 0 and "View evidence and sources" in run.stdout
          and "View checking details" not in run.stdout,
          "a source cited by the answer keeps 'View evidence and sources'")

print()
if failures:
    print(f"{failures} check(s) failed.")
    sys.exit(1)
print("All evidence disclosure checks passed.")
