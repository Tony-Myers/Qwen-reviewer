import json
import re
import shutil
import subprocess
import tempfile
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



print("\n[a methodological check that could not be completed is labelled as such]")

node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run.")
else:
    page_functions = re.findall(r"^function \w+\(.*?\n}\n", html, re.S | re.M)

    def render(expression):
        script = "\n".join(page_functions) + (
            f"\nprocess.stdout.write({expression});")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
        run = subprocess.run([node, f.name], capture_output=True, text=True,
                             timeout=30)
        Path(f.name).unlink()
        if run.returncode != 0:
            print(run.stderr)
        return run.stdout

    NOT_ESTABLISHED = "methodological_consistency_not_established"
    passage = {"note": "Missing Data", "heading": "Imputations", "score": 0.4}

    def methodology(error=None):
        result = {"status": NOT_ESTABLISHED, "passages": [passage],
                  "reasons": ["Synthetic reason."]}
        if error:
            result["assessment_error"] = error
        return result

    def technical(error=None):
        return {"claim": {"statement": "A claim."},
                "verification": {"status": "not_technically_verified", "reasons": []},
                "methodological_consistency": methodology(error)}

    def context(error=None):
        return {"claim_statement": "A claim.", "source_sentence": "A sentence.",
                "context_excerpt": "Context.", "material_restriction_omitted": True,
                "contextual_methodological_consistency": methodology(error)}

    ERROR = "ClaimAssessorOutputError: synthetic"
    failed_technical = render(
        f"renderAcademicTechnicalClaim({json.dumps(technical(ERROR))}, 0)")
    valid_technical = render(
        f"renderAcademicTechnicalClaim({json.dumps(technical())}, 0)")
    failed_context = render(
        f"renderAcademicClaimContext({json.dumps(context(ERROR))}, 0)")
    valid_context = render(
        f"renderAcademicClaimContext({json.dumps(context())}, 0)")

    check(
        "Methodological check not completed" in failed_technical
        and "Methodological consistency not established" not in failed_technical,
        "failed standalone check: 'Methodological check not completed'",
    )
    check(
        "Methodological consistency not established" in valid_technical
        and "not completed" not in valid_technical,
        "valid standalone 'not established' keeps its existing label",
    )
    check(
        "Methodological check not completed" in failed_context
        and "Methodological consistency not established" not in failed_context,
        "failed contextual check: 'Methodological check not completed'",
    )
    check(
        "Methodological consistency not established" in valid_context
        and "not completed" not in valid_context,
        "valid contextual 'not established' keeps its existing label",
    )

    diagnostics = render("renderCheckFurtherDiagnostics(" + json.dumps({
        "rules_version": "4",
        "counts": {"not_established": 0, "failed_methodology_checks": 1},
        "lost_conditions": [{
            "answer_sentence": "A sentence.", "atomic_claim": "A claim.",
            "contextual_status": NOT_ESTABLISHED,
            "contextual_assessment_error": ERROR}],
        "failed_methodology_checks": [{
            "statement": "A claim.", "answer_text": "A sentence.",
            "contextual": True, "assessment_error": ERROR, "sections": []}],
    }) + ")")
    check(
        "Methodological checks not completed" in diagnostics and ERROR in diagnostics,
        "technical diagnostics list the failed check with its error",
    )
    check(
        "Contextual status: check not completed" in diagnostics,
        "a lost condition whose contextual check failed says so",
    )


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat methodology-UI checks passed.")
