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


print("\nRetrieval")

hits = rp.select_passages("how was convergence checked?", TEXT)
check("the relevant page is retrieved", hits and hits[0][0] == 5, hits[:1])
check("only what is needed is retrieved", len(hits) == 1, len(hits))
check("page numbers survive", all(isinstance(p, int) for p, _ in hits))

none_match = rp.select_passages("what does it say about heterogeneity?", TEXT)
check("a question matching nothing still returns passages to answer from",
      len(none_match) > 0, len(none_match))
check("an empty manuscript returns nothing", rp.select_passages("anything", "") == [])

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
      "Answer only from the passages below" in rp.QA_SYSTEM)
check("it forbids inferring an absence in the manuscript",
      "not in the passages I can see" in rp.QA_SYSTEM)
check("it forbids judging the paper unasked",
      "Do not judge the paper" in rp.QA_SYSTEM)

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
