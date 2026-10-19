#!/usr/bin/env python3
"""
What the academic reader is told about the evidence behind an answer.

    python3 tests/test_academic_check_further.py

Covers the deterministic routing of unsettled points to curated literature,
the use of the answer's own sentence wherever one exists, the five reader-
facing states, and the separation of what the reader sees from the technical
diagnostics. The layer makes no model call, so every case is deterministic.
"""
import json
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
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


# A notes folder with three sections: one curated, one curated only through
# its note's list, and a note with nothing curated at all.
CURATED = """# Curated Note

##### Section A?

Section A text, long enough to stand as its own section rather than be folded
into the section before it by the chunker, which needs a couple of hundred
characters of body text before it will treat a section as standing alone.

```references
- cite: Smith, J. (2020). On A. Journal, 1, 1-2.
  doi: 10.1000/a
  supports: Topic A.
  short: topic A in brief
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open
  checked: 2026-10-01, Crossref
```

##### Section B?

Section B text, also long enough to be kept as a section in its own right by
the chunker rather than being merged into the previous section, so that a
passage can carry this heading without anything else attached to it.

#### References

```references
- cite: Jones, K., & Brown, L. (2019). General. Journal, 2, 3-4.
  doi: 10.1000/note
  supports: The whole topic.
  checked: 2026-10-01, Crossref
```
"""

UNCURATED = """# Bare Note

##### Unrelated misconception?

A section with no curated sources at all, long enough to be a passage of its
own, which can still rank highly for a claim through word overlap alone and
must not become a reading recommendation on that basis.
"""

tmp = Path(tempfile.mkdtemp())
(tmp / "Curated Note.md").write_text(CURATED, encoding="utf-8")
(tmp / "Bare Note.md").write_text(UNCURATED, encoding="utf-8")
index = rn.NotesIndex(tmp)

A = ("Curated Note", "Section A?")
B = ("Curated Note", "Section B?")
BARE = ("Bare Note", "Unrelated misconception?")


def P(section, score=0.5):
    return rn.Passage(section[0], section[1], "text", score)


def tclaim(statement, status, passages, reasons=("judge reason",)):
    claim = NS(statement=statement)
    return NS(claim=claim, verification=NS(status="not_technically_verified"),
              methodological_consistency=NS(status=status, passages=passages,
                                            reasons=list(reasons)))


def context(statement, sentence, status, passages, omitted=False, claim=None):
    return NS(
        discovered_claim=NS(claim=claim or NS(statement=statement)),
        source_context=NS(source_sentence=sentence),
        material_restriction=NS(material_restriction_omitted=omitted),
        contextual_methodological_consistency=(
            None if status is None else
            NS(status=status, passages=passages, reasons=["context reason"])),
    )


def result(technical=(), contexts=(), references=(), guidance=(A,),
           status="release_allowed_with_unverified_claims", linked=None):
    return NS(
        release=NS(safe_to_present=not status.startswith(("blocked", "checking")),
                   status=status, reasons=["reason"]),
        technical_claims=list(technical),
        discovered_claim_assessments=list(contexts),
        references=list(references),
        # A source claim points to each reference by position; by default
        # every reference is linked, as a cited reference is.
        source_claims=[NS(claim=NS(claim="c", reference_index=i))
                       for i in (range(len(references)) if linked is None else linked)],
        local_guidance=NS(passages=[P(s, 0.4) for s in guidance]),
    )


def run(r):
    return cf.assess_check_further(r, index).to_dict()


def user_facing(d):
    """Everything the reader can see at levels one and two."""
    return json.dumps({k: v for k, v in d.items() if k != "diagnostics"})


# ===========================================================================
print("\n[routing] a group needs a question section, curated sources and a judgement")
d = run(result([tclaim("X", NOT_EST, [P(A)])], guidance=(A,)))
check([g["heading"] for g in d["further_reading"]] == ["Section A?"],
      "a point judged against a curated question section is routed there")
