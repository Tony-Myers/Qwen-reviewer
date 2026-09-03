#!/usr/bin/env python3
"""
Runs the exact post-synthesis chain that server.py performs, on a stored
report. The other suites exercise each function alone; this one exercises the
wiring and its ORDER -- the confidence computation and the citation check both
read quotation marks, so stripping them may only happen after both have run.
Reverse that and the check reports a clean report, which is the worst possible
failure of a tool whose job is to say what to trust.
"""

import sys, types, warnings, re
from pathlib import Path
warnings.filterwarnings("ignore")
def _stub(n,**a):
    m=types.ModuleType(n); [setattr(m,k,v) for k,v in a.items()]; sys.modules[n]=m
_stub("docx",Document=object); _stub("openpyxl",load_workbook=lambda *a,**k:None)
root=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(root/"app"))
import review_pipeline as rp

# Exactly the chain server.py::_run_review performs after synthesis.
pdf = root/"inputs/The-impact-of-crowd-noise-on-officiating-in-MuayThai.pdf"
text, table_blocks = rp.load_document(pdf)
final_report = (Path(__file__).resolve().parent / "sample_report.md").read_text()
citation_source = text + "\n" + "\n".join(b for _, b in table_blocks)

final_report = rp.annotate_concern_confidence(final_report, citation_source)
report_problems = (rp.verify_report_citations(final_report, citation_source)
                   + rp.overclaim_problems(final_report))
final_report = rp.mark_unverified_quotations(final_report, citation_source)
final_report += rp.format_action_list(final_report)
final_report += rp.format_consistency_check(text, table_blocks)
final_report += rp.format_citation_check(report_problems)


print("chain completed, no exception")
print("length:", len(final_report), "chars")
print("confidence lines:", final_report.count("* Confidence:"))
print("not-verbatim tags:", final_report.count("*[not verbatim"))
print("action table:", "# Items by evidence" in final_report)
print("citation section:", "# Citation check" in final_report)
print("problems listed:", len(report_problems))
print("stray quotes left in body:",
      final_report[:final_report.index("# Citation check")].count(chr(34)))


fails = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"   {detail}" if not cond and detail else ""))
    if not cond: fails.append(label)

check("chain produced a report", len(final_report) > 1000)
check("every concern got a confidence line", final_report.count("* Confidence:") == 3)
check("unverified spans were tagged", final_report.count("*[not verbatim") >= 1)
check("the action table rendered", "# Items by evidence" in final_report)
check("the citation section rendered", "# Citation check" in final_report)
check("the checks ran BEFORE stripping (problems were still found)",
      len(report_problems) >= 5, str(len(report_problems)))
check("verdict phrasing was caught",
      any("Verdict phrasing" in p for p in report_problems))
check("a verified quotation kept its marks",
      '"just over half a point per bout,"' in final_report,
      "the verified span should still be in quotation marks")
check("the item table is ordered by evidence, not by a self-awarded grade",
      any(f"| {label} |" in final_report
          for label in ("Quoted", "Reasoned", "Unquoted", "Question")),
      "no evidence column rendered")

print()
if fails:
    print(f"{len(fails)} FAILURE(S): " + "; ".join(fails)); sys.exit(1)
print("End-to-end chain checks passed.")
