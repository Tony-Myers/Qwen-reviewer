from pathlib import Path

html = Path("app/chat.html").read_text()

fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[Academic Chat exposes methodological assessment]")

start = html.find("function renderAcademicTechnicalClaim")
end = html.find("function academicVerificationSummary", start)
renderer = html[start:end]

check(
    start >= 0 and end > start,
    "Academic technical-claim renderer is located",
)

check(
    "item?.methodological_consistency" in renderer,
    "technical-claim renderer consumes methodological consistency",
)

check(
    "Methodological check:" in renderer,
    "methodological status is exposed",
)

check(
    "academicReasons(methodology.reasons)" in renderer,
    "methodological reasons are exposed",
)

check(
    "Guidance considered for this claim" in renderer,
    "guidance provenance is exposed",
)

check(
    "passage?.note" in renderer and "passage?.heading" in renderer,
    "reviewer-note identity and heading are exposed",
)

check(
    "passage?.text" not in renderer,
    "full local guidance text is not rendered into the audit UI",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat methodology-UI checks passed.")