check([r["doi"] for r in d["further_reading"][0]["references"]] == ["10.1000/a"],
      "with that section's own references")

d = run(result([tclaim("X", NOT_EST, [P(BARE, 0.9)])], guidance=(A, BARE)))
check(d["further_reading"] == [],
      "a question section with no curated sources produces no group")
check(d["diagnostics"]["unrouted"][0]["nearest_section"] == "Bare Note - Unrelated misconception?",
      "the unrouted point is kept in the diagnostics with its nearest section")

d = run(result([tclaim("X", NOT_EST, [P(A)])], guidance=(BARE,)))
check(d["further_reading"] == [],
      "a curated section not retrieved for the question produces no group")

d = run(result([tclaim("X", NOT_EST, [P(BARE, 0.9), P(A, 0.2)])], guidance=(A, BARE)))
check([g["heading"] for g in d["further_reading"]] == ["Section A?"],
      "a higher-ranking source-less match does not win over a qualifying section")

d = run(result([tclaim("X", NOT_EST, [])], guidance=(A,)))
check(d["further_reading"] == [] and len(d["diagnostics"]["unrouted"]) == 1,
      "a point judged against nothing is not routed")

d = run(result([tclaim("X", NOT_EST, [P(B)])], guidance=(B,)))
check([r["doi"] for r in d["further_reading"][0]["references"]] == ["10.1000/note"],
      "a section without its own list qualifies through its note's list")

# ===========================================================================
print("\n[what the answer said] points use the answer's own sentence")
c = context("Atomic X without its condition",
            "For skewed posteriors, X holds.", NOT_EST, [P(A)])
d = run(result(contexts=[c]))
pts = d["further_reading"][0]["points"]
check(pts == [{"text": "For skewed posteriors, X holds.", "kind": "answer_sentence"}],
      "a contextual point is shown as the verified source sentence")
check("Atomic X without its condition" not in user_facing(d),
      "the stripped atomic claim appears nowhere the reader can see")

shared = NS(statement="Y holds")
d2 = run(result([NS(claim=shared, verification=NS(status="x"),
                    methodological_consistency=NS(status=NOT_EST, passages=[P(A)], reasons=[]))],
                contexts=[context("Y holds", "In the answer, Y holds.", None, [], claim=shared)]))
check(d2["further_reading"][0]["points"][0] ==
      {"text": "In the answer, Y holds.", "kind": "answer_sentence"},
      "a structured claim located in the answer is shown as that sentence")

d = run(result([tclaim("Z is so", NOT_EST, [P(A)])]))
check(d["further_reading"][0]["points"][0] == {"text": "Z is so", "kind": "summarised_point"},
      "a structured claim with no located sentence is labelled as summarised")

d = run(result(contexts=[
    context("First fragment", "One sentence with two parts.", NOT_EST, [P(A)]),
    context("Second fragment", "One sentence with two parts.", NOT_EST, [P(A)])]))
check(len(d["further_reading"][0]["points"]) == 1,
      "fragments of one sentence become one point")

lost = context("Narrower, unconditionally",
               "For skewed unimodal posteriors, the HDI tends to be narrower.",
               NOT_EST, [P(A)], omitted=True)
d = run(result(contexts=[lost]))
lc = d["diagnostics"]["lost_conditions"][0]
check(lc["answer_sentence"].startswith("For skewed unimodal posteriors")
      and lc["atomic_claim"] == "Narrower, unconditionally",
      "a lost condition is diagnosed with the answer's sentence beside the atomic claim")
check("Narrower, unconditionally" not in user_facing(d)
      and "condition" not in user_facing(d).lower(),
      "and is not presented to the reader at all")

# ===========================================================================
print("\n[states] five states, each worded for the reader")
d = run(result([tclaim("X", CONSISTENT, [P(A)])]))
check(d["state"] == "no_specific_concern" and d["secondary"] == "",
      "everything consistent: no specific concern, nothing more to say")

