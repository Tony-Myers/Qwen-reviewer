#!/usr/bin/env python3
"""
Tests for the manuscript lookup bound to a completed review.

The point of the feature is that an answer is checked the way a report is, so
these tests are mostly about the checking, not the answering.

    python3 tests/test_manuscript_qa.py
"""

import sys
import types
from pathlib import Path


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


ANSWER = "placeholder"


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)
_stub("llm_backend",
      available_context=lambda *a, **k: 0, BackendError=Exception,
      current_backend=lambda *a, **k: "", generate=lambda *a, **k: ANSWER,
      load=lambda *a, **k: (None, None), make_sampler=lambda *a, **k: None,
      set_backend=lambda *a, **k: None, strip_reasoning=lambda t: t,
      thinking_enabled=lambda *a, **k: False,
      thinking_token_allowance=lambda *a, **k: 0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import review_pipeline as rp  # noqa: E402

failures = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        failures.append(label)


class Tokenizer:
    chat_template = None

    def apply_chat_template(self, *a, **k):
        return ""


TEXT = (
    "[Page 5]\n"
    "The hierarchical model was fitted using Markov Chain Monte Carlo and "
    "convergence was checked with trace plots (refer to Appendix).\n\n"
    "[Page 10]\n"
    "The prior for the intercept was a student-t distribution with 3 degrees "
    "of freedom, and the scale parameter was the median absolute deviation.\n\n"
    "[Page 12]\n"
    "Results show entropy values were, on average, highest in the 6x6 grid.\n"
)
REPORT = "# Directly supported concerns\n- Concern: the prior is not fully specified.\n"


def ask(question, answer, report=""):
    global ANSWER
    ANSWER = answer
    sys.modules["llm_backend"].generate = lambda *a, **k: ANSWER
    return rp.answer_manuscript_question(None, Tokenizer(), question, TEXT,
                                         report_text=report)


print("\nRetrieval: a manuscript that fits is not retrieved from")

# A paper in this field extracts to around 20,000 tokens against a 32,768
# context, so the whole document usually fits. A passage never selected cannot
# be quoted, so selection is the fallback, not the design.
hits = rp.select_passages("how was convergence checked?", TEXT)
check("a short manuscript is sent whole", len(hits) == len(rp._qa_blocks(TEXT)), len(hits))
check("in document order", [p for p, _ in hits] == sorted(p for p, _ in hits))
check("page numbers survive", all(isinstance(p, int) for p, _ in hits))
check("an empty manuscript returns nothing", rp.select_passages("anything", "") == [])

print("\nRetrieval: a long manuscript is narrowed, by BM25")

LONG = TEXT + "\n\n" + "\n\n".join(
    f"[Page {n}]\nA paragraph about clustering and pacing and clustering again, "
    f"with no bearing on the question, numbered {n}." for n in range(20, 120))
narrowed = rp.select_passages("how was convergence checked?", LONG, budget=2500)
check("a long manuscript is narrowed", 0 < len(narrowed) < len(rp._qa_blocks(LONG)),
      len(narrowed))
check("the relevant page is still found", any(p == 5 for p, _ in narrowed),
      [p for p, _ in narrowed])
check("the selection respects the budget",
      sum(len(b) for _, b in narrowed) <= 2500)

# "clustering" is in every filler block and carries no information; "prior" is
# in one. Counting terms weighs them the same, BM25 does not.
scores = rp._bm25_scores({"clustering"}, rp._qa_blocks(LONG))
rare = rp._bm25_scores({"prior"}, rp._qa_blocks(LONG))
check("a term in every block scores below a term in one",
      max(scores) < max(rare), (round(max(scores), 2), round(max(rare), 2)))

none_match = rp.select_passages("xyzzy plugh", LONG, budget=2500)
check("a question matching nothing still returns passages to answer from",
      len(none_match) > 0, len(none_match))

print("\nWhat the model may conclude from an absence")

check("a selection forbids inferring absence",
      "not in the passages I can see" in rp.QA_SYSTEM_PARTIAL)
check("a complete document allows it",
      "If something is not in them it is not in the paper" in rp.QA_SYSTEM_COMPLETE)
check("and still excludes figures", "figures are not" in rp.QA_SYSTEM_COMPLETE)

print("\nChecking the answer")

answer, problems = ask("how was convergence checked?",
                       'The paper says "convergence was checked with trace plots" (p. 5).')
check("a located quotation produces no problem", problems == [], problems)
check("and the footer says so",
      "every quotation was located" in rp.format_answer_check(answer, problems))

answer, problems = ask("how was convergence checked?",
                       'The paper says "convergence was assessed with R-hat and ESS" (p. 5).')
check("an invented quotation is caught", len(problems) == 1, problems)
check("the footer carries it",
      "Check:" in rp.format_answer_check(answer, problems)
      and "not found" in rp.format_answer_check(answer, problems).lower(),
      rp.format_answer_check(answer, problems))

answer, problems = ask("what did the review say?",
                       'The review states "the prior is not fully specified." here.',
                       report=REPORT)
check("a quotation from the review is relabelled, not called invented",
      problems and "Quoted from the review" in problems[0], problems)

answer, problems = ask("was R-hat reported?", "No, it was not reported anywhere.")
check("an unquoted answer is flagged as unchecked",
      "quotes nothing" in rp.format_answer_check(answer, problems),
      rp.format_answer_check(answer, problems))

answer, problems = ask("was R-hat reported?", 'It says "trace plots" only.')
check("a quotation too short to check is described as such",
      "too short" in rp.format_answer_check(answer, problems),
      rp.format_answer_check(answer, problems))

print("\nScope")

check("the system prompt forbids answering beyond the passages",
      "Answer only from the passages below" in rp.QA_SYSTEM_PARTIAL)
check("it forbids inferring an absence from a selection",
      "not in the passages I can see" in rp.QA_SYSTEM_PARTIAL)
check("it forbids judging the paper unasked",
      "Do not judge the paper" in rp.QA_SYSTEM_PARTIAL)

server_src = (ROOT / "app" / "server.py").read_text()
check("the endpoint refuses a review that has not finished",
      "has not finished, so there is nothing to ask about" in server_src)
check("the endpoint returns the check alongside the answer",
      "rp.format_answer_check(answer, problems)" in server_src)
check("the review keeps its extracted text so answers use the same source",
      'review_jobs[job_id]["text"] = text' in server_src)

print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    sys.exit(1)
print("All checks passed.")
