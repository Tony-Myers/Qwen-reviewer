#!/usr/bin/env python3
"""
Covers the per-review reasoning choice and the tally that makes it useful.

The pipeline has always run in instruct mode and thinking mode has never been
tested. Rather than a controlled sweep -- which costs an hour per comparison and
which the measured noise floor says needs eight or more papers anyway -- the
browser now offers the choice per review, the mode is recorded in the report
header, and reviews done for real work accumulate into an evaluation.

The header record is the part that matters: without it the comparison is
unrecoverable after the fact.
"""
import importlib.util
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import llm_backend  # noqa: E402

_spec = importlib.util.spec_from_file_location("tally", ROOT / "tests" / "report_tally.py")
tally = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tally)

F = 0


def ok(label, cond, detail=""):
    global F
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"   {detail}" if not cond and detail else ""))
    if not cond:
        F += 1


print("[the thinking switch]")
base = llm_backend.thinking_enabled()
with llm_backend.thinking(True):
    ok("forced on", llm_backend.thinking_enabled() is True)
ok("restored afterwards", llm_backend.thinking_enabled() == base)
with llm_backend.thinking(False):
    ok("forced off", llm_backend.thinking_enabled() is False)
with llm_backend.thinking(None):
    ok("None leaves the default alone", llm_backend.thinking_enabled() == base)
try:
    with llm_backend.thinking(True):
        raise RuntimeError("a review that fails")
except RuntimeError:
    pass
ok("restored even when the review fails", llm_backend.thinking_enabled() == base,
   "a leaked override would silently change every later review")
with llm_backend.thinking(True):
    with llm_backend.thinking(False):
        ok("nesting works", llm_backend.thinking_enabled() is False)
    ok("the outer setting comes back", llm_backend.thinking_enabled() is True)

print("\n[reasoning is counted, not assumed]")
# Requesting thinking and getting it are different things. Three paths fail
# silently -- a rejected chat_template_kwargs, an empty <think></think> pair,
# and a server that returns reasoning in its own field -- and each yields a
# report headed "thinking" containing none.
llm_backend.reset_reasoning_stats()
ok("a fresh count is empty", llm_backend.reasoning_stats()["chars"] == 0)

llm_backend.reset_reasoning_stats()
out = llm_backend.strip_reasoning("<think>weighing the priors</think>\nThe report.")
ok("the span is still removed", out == "The report.", repr(out))
ok("its characters are counted",
   llm_backend.reasoning_stats()["chars"] == len("weighing the priors"),
   str(llm_backend.reasoning_stats()))

llm_backend.reset_reasoning_stats()
llm_backend.strip_reasoning("<think></think>\nThe report.")
ok("an empty pair counts as no reasoning",
   llm_backend.reasoning_stats()["chars"] == 0,
   "this is the instruct-mode default, and must not read as thinking")

llm_backend.reset_reasoning_stats()
llm_backend.strip_reasoning("<think>   \n  </think>\nThe report.")
ok("a whitespace-only pair counts as no reasoning",
   llm_backend.reasoning_stats()["chars"] == 0)

llm_backend.reset_reasoning_stats()
llm_backend._note_reasoning_chars(120)
llm_backend._close_generation()
llm_backend._close_generation()
st = llm_backend.reasoning_stats()
ok("generations are counted", st["generations"] == 2, str(st))
ok("only the one carrying reasoning is flagged", st["with_reasoning"] == 1, str(st))

llm_backend.reset_reasoning_stats()
llm_backend._extract_chat_text(
    {"choices": [{"message": {"content": "The report.",
                              "reasoning_content": "weighing the priors"}}]})
ok("reasoning returned in its own field is counted too",
   llm_backend.reasoning_stats()["chars"] == len("weighing the priors"),
   "llama-server --reasoning-format deepseek puts it here, not inline")

llm_backend.reset_reasoning_stats()
ok("reset clears everything",
   llm_backend.reasoning_stats() == {"generations": 0, "with_reasoning": 0,
                                     "chars": 0, "template_kwargs_dropped": False,
                                     "retries": 0, "fallbacks": 0},
   str(llm_backend.reasoning_stats()))

backend_src = (ROOT / "app" / "llm_backend.py").read_text()
ok("a rejected chat_template_kwargs is recorded, not just swallowed",
   "_note_template_kwargs_dropped()" in backend_src)