d = run(result([tclaim("X", CONSISTENT, [P(A)]), tclaim("W", NOT_EST, [P(A)])]))
check(d["state"] == "further_reading"
      and d["summary"].startswith("Parts of this answer align with the local methodological guidance"),
      "some consistent, some routed: parts align, some details go beyond")
check(d["source_count"] == 1, "the number of sources, not of claims, is offered")

d = run(result([tclaim("W", NOT_EST, [P(A)])]))
check(d["state"] == "further_reading"
      and d["summary"].startswith("Some details of this answer go beyond"),
      "nothing consistent: does not claim that parts align")

d = run(result([tclaim("X", CONSISTENT, [P(A)]), tclaim("W", NOT_EST, [P(BARE)])],
               guidance=(A, BARE)))
check(d["state"] == "no_specific_concern"
      and "no curated sources are available" in d["secondary"],
      "unsettled but unroutable: no concern, and says no sources exist yet")

d = run(result(contexts=[context("C", "The answer's sentence about C.", CONFLICT, [P(A)])],
               status="release_allowed_with_methodological_conflict"))
check(d["state"] == "worth_checking", "a conflict with the guidance is worth checking")
check(d["summary"] == cf.METHODOLOGICAL_CONFLICT_SUMMARY,
      "and says the guidance appears to say something different")
check(d["worth_checking"][0]["text"] == "The answer's sentence about C."
      and d["worth_checking"][0]["topic"] == "Section A?",
      "naming the answer's sentence and the topic")
check("context reason" not in user_facing(d)
      and d["diagnostics"]["conflicts"][0]["reasons"] == ["context reason"],
      "the judge's own reason stays in the diagnostics")

d = run(result(status="blocked_technical_conflict"))
check(d["state"] == "worth_checking" and "technical statement" in d["summary"],
      "a blocked technical conflict is worth checking, in its own words")

d = run(result([tclaim("X", NOT_EST, [P(A)])], status="checking_incomplete"))
check(d["state"] == "incomplete" and d["title"] == "Evidence check incomplete",
      "incomplete checking is not presented as a concern about the answer")
check(d["worth_checking"] == [], "and raises no worth-checking item")
check(d["secondary"] == cf.INCOMPLETE_SECONDARY
      and "does not mean the answer is wrong" in d["secondary"],
      "it says once that incomplete checking does not mean the answer is wrong")
check(cf.incomplete_assessment("boom")["secondary"] == cf.INCOMPLETE_SECONDARY,
      "a failed assessment says the same")

d = run(result(contexts=[context("C", "The answer's sentence about C.", CONFLICT, [P(A)])],
               status="checking_incomplete"))
check(d["state"] == "worth_checking"
      and d["worth_checking"][0]["text"] == "The answer's sentence about C.",
      "a recorded conflict is still reported when other checking was incomplete")
check(d["secondary"] == cf.INCOMPLETE_WITH_CONCERN_SECONDARY,
      "and the reader is told the check was incomplete, so it may not be the only point")
check("blocked_methodological_conflict" not in cf._BLOCKED_SUMMARIES,
      "a methodological conflict is not among the statuses that withhold the answer")

d = run(result(guidance=()))
check(d["state"] == "outside_guidance" and "not covered" in d["summary"],
      "nothing retrieved: outside the local guidance, not covered")

d = run(result(guidance=(A,)))
check(d["state"] == "outside_guidance" and "has not been compared" in d["summary"],
      "retrieved but nothing judged: outside, and says it was not compared")

# ===========================================================================
print("\n[failed judgements] a judgement that could not be completed is not a gap")


def failed_tclaim(statement, passages, error="ClaimAssessorOutputError: synthetic"):
    """A judgement the model could not complete, as the pipeline records it."""
    item = tclaim(statement, NOT_EST, passages,
                  reasons=("The methodological check could not be completed for this claim.",))
    item.methodological_consistency.assessment_error = error
    return item


