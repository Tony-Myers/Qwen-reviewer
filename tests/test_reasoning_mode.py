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

print("\n[the choice reaches the pipeline]")
server_src = (ROOT / "app" / "server.py").read_text()
ok("the endpoint accepts it", 'thinking: str = Form("")' in server_src)
ok("it is held for the whole review", "with llm_backend.thinking(want_thinking):" in server_src)
ok("blank means the server default", 'want_thinking = None' in server_src)
ok("the mode is written into the header", '"Reasoning: ' in server_src or "Reasoning:" in server_src)

html = (ROOT / "app" / "chat.html").read_text()
ok("the browser offers the choice", 'id="reasoningMode"' in html)
ok("all three options are present",
   'value=""' in html and 'value="0"' in html and 'value="1"' in html)
ok("it is sent with the upload", "fd.append('thinking'" in html)

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
