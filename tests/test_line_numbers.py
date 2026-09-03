#!/usr/bin/env python3
"""
Tests for marginal line-number stripping.

    python3 tests/test_line_numbers.py
"""

import sys
import types
from pathlib import Path


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)
_stub("llm_backend",
      available_context=lambda *a, **k: 0, BackendError=Exception,
      current_backend=lambda *a, **k: "", generate=lambda *a, **k: "",
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


# A line-numbered manuscript. Line 116 ends on an operator, so its number is
# glued to the text with no space before it, and the value it introduces wraps
# to the next line. This is RPAN-2026-0184: the sample was read as "116 173"
# by two generations and the citation check endorsed it, because the extracted
# text said exactly that.
def _document(special):
    lines = [f"ordinary sentence number {n} continues here {n}" for n in range(100, 116)]
    lines.append(special)
    lines.append("173). Swimmers were deidentified, however results are preserved. 117")
    lines += [f"more ordinary text on this line {n}" for n in range(118, 140)]
    return "\n".join(lines)


print("\nA line number with no space before it")

text, removed = rp.strip_marginal_line_numbers(
    _document("and women's 200m (n =116"))
check("the abutting line number is removed", "=116" not in text, text[:0])
check("the value it preceded survives", "173)" in text)
check("it is counted", removed >= 25, removed)
check("the line now ends on the operator", "(n =" in text)

print("\nWhat must not be touched")

text, _ = rp.strip_marginal_line_numbers(
    _document("the sample for that event was n=116 in total 116"))
check("a genuine value abutting an equals sign survives",
      "n=116 in total" in text, text[text.find("sample"):][:60])

text, _ = rp.strip_marginal_line_numbers(
    _document("and women's 200m (n =999"))
check("a number that is not the missing one is left alone", "=999" in text)

plain = "\n".join(f"a sentence of prose, the {n}th of many words" for n in range(1, 40))
out, removed = rp.strip_marginal_line_numbers(plain)
check("an unnumbered document is unchanged", out == plain and removed == 0, removed)

table = "\n".join([f"row label {n} value {n * 3}" for n in range(1, 40)])
out, removed = rp.strip_marginal_line_numbers(table)
check("a table of climbing values is not mistaken for line numbers",
      removed == 0 or "value" in out, removed)

print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    sys.exit(1)
print("All line-number checks passed.")