check(not hasattr(tclaim("X", NOT_EST, [P(A)]).methodological_consistency,
                  "assessment_error"),
      "the existing test doubles carry no assessment_error and still route as before")

d = run(result([failed_tclaim("X", [P(A)])]))
check(d["state"] == "incomplete" and d["summary"] == cf.INCOMPLETE_SUMMARY
      and d["secondary"] == cf.INCOMPLETE_SECONDARY,
      "a failed judgement makes the evidence check incomplete, in the existing words")
check(d["further_reading"] == [] and d["worth_checking"] == [],
      "it offers no further reading and raises no worth-checking item")
counts = d["diagnostics"]["counts"]
check(counts["failed_methodology_checks"] == 1 and counts["not_established"] == 0
      and counts["unsettled_statements"] == 0,
      "diagnostics count it as a failed check, not as 'not established'")
failed_rows = d["diagnostics"]["failed_methodology_checks"]
check(len(failed_rows) == 1 and failed_rows[0]["statement"] == "X"
      and failed_rows[0]["assessment_error"] == "ClaimAssessorOutputError: synthetic",
      "diagnostics name the statement and keep its assessment_error")
check("ClaimAssessorOutputError" not in user_facing(d),
      "the error text stays out of what the reader sees")

d = run(result([failed_tclaim("X", [P(A)]), tclaim("W", NOT_EST, [P(A)])]))
check(d["state"] == "incomplete",
      "failed and valid 'not established' together: the check is incomplete")
points = [pt["text"] for g in d["further_reading"] for pt in g["points"]]
check([g["heading"] for g in d["further_reading"]] == ["Section A?"]
      and points == ["W"],
      "further reading is still offered, for the valid point only")
check(d["diagnostics"]["counts"]["not_established"] == 1
      and d["diagnostics"]["counts"]["failed_methodology_checks"] == 1,
      "each is counted in its own place")

d = run(result([failed_tclaim("X", [P(A)])],
               contexts=[context("C", "The answer's sentence about C.", CONFLICT, [P(A)])],
               status="release_allowed_with_methodological_conflict"))
check(d["state"] == "worth_checking"
      and d["secondary"] == cf.INCOMPLETE_WITH_CONCERN_SECONDARY,
      "a conflict stays worth checking, with the existing incomplete-checking secondary")
check([w["text"] for w in d["worth_checking"]] == ["The answer's sentence about C."],
      "the failed point is not presented as a point worth checking")

check(cf.RULES_VERSION == "8" and d["rules_version"] == "8",
      "rules version 8 distinguishes citation identity outcomes")

# ===========================================================================
print("\n[failed checks] dropped-condition and source checks that could not be completed")

ERROR = "MaterialRestrictionOutputError: synthetic"
failed_context = context("Atomic X", "For skewed posteriors, X holds.", None, [P(A)])
failed_context.material_restriction = NS(material_restriction_omitted=None,
                                         assessment_error=ERROR)
d = run(result([tclaim("X", CONSISTENT, [P(A)])], contexts=[failed_context]))
check(d["state"] == "incomplete" and d["summary"] == cf.INCOMPLETE_SUMMARY
      and d["secondary"] == cf.INCOMPLETE_SECONDARY,
      "a context check that could not be completed makes the evidence check incomplete")
check(d["diagnostics"]["lost_conditions"] == []
      and d["diagnostics"]["counts"]["failed_restriction_checks"] == 1
      and d["diagnostics"]["failed_restriction_checks"][0]["assessment_error"] == ERROR
      and d["diagnostics"]["failed_restriction_checks"][0]["answer_sentence"]
      == "For skewed posteriors, X holds.",
      "it is not a lost condition; diagnostics name the sentence and keep the error")
check("MaterialRestrictionOutputError" not in user_facing(d),
      "the error stays out of what the reader sees")