# Reasoning is generated inside max_tokens. The chunk-note cap of 900 is
# already reached on most calls in instruct mode, so without an allowance a
# thinking run answers at a shorter length than the mode it is compared with.
import os as _os  # noqa: E402
_saved_effort = _os.environ.get("LLAMA_REASONING_EFFORT")
try:
    for _value in ("low", "medium", "high", "xhigh"):
        _os.environ["LLAMA_REASONING_EFFORT"] = _value
        ok(f"{_value} is accepted", llm_backend.reasoning_effort() == _value)
    # "high" was missing from the accepted set, so setting it produced silence
    # and the template default -- the same quiet mismatch as everything else
    # fixed today.
    _os.environ["LLAMA_REASONING_EFFORT"] = "HIGH"
    ok("case does not matter", llm_backend.reasoning_effort() == "high")
    _os.environ["LLAMA_REASONING_EFFORT"] = "very-high"
    ok("an unrecognised value is ignored", llm_backend.reasoning_effort() == "")
    _os.environ.pop("LLAMA_REASONING_EFFORT")
    # Nothing was sent at all until it was measured. Medium halved the reasoning
    # per generation on a full hybrid review and cut the retries from four to
    # one, so it is the default; "template" restores the old behaviour.
    ok("unset now means medium", llm_backend.reasoning_effort() == "medium",
       llm_backend.reasoning_effort())
    _os.environ["LLAMA_REASONING_EFFORT"] = "template"
    ok("template sends nothing, as every run before today did",
       llm_backend.reasoning_effort() == "")
finally:
    if _saved_effort is None:
        _os.environ.pop("LLAMA_REASONING_EFFORT", None)
    else:
        _os.environ["LLAMA_REASONING_EFFORT"] = _saved_effort
_server_src = (ROOT / "app" / "server.py").read_text()
ok("the header says which effort was in force",
   "reasoning effort was requested as" in _server_src
   and "the chat template's" in _server_src)

ok("instruct gets no allowance", llm_backend.thinking_token_allowance() == 0)
with llm_backend.thinking(True):
    ok("thinking gets one", llm_backend.thinking_token_allowance() > 0,
       str(llm_backend.thinking_token_allowance()))
ok("it is applied to the request, not just reported",
   "budget = max_tokens + THINKING_EXTRA_TOKENS" in backend_src)

# An answer that never arrived because the reasoning used the whole budget must
# not pass silently. The first working thinking run produced 125,512 characters
# of reasoning across 14 generations against caps of 2,100 to 3,200 tokens, so
# every generation returned reasoning and no content -- and the pipeline built a
# tidy, entirely empty report from it.
try:
    llm_backend._reject_if_reasoning_ate_the_answer("", 9000, 2100)
    ok("an empty answer after reasoning is refused", False, "no exception raised")
except llm_backend.BackendError as exc:
    ok("an empty answer after reasoning is refused", True)
    ok("and the message says what to change",
       "QWEN_THINKING_EXTRA_TOKENS" in str(exc) and "Instruct" in str(exc),
       str(exc))
try:
    llm_backend._reject_if_reasoning_ate_the_answer("", 0, 900)
    ok("an empty instruct answer is left alone", True,
       "not this failure mode, and raising here would change instruct behaviour")
except llm_backend.BackendError:
    ok("an empty instruct answer is left alone", False)
try:
    llm_backend._reject_if_reasoning_ate_the_answer("a real answer", 9000, 2100)
    ok("reasoning followed by an answer is fine", True)
except llm_backend.BackendError:
    ok("reasoning followed by an answer is fine", False)

# Three fixed allowances were tried and all three stopped a review partway
# through. How long a thinking span runs is not knowable in advance -- the same
# paper ended by itself at 3,200 tokens on chunk 1 and overran 8,900 on chunk 4.


class _FakeServerModel(llm_backend.LlamaServerModel):
    """Returns reasoning and no answer until the budget is large enough."""

    def __init__(self, needs):
        self.needs = needs
        self.calls = []

    def complete(self, messages, max_tokens, sampler, enable_thinking):
        self.calls.append((max_tokens, enable_thinking))
        llm_backend._LAST_FINISH_REASON = "stop"
        if not enable_thinking:
            return "an instruct answer"
        if max_tokens >= self.needs:
            return "<think>" + "r" * 500 + "</think>\nthe answer"
        llm_backend._LAST_FINISH_REASON = "length"
        return "<think>" + "r" * (max_tokens * 4) + "</think>"


llm_backend.reset_reasoning_stats()
_model = _FakeServerModel(needs=9000)
_msgs = [{"role": "user", "content": "x" * 4000}]
_out = llm_backend._generate_with_recovery(_model, _msgs, 900, None, True)
ok("a retry at a larger budget rescues the generation", _out == "the answer",
   f"{_out!r} after budgets {[c[0] for c in _model.calls]}")
ok("the budgets escalate rather than repeat",
   [c[0] for c in _model.calls] == sorted(set(c[0] for c in _model.calls)),
   str([c[0] for c in _model.calls]))
ok("the retry is counted", llm_backend.reasoning_stats()["retries"] >= 1,
   str(llm_backend.reasoning_stats()))

