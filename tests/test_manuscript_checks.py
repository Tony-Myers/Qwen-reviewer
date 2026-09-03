#!/usr/bin/env python3
"""
Tests for tests/manuscript_checks.py.

Standard library only; the passages are written for this file. Each case is a
fault the checks were built from, or a false positive the corpus run exposed.

    python3 tests/test_manuscript_checks.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import manuscript_checks as mc  # noqa: E402

failures = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        failures.append(label)


def keys(findings):
    return sorted({f.key for f in findings})


TABLE = """Source: pdfplumber
Page: 7
Label: Table 4
Parameter | B | SE | t | Sig. | Lower bound | Upper bound
Table 4a |  |  |  |  |  |
Intercept Ln(a) | -1.303 | 0.091 | -14.263 | <0.001 | -1.482 | -1.124
Ln(FFMkg) | 0.643 | 0.022 | 29.683 | <0.001 | 0.6 | 0.685
Age2 | -1.02E04 | 2.11E-06 | -48.644 | <0.001 | -1.07E-04 | -9.83E-05
R squared=0.727; AIC=-1986.63
Table 4b |  |  |  |  |  |
Ln(mass.kg) | 0.636 | 0.021 | 30.19 | <0.001 | 0.595 | 0.678
R squared=0.733; AIC=-2077.4
"""

TABLE_3 = """Source: pdfplumber
Page: 6
Label: Table 3
Parameter | B | SE | T | Sig. | Lower bound | Upper bound
Table 3a |  |  |  |  |  |
Ln(FFM)(b) | 1.178 | 0.017 | 67.348 | <0.001 | 1.143 | 1.212
R squared=0.536
"""

# A correlation matrix has no interval columns and must never be read as one.
MATRIX = """Source: pdfplumber_text
Page: 19
Label: Table 2
1 2 3 4 5
1. interest-boredom 1.00
2. competence-incompetence 0.55 1.00
3. honor-guilt 0.67 0.60 1.00
"""

print("\nEstimate outside its own interval")

f = mc.estimate_outside_interval("", [TABLE])
check("a lost exponent minus is caught", "estimate_outside_interval" in keys(f), keys(f))
check("only the faulty row fires", len(f) == 1, [x.line() for x in f])
check("a correlation matrix produces nothing",
      mc.estimate_outside_interval("", [MATRIX]) == [])
check("a row label containing a number is not the estimate",
      mc.estimate_outside_interval("", ["""Label: Table 3
