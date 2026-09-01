#!/usr/bin/env python3
"""
Covers the prompt budgeting added after a 127-page submission crashed a review.

The file was a 22-page article bound together with 105 pages of supplementary
tables -- 73% of the document by characters, not a duplicated article as it
first appeared. Chunk notes were concatenated into the file-level prompt with
no limit, producing a 45,904-token prompt against a 32,768-token server, and
the run died with a raw traceback partway through.
"""
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import review_pipeline as rp  # noqa: E402
import llm_backend  # noqa: E402

F = 0


def ok(label, cond, detail=""):
    global F
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"   {detail}" if not cond and detail else ""))
    if not cond:
        F += 1


print("[budget derived from the server's real window]")
budget = rp.prompt_char_budget()
ok("a budget is produced", budget > 4000, str(budget))
ok("reserving for generation shrinks it",
   rp.prompt_char_budget(reserve_tokens=5000) < budget)
ok("it never goes below the floor",
   rp.prompt_char_budget(reserve_tokens=10 ** 6) == 4000,
   str(rp.prompt_char_budget(reserve_tokens=10 ** 6)))
ok("an unreachable server still yields a sane number",
   llm_backend.available_context() > 0, str(llm_backend.available_context()))

print("\n[trimming keeps the front of the document]")
BODY = "\n".join(f"[Page {i}] article content for page {i}. " * 20 for i in range(1, 12))
SUPP = "\n".join(f"[Page {i}] Table S{i}: supplementary rows. " * 20 for i in range(12, 90))
kept, note = rp.fit_to_budget(BODY + "\n" + SUPP, len(BODY), "chunk")
ok("something is dropped", bool(note))
ok("the article body survives", "[Page 1]" in kept and "[Page 11]" in kept)
ok("the supplementary tail is what goes", "Table S80" not in kept)
ok("the note quantifies the loss", "characters of chunk notes" in note, note[:90])
ok("the note says omitted, not unreported", "unexamined rather than unreported" in note)
ok("it stays within budget", len(kept) <= len(BODY))

print("\n[it does nothing when nothing is needed]")
short = "A short set of notes."
ok("short text is returned unchanged", rp.fit_to_budget(short, 10000)[0] == short)
ok("and carries no note", rp.fit_to_budget(short, 10000)[1] == "")
ok("empty text is safe", rp.fit_to_budget("", 10000) == ("", ""))
ok("text with no boundaries is still cut",
   len(rp.fit_to_budget("x" * 5000, 1000)[0]) == 1000)

print("\n[the backend explains a context overflow instead of raising a traceback]")
src = (ROOT / "app" / "llm_backend.py").read_text()
ok("the overflow case is detected", "exceed_context_size" in src)
ok("the message names the remedy", "LLAMA_SERVER_CTX=65536" in src)
ok("it names the usual cause", "supplementary appendix" in src)

print()
if F:
    print(f"{F} FAILURE(S)")
    sys.exit(1)
print("All context-budget checks passed.")
