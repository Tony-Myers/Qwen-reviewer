#!/usr/bin/env python3
"""
The check-further rules, one scenario per rule, plus the ETI/HDI answer.

    python3 tests/test_academic_check_further.py

The layer reads verdicts the checking machinery has already reached and
decides whether the reader should check the answer further and against which
curated sources. It makes no model call, so every case here is deterministic.
"""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import academic_check_further as cf           # noqa: E402
import reviewer_notes as rn                   # noqa: E402

CONSISTENT = "methodologically_consistent"
CONFLICT = "methodological_conflict"
NOT_EST = "methodological_consistency_not_established"

failures = 0


def check(condition, label):
    global failures
    if condition:
        print(f"PASS: {label}")
    else:
        failures += 1
        print(f"FAIL: {label}")


NOTE = """# Test Note

#### Common reviewer questions

##### What is alpha?

Alpha is a threshold for rejecting a null hypothesis, and this paragraph is
long enough to stand as its own section rather than being merged into the
section before it during chunking, which needs a couple of hundred characters.

```references
- cite: Section Source (2020). On alpha. Journal, 1, 1-2.
  doi: 10.1000/section
  supports: What alpha is.
  checked: 2026-09-30, Crossref
```

##### What is beta?

Beta is the type II error rate, and this paragraph is also long enough to be
kept as a section in its own right by the chunker rather than folded into the
previous one, so that a passage can carry this heading on its own.

#### References

Intro sentence for the list.

```references
- cite: Note Source (2019). General. Journal, 2, 3-4.
  doi: https://doi.org/10.1000/NOTE
  supports: The whole topic.
  checked: 2026-09-30, Crossref
```

---

*Based on:* something.
"""

tmp = Path(tempfile.mkdtemp())
(tmp / "Test Note.md").write_text(NOTE, encoding="utf-8")
index = rn.NotesIndex(tmp)


def passage(heading, score=0.5):
    return rn.Passage("Test Note", heading, "text", score)


def tclaim(statement, status, heading="What is alpha?"):
    claim = NS(statement=statement)
    method = NS(status=status, passages=[passage(heading)], reasons=["r"])
    return NS(claim=claim, verification=NS(status="not_technically_verified"),
              methodological_consistency=method)


def result(technical=(), contexts=(), references=(), guidance=None,
           safe=True, status="release_allowed_with_unverified_claims"):
    return NS(
        release=NS(safe_to_present=safe, status=status,
                   reasons=["blocked for a reason"] if not safe else []),
        technical_claims=list(technical),
        discovered_claim_assessments=list(contexts),
        references=list(references),
        local_guidance=NS(passages=[passage("What is alpha?")]
                          if guidance is None else guidance),
    )


def rules(assessment):
    return [t.rule for t in assessment.triggers]


print("\n[parser] references are split from the text and keyed correctly")
check(index.reference_errors == [], "the test note parses without errors")
check([r.doi for r in index.references_for("Test Note", "What is alpha?")]
      == ["10.1000/section"], "a section list overrides the note list")
check([r.doi for r in index.references_for("Test Note", "What is beta?")]
      == ["10.1000/NOTE"], "a section without a list falls back to the note's")
check(index.references_for("Test Note", "What is beta?")[0].link()
      == "https://doi.org/10.1000/NOTE", "a DOI given as a URL is normalised")
check(not any("```references" in p.text or "doi:" in p.text
              for p in index.passages), "no reference text reaches a passage")
check(not any(p.heading == "References" for p in index.passages),
      "the References section is not indexed as guidance")
check(any("*Based on:*" in p.text for p in index.passages),
      "the Based on line is still indexed, as before")

print("\n[parser] malformed entries are reported, not raised")
bad = NOTE.replace("  supports: What alpha is.\n", "  suports: typo\n")
(tmp / "Test Note.md").write_text(bad, encoding="utf-8")
bad_index = rn.NotesIndex(tmp)
check(len(bad_index.reference_errors) == 1
      and "unknown field 'suports'" in bad_index.reference_errors[0],
      "a misspelt field is reported with its name")
