#!/usr/bin/env python3
"""
Ask the reviewer notes a question, or measure them over a question set.

    python3 tests/run_reviewer_notes.py "is an R-hat of 1.01 acceptable"
    python3 tests/run_reviewer_notes.py --measure

--measure runs the 51 CrossValidated questions of section 9 of
reports/CHAT-RETRIEVAL-PROBE.md, labelled in advance as in scope (the notes
are meant to cover it) or out of scope. It reports how often a note is
returned and how the score distributions compare, which is the only check
that can distinguish coverage from ranking.

No model is loaded and nothing in app/ is touched.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reviewer_notes import NotesIndex, format_passages   # noqa: E402

# (in scope?, question). Out-of-scope questions are the ones the notes are not
# for -- principal components, clustering, degrees of freedom and so on -- and
# they are the half that matters: a corpus that answers them confidently is
# misleading a reviewer.
QUESTIONS = [
    (0, "Is normality testing essentially useless?"),
    (1, "What is the meaning of p values and t values in statistical tests?"),
    (0, "What is the benefit of breaking up a continuous predictor variable?"),
    (0, "Can a probability distribution value exceeding 1 be OK?"),
    (0, "Making sense of principal component analysis, eigenvectors and eigenvalues"),
    (0, "How to understand degrees of freedom?"),
    (0, "Difference between logit and probit models"),
    (0, "What are the shortcomings of the Mean Absolute Percentage Error MAPE?"),
    (1, "Why does a 95% confidence interval not imply a 95% chance of containing the mean?"),
    (0, "When is it ok to remove the intercept in a linear regression model?"),
    (0, "Including the interaction but not the main effects in a model"),
    (0, "Principled way of collapsing categorical variables with many levels?"),
    (0, "Crossed vs nested random effects: how do they differ?"),
    (0, "How exactly does one control for other variables?"),
    (1, "What is a complete list of the usual assumptions for linear regression?"),
    (1, "What if residuals are normally distributed, but y is not?"),
    (0, "Maximum likelihood estimation in layman terms"),
    (1, "When and why should you take the log of a distribution of numbers?"),
    (0, "How to interpret type I, type II, and type III ANOVA and MANOVA?"),
    (1, "Relation between confidence interval and testing statistical hypothesis for t-test"),
    (0, "How do you deal with nested variables in a regression model?"),
    (1, "Interpretation of log transformed predictor and or response"),
    (1, "Why do statisticians say a non-significant result means you cannot reject the null "
        "as opposed to accepting the null hypothesis?"),
    (0, "Is there a difference between controlling for and ignoring other variables in "
        "multiple regression?"),
    (0, "How to tell the difference between linear and non-linear regression models?"),
    (1, "How to interpret a QQ plot?"),
    (1, "What is an uninformative prior? Can we ever have one with truly no information?"),
    (0, "How can adding a second independent variable make the first significant?"),
    (1, "Box-Cox like transformation for independent variables?"),
    (1, "Interpreting nonlinear regression R squared"),
    (0, "What are chunk tests?"),
    (0, "What are the differences between factor analysis and principal component analysis?"),
    (1, "When to use an offset in a Poisson regression?"),
    (0, "How to select a clustering method and validate a cluster solution?"),
    (1, "What, precisely, is a confidence interval?"),
    (1, "Nested cross validation for model selection"),
    (0, "Does the sign of scores or loadings in PCA or factor analysis have a meaning?"),
    (1, "Which pseudo R squared measure should be reported for logistic regression, "
        "Cox and Snell or Nagelkerke?"),
    (0, "Interpretation of simple predictions to odds ratios in logistic regression"),
    (1, "Confidence interval for Bernoulli sampling"),
    (0, "Statistical inference when the sample is the population"),
    (1, "What is the difference between a confidence interval and a credible interval?"),
    (0, "Why is it possible to get a significant F statistic but non-significant "
        "regressor t-tests?"),
    (0, "How can a regression be significant yet all predictors be non-significant?"),
    (1, "Are large data sets inappropriate for hypothesis testing?"),
    (0, "Why do my p-values differ between logistic regression output, chi-squared test, "
        "and the confidence interval for the odds ratio?"),
    (0, "Correlations between continuous and categorical nominal variables"),
    (0, "Explaining to laypeople why bootstrapping works"),
    (1, "Alternatives to one-way ANOVA for heteroskedastic data"),
    (1, "Is there any reason to prefer the AIC or BIC over the other?"),
    (0, "Do we need a global test before post hoc tests?"),
]


def measure(index: NotesIndex) -> int:
    import statistics as st
    ins, outs = [], []
    print(f"{len(index.passages)} passages from "
          f"{len(set(p.note for p in index.passages))} notes\n")
    print(f"{'':4} {'top':>6}  citation")
    for scope, question in QUESTIONS:
        hits = index.search(question, k=1)
        top = hits[0].score if hits else 0.0
        (ins if scope else outs).append(top)
        cite = hits[0].cite() if hits else "-"
        print(f"{'IN ' if scope else 'out':4} {top:6.3f}  {cite[:72]}")
        if scope:
            pass
    print()
    for name, rows in (("in scope", ins), ("out of scope", outs)):
        print(f"  {name:13} n={len(rows):2}  median {st.median(rows):.3f}  "
              f"max {max(rows):.3f}  min {min(rows):.3f}")
    med = st.median(ins)
    above = sum(1 for s in outs if s >= med)
    print(f"\n  out-of-scope questions at or above the in-scope median: "
          f"{above} of {len(outs)}")
    print("\n  The score is reported to show the separation, not because it gates "
          "anything.\n  Passages are always displayed; see design note 2 in "
          "tests/reviewer_notes.py.")
    return 0


def main() -> int:
    index = NotesIndex()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--measure" in sys.argv:
        return measure(index)
    if not args:
        print(__doc__)
        return 0
    question = " ".join(args)
    print(f"Question: {question}\n")
    print(format_passages(index.search(question, k=3)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