SOURCE_ERROR = "ClaimAssessmentOutputError: Assessor output contains an invalid status."
r = result([tclaim("X", CONSISTENT, [P(A)])],
           references=[NS(proposed_reference=NS(author="Rubin, D. B.", year=1987,
                                                title="Multiple Imputation", doi=None),
                          verification=NS(identity_conflict=False,
                                          crossref_verification=NS(status="verified")))])
r.source_claims[0].claim_assessment = None
r.source_claims[0].claim_assessment_error = SOURCE_ERROR
r.source_claims[0].claim_location = NS(evidence=[NS(page_number=4), NS(page_number=4)])
d = run(r)
check(d["state"] == "incomplete"
      and d["secondary"] == cf.INCOMPLETE_SECONDARY + " " + cf.SOURCE_INCOMPLETE_NOTE,
      "a source assessment that could not be completed: incomplete, saying a source "
      "could not be fully checked")
row = d["diagnostics"]["failed_source_assessments"][0]
check(d["diagnostics"]["counts"]["failed_source_assessments"] == 1
      and row["assessment_error"] == SOURCE_ERROR and row["located_passages"] == 2
      and row["pages"] == [4] and row["reference"].startswith("Rubin, D. B. (1987)"),
      "diagnostics keep the claim, its reference, the located evidence and the error")
check("ClaimAssessmentOutputError" not in user_facing(d) and d["citation_notice"] is None,
      "no error text for the reader, and no citation notice for a verified reference")

d = run(result(
    contexts=[context("C", "The answer's sentence about C.", CONFLICT, [P(A)])],
    status="release_allowed_with_methodological_conflict"))
check(d["secondary"] == "", "control: a conflict alone has no incomplete secondary")
r2 = result(contexts=[context("C", "The answer's sentence about C.", CONFLICT, [P(A)]),
                      failed_context],
            status="release_allowed_with_methodological_conflict")
d = run(r2)
check(d["state"] == "worth_checking"
      and d["secondary"] == cf.INCOMPLETE_WITH_CONCERN_SECONDARY,
      "a genuine concern stays primary, with the incomplete secondary")

check(not hasattr(context("Y", "S.", NOT_EST, [P(A)]).material_restriction,
                  "assessment_error")
      and run(result(contexts=[context("Y", "S.", NOT_EST, [P(A)], omitted=True)]))
      ["diagnostics"]["counts"]["failed_restriction_checks"] == 0,
      "doubles without assessment_error remain compatible")

print("\n[incomplete wording] accurate for any check")
for text in (cf.INCOMPLETE_SUMMARY, cf.INCOMPLETE_SECONDARY):
    check("methodological" not in text and "guidance" not in text,
          f"no mechanism-specific wording: {text!r}")
check(cf.INCOMPLETE_SUMMARY == "Some of the checks on this answer could not be completed."
      and cf.INCOMPLETE_SECONDARY == ("This does not mean the answer is wrong, but some "
                                      "points could not be fully checked."),
      "the generalised incomplete wording")

# ===========================================================================
print("\n[citations] an unmatched citation has its own notice")
bad = NS(proposed_reference=NS(author="Lakens, Scheel, Ismar", year=2018,
                               title="Justify your alpha", doi=None),
         verification=NS(crossref_verification=NS(status="not_verified"),
                         identity_conflict=False))
clash = NS(proposed_reference=NS(author="C", year=2022, title="V", doi="10.1/c"),
           verification=NS(crossref_verification=NS(status="verified"),
                           identity_conflict=True))
d = run(result([tclaim("X", CONSISTENT, [P(A)])], references=[bad]))
check(d["state"] == "no_specific_concern" and d["citation_notice"] is not None,
      "the notice stands alone and does not change the evidence state")
check("could not be matched to a published record" in d["citation_notice"]["message"],
      "an unmatched citation says so")
check(d["citation_notice"]["message"].startswith(
          "A source given in support of this answer could not be matched")
      and "cited in this answer" not in d["citation_notice"]["message"],
      "it says the source was given in support of the answer, not cited in it")
