"""Static checks for the application's documented privacy/network boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
HTML = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")
SERVER = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
ORCHESTRATOR = (ROOT / "app" / "academic_orchestrator.py").read_text(
    encoding="utf-8"
)

failures = 0


def check(label, condition, detail=""):
    global failures
    if condition:
        print(f"  PASS  {label}")
    else:
        failures += 1
        print(f"  FAIL  {label}" + (f"   {detail}" if detail else ""))


print("\n[documented privacy boundary]")

check(
    "README still guarantees manuscript text remains local",
    "No manuscript text leaves the machine" in README,
)

check(
    "README no longer claims the whole application makes no API calls",
    "there are no API calls to anyone" not in README,
    "Academic Chat now uses scholarly metadata and source services",
)

check(
    "README names Academic Chat external scholarly services",
    "Crossref" in README and "OpenAlex" in README,
)

check(
    "README distinguishes external lookup from local model inference",
    "bibliographic" in README.lower()
    and "local model" in README.lower(),
)

print("\n[enforced Academic Chat boundary]")

check(
    "server documents that the complete question is local-only",
    "The complete question is passed only to the local model." in SERVER,
)

check(
    "orchestrator limits external verification to bibliographic metadata",
    "External reference verification receives bibliographic metadata only."
    in ORCHESTRATOR,
)

print("\n[local interface]")

check(
    "chat UI loads no Google-hosted fonts",
    "fonts.googleapis.com" not in HTML
    and "fonts.gstatic.com" not in HTML,
    "opening the local UI should not contact Google for typography",
)

if failures:
    raise SystemExit(f"\n{failures} FAILURE(S)")

print("\nAll privacy-boundary checks passed.")
