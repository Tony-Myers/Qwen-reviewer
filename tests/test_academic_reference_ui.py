from pathlib import Path

html = Path("app/chat.html").read_text()

fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[academic reference UI reports unavailable corroboration]")

start = html.find("function renderAcademicReference(")
end = html.find("function renderAcademicSourceClaim(", start)
reference_function = html[start:end]

check(
    start >= 0 and end > start,
    "Academic reference renderer is located",
)

check(
    "verification.corroboration_status === 'unavailable'"
    in reference_function,
    "reference renderer uses structured corroboration status",
)

check(
    "Independent corroboration unavailable."
    in reference_function,
    "unavailable independent corroboration is visible to the user",
)

check(
    "verification.bibliographic_notice"
    in reference_function,
    "warning renders the application-owned bibliographic distinction",
)

check(
    "Source retrieval was not attempted."
    in reference_function,
    "warning explains that source retrieval was not completed",
)

check(
    "Retry Academic Chat to attempt these checks again."
    not in reference_function,
    "warning does not misdescribe every failure as transient",
)

check(
    "Bibliographic identity verified"
    in reference_function,
    "successful Crossref verification remains separately visible",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat reference-UI checks passed.")
