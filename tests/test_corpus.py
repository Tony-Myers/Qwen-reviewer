#!/usr/bin/env python3
"""
Diagnostic sweep over a folder of PDFs, to check that extraction behaves on
papers other than the one the extraction was written against.

This is a report, not a pass/fail suite: run it whenever you add papers, or
after changing anything in the extraction, and look at the columns.

    .venv/bin/python tests/test_corpus.py            # uses inputs/
    .venv/bin/python tests/test_corpus.py ~/papers

Columns:
  tables      how many table blocks were extracted
  announced   distinct numbered tables the document's own captions declare
  got         how many of those were actually extracted
  models      model predictor lists recovered from stacked coefficient tables
  frag        tables whose numbers were split across rows (values unusable)
  degraded    the document's text itself did not extract cleanly

A shortfall in "got" is not necessarily a defect in this pipeline: some
journal PDFs place tables as images, or in layouts no text extractor can
linearise. What matters is that the reviewer is told, rather than concluding
the paper failed to report something.
"""

import re
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_pipeline as rp  # noqa: E402

folder = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(__file__).resolve().parent.parent / "inputs"
pdfs = sorted(folder.glob("*.pdf"))
if not pdfs:
    print(f"No PDFs in {folder}")
    sys.exit(1)

print(f"Sweeping {len(pdfs)} PDFs in {folder}\n")
header = f"{'paper':42s} {'tables':>6} {'ann':>4} {'got':>4} {'models':>6} {'frag':>4} {'degraded':>8}"
print(header)
print("-" * len(header))

totals = {"tables": 0, "shortfall": 0, "frag": 0, "degraded": 0, "models": 0}
for pdf in pdfs:
    try:
        text, blocks = rp.load_document(pdf)
    except Exception as exc:
        print(f"{pdf.stem[:42]:42s}  FAILED TO READ: {type(exc).__name__}")
        continue

    announced = rp._table_numbers(text)
    found = set()
    for _, block in blocks:
        found |= rp._table_numbers(block)
    got = len(announced & found)

    models = rp.extract_model_predictors(blocks)
    frag = sum(1 for _, b in blocks if rp.table_fragmentation_warning(b))
    degraded = bool(rp.document_extraction_quality(text))

    totals["tables"] += len(blocks)
    totals["models"] += len(models)
    totals["frag"] += frag
    totals["degraded"] += int(degraded)
    if announced and got < len(announced):
        totals["shortfall"] += 1

    print(f"{pdf.stem[:42]:42s} {len(blocks):>6} {len(announced):>4} {got:>4} "
          f"{len(models):>6} {frag:>4} {('YES' if degraded else '-'):>8}")

print("-" * len(header))
n = len(pdfs)
print(f"\n{totals['tables']} table blocks extracted across {n} papers")
print(f"{totals['shortfall']}/{n} papers have tables the extractor could not read "
      f"(the review is told, and must not treat them as unreported)")
print(f"{totals['frag']} tables had numbers split across rows and are flagged unusable")
print(f"{totals['degraded']}/{n} documents did not extract cleanly as text")
print(f"{totals['models']} model predictor lists recovered from stacked coefficient tables")
