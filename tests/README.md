# Tests

`test_extraction.py` guards the table extraction against the regression that
prompted it: the coefficient tables of a journal article were invisible to the
pipeline, because pdfplumber's default strategy needs ruled lines in both
directions and most journal tables are set booktabs-style with horizontal
rules only.

It needs the paper it was written against:

    cd ~/local-llm/qwen35-review
    cp /path/to/Myers_et_al_2020_swimming.pdf tests/paper.pdf
    .venv/bin/python tests/test_extraction.py

To check a different paper, point `PDF` at it and update the page numbers and
the expected values near the top. The useful checks to keep are: the results
tables are found, no narrative page is mistaken for a table, and the
coefficients survive intact rather than being split across cells.

---

`design_expectations.py` adds a study-design axis alongside the existing method
classification, and a registry of the elements a study of that design is
normally expected to report. It exists because the pipeline scrutinises what a
manuscript says about itself but has no way to raise what a manuscript omits:
every concern must carry a verbatim quotation, and an absence has none.

The two axes are orthogonal and neither replaces the other:

    Design:  evidence_synthesis        (what kind of study this is)
    Method:  frequentist_* | bayesian_*  (what the analysis does)

A meta-analysis may pool with REML or with a Bayesian hierarchical model. Both
are evidence syntheses, and the existing method expectations remain correct for
each.

The module is standalone. It imports nothing from `review_pipeline.py`,
`server.py` or `llm_backend.py`, so it cannot move the pipeline fingerprint and
cannot alter any report, and it needs only the standard library. Integration is
a later, separate step, deliberately deferred until the current evaluation set
is finished.

Absence checks fail in the opposite direction from the pipeline's presence
checks: a missed synonym produces a false accusation rather than a missed catch.
Every finding therefore prints the terms that were searched for, so a wrong line
can be dismissed in seconds, and the patterns are deliberately generous.

    python3 tests/test_design_expectations.py         # 42 checks, synthetic text
    python3 tests/run_design_expectations.py          # dry run over inputs/
    python3 tests/run_design_expectations.py --quiet  # one line per paper

The dry run loads no model and produces no report. On a corpus of primary
studies every evidence-synthesis classification is a false positive, which is
what makes it a useful check: the registry must stay silent on papers it does
not apply to.
