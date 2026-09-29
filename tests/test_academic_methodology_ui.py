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

print("\n[Academic Chat exposes occurrence-level claim context]")

context_start = html.find("function renderAcademicClaimContext")
context_end = html.find("function academicVerificationSummary", context_start)
context_renderer = html[context_start:context_end]

check(
    context_start >= 0 and context_end > context_start,
    "claim-context renderer is located",
)

check(
    "item?.material_restriction_omitted" in context_renderer,
    "claim-context renderer consumes material-restriction state",
)

check(
    "Material restriction omitted from the atomic claim." in context_renderer,
    "omitted material restriction is exposed explicitly",
)

check(
    "No material restriction omission detected." in context_renderer,
    "assessed negative restriction state remains explicit",
)

check(
    "Context restriction not assessed." in context_renderer,
    "unattempted restriction assessment remains distinct",
)

check(
    "Verified source sentence:" in context_renderer,
    "verified occurrence sentence is exposed",
)

check(
    "Bounded answer context:" in context_renderer,
    "bounded answer context is exposed without implying inheritance",
)

check(
    "Contextual methodological check:" in context_renderer,
    "contextual methodology is presented separately",
)

check(
    "Guidance considered in this context" in context_renderer,
    "contextual guidance provenance is exposed",
)

check(
    "passage?.note" in context_renderer
    and "passage?.heading" in context_renderer,
    "contextual reviewer-note provenance is exposed",
)

check(
    "passage?.text" not in context_renderer,
    "full local guidance text is not exposed in claim context",
)

audit_start = html.find("function renderAcademicAudit")
audit_end = html.find("function renderAcademicEvidence", audit_start)
audit_renderer = html[audit_start:audit_end]

check(
    "data.claim_context_assessments" in audit_renderer,
    "audit consumes bounded public claim-context assessments",
)

check(
    "renderAcademicClaimContext" in audit_renderer,
    "claim-context assessments are rendered in the detailed audit",
)

technical_start = html.find("function renderAcademicTechnicalClaim")
technical_end = html.find("function renderAcademicClaimContext", technical_start)
technical_renderer = html[technical_start:technical_end]

check(
    "Generated category:" in technical_renderer,
    "generated concept is labelled as a category rather than claim evidence",
)

summary_start = html.find("function academicVerificationSummary")
summary_end = html.find("function renderAcademicLocalGuidance", summary_start)
summary_renderer = html[summary_start:summary_end]

check(
    "claim_context_assessments" not in summary_renderer,
    "claim-context diagnosis does not become a top-level evidence verdict",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat methodology-UI checks passed.")
