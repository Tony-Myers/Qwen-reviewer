"""Regression tests for application-owned per-concern evidence labels."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import review_pipeline as rp


SOURCE = """
The participants completed three trials under each condition.
Subgroup analyses were adjusted for multiple comparisons.
The intervention improved mean performance by 2.50 seconds.
"""

TABLE_SOURCE = """
Table 2
Condition    Mean change
Intervention    2.50
"""


def concern(title, evidence, supplied_label=""):
    label = f"\n* {supplied_label}" if supplied_label else ""
    return (
        f"* **Concern:** {title}\n"
        f"* **Evidence:** {evidence}"
        f"{label}\n"
    )


def report(*concerns):
    return (
        "# Overall synopsis\n"
        "* Test report.\n\n"
        "# Directly supported concerns\n\n"
        + "\n".join(concerns)
        + "\n# Verification prompts\n"
        "* **Check:** Something else.\n"
    )


fails = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        fails.append(label)


print("\n[invented quotation cannot promote itself]")
text = report(
    concern(
        "Invented evidence.",
        '"This sentence was never in the manuscript."',
        "Confidence: High — supplied by the model.",
    )
)
out = rp.annotate_concern_confidence(text, SOURCE, TABLE_SOURCE)
check("model Confidence field is removed", "Confidence:" not in out)
check("invented quotation is recomputed Low",
      "Evidence match: Low" in out)


print("\n[real quotation cannot demote itself]")
text = report(
    concern(
        "Located evidence.",
        '"The participants completed three trials under each condition."',
        "Confidence: Low — supplied by the model.",
    )
)
out = rp.annotate_concern_confidence(text, SOURCE, TABLE_SOURCE)
check("old Confidence field is removed", "Confidence:" not in out)
check("located quotation is recomputed High",
      "Evidence match: High" in out)


print("\n[one supplied label cannot suppress other concerns]")
text = report(
    concern(
        "First concern.",
        '"The participants completed three trials under each condition."',
        "Confidence: Low — supplied by the model.",
    ),
    concern(
        "Second concern.",
        '"Subgroup analyses were adjusted for multiple comparisons."',
    ),
)
out = rp.annotate_concern_confidence(text, SOURCE, TABLE_SOURCE)
check("both concerns receive labels",
      out.count("* Evidence match:") == 2,
      f"found {out.count('* Evidence match:')}")
check("both located quotations are independently High",
      out.count("* Evidence match: High") == 2,
      f"found {out.count('* Evidence match: High')}")


print("\n[model-supplied Evidence match is also untrusted]")
text = report(
    concern(
        "Invented evidence.",
        '"Another sentence absent from the manuscript."',
        "Evidence match: High — supplied by the model.",
    )
)
out = rp.annotate_concern_confidence(text, SOURCE, TABLE_SOURCE)
check("exactly one evidence-match field remains",
      out.count("* Evidence match:") == 1,
      f"found {out.count('* Evidence match:')}")
check("model Evidence match is replaced",
      "Evidence match: High — supplied by the model." not in out)
check("replacement is deterministic Low",
      "Evidence match: Low" in out)


print("\n[duplicate model labels collapse to one application label]")
text = report(
    (
        "* **Concern:** Duplicate labels.\n"
        '* **Evidence:** "The participants completed three trials under each condition."\n'
        "* Confidence: Low — supplied by the model.\n"
        "* Evidence match: Low — also supplied by the model.\n"
    )
)
out = rp.annotate_concern_confidence(text, SOURCE, TABLE_SOURCE)
check("legacy Confidence is removed", "Confidence:" not in out)
check("one application-owned label remains",
      out.count("* Evidence match:") == 1,
      f"found {out.count('* Evidence match:')}")
check("verified evidence determines the value",
      "Evidence match: High" in out)


if fails:
    print(f"\nFAILED: {len(fails)} check(s)")
    raise SystemExit(1)

print("\nPASS: evidence-match labels are application-owned and recomputed")