d = run(result([tclaim("X", CONSISTENT, [P(A)])], references=[clash]))
check(d["citation_notice"]["message"].startswith(
          "The details of a source given in support of this answer conflict "
          "with the published record."),
      "a citation whose details conflict says that instead")

# ===========================================================================
print("\n[reader-facing wording] no maintainer language, no counts")
samples = [
    run(result([tclaim("X", CONSISTENT, [P(A)])])),
    run(result([tclaim("X", CONSISTENT, [P(A)]), tclaim("W", NOT_EST, [P(A)])])),
    run(result([tclaim("W", NOT_EST, [P(BARE)])], guidance=(A, BARE))),
    run(result(status="blocked_technical_conflict")),
    run(result(status="checking_incomplete")),
    run(result(guidance=())),
    run(result(guidance=(A,))),
]
texts = []
for s in samples:
    texts += [s["title"], s["summary"], s["secondary"], s["about"]]
    texts += [w["explanation"] for w in s["worth_checking"]]
check(not any("your" in t.lower() for t in texts),
      "nothing is addressed to the owner of the guidance")
check(not any(ch.isdigit() for t in texts for ch in t),
      "no counts in any title, summary or explanation")
check(set(samples[0]) == set(cf.incomplete_assessment("boom")),
      "a failed assessment has the same shape as a completed one")

# ===========================================================================
print("\n[relevant literature] completed checking, separate from targeted reading")
d = run(result([tclaim("X", CONSISTENT, [P(A)])], guidance=(A, B)))
check(d["state"] == cf.STATE_NO_CONCERN
      and [g["heading"] for g in d["relevant_literature"]] == [A[1]],
      "consistent completed judgement exposes only the section actually used")
check(d["source_count"] == 0 and d["relevant_literature_count"] == 1,
      "relevant literature does not change targeted source_count")
check(d["relevant_literature"][0]["points"] == [],
      "general literature is not presented as an unsettled point")
check(run(result(guidance=(A,)))["relevant_literature"] == [],
      "question retrieval alone supplies no relevant literature")
check(run(result([tclaim("X", CONSISTENT, [P(B)])], guidance=(A,)))["relevant_literature"] == [],
      "completed checking outside question sections does not qualify")
check(run(result([tclaim("X", CONSISTENT, [P(BARE)])], guidance=(BARE,)))["relevant_literature"] == [],
      "sections without curated references do not qualify")
failed_claim = tclaim("Failed", NOT_EST, [P(B)])
failed_claim.methodological_consistency.assessment_error = "Malformed output"
d = run(result([failed_claim], guidance=(B,)))
check(d["state"] == cf.STATE_INCOMPLETE and not d["relevant_literature"],
      "failed methodology is not completed checking")
d = run(result([tclaim("X", CONSISTENT, [P(A)]), failed_claim], guidance=(A, B)))
check(d["state"] == cf.STATE_INCOMPLETE
      and [g["heading"] for g in d["relevant_literature"]] == [A[1]],
      "unrelated failure preserves literature from completed checking")
for release in ("checking_incomplete", "blocked_technical_conflict"):
    d = run(result([tclaim("X", CONSISTENT, [P(A)])], status=release))
    check(d["relevant_literature_count"] == 1,
          f"completed literature survives release state {release}")
d = run(result([tclaim("X", NOT_EST, [P(A)]),
                tclaim("Y", CONSISTENT, [P(A), P(B)])], guidance=(A, B)))
check(d["state"] == cf.STATE_FURTHER_READING
      and [g["heading"] for g in d["further_reading"]] == [A[1]]
      and [g["heading"] for g in d["relevant_literature"]] == [B[1]]
      and d["source_count"] == 1 and d["relevant_literature_count"] == 1,
      "targeted reading wins for its section while other relevant literature remains")