llm_backend.reset_reasoning_stats()
_never = _FakeServerModel(needs=10 ** 9)
_out = llm_backend._generate_with_recovery(_never, _msgs, 900, None, True)
ok("an impossible one finishes in instruct mode rather than killing the review",
   _out == "an instruct answer", repr(_out))
ok("the fallback is counted", llm_backend.reasoning_stats()["fallbacks"] == 1,
   str(llm_backend.reasoning_stats()))
ok("it does not retry for ever",
   len(_never.calls) <= 8, f"{len(_never.calls)} calls")
ok("the last attempt asked for instruct", _never.calls[-1][1] is False)

# An answer that arrives but breaks off mid-sentence is the same budget
# failure, and reads far more convincingly than no answer at all.
class _TruncatingModel(_FakeServerModel):
    """Returns reasoning plus a clipped answer until the budget is large enough."""

    def complete(self, messages, max_tokens, sampler, enable_thinking):
        self.calls.append((max_tokens, enable_thinking))
        if not enable_thinking:
            llm_backend._LAST_FINISH_REASON = "stop"
            return "an instruct answer"
        if max_tokens >= self.needs:
            llm_backend._LAST_FINISH_REASON = "stop"
            return "<think>" + "r" * 500 + "</think>\nthe whole answer."
        llm_backend._LAST_FINISH_REASON = "length"
        return "<think>" + "r" * (max_tokens * 4) + "</think>\nthe answer breaks off"


llm_backend.reset_reasoning_stats()
_clipped = _TruncatingModel(needs=9000)
_out = llm_backend._generate_with_recovery(_clipped, _msgs, 900, None, True)
ok("a truncated answer is retried, not returned", _out == "the whole answer.",
   f"{_out!r}: half a report is still valid markdown")
ok("that retry is counted too",
   llm_backend.reasoning_stats()["retries"] >= 1)

llm_backend.reset_reasoning_stats()
_instruct_cap = _TruncatingModel(needs=10 ** 9)
llm_backend._generate_with_recovery(_instruct_cap, _msgs, 900, None, False)
ok("instruct answers may still hit their cap without a retry",
   len(_instruct_cap.calls) == 1,
   "chunk notes have always been capped at 900; nothing changes for them")

llm_backend.reset_reasoning_stats()
_easy = _FakeServerModel(needs=0)
llm_backend._generate_with_recovery(_easy, _msgs, 900, None, True)
ok("a generation that fits is not retried", len(_easy.calls) == 1,
   str([c[0] for c in _easy.calls]))

ok("the allowance is sized against that measurement",
   llm_backend.THINKING_EXTRA_TOKENS >= 3000,
   f"{llm_backend.THINKING_EXTRA_TOKENS}: 1,200 was exhausted mid-thought")

import review_pipeline as rp  # noqa: E402
_plain = rp.prompt_char_budget()
with llm_backend.thinking(True):
    _thought = rp.prompt_char_budget()
ok("the prompt budget gives that room back",
   _thought < _plain,
   f"{_thought} vs {_plain}: a thinking run would otherwise overrun the window")

print("\n[the choice survives prompt building]")
# The switch worked, the header recorded it, and nothing happened: every prompt
# was built by apply_chat_template_compat with enable_thinking hard-coded to
# False, which outranked the override. A run headed "thinking" was an instruct
# run. Nothing downstream could detect that; only the prompt builder knew.
import review_pipeline as rp2  # noqa: E402

class _FakeTokenizer:
    """Records the flag it was templated with."""
    chat_template = "present"

    def __init__(self):
        self.seen = None

    def apply_chat_template(self, messages, tokenize=False,
                            add_generation_prompt=True, enable_thinking=None,
                            **kwargs):
        self.seen = enable_thinking
        return "PROMPT"

_tok = _FakeTokenizer()
rp2.apply_chat_template_compat(_tok, "some text")
ok("instruct by default", _tok.seen is False, repr(_tok.seen))
with llm_backend.thinking(True):
    rp2.apply_chat_template_compat(_tok, "some text")
ok("thinking reaches the template when asked for", _tok.seen is True,
   f"{_tok.seen!r}: the dropdown would be recorded and ignored")
with llm_backend.thinking(False):
    rp2.apply_chat_template_compat(_tok, "some text")
ok("and off when asked for that", _tok.seen is False, repr(_tok.seen))

pipeline_src = (ROOT / "app" / "review_pipeline.py").read_text()
ok("no prompt builder hard-codes the flag any more",
   "enable_thinking=False," not in pipeline_src,
   "a literal False here silently outranks the per-review choice")

