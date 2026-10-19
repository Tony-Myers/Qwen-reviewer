#!/usr/bin/env python3
"""
Does StatsRAG's corpus retrieval earn a place in the review chat?

A measurement, not an integration. Nothing in app/ is touched and the pipeline
fingerprint does not move. The question asked here is narrow: when a reviewer
is reading a completed review and asks a question, or when the model answers,
would retrieving passages from the local methods corpus help?

Three designs are compared.

  Arm A  retrieval over the whole index, on the text itself
  Arm B  retrieval restricted to Interpretation_guardrails, on the text itself
  Arm C  one curated query per deterministic rule, fired only when that rule
         matches -- retrieval as citation lookup rather than as a detector
  Arm D  --lookup: realistic reviewer questions, judged on whether the top
         passages answer the question. This is the case the chat actually
         serves: the reviewer supplies the topic and nothing is being judged.

Usage (StatsRAG must have a built index):

    python3 tests/probe_guardrail_retrieval.py \
        --repo ~/Desktop/statsrag_docker_repo_v3_15

It loads statsrag.indexing directly and makes no network call.
"""

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

GUARDRAILS = ["Interpretation_guardrails"]

# Twelve items: six carrying a known misinterpretation, six correct or merely
# factual. The clean half is the important half -- a retrieval layer that
# attaches cautionary passages to a correct statement is worse than one that
# says nothing.
ITEMS = [
    ("E1", "error", "The 95% confidence interval was 0.40 to 1.25, so there is a 95% "
                    "probability that the true effect lies in that range."),
    ("E2", "error", "The p-value of 0.03 means there is a 3% probability that the null "
                    "hypothesis is true."),
    ("E3", "error", "The effect was non-significant (p = 0.21), so we can conclude the "
                    "intervention has no effect."),
    ("E4", "error", "The model with the highest WAIC was selected as the best fitting model."),
    ("E5", "error", "Exercise dose causes improvements in executive function, as this "
                    "meta-analysis shows."),
    ("E6", "error", "Observed power was 0.45, which confirms that the non-significant "
                    "result reflects a true null."),
    ("C1", "clean", "What priors did the authors place on the between-study standard deviation?"),
    ("C2", "clean", "Is a DIC difference of three points meaningful for choosing between "
                    "these models?"),
    ("C3", "clean", "The authors report an SMD of 0.82 with a 95% credible interval of "
                    "0.41 to 1.25."),
    ("C4", "clean", "Should the review have assessed publication bias with a funnel plot?"),
    ("C5", "clean", "Does treating multi-arm studies as independent inflate precision at "
                    "the control node?"),
    ("C6", "clean", "The authors log-transformed the outcome and back-transformed the "
                    "fitted predictions."),
]

# Arm C. Each entry is a deterministic rule, the pattern that fires it, and the
# single curated query used to fetch a citation for it. The query is written
# once and checked once; it never varies with the text, so it cannot drift.
RULES = [
    ("CI_AS_PROBABILITY",
     r"confidence interval.{0,80}(probability|chance) that the true"
     r"|(probability|chance) that the true.{0,40}(lies|falls) (with)?in.{0,40}confidence",
     "a confidence interval is not a probability statement about the parameter"),
    ("P_AS_NULL_PROBABILITY",
     r"p[- ]?value.{0,60}probability that the null|probability that the null.{0,40}is true",
     "the p value is not the probability that the null hypothesis is true"),
    ("NONSIG_AS_NO_EFFECT",
     r"non[- ]?significant.{0,80}(no effect|no difference|no association)"
     r"|p\s*[=>]\s*0?\.\d+.{0,60}(no effect|no difference)",
     "a nonsignificant result does not mean there is no effect absence of evidence"),
    ("IC_DIRECTION",
     r"(highest|largest)\s+(waic|looic|dic|aic|bic)|(lowest|smallest)\s+elpd",
     "information criterion lower value indicates better predictive fit deviance"),
    ("CAUSAL_WITHOUT_DESIGN",
     r"\b(causes?|caused by|leads to|results in)\b",
     "association does not imply causation observational study causal inference"),
    ("POWER_MISREAD",
     r"observed power|post[- ]?hoc power|power was 0?\.\d+.{0,60}(confirms|shows|means)",
     "observed power after the study is not evidence for the null hypothesis"),
    ("SIG_AS_IMPORTANT",
     r"significant.{0,50}(therefore|so).{0,40}(important|meaningful|clinically)",
     "statistical significance does not mean the effect is scientifically important"),
]