# Both B and this other section inherit the same note-level reference.
C = (A[0], "Another section using note-level references")
d = run(result([tclaim("X", CONSISTENT, [P(B), P(A), P(B), P(C)]),
                tclaim("Y", CONSISTENT, [P(A)])], guidance=(A, B, C)))
check([g["heading"] for g in d["relevant_literature"]] == [B[1], A[1]]
      and d["relevant_literature_count"] == 2,
      "sections and references deduplicate in judgement/passage first-occurrence order")
check([r["doi"] for g in d["relevant_literature"] for r in g["references"]]
      == ["10.1000/note", "10.1000/a"],
      "note-level fallback uses existing reference lookup and identity semantics")
d = run(result(contexts=[context("X", "Sentence X.", CONSISTENT, [P(A)])]))
check(d["relevant_literature_count"] == 1,
      "completed contextual judgements qualify too")
standalone = tclaim("Restricted", NOT_EST, [P(A)])
d = run(result([standalone], contexts=[context(
    "Restricted", "Restricted in context.", CONSISTENT, [P(B)],
    omitted=True, claim=standalone.claim)], guidance=(A, B)))
check(not d["diagnostics"]["methodology_reconciliation"][0]["retain_standalone"]
      and [g["heading"] for g in d["relevant_literature"]] == [A[1], B[1]]
      and d["further_reading"] == [],
      "completed superseded judgement still used guidance, without restoring its verdict")
empty = cf.incomplete_assessment("boom")
check(empty["relevant_literature"] == [] and empty["relevant_literature_count"] == 0
      and set(empty) == set(d), "incomplete fallback preserves the expanded public shape")

print("\n[real notes] the ETI/HDI answer of 30 September")
real = rn.NotesIndex()
check(real.reference_errors == [], "every curated reference in the notes parses")
CI = ("Bayesian Decision Rules and Posterior Interpretation",
      "Are all 95% credible intervals the same?")
LEE = next((p.note, p.heading) for p in real.passages
           if p.heading.startswith('"The credible interval is just a confidence interval'))
eti = result(
    [tclaim("A 95% ETI leaves 2.5% in each tail.", CONSISTENT, [P(CI)])],
    contexts=[
        context("Both intervals contain 95% of the posterior probability.",
                "Both intervals contain 95% of the posterior probability, but they "
                "select different subsets of the parameter space to achieve this coverage.",
                NOT_EST, [P(LEE, 0.6), P(CI, 0.3)]),
        context("The HDI tends to be narrower than the ETI.",
                "The HDI tends to be narrower because it excludes low-density tails "
                "more aggressively than the ETI.", NOT_EST, [P(CI, 0.5)], omitted=True),
        context("They coincide only when symmetric.",
                "The HDI and ETI coincide only when the posterior distribution is "
                "symmetric and unimodal.", NOT_EST, [P(CI, 0.5)]),
    ],
    guidance=(CI, LEE))
d = cf.assess_check_further(eti, real).to_dict()
check(d["state"] == "further_reading", "the answer offers further reading")
check([g["heading"] for g in d["further_reading"]] == [CI[1]],
      "one topic only: credible intervals, and no Lee & Yin group")
check(d["source_count"] == 4 and {r["author_year"] for r in d["further_reading"][0]["references"]}
      == {"Hyndman (1996)", "Kruschke (2015)", "Makowski et al. (2019)", "bayestestR documentation"},
      "with the four curated sources in compact form")
check(all(p["kind"] == "answer_sentence" for p in d["further_reading"][0]["points"]),
      "every point shown is a sentence the answer actually wrote")
access = {r["author_year"]: r["access_label"] for r in d["further_reading"][0]["references"]}
check(access["Hyndman (1996)"] == "May need institutional access"
      and access["Makowski et al. (2019)"] == "Free to read"
      and access["Kruschke (2015)"] == "",
      "access is shown where checked, and not invented where it was not")

print()
if failures:
    print(f"{failures} check(s) failed.")
    sys.exit(1)
print("All check-further checks passed.")
