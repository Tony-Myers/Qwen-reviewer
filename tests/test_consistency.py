#!/usr/bin/env python3
"""
Covers two fixes made after comparing three reviews of the same paper.

1. The citation check reported correct numbers and correct quotations as
   absent, because it compared the report against raw extraction. Elsevier
   PDFs of this vintage set the decimal point in a font that extracts as "$"
   (314 such numbers in one paper), and ligatures arrive with a space wedged
   into the word ("strati fied"). Both defeated the comparison, so the check
   was telling the reader to distrust accurate citations.

2. Three consecutive runs over one paper found its sample-size contradiction
   once. On the third run the model quoted N=36,660 and N=58,848 in a single
   sentence against a stated total of 53,390 and did not subtract. Anything
   that reduces to arithmetic is computed here instead.
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

fails = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}"
          + (f"  {detail}" if not condition and detail else ""))
    if not condition:
        fails.append(label)


print("[1] decimal separators extracted as '$'")
SRC = ("Anthropometric variable Wilks Lambda F ratio\n"
       "BMI 0$820 1844$9\nWHTR 0$795 2199$7\n"
       "WHT$5R 0$794 2216$3\nWC 0$802 2112$9\n")
check("0.795 is no longer reported missing",
      not any("0.795" in p for p in
              rp.verify_report_citations("Lambda was 0.795.", SRC)))
check("0.794 is no longer reported missing",
      not any("0.794" in p for p in
              rp.verify_report_citations("Lambda was 0.794.", SRC)))
check("2216.3 is no longer reported missing",
      not any("2216.3" in p for p in
              rp.verify_report_citations("The F ratio was 2216.3.", SRC)))
check("an index name is not turned into a decimal",
      "WHT.5R" not in rp._normalise_numeric_artefacts("WHT$5R"))
check("the separator is folded when spaced (0 $235)",
      rp._normalise_numeric_artefacts("Correlation 0 $235 N").endswith("0.235 N"))
check("a genuinely absent number is still caught",
      any("0.611" in p for p in
          rp.verify_report_citations("Lambda was 0.611.", SRC)))

print("\n[2] words split by ligature extraction")
SRC2 = ("We obtained a strati fied random probability sample of 53,390 "
        "participants from the Health Survey for England.")
check("a faithful quotation across a split word is found",
      not rp.verify_report_citations(
          'The paper reports a "stratified random probability sample".', SRC2))
check("an invented quotation is still caught",
      any("not found" in p for p in rp.verify_report_citations(
          'The paper reports a "randomised double blind crossover trial".', SRC2)))

print("\n[3] a reported N that exceeds the stated total")
TEXT = ("We obtained a stratified random probability sample of 53,390 "
        "participants from the Health Survey for England.")
TABLES = [(5,
           "HDL Pearson Correlation 0.29 0.294 0.341 0.373\n"
           "N 36,660 37,279 37,279 37,279\n"
           "SBP Pearson Correlation 0.268 0.337 0.353 0.356\n"
           "N 57,857 58,848 58,848 58,848\n")]
warning = rp.sample_size_warning(TEXT, TABLES)
check("the warning fires", bool(warning))
check("it names the stated total", "53,390" in warning)
check("it names the offending value", "58,848" in warning)
check("it states the size of the excess", "5,458" in warning)
check("it leaves the legitimate smaller N alone", "36,660" not in warning)
check("the report section renders",
      "# Data consistency check" in rp.format_consistency_check(TEXT, TABLES))
check("the finding also reaches the synthesis prompt",
      "exceed it" in rp.tables_for_prompt(TABLES, TEXT))

print("\n[4] silence when there is nothing to report")
check("a consistent paper produces nothing",
      rp.sample_size_warning(TEXT, [(5, "N 40,348 41,015 41,015\n")]) == "")
check("no stated total means no warning",
      rp.sample_size_warning("No sample size is given.", TABLES) == "")
check("no tables means no warning", rp.sample_size_warning(TEXT, []) == "")
check("no section is added when clean",
      rp.format_consistency_check(TEXT, [(5, "N 100 200\n")]) == "")

print("\n[5] the stated total is read from the usual phrasings")
for phrase, expected in (
    ("A total of 1,204 patients were included.", 1204),
    ("1,204 adults were recruited from four sites.", 1204),
    ("a cohort of 1,204 subjects", 1204),
    ("Total: n = 191, (females: n = 93; males: n = 98)", 191),
    ("the total sample comprises 94,484 children and adolescents", 94484),
    ("a healthy random sample of 44 players", 44),
):
    check(f"parses {expected:,} from: {phrase[:44]}",
          rp.stated_total_sample(phrase) == expected,
          str(rp.stated_total_sample(phrase)))
check("no false total from prose without one",
      rp.stated_total_sample("The study measured height and body mass.") is None)

print("\n[6] a rounded value is not a fabricated one")
ROUNDING_SRC = ("Test R2 = 0.134 +- 0.118, MAE = 0.211 +- 0.030 on the test set; "
                "the rf model reached R2 = 0.361 +- 0.175 and MAE = 0.013 +- 0.002.")
for value in ("0.13", "0.36", "0.01"):
    check(f"{value} accepted as a rounding of a real value",
          not any(f"Number {value} " in p for p in
                  rp.verify_report_citations(f"approximately {value} here", ROUNDING_SRC)))
check("an invented value is still caught",
      any("0.999" in p for p in
          rp.verify_report_citations("a value of 0.999", ROUNDING_SRC)))
check("a wrong value at the same precision is still caught",
      any("0.987" in p for p in
          rp.verify_report_citations("a value of 0.987", ROUNDING_SRC)))

print("\n[7] sample sizes written out in words")
for phrase, expected in (
    ("Twenty-seven recreational cyclists completed baseline tests.", 27),
    ("Thirty-four participants were recruited for this study.", 34),
    ("Three hundred sixty-three competitive-level swimmers "
     "(male [n=202]; female [n=161]) participated in the study.", 363),
    ("One hundred and twelve patients were enrolled.", 112),
):
    check(f"parses {expected} from words", rp.stated_total_sample(phrase) == expected,
          str(rp.stated_total_sample(phrase)))
check("prose without a sample size still yields nothing",
      rp.stated_total_sample("Participants completed a warm-up before testing.") is None)

print("\n[8] quotations that elide with '...'")
ELIDE_SRC = ("The difference between home and away scores over five rounds was "
             "modeled as a normal response variable. Judges were randomised.")
check("a faithful elision verifies",
      not rp.verify_report_citations(
          'The text states "The difference between home and away scores... '
          'as a normal response variable."', ELIDE_SRC))
partial = rp.verify_report_citations(
    'The text states "The difference between home and away scores over five '
    'rounds... treating judges and bouts as crossed random effects."', ELIDE_SRC)
check("an invented half is named, not the whole quotation",
      any("only partly found" in p and "crossed random effects" in p
          for p in partial), str(partial)[:120])

print("\n[9] self-citation phrasings")
for phrase in ("The synopsis notes that the design is strong.",
               "The file summary states that ten participants took part.",
               "The evidence appendix reports four tables."):
    check(f"caught: {phrase[:38]}", bool(rp._SELF_CITATION_RE.search(phrase)))
check("ordinary prose is not caught",
      not rp._SELF_CITATION_RE.search("The authors note that judges were randomised."))

print("\n[10] captions split as 'T able 2' by extraction")
check("split caption is recognised",
      rp._table_numbers("T able 2 | Points in favour of the home boxer") == {"2"})
check("normal caption still recognised",
      rp._table_numbers("Table 3. Model performance") == {"3"})
check("an in-text reference is still ignored",
      rp._table_numbers("as shown in Table 4 the effect is small") == set())

print("\n[11] confidence needs every quotation to hold")
MIX = "The abstract says just over half a point per bout. Judges were randomised."
check("one good and one invented quotation -> Low",
      rp.concern_confidence(
          'Evidence: the paper says "just over half a point per bout" and '
          '"the effect was reversed under control conditions".', MIX)[0] == "Low")
check("all quotations verifying -> High",
      rp.concern_confidence(
          'Evidence: the paper says "just over half a point per bout".',
          MIX)[0] == "High")

print("\n[12] unverified quotations lose their marks, verified ones keep them")
MARK_SRC = ("The abstract reports just over half a point per bout. "
            "Judges were randomised into two conditions.")
verified = 'Evidence: the paper says "just over half a point per bout" here.'
check("a verified quotation is left alone",
      rp.mark_unverified_quotations(verified, MARK_SRC) == verified)

invented = 'Evidence: the paper says "the effect reversed under control conditions" here.'
marked = rp.mark_unverified_quotations(invented, MARK_SRC)
check("an unverified quotation loses its marks", '"' not in marked, marked)
check("and is tagged in place", "*[not verbatim" in marked, marked)
check("the wording itself is preserved",
      "the effect reversed under control conditions" in marked)

mixed = ('Evidence: the paper says "just over half a point per bout" but also '
         '"the effect reversed under control conditions".')
out = rp.mark_unverified_quotations(mixed, MARK_SRC)
check("the genuine quotation keeps its marks",
      '"just over half a point per bout"' in out, out)
check("only the invented one is stripped", out.count("*[not verbatim") == 1, out)

check("a short span is not touched",
      rp.mark_unverified_quotations('He said "no way" loudly.', MARK_SRC)
      == 'He said "no way" loudly.')
check("running twice does not tag twice",
      rp.mark_unverified_quotations(marked, MARK_SRC).count("*[not verbatim") == 1)
check("empty input is safe", rp.mark_unverified_quotations("", MARK_SRC) == "")
check("no quotations is safe",
      rp.mark_unverified_quotations("A plain sentence.", MARK_SRC)
      == "A plain sentence.")

print()
if fails:
    print(f"{len(fails)} FAILURE(S): " + "; ".join(fails))
    sys.exit(1)
print("All consistency checks passed.")