# Arm D. Questions a reviewer might ask in chat after reading a report on a
# Bayesian manuscript, plus three deliberately out of scope (X) to see whether
# an unanswerable question is distinguishable from an answerable one.
QUESTIONS = [
    ("Q1", "How should prior distributions be reported in a Bayesian analysis?"),
    ("Q2", "What convergence diagnostics should a Bayesian analysis report?"),
    ("Q3", "Is an R-hat value of 1.01 acceptable?"),
    ("Q4", "What is a prior predictive check and why should it be done?"),
    ("Q5", "Should I ask the authors for a prior sensitivity analysis?"),
    ("Q6", "How should a Bayes factor be interpreted, what does BF10 of 3 mean?"),
    ("Q7", "What is the difference between a credible interval and a confidence interval?"),
    ("Q8", "Is it acceptable to report only the posterior mean without an interval?"),
    ("Q9", "What is effective sample size and how large should it be?"),
    ("Q10", "What should be reported when using WAIC or LOO for model comparison?"),
    ("Q11", "Should the authors report the number of chains and iterations?"),
    ("Q12", "How should posterior predictive checks be reported?"),
    ("Q13", "What does the ASA statement say about interpreting p-values?"),
    ("Q14", "Does a non-significant p-value mean there is no effect?"),
    ("Q15", "What is the region of practical equivalence and how is it used?"),
    ("Q16", "How should a Bayesian clinical trial be reported?"),
    ("X1", "What sample size is needed for a repeated measures ANOVA in sport science?"),
    ("X2", "Does treating multi-arm studies as independent inflate precision in a "
            "network meta-analysis?"),
    ("X3", "How should missing data be handled with multiple imputation?"),
]

# Exact technical synonyms only. Expanding "WAIC or LOO" with the conceptual
# phrase "model comparison cross validation" made that question worse, because
# the added words pull towards the prediction textbooks. Aliasing R-hat to PSRF
# turned a complete miss into the defining passage.
ALIASES = {
    r"\br[- ]?hat\b": "potential scale reduction factor PSRF",
    r"\beffective sample size\b|\bess\b": "ESS MCMC chain autocorrelation",
}


def expand(text: str) -> str:
    import re as _re
    extra = [v for k, v in ALIASES.items() if _re.search(k, text.lower())]
    return text + (" " + " ".join(extra) if extra else "")


def short(path: str) -> str:
    name = Path(path).name
    for tag in ("Greenland", "Wasserstein", "Shmueli", "James_Witten", "Kuhn",
                "Steyerberg", "Harrell", "Snijders", "TRIPOD", "Nevill", "Tanner",
                "Duan", "Xiao"):
        if tag.lower() in name.lower():
            return tag
    return name[:26]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True,
                    help="StatsRAG repository root (must contain data/index and data/sources)")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--lookup", action="store_true",
                    help="Arm D only: reviewer questions rather than statements")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser()
    sys.path.insert(0, str(repo / "src"))
    try:
        from statsrag.indexing import query as sr_query, get_chunk_text
    except Exception as exc:                                    # noqa: BLE001
        print(f"Could not import statsrag from {repo/'src'}: {exc}")
        return 1

    index, sources = repo / "data" / "index", repo / "data" / "sources"
    if not (index / "tfidf_index.joblib").exists():
        print(f"No index at {index}. Build it in the StatsRAG app first.")
        return 1

    import re
    import joblib
    bundle = joblib.load(index / "tfidf_index.joblib")
    from collections import Counter
    folders = Counter(m["path"].split("/")[0] for m in bundle.meta)
    total = sum(folders.values())
    print(f"index: {total:,} chunks")
    for folder, n in folders.most_common():
        print(f"   {n:6,}  ({100.0*n/total:4.1f}%)  {folder}")

    def hits(text, prefixes, k):
        return sr_query(index_dir=index, question=text, top_k=k,
                        allowed_prefixes=prefixes)

    if args.lookup:
        print("\n" + "=" * 76)
        print("ARM D - reviewer questions, plain and alias-expanded")
        print("=" * 76)
        for tag, question in QUESTIONS:
            print(f"\n{tag}  {question}")
            for label, text in (("plain", question), ("expanded", expand(question))):
                got = sr_query(index_dir=index, question=text, top_k=2)
                line = " | ".join(f"{short(m['path'])} c{m['chunk']} {sc:.3f}"
                                  for sc, m in got)
                print(f"   {label:9} {line}")
                if label == "expanded":
                    sc, m = got[0]
                    body = " ".join(get_chunk_text(sources, m["path"],
                                                   int(m["chunk"])).split())
                    print(f"      {body[:220]}")
        return 0

    print("\n" + "=" * 76)
    print("ARM A / ARM B - retrieval on the text itself")
    print("=" * 76)
    print(f"{'item':5} {'kind':6} {'A top':>7} {'A guard/k':>10} {'B top':>7}  A sources")
    for tag, kind, text in ITEMS:
        a = hits(text, None, args.k)
        b = hits(text, GUARDRAILS, args.k)
        guard = sum(1 for _, m in a if m["path"].startswith(GUARDRAILS[0]))
        srcs = ", ".join(short(m["path"]) for _, m in a)
        print(f"{tag:5} {kind:6} {a[0][0]:7.3f} {guard:10d} {b[0][0]:7.3f}  {srcs}")

    print("\n" + "=" * 76)
    print("ARM C - one curated query per rule, fired only when the rule matches")
    print("=" * 76)
    for tag, kind, text in ITEMS:
        low = text.lower()
        fired = [(code, q) for code, pat, q in RULES if re.search(pat, low)]
        if not fired:
            print(f"\n{tag} [{kind}] no rule fired -- nothing retrieved")
            continue
        for code, q in fired:
            got = hits(q, GUARDRAILS, 3)
            print(f"\n{tag} [{kind}] {code}")
            for score, meta in got:
                txt = " ".join(get_chunk_text(sources, meta["path"],
                                              int(meta["chunk"])).split())
                print(f"     {short(meta['path'])} c{meta['chunk']} score={score:.3f}")
                print(f"       {txt[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
