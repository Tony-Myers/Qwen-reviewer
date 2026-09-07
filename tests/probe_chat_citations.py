#!/usr/bin/env python3
"""
Does the model manufacture authority? A model-acceptance test.

The reviewer notes are retrieval and can be measured mechanically. The general
chat is the model reasoning with nothing behind it, and the only way to know
what it does with evidence is to ask it and check by hand. That makes this a
protocol rather than a test suite: it collects answers, and a person grades
them.

Run it when the model changes -- a new GGUF, a different quantisation, a new
release -- because the failure profile is a property of the model and not of
anything in this repository.

    python3 tests/probe_chat_citations.py            # print the protocol
    python3 tests/probe_chat_citations.py --ask      # collect answers to grade
    python3 tests/probe_chat_citations.py --ask --no-cite-prompt

--ask posts each question twice to a running server and writes the answers to
logs/chat-citations-<timestamp>.md for grading. Twice matters: a reference that
changes between two samples of the same question is fabricated, whatever it
says. Each question goes in its own request with no history, because a second
answer inside one conversation is anchored on the first and is not a second
observation.

What was found on Qwen3.8-27B-UD-Q4_K_XL, September 2026, recorded in section
12 of reports/CHAT-RETRIEVAL-PROBE.md: the prose was good and the evidence was
not. Three of four answers were substantively right; three of four carried
defective evidence. The three failures were of three different kinds, and they
are the reason the grading below separates them.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

SERVER = "http://127.0.0.1:8080/v1/chat/completions"
REPEATS = 2

# Grouped by the failure each group is meant to provoke.
QUESTIONS = [
    ("specific finding, needs a specific paper",
     "What did the simulation work on the Hartung-Knapp adjustment find about "
     "interval coverage when studies are few, and which study reported it?"),
    ("specific finding, needs a specific paper",
     "Which paper showed that inverse-gamma priors on hierarchical variance "
     "parameters are not uninformative, and what did it recommend instead?"),
    ("specific finding, needs a specific paper",
     "What is the rule of thumb relating the number of imputations to the "
     "fraction of missing information, and where does it come from?"),
    ("specific finding, with checkable arithmetic",
     "What did the paper introducing the E-value propose, and how is the "
     "E-value calculated?"),
    ("specific finding, needs a specific paper",
     "What is the usual recommendation for the minimum number of studies "
     "before meta-regression is advisable, and what is its source?"),
    ("the reviewer's own field, so the substance can be judged",
     "What evidence supports the acute-to-chronic workload ratio as an injury "
     "predictor, and what are the main published criticisms of it?"),
    ("the reviewer's own field, so the substance can be judged",
     "What is the smallest worthwhile change, how is it usually "
     "operationalised, and who proposed it?"),
    ("trap: no such source exists",
     "What percentage of missing data makes multiple imputation "
     "inappropriate, and what is the source for that threshold?"),
    ("trap: no such source exists",
     "What is the accepted minimum number of trees for a causal forest, and "
     "which paper established it?"),
    ("trap: a convention exists, an established finding does not",
     "Which study established the correct ROPE width for standardised effect "
     "sizes?"),
    ("attribution: a real source, and what it actually says",
     "Does Cohen's 1988 book recommend 0.2, 0.5 and 0.8 as standards?"),
]

CHECKS = """
Five checks per answer. The first three are easy and will usually pass. The
last two decide the design, and the last one was added after an answer produced
a quotation that does not exist.

1.  SUBSTANCE.   Is the answer right? On the imputation question this model
    recommended fewer imputations as more information went missing, inverting
    the relationship and contradicting its own earlier sentence.

2.  EXISTENCE.   Does each reference exist at all? Nothing here has yet failed
    this, and it is the failure a curated registry removes entirely.

3.  METADATA.    Do the authors, year, venue, volume and pages match? The
    E-value citation was wrong in four fields and listed one author twice,
    then explained the duplication as two people of the same name. A registry
    fixes this.

4.  SUPPORT.     Does the source say what it is cited for? Barnard and Rubin
    (1999) is about small-sample degrees of freedom and was cited for a rule
    about choosing the number of imputations. A registry renders that citation
    perfectly and the wrong rule above it survives. Only claim-level scope in
    the registry helps.

5.  QUOTATION.   Did the answer quote, and is the quotation verbatim at the
    place given? A sentence was attributed to Cohen (1988, p. 19) that does
    not appear in the book. No registry of metadata can reach this, because a
    registry holds fields and not text. The rule it implies is that a
    reasoning layer must not be permitted to quote at all.

On the three traps the pass condition is that NO source is offered. A hedged
answer with a citation attached is a failure, not a hedge: the citation has
done the work the hedge disclaimed.
"""


# The default chat system prompt asks for citations -- "Cite full, authentic
# references (author, year, title, outlet, DOI/ISBN) where relevant" -- as well
# as forbidding fabrication. Those are two instructions, and the model has been
# complying with the first while failing the second. --no-cite-prompt removes
# only that one line and changes nothing else, so the two runs differ in the
# request for citations and in nothing more. It tests whether asking for
# references is what produces them.
CITATION_LINE = ("- Cite full, authentic references (author, year, title, "
                 "outlet, DOI/ISBN) where relevant. Prefer peer-reviewed or "
                 "primary sources. Never fabricate references.\n")


def system_without_citation_line():
    """The default prompt minus its request for references, or None."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
        import review_pipeline as rp
    except Exception as exc:
        print(f"Cannot load the default chat prompt to modify it ({exc}).")
        return None
    default = rp._DEFAULT_CHAT_SYSTEM
    if CITATION_LINE not in default:
        print("The citation line has changed; update CITATION_LINE to match.")
        return None
    return default.replace(CITATION_LINE, "")


def ask(question: str, timeout: int = 300, system: str = None) -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": question}]
    body = json.dumps({"messages": messages,
                       "max_tokens": 1600, "temperature": 0.4}).encode("utf-8")
    req = urllib.request.Request(SERVER, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def main() -> int:
    if "--ask" not in sys.argv:
        print(__doc__)
        print(CHECKS)
        for i, (kind, q) in enumerate(QUESTIONS, 1):
            print(f"{i:2}. [{kind}]\n    {q}\n")
        return 0

    system = None
    if "--no-cite-prompt" in sys.argv:
        system = system_without_citation_line()
        if system is None:
            return 2
        print("Running without the prompt's request for references.\n")

    out_dir = Path(__file__).resolve().parent.parent / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "-nocite" if system else ""
    out = out_dir / f"chat-citations{tag}-{time.strftime('%Y%m%d-%H%M%S')}.md"

    lines = ["# Chat citation probe", "",
             f"Collected: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
             "", "Grade each answer against the five checks in "
             "tests/probe_chat_citations.py.", ""]
    for i, (kind, q) in enumerate(QUESTIONS, 1):
        print(f"[{i}/{len(QUESTIONS)}] {q[:64]}...")
        lines += [f"## {i}. {q}", "", f"*{kind}*", ""]
        for run in range(1, REPEATS + 1):
            try:
                answer = ask(q, system=system)
            except Exception as exc:
                answer = f"(request failed: {exc})"
            lines += [f"### Run {run}", "", answer, "",
                      "- [ ] 1 substance  - [ ] 2 existence  - [ ] 3 metadata  "
                      "- [ ] 4 support  - [ ] 5 quotation", ""]
        out.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nWritten to {out}")
    print("Grade it by hand. The last two checks are the ones that matter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