check(bad_index.references_for("Test Note", "What is alpha?")[0].doi
      == "10.1000/NOTE", "the bad section list is skipped, not half-read")
for missing, text in (
        ("supports", "- cite: X (2020).\n  doi: 10.1/x\n"),
        ("identifier", "- cite: X (2020).\n  supports: y\n")):
    try:
        rn.parse_references_block(text, "t")
        check(False, f"an entry without {missing} is rejected")
    except rn.ReferenceFormatError:
        check(True, f"an entry without {missing} is rejected")
(tmp / "Test Note.md").write_text(NOTE, encoding="utf-8")

print("\n[rules] consistent with the notes")
a = cf.assess_check_further(result([tclaim("A", CONSISTENT)]), index)
check(a.level == cf.LEVEL_SETTLED and rules(a) == [],
      "every claim consistent, nothing blocked: consistent_with_notes")
check("guidance rather than proof" in a.headline,
      "the best outcome still says the notes are not proof")
check([r.doi for _, _, r in a.further_reading] == ["10.1000/section"],
      "further reading is drawn from the sections consulted")

print("\n[rules] not settled, grouped by section, with where to check")
a = cf.assess_check_further(result([
    tclaim("A", NOT_EST), tclaim("a.", NOT_EST), tclaim("B", NOT_EST),
    tclaim("C", NOT_EST, heading="What is beta?"), tclaim("D", CONSISTENT),
]), index)
check(a.level == cf.LEVEL_ADVISED, "unsettled claims advise a check")
check(rules(a) == ["not_settled_by_notes"], "and trigger only that rule")
check("3 claims" in a.triggers[0].message,
      "case and punctuation variants count once; paraphrases do not merge")
check([(g.heading, g.claims) for g in a.groups]
      == [("What is alpha?", ["A", "B"]), ("What is beta?", ["C"])],
      "claims are grouped under the section they were judged against")
check([r.doi for r in a.groups[1].references] == ["10.1000/NOTE"],
      "each group carries its section's references, or the note's")

print("\n[rules] a statement judged consistent anywhere is settled")
ctx = NS(discovered_claim=NS(claim=NS(statement="A")),
         material_restriction=NS(material_restriction_omitted=False),
         contextual_methodological_consistency=NS(
             status=CONSISTENT, passages=[passage("What is alpha?")]))
a = cf.assess_check_further(result([tclaim("A", NOT_EST)], [ctx]), index)
check(a.level == cf.LEVEL_SETTLED,
      "a consistent contextual judgement settles the same statement")

print("\n[rules] conflicts and blocked answers need checking")
a = cf.assess_check_further(result([tclaim("A", CONFLICT)]), index)
check(a.level == cf.LEVEL_NEEDED and "notes_conflict" in rules(a),
      "a conflict with the notes needs checking")
check("What is alpha?" in a.triggers[0].items[0],
      "and names the section it conflicts with")
check(a.groups == [], "a conflicting claim is not also listed as unsettled")
a = cf.assess_check_further(result(safe=False,
                                   status="blocked_technical_conflict"), index)
check(a.level == cf.LEVEL_NEEDED and rules(a)[0] == "release_blocked",
      "a blocked release needs checking, and is reported first")

print("\n[rules] references the answer proposed")
good = NS(proposed_reference=NS(author="A", year=2020, title="T", doi="10.1/a"),
          verification=NS(crossref_verification=NS(status="verified"),
                          identity_conflict=False))
bad = NS(proposed_reference=NS(author="B", year=2021, title="U", doi=None),
         verification=NS(crossref_verification=NS(status="not_verified"),
                         identity_conflict=False))
clash = NS(proposed_reference=NS(author="C", year=2022, title="V", doi="10.1/c"),
           verification=NS(crossref_verification=NS(status="verified"),
                           identity_conflict=True))
a = cf.assess_check_further(result([tclaim("A", CONSISTENT)],
                                   references=[good, bad, clash]), index)
