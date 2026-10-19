#!/usr/bin/env python3
"""
A verified reference is shown with its full title, subtitle included.

    python3 tests/test_academic_reference_subtitle_display.py

Crossref often splits a book's title from its subtitle: Pearl (2009) is
recorded as title "Causality", subtitle "Models, Reasoning, and Inference".
Since 2f82cba matching reads both, so the proposal "Causality: Models,
Reasoning, and Inference" verifies, but the page then showed the verified
record's title alone. Only the verified identity's displayed title changes:
an unverified proposal keeps its proposed identity, and a record that
verification attached without accepting it (a probable match, or the record
a conflicting DOI resolves to) is shown exactly as before.

Runs the page's own renderer under Node. Checked:

  1. a verified record with a subtitle is shown with both;
  2. a verified record without one is unchanged;
  3. an unverified proposal keeps its proposed identity;
  4. the metadata-conflict display from 1f7d363 is unchanged;
  5. a subtitle already in the title is not repeated.
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


def check(condition, label, detail=""):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label
          + (f"  [{detail}]" if not condition and detail else ""))
    if not condition:
        failures += 1


def record(title, subtitle="", **extra):
    return dict({"title": title, "subtitle": subtitle, "authors": ["Judea Pearl"],
                 "year": 2009, "venue": "", "doi": "10.1017/cbo9780511803161",
                 "work_type": "monograph", "publisher": "Cambridge University Press",
                 "container_titles": []}, **extra)


def reference(proposed, status, candidate=None, related=None):
    return {"proposed_reference": proposed,
            "verification": {"crossref_verification": {
                "status": status, "candidate": candidate, "related_candidate": related,
                "reasons": []}}}


PROPOSED_PEARL = {"title": "Causality: Models, Reasoning, and Inference",
                  "author": "Pearl, J.", "year": 2009,
                  "venue": "Cambridge University Press", "doi": None}

node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run.")
    sys.exit(0)

page_functions = re.findall(r"^function \w+\(.*?\n}\n", HTML, re.S | re.M)


def render(ref):
    script = "\n".join(page_functions) + (
        f"\nprocess.stdout.write(renderAcademicReference({json.dumps(ref)}, 0));")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    run = subprocess.run([node, f.name], capture_output=True, text=True, timeout=30)
    Path(f.name).unlink()
    if run.returncode != 0:
        print(run.stderr)
    return run.stdout


def heading(html):
    match = re.search(r"<strong>1\. (.*?)</strong>", html)
    return match.group(1) if match else None


# ===========================================================================
print("\n[1] verified record with a subtitle")
out = render(reference(PROPOSED_PEARL, "verified",
                       record("Causality", "Models, Reasoning, and Inference")))
check(heading(out) == "Causality: Models, Reasoning, and Inference",
      "shown as 'Causality: Models, Reasoning, and Inference'", heading(out))
check("Bibliographic identity verified" in out, "still marked verified")

# ===========================================================================
print("\n[2] verified record without a subtitle")
rubin = record("Multiple Imputation for Nonresponse in Surveys", "",
               authors=["Donald B. Rubin"], year=1987,
               venue="Wiley Series in Probability and Statistics",
               doi="10.1002/9780470316696")
out = render(reference({"title": "Multiple Imputation for Nonresponse in Surveys",
                        "author": "Rubin, D. B.", "year": 1987,
                        "venue": "John Wiley & Sons", "doi": None}, "verified", rubin))
check(heading(out) == "Multiple Imputation for Nonresponse in Surveys",
      "the title is unchanged", heading(out))
out = render(reference(PROPOSED_PEARL, "verified", {k: v for k, v in record("Causality").items()
                                                     if k != "subtitle"}))
check(heading(out) == "Causality",
      "a record from before subtitles were kept still renders", heading(out))

# ===========================================================================
print("\n[3] unverified proposal keeps its proposed identity")
proposed = dict(PROPOSED_PEARL, title="Causality")
out = render(reference(proposed, "not_verified", None,
                       related=record("Causality", "Models, Reasoning, and Inference")))
check(heading(out) == "Causality", "the proposal's own title is shown", heading(out))
check("Bibliographic identity not independently established" in out
      and "Related Crossref record:" in out,
      "it stays unverified, with the related record separate")
probable = render(reference(proposed, "probable",
                            record("Causality", "Models, Reasoning, and Inference")))
check(heading(probable) == "Causality"
      and "Bibliographic identity not independently established" in probable,
      "a probable match does not replace or extend the proposal's title", heading(probable))

# ===========================================================================
print("\n[4] metadata conflict: unchanged")
conflict = reference(
    {"title": "Multiple imputation using chained equations: issues and guidance "
              "for practice", "author": "White, I. R.", "year": 2011,
     "venue": "Statistics in Medicine", "doi": "10.1002/sim.4192"},
    "metadata_conflict",
    {"title": "Comparison of two populations of curves with an application in "
              "neuronal data analysis", "subtitle": "",
     "authors": ["Sam Behseta", "Shojaeddin Chenouri"], "year": 2011,
     "venue": "Statistics in Medicine", "doi": "10.1002/sim.4192",
     "work_type": "journal-article", "publisher": "Wiley", "container_titles": []})
out = render(conflict)
check(heading(out).startswith("Multiple imputation using chained equations")
      and "White, I. R." in out.split("academic-related-record")[0],
      "the proposal keeps its own title and author", heading(out))
check("The DOI given resolves to a different publication:" in out
      and out.find("Comparison of two populations of curves")
      > out.find("The DOI given resolves to a different publication:"),
      "the DOI's record is still shown separately, as a different publication")
check("DOI given: 10.1002/sim.4192" in out
      and 'href="https://doi.org/10.1002%2Fsim.4192"' not in out.split("academic-related-record")[0],
      "the conflicting DOI is still not linked as the proposal's own")

# ===========================================================================
print("\n[5] a subtitle already in the title is not repeated")
out = render(reference(PROPOSED_PEARL, "verified",
                       record("Causality: Models, Reasoning, and Inference",
                              "Models, Reasoning, and Inference")))
check(heading(out) == "Causality: Models, Reasoning, and Inference",
      "the title is shown once", heading(out))
out = render(reference(PROPOSED_PEARL, "verified",
                       record("Causality: models, reasoning and inference",
                              "Models, Reasoning, and Inference")))
check(heading(out) == "Causality: models, reasoning and inference",
      "nor when it differs only in case and punctuation", heading(out))
out = render(reference({"title": "How many imputations do you need? A two-stage calculation"},
                       "verified",
                       record("How many imputations do you need?",
                              "A two-stage calculation using a quadratic rule")))
check(heading(out) == ("How many imputations do you need? "
                       "A two-stage calculation using a quadratic rule"),
      "a title ending in a question mark is followed by the subtitle without a colon",
      heading(out))

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