print("\n[the choice reaches the pipeline]")
server_src = (ROOT / "app" / "server.py").read_text()
ok("the endpoint accepts it", 'thinking: str = Form("")' in server_src)
ok("it is held for the whole review", "with llm_backend.thinking(want_thinking):" in server_src)
ok("blank means the server default", 'want_thinking = None' in server_src)
ok("the mode is written into the header", "Reasoning:" in server_src)
ok("so is what the model actually did", "Reasoning check:" in server_src)
ok("the counters are reset per review",
   "llm_backend.reset_reasoning_stats()" in server_src,
   "otherwise the header reports the previous review")

ok("the hybrid is accepted", '"synthesis", "hybrid", "2"' in server_src)
# Passes repeat the synthesis, which is the stage that reasons: three passes of
# a thinking synthesis is seven thinking generations before retries. One
# measured hybrid run took eighty minutes with a single pass.
ok("a thinking review drops to one pass by default",
   'passes > rp.THINKING_PASSES' in server_src
   and 'passes = rp.THINKING_PASSES' in server_src)
ok("the reduction is announced while it runs",
   "_add_progress(job_id, passes_note" in server_src)
ok("and recorded in the header afterwards",
   'passes_note' in server_src and 'check += f"; {passes_note}"' in server_src)
ok("an instruct review keeps its passes",
   'if review_jobs.get(job_id, {}).get("thinking") and passes > rp.THINKING_PASSES'
   in server_src)
ok("the reduction is overridable",
   "QWEN_THINKING_PASSES" in (ROOT / "app" / "review_pipeline.py").read_text())

import review_pipeline as rp3  # noqa: E402
ok("one thinking pass by default", rp3.THINKING_PASSES == 1,
   str(rp3.THINKING_PASSES))
ok("the chunk loop can step back into instruct",
   "with model_lock, _chunk_reasoning(job_id):" in server_src,
   "otherwise the hybrid is just a thinking run")
ok("the header names the hybrid",
   'thinking (synthesis and validation only)' in server_src)

html = (ROOT / "app" / "chat.html").read_text()
ok("the browser offers the choice", 'id="reasoningMode"' in html)
ok("all three options are present",
   'value=""' in html and 'value="0"' in html and 'value="1"' in html)
ok("it is sent with the upload", "fd.append('thinking'" in html)
ok("the hybrid is offered too", 'value="synthesis"' in html)

print("\n[the tally groups reports by what they record]")
THINK = "# Local peer-review report\nPipeline: abc123\nReasoning: thinking\n"
INSTR = "# Local peer-review report\nPipeline: abc123\nReasoning: instruct\n"
OLD = "# Local peer-review report\nPipeline: abc123\n"
ok("thinking is recognised", tally.group_of(THINK, "mode") == "thinking")
ok("instruct is recognised", tally.group_of(INSTR, "mode") == "instruct")
ok("older reports are marked, not guessed",
   tally.group_of(OLD, "mode") == "unrecorded")
ok("passes are read when asked for",
   tally.group_of("Synthesis: 3 pass(es), each validated", "passes") == "3 passes")
ok("a single-pass report is labelled as such",
   tally.group_of(OLD, "passes") == "1 pass")
ok("pipeline version groups too", tally.group_of(OLD, "pipeline") == "abc123")
UNPROVEN = (THINK + "Reasoning check: no reasoning emitted in any of 16 "
            "generations, so this run behaved as instruct\n")
PROVEN = THINK + "Reasoning check: reasoning emitted in 14 of 16 generations (52,118 characters)\n"
ok("a thinking run with no reasoning is held apart",
   tally.group_of(UNPROVEN, "mode") == "thinking-unproven",
   "counting it as thinking would corrupt the comparison")
ok("a thinking run that did think still groups as thinking",
   tally.group_of(PROVEN, "mode") == "thinking")
HYBRID = ("# Local peer-review report\nPipeline: abc123\n"
          "Reasoning: thinking (synthesis and validation only)\n"
          "Reasoning check: reasoning emitted in 3 of 14 generations (40,000 characters)\n")
ok("the hybrid is tallied apart from full thinking",
   tally.group_of(HYBRID, "mode") == "thinking-synth",
   "pooling them would hide which of the two helps")

print("\n[it scores what it finds]")
REPORT = (INSTR + "* Confidence: High — every quotation was located in the manuscript.\n"
          "* Cites this pipeline's own summary rather than the manuscript: ...x\n"
          "* Quotation not found in the manuscript: \"y\"\n")
sc = tally._sweep.score(REPORT)
ok("scores a real header", sc["high"] == 1 and sc["self-cite"] == 1 and sc["bad-quote"] == 1,
   str(sc))

print()
if F:
    print(f"{F} FAILURE(S)")
    sys.exit(1)
print("All reasoning-mode checks passed.")