check(rules(a) == ["reference_not_confirmed"] and len(a.triggers[0].items) == 2,
      "an unmatched reference and an identity conflict both need checking")

print("\n[rules] nothing to check against")
a = cf.assess_check_further(result(guidance=[]), index)
check(a.level == cf.LEVEL_NEEDED and "no_guidance" in rules(a),
      "no guidance retrieved: the answer was not checked at all")
a = cf.assess_check_further(result(), index)
check(rules(a) == ["nothing_checked"] and a.level == cf.LEVEL_ADVISED,
      "guidance retrieved but no claim judged: agreement is unknown")

print("\n[rules] a lost condition that was not resolved")
lost = NS(discovered_claim=NS(claim=NS(statement="E")),
          material_restriction=NS(material_restriction_omitted=True),
          contextual_methodological_consistency=NS(
              status=NOT_EST, passages=[passage("What is alpha?")]))
a = cf.assess_check_further(result([tclaim("A", CONSISTENT)], [lost]), index)
check("condition_not_resolved" in rules(a), "is reported")
resolved = NS(discovered_claim=NS(claim=NS(statement="E")),
              material_restriction=NS(material_restriction_omitted=True),
              contextual_methodological_consistency=NS(
                  status=CONSISTENT, passages=[passage("What is alpha?")]))
a = cf.assess_check_further(result([tclaim("A", CONSISTENT)], [resolved]), index)
check("condition_not_resolved" not in rules(a),
      "and not reported once the restored condition checks out")

print("\n[rules] every 'check this' says where, or says there is nowhere")
empty = Path(tempfile.mkdtemp())
(empty / "Test Note.md").write_text(
    NOTE.split("```references")[0] + "\n##### What is beta?\n\n" + "x " * 150,
    encoding="utf-8")
bare = rn.NotesIndex(empty)
a = cf.assess_check_further(result([tclaim("A", NOT_EST)]), bare)
check("no_curated_references" in rules(a),
      "an unsettled group with no curated sources is reported as such")

print("\n[real notes] the ETI/HDI answer from 30 September")
real = rn.NotesIndex()
check(real.reference_errors == [], "every curated reference in the notes parses")
section = ("Bayesian Decision Rules and Posterior Interpretation",
           "Are all 95% credible intervals the same?")
guide = [rn.Passage(*section, "t", 0.4)]


def real_claim(statement, status):
    return NS(claim=NS(statement=statement),
              verification=NS(status="not_technically_verified"),
              methodological_consistency=NS(
                  status=status, reasons=["r"],
                  passages=[rn.Passage(*section, "t", 0.4)]))


eti_hdi = result([
    real_claim("A 95% ETI leaves 2.5% of the posterior probability in each tail.", CONSISTENT),
    real_claim("A 95% HDI contains the values with the highest posterior density.", NOT_EST),
    real_claim("For skewed unimodal posteriors the HDI is typically narrower.", NOT_EST),
    real_claim("For skewed unimodal distributions the HDI will generally be narrower.", CONSISTENT),
], guidance=guide)
a = cf.assess_check_further(eti_hdi, real)
check(a.level == cf.LEVEL_ADVISED, "advises a check rather than raising an alarm")
check(len(a.groups) == 1 and a.groups[0].heading == section[1],
      "the unsettled claims fall under the credible-interval section")
check({r.doi for r in a.groups[0].references} >= {
          "10.1080/00031305.1996.10474359", "10.21105/joss.01541"},
      "and carry that section's curated sources, Hyndman and bayestestR")
check("no_curated_references" not in rules(a),
      "so the reader is told where to check")
d = a.to_dict()
check(set(d) >= {"level", "headline", "triggers", "groups",
                 "further_reading", "rules"}, "the payload has its fields")
check(all(r["link"] for g in d["groups"] for r in g["references"]),
      "every reference shown has a link to follow")

print()
if failures:
    print(f"{failures} check(s) failed.")
    sys.exit(1)
print("All check-further checks passed.")
