#!/usr/bin/env python3
"""
Tests for tests/design_expectations.py.

Standard-library only and self-contained: the passages below are written for
this file, not taken from any manuscript. Nothing here imports the pipeline,
so these tests cannot move the fingerprint.

    python3 tests/test_design_expectations.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import design_expectations as de  # noqa: E402

failures = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        failures.append(label)


def keys(findings, kind=None):
    return {f.key for f in findings if kind is None or f.kind == kind}


# ---------------------------------------------------------------------------
# Fixtures (synthetic)
# ---------------------------------------------------------------------------

THIN_SYNTHESIS = """
Methods

We searched SPORTDiscus for articles published between 2019 and 2023. The
search strategy combined terms for training, performance and effect size.
Records were screened by the first author against the criteria below.

Exclusion criteria were applied as follows. Articles published by MDPI were
excluded. Studies using a within-subject design were excluded. Reviews,
editorials and conference abstracts were excluded, as were articles not
published in English.

We calculated statistical power for each primary study using the non-central t
distribution, and report the median across studies.

Results

The median power was low across the sample.
"""

FULL_SYNTHESIS = """
Methods

We searched PubMed, Embase and Web of Science for articles published between
1998 and 2023. The search strategy is reported in full in the supplement. The
protocol was registered with PROSPERO.

Inclusion criteria were randomised trials of adult participants reporting a
continuous outcome. Exclusion criteria were animal studies and case reports.

Records were screened independently by two reviewers, with disagreements
resolved by a third. Risk of bias was assessed with RoB 2.

Data were analysed with a random-effects model. Heterogeneity was quantified
with I2 and tau2, and small-study effects were examined with funnel plots and
Egger's regression test.

Results

The pooled estimate was small.
"""

BAYESIAN_SYNTHESIS = """
Methods

We searched PubMed and Scopus for studies published between 1990 and 2024. The
search strategy is given in Appendix A, and the protocol was preregistered on
the Open Science Framework.

Inclusion criteria are listed in Table 1. Two authors screened all records
independently. Methodological quality was appraised with the Downs and Black
checklist.

We fitted a Bayesian hierarchical model in brms with a weakly informative
half-normal prior on the between-study standard deviation. Convergence was
assessed with R-hat and effective sample size. Funnel plots were inspected.

Results

The posterior median for the pooled effect was small.
"""

CONTAMINATED_SYNTHESIS = """
Abstract

This systematic review summarises trials of a training intervention.

Methods

We searched PubMed and CINAHL. Records were screened by two authors. Inclusion
criteria are given below. Risk of bias was assessed with RoB 2. Heterogeneity
was quantified with I2 and funnel plots were inspected. The protocol was
registered with PROSPERO.

The included studies analysed their outcomes with repeated measures ANOVA and
reported partial eta-squared. Several used a mixed-effects model fitted by
restricted maximum likelihood. Three reported Cohen's d for the group
contrast.

We computed a random-effects pooled estimate across the included trials using
REML, and report the estimate with a 95% confidence interval.

Results

The pooled estimate favoured the intervention.
"""

PRIMARY_STUDY = """
Methods

Twenty-four trained cyclists were randomly allocated to an intervention or a
control group. Participants completed a baseline test and a follow-up test
after eight weeks.

Data were analysed with a repeated measures ANOVA, with partial eta-squared
reported as the effect size. Levene's test was used to check homogeneity of
variance.

Results

There was a significant group by time interaction.

References

Smith, J. (2019). A systematic review and meta-analysis of training load and
injury. Sports Medicine. The authors searched PubMed and Embase and screened
records against eligibility criteria.
"""

SAMPLE_REPORT = """# Overall synopsis

- Something about the paper.

# Major strengths

- Strength: Transparent screening with itemised exclusion reasons.
  Evidence: "reasons for exclusion are given in Figure 1" (p. 6)
- Strength: Data and code availability supporting reproducibility.
  Evidence: "R code is available at the repository listed above" (p. 14)
- Strength: The non-central t calculation is stated explicitly.
  Evidence: Equation 2 (p. 7)

# Directly supported concerns

