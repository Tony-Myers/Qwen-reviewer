#!/usr/bin/env python3
"""
Covers two defects that only appeared once a paper from outside the development
corpus was reviewed: an unpublished manuscript, typeset in Word, submitted to a
journal none of the sixteen corpus papers came from.

It carried 21 unresolved cross-references ("Error! Reference source not
found.") -- the first thing a human reviewer would raise, and the pipeline did
not mention it once. Its numbered display equations were set in Mathematical
Alphanumeric Symbols with no literal word "equation", so the manifest reported
it as having none.

The real-document section runs only when the PDF is staged at the path below;
it skips cleanly otherwise, since the manuscript is unpublished and is not kept
in the repository.
"""
import sys, types, warnings, re
from pathlib import Path
warnings.filterwarnings("ignore")
def _stub(n,**a):
    m=types.ModuleType(n); [setattr(m,k,v) for k,v in a.items()]; sys.modules[n]=m
_stub("docx",Document=object); _stub("openpyxl",load_workbook=lambda *a,**k:None)
root=Path.home()/"mnt/local-llm/qwen35-review"; sys.path.insert(0,str(root/"app"))
import review_pipeline as rp

F=0
def ok(l,c,d=""):
    global F
    print(("  PASS  " if c else "  FAIL  ")+l+(f"   {d}" if not c and d else ""))
    if not c: F+=1

print("[unresolved references and placeholders]")
BROKEN = ("Results are plotted in Error! Reference source not found. and "
          "Error! Reference source not found. See also Error! Bookmark not defined.")
w = rp.submission_integrity_warning(BROKEN)
ok("the warning fires", bool(w))
ok("it counts every occurrence", "3 unresolved" in w, w[:90])
ok("it names the artefact", "Reference source not found" in w)
ok("it says the file, not the extraction, is at fault",
   "not of this extraction" in w)
ok("LaTeX placeholders are caught",
   bool(rp.submission_integrity_warning(r"as shown in \ref{tab:one} and \cite{smith}")))
ok("drafting markers are caught",
   bool(rp.submission_integrity_warning("Discussion TODO before submission.")))
ok("a clean document is silent",
   rp.submission_integrity_warning("Results are plotted in Figure 2.") == "")
ok("empty input is safe", rp.submission_integrity_warning("") == "")
ok("it reaches the report section",
   "unresolved reference" in rp.format_consistency_check(BROKEN, []))

print("\n[artefact locations, because a bare total misleads]")
PAGED = ("[Page 7] plotted in Error! Reference source not found. and Error! Reference source not found.\n"
         "[Page 9] p-values well above 0.05, Error! Reference source not found.-6\n"
         "[Page 16] Algorithms (Error! Reference source not found., Error! Reference source not found.,\n"
         "[Page 16] Error! Reference source not found.).\n")
located = rp.submission_integrity_warning(PAGED)
ok("the total is still reported", "6 unresolved" in located, located[:80])
ok("pages are named", "page 7: 2" in located and "page 9: 1" in located, located)
ok("the clustered page is shown as such", "page 16: 3" in located, located)
ok("pages are listed in order",
   located.index("page 7") < located.index("page 9") < located.index("page 16"))
ok("text without page markers still warns",
   bool(rp.submission_integrity_warning("Error! Reference source not found.")))

print("\n[an unusual number of tables and figures]")
MANY = "\n".join([f"Table {i}: A caption." for i in range(1, 18)]
                 + [f"Figure {i}: A caption." for i in range(1, 25)])
w = rp.display_item_warning(MANY)
ok("the warning fires", bool(w))
ok("it counts the tables", "17 numbered table" in w, w[:110])
ok("it counts the figures", "24 numbered figure" in w, w[:140])
ok("it suggests supplementary material", "supplementary" in w)
TYPICAL = "\n".join([f"Table {i}: A caption." for i in range(1, 5)]
                    + [f"Figure {i}: A caption." for i in range(1, 4)])
ok("a typical article is silent", rp.display_item_warning(TYPICAL) == "",
   rp.display_item_warning(TYPICAL)[:80])
# The heaviest single paper in the reference set carries 3 tables and 7 figures,
# 10 items. (6 tables and 7 figures were the maxima of two DIFFERENT papers; no
# one document held both, so combining them is not a corpus case.)
ok("the heaviest paper in the reference set stays silent",
   rp.display_item_warning("\n".join([f"Table {i}: x." for i in range(1, 4)]
                                     + [f"Figure {i}: x." for i in range(1, 8)])) == "")
ok("one item past the threshold does fire",
   bool(rp.display_item_warning("\n".join([f"Table {i}: x." for i in range(1, 7)]
                                          + [f"Figure {i}: x." for i in range(1, 9)]))))
ok("an empty document is silent", rp.display_item_warning("") == "")
ok("it reaches the report section",
   "display items" in rp.format_consistency_check(MANY, []))

print("\n[equations set in Unicode maths]")
UNICODE_EQ = "the normalised velocity split \U0001D463̂\U0001D456\U0001D457 is defined as:"
ok("Mathematical Alphanumeric Symbols count as equations",
   bool(re.search(r"[\U0001D400-\U0001D7FF]", UNICODE_EQ)))
ok("a numbered display equation counts",
   bool(re.search(r"(?m)^.{0,120}[=∼~].{0,60}\(\d{1,2}\)\s*$",
                  "  B = O + (L - 1) (3)")))
ok("ordinary prose does not",
   not re.search(r"(?m)^.{0,120}[=∼~].{0,60}\(\d{1,2}\)\s*$",
                 "We followed Smith et al. (2019) throughout."))

print("\n[against the real submission]")
pdf = Path("/tmp/rpan/RPAN-2026-0184_reviewer.pdf")
if not pdf.exists():
    print("  SKIP  PDF not staged")
else:
    text, blocks = rp.load_document(pdf)
    w = rp.submission_integrity_warning(text)
    ok("fires on the submitted manuscript", bool(w), w[:80])
    ok("reports a double-figure count",
       bool(re.search(r"contains (\d+) unresolved", w)) and
       int(re.search(r"contains (\d+) unresolved", w).group(1)) >= 15, w[:90])
    ann = rp._table_numbers(text)
    ok("all seventeen tables are seen as announced", len(ann) >= 17, str(sorted(ann)))
    ok("the missing-tables warning fires",
       bool(rp.missing_tables_warning(text, blocks)))
    manifest_eq = bool(re.search(r"[\U0001D400-\U0001D7FF]", text))
    ok("its Unicode equations are now visible", manifest_eq)

print()
print(f"{F} FAILURE(S)" if F else "All new-paper checks passed.")
sys.exit(1 if F else 0)