Parameter | B | Lower bound | Upper bound
(Agegroup=20.00) | 0.601 | 0.56 | 0.642
"""]) == [])

prose = ("Additionally, the Root Mean Square Error of Approximation (RMSEA) was "
         "0.86, with a 90% confidence interval of [0.06, 0.11].")
check("a prose estimate outside its interval is caught",
      "estimate_outside_interval" in keys(mc.estimate_outside_interval(prose)))
check("a prose estimate inside its interval is not",
      mc.estimate_outside_interval(
          "The RMSEA was 0.086, with a 90% confidence interval of [0.06, 0.11].") == [])

print("\nCriteria the manuscript sets for itself")

criteria = ("Model fit was considered acceptable if fit indices approximated the "
            "following criteria: CFI > 0.9, TLI > 0.95, RMSEA < 0.10 and SRMR < 0.08. "
            "The model indicated an acceptable fit, as evidenced by a CFI of 0.94 "
            "and a TLI of 0.92. The RMSEA was 0.086.")
f = mc.stated_criteria(criteria)
found = {x.key + ":" + x.label.split()[0] for x in f}
check("an index failing the manuscript's own threshold is caught",
      "criterion_not_met:TLI" in found, sorted(found))
check("an index declared and never reported is caught",
      "criterion_not_reported:SRMR" in found, sorted(found))
check("an index that passes is not reported", "criterion_not_met:CFI" not in found)
check("RMSEA passes the manuscript's own 0.10 and is not reported",
      "criterion_not_met:RMSEA" not in found, sorted(found))
check("a threshold split across the colon is still found", len(f) == 2, [x.line() for x in f])
check("a lower-case word before a threshold is not an index",
      mc.stated_criteria("Studies were excluded by the criteria if the score < 5.") == [])

print("\nCategory percentages")

f = mc.percentage_sums(
    "Participants were admitted for acute myocardial infarction (60%), coronary "
    "artery bypass grafting (14%), percutaneous cardiac intervention (66%), "
    "valvular replacement (10%), or other CVD reasons (13%).")
check("a list summing to 163% is caught", len(f) == 1, [x.line() for x in f])
check("a list summing to 100% is not",
      mc.percentage_sums("Participants were male (60%), female (39%), or other (1%).") == [])
check("posterior probabilities are not category shares",
      mc.percentage_sums(
          "There are high probabilities of positive relationships with shoulder-width "
          "(100%), arm span (100%), and seated-height (99.95%).") == [])

print("\nValues attributed to the wrong table")

text = ("Table 3a gives the FFM exponent to be b=0.643 (95% CI 0.60 to 0.685) with an "
        "explained variance R2=0.727 and an AIC=-1986.63. ")
f = mc.table_cross_references(text, [TABLE, TABLE_3])
check("a mislabelled cross-reference is caught", len(f) == 1, [x.line() for x in f])
check("the finding names the table the values belong to",
      f and "table 4a" in f[0].label, f[0].label if f else "")
check("values grouped into one finding, not one each",
      f and "5 value(s)" in f[0].label, f[0].label if f else "")
check("a correct cross-reference produces nothing",
      mc.table_cross_references(
          "Table 4a gives the FFM exponent as 0.643 with an AIC=-1986.63. ",
          [TABLE, TABLE_3]) == [])

print("\nAn operator the font cannot render")

f = mc.unsuitable_math_glyph("3.3 ‧ 4 and 2 ‧ 5 and 7 ‧ 9 with 1 · 2")
check("a hyphenation point used as a multiplication sign is caught", len(f) == 1)
check("one stray occurrence is not enough",
      mc.unsuitable_math_glyph("3.3 ‧ 4 with 1 · 2 and 5 · 6") == [])
check("ordinary operators are ignored",
      mc.unsuitable_math_glyph("3.3 · 4 ⋅ 5 × 6") == [])

print("\nPlaceholders, with the blinding excluded")

blinded = ("This work was funded by XXXX Grant XXX-XX-XXX from the XXX. "
           "For comments, contact me at xxxxxx@xxxxxx.xxx.xxx. "
           "This spreadsheet was used to perform all the calculations reported in XXXXXXX.")
check("review blinding is not reported", mc.placeholder_warning(blinded) == [],
      [x.line() for x in mc.placeholder_warning(blinded)])
artefact = "As shown in Error! Reference source not found, the effect was small."
check("a genuine authoring artefact is reported",
      "authoring_artefact" in keys(mc.placeholder_warning(artefact)))

print("\nWhat to say when a quotation will not verify")

source = "Table 3a gives the FFM exponent with an explained variance and an AIC=-1986.63."
msg = mc.numeric_fallback("Table 3a (AIC = -1986.63)", source)
check("a failed quotation whose numbers are present says so",
      msg and "every value it cites" in msg, msg)
msg2 = mc.numeric_fallback("the coefficient was -0.999", source)
check("a failed quotation whose numbers are absent says that instead",
      msg2 and "none of the values" in msg2, msg2)
check("a quotation with no numbers returns nothing",
      mc.numeric_fallback("a plausible sounding phrase", source) is None)

print("\nThe check that is not shipped")

check("duplicated_sentences is excluded from run_all",
      "duplicated_sentence" not in keys(mc.run_all(
          "The same thing was measured. The same thing was measured.")))

print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    sys.exit(1)
print("All checks passed.")