- Concern: Something else.
"""


# ---------------------------------------------------------------------------
# 1. Design classification
# ---------------------------------------------------------------------------

print("\nDesign classification")

v = de.classify_design(THIN_SYNTHESIS)
check("thin synthesis classified as evidence synthesis",
      v.design_class is de.DesignClass.EVIDENCE_SYNTHESIS, v.design_class.value)

v = de.classify_design(FULL_SYNTHESIS)
check("well-reported synthesis classified as evidence synthesis",
      v.design_class is de.DesignClass.EVIDENCE_SYNTHESIS, v.design_class.value)

v = de.classify_design(PRIMARY_STUDY)
check("primary study is not an evidence synthesis",
      v.design_class is not de.DesignClass.EVIDENCE_SYNTHESIS, v.design_class.value)
check("primary study recognised as a randomised trial",
      v.design_class is de.DesignClass.RANDOMISED_TRIAL, v.design_class.value)

v = de.classify_design(CONTAMINATED_SYNTHESIS)
check("evidence synthesis outranks the designs it contains",
      v.design_class is de.DesignClass.EVIDENCE_SYNTHESIS, v.design_class.value)

check("a citation in the reference list does not create a synthesis",
      "systematic review" not in de.strip_back_matter(PRIMARY_STUDY))

v = de.classify_design("The authors of a recent systematic review disagree.")
check("a passing mention is not enough to classify",
      v.design_class is de.DesignClass.UNCLASSIFIED, v.design_class.value)


# ---------------------------------------------------------------------------
# 2. Expected elements
# ---------------------------------------------------------------------------

print("\nExpected elements: thinly reported synthesis")

f = de.check_expected_elements(THIN_SYNTHESIS, de.DesignClass.EVIDENCE_SYNTHESIS)
absent = keys(f, "absent")
restricted = keys(f, "restriction")

check("single database reported as a restriction", "databases" in restricted, sorted(restricted))
check("narrow search window reported", "search_window" in restricted, sorted(restricted))
check("inclusion criteria absence caught", "inclusion_criteria" in absent, sorted(absent))
check("single-reviewer screening caught", "independent_screening" in absent, sorted(absent))
check("heterogeneity absence caught", "heterogeneity" in absent, sorted(absent))
check("publication bias absence caught", "publication_bias" in absent, sorted(absent))
check("risk of bias absence caught", "risk_of_bias" in absent, sorted(absent))
check("registration absence caught", "registration" in absent, sorted(absent))
check("publisher-level exclusion caught", "publisher_exclusion" in restricted, sorted(restricted))
check("design-level exclusion caught", "design_exclusion" in restricted, sorted(restricted))
check("language restriction caught", "language_restriction" in restricted, sorted(restricted))
check("grey literature exclusion caught", "grey_literature" in restricted, sorted(restricted))

print("\nExpected elements: well-reported synthesis (false positives)")

f = de.check_expected_elements(FULL_SYNTHESIS, de.DesignClass.EVIDENCE_SYNTHESIS)
absent = keys(f, "absent")
check("no absence findings on a well-reported synthesis", absent == set(), sorted(absent))
check("multiple databases recognised",
      any(x.key == "databases" and x.kind == "present" for x in f))
check("wide search window not flagged", "search_window" not in keys(f, "restriction"))

print("\nExpected elements: Bayesian synthesis")

f = de.check_expected_elements(BAYESIAN_SYNTHESIS, de.DesignClass.EVIDENCE_SYNTHESIS)
absent = keys(f, "absent")
check("between-study standard deviation satisfies heterogeneity",
      "heterogeneity" not in absent, sorted(absent))
check("OSF preregistration satisfies registration",
      "registration" not in absent, sorted(absent))
check("Downs and Black satisfies risk of bias",
      "risk_of_bias" not in absent, sorted(absent))

print("\nExpected elements: not applied outside the registry")

f = de.check_expected_elements(PRIMARY_STUDY, de.DesignClass.RANDOMISED_TRIAL)
check("no registry for other designs yet, so no findings", f == [], f)
check("empty findings render no section", de.format_expected_elements_section(f) == "")


# ---------------------------------------------------------------------------
# 3. Scoped method text (contamination)
# ---------------------------------------------------------------------------

print("\nScoped synthesis text")

scoped = de.scoped_synthesis_text(CONTAMINATED_SYNTHESIS)
check("scoped window found", scoped is not None)
if scoped:
    low = scoped.lower()
    check("scoped window contains the review's own analysis", "random-effects pooled" in low)
    check("scoped window excludes the results section", "favoured the intervention" not in low)
    check("scoped window is shorter than the document",
          len(scoped) < len(CONTAMINATED_SYNTHESIS), f"{len(scoped)} vs {len(CONTAMINATED_SYNTHESIS)}")

check("no analysis cue returns None rather than guessing",
      de.scoped_synthesis_text("A short note with no methods at all.") is None)


# ---------------------------------------------------------------------------
# 4. Design expectations block
# ---------------------------------------------------------------------------

print("\nDesign expectations")

block = de.get_design_expectations(de.DesignClass.EVIDENCE_SYNTHESIS)
check("evidence synthesis has an expectations block", bool(block))
check("block warns about method attribution", "whose analysis it is" in block)
check("block preserves method expectations rather than replacing them",
      "in addition to these, not instead of them" in block)
check("unregistered designs contribute nothing",
      de.get_design_expectations(de.DesignClass.CROSS_SECTIONAL) == "")


# ---------------------------------------------------------------------------
# 5. Self-report strength guard
# ---------------------------------------------------------------------------

print("\nSelf-report strength guard")

flagged = de.self_report_strengths(SAMPLE_REPORT)
matched = {term.lower() for _, _, term in flagged}
check("data and code availability flagged", len(flagged) == 1, [t for _, _, t in flagged])
check("the equation strength is not flagged",
      all("equation" not in text.lower() for _, text, _ in flagged))

annotated = de.annotate_self_report_strengths(SAMPLE_REPORT)
check("note inserted once", annotated.count("stated by the authors, not verified") == 1)
check("note follows the flagged bullet",
      annotated.index("R code is available") < annotated.index("stated by the authors"))
check("note precedes the next strength",
      annotated.index("stated by the authors") < annotated.index("non-central t"))
check("report otherwise unchanged",
      all(line in annotated for line in SAMPLE_REPORT.splitlines() if line.strip()))
check("a report with no strengths section is returned unchanged",
      de.annotate_self_report_strengths("# Concerns\n\n- Concern: x") == "# Concerns\n\n- Concern: x")


# ---------------------------------------------------------------------------
# 6. Section rendering
# ---------------------------------------------------------------------------

print("\nSection rendering")

f = de.check_expected_elements(THIN_SYNTHESIS, de.DesignClass.EVIDENCE_SYNTHESIS)
section = de.format_expected_elements_section(f)
check("section has the heading", section.startswith("# Expected reporting elements"))
check("every rendered line states what was searched",
      all("Searched:" in b for b in section.split("\n- ")[1:]))
check("section warns it is a keyword search", "keyword search, not a" in section)
check("present findings are not rendered", "Databases named" not in section)

# ---------------------------------------------------------------------------
# 7. Regressions found on a real manuscript
# ---------------------------------------------------------------------------

print("\nRegressions from a real manuscript")

# Every one of these was a wrong answer on RJSP-2025-0796 before it was fixed.

REAL_SHAPED = (
    "Methods\n"
    "We searched PubMed for meta-analyses. All identified references were imported "
    "into the online Rayyan application. Studies were screened by the author.\n"
    + ("Filler sentence to push the body past the halfway point. " * 60) +
    "\nArticles published in multidisciplinary digital publishing institute (mdpi) "
    "journals were excluded at this stage. In the context of this study, within "
    "-subject designs were excluded to ensure consistency. Multiple meta -analyses "
    "were only included if they used different study samples.\n"
    "This problem is exacerbated by publication bias, where significant findings "
    "are preferably published. Effect sizes may show considerable heterogeneity.\n"
    "All data relevant to the study are uploaded to OSF at https://osf.io/xxxxx/.\n"
    "References\n"
    "Abt, G. (2020). Power, precision and sample size. Journal of Sports Sciences.\n"
    "Sutton, A. J. (2009). Publication bias. Handbook of Research Synthesis.\n"
)

body = de.strip_back_matter(REAL_SHAPED)
check("a body sentence about references does not truncate the document",
      "within-subject" in body, f"kept {len(body)} of {len(REAL_SHAPED)}")
check("the reference list is still removed",
      "handbook of research synthesis" not in body)
check("split hyphens are closed up", "meta-analyses" in body and "meta -analyses" not in body)

f = de.check_expected_elements(REAL_SHAPED, de.DesignClass.EVIDENCE_SYNTHESIS)
absent, restricted = keys(f, "absent"), keys(f, "restriction")

check("publisher exclusion found past the halfway point",
      "publisher_exclusion" in restricted, sorted(restricted))
check("a hyphen split by extraction does not hide a design exclusion",
      "design_exclusion" in restricted, sorted(restricted))
check("a rule about overlapping studies is not an inclusion criterion",
      "inclusion_criteria" in absent, sorted(absent))
check("publication bias in discussion is not an assessment of it",
      "publication_bias" in absent, sorted(absent))
check("heterogeneity as a word is not an assessment of it",
      "heterogeneity" in absent, sorted(absent))
check("an OSF data link is not a registered protocol",
      "registration" in absent, sorted(absent))
check("a single database is still reported", "databases" in restricted, sorted(restricted))

check("preregistered is matched despite the missing stem",
      "registration" not in keys(
          de.check_expected_elements(
              "We searched PubMed and Scopus. The protocol was preregistered.",
              de.DesignClass.EVIDENCE_SYNTHESIS), "absent"))


print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    sys.exit(1)
print("All checks passed.")
