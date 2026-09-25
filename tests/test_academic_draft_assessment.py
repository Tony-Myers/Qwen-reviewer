from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import academic_orchestrator
import academic_technical


fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[academic draft assessment boundary]")

check(
    hasattr(academic_orchestrator, "assess_academic_draft"),
    "orchestrator exposes assessment of an already-generated AcademicDraft",
)

if hasattr(academic_orchestrator, "assess_academic_draft"):
    draft = academic_chat.AcademicDraft(
        answer_draft="Already generated answer.",
        references=[],
        source_claims=[],
        technical_claims=[
            academic_chat.TechnicalClaim(
                type="synthetic",
                concept="synthetic concept",
                statement="Synthetic structured claim.",
                parameterisation=None,
            )
        ],
    )

    guidance = academic_orchestrator.LocalGuidanceResult(passages=[])

    technical_calls = []

    def technical_verifier(claim):
        technical_calls.append(claim)
        return academic_technical.TechnicalVerification(
            status=academic_technical.TECHNICAL_STATUS_VERIFIED,
            verifier="synthetic_verifier",
            canonical_claim=claim.statement,
            reasons=["Synthetic verification."],
        )

    result = academic_orchestrator.assess_academic_draft(
        draft,
        local_guidance=guidance,
        technical_verifier=technical_verifier,
    )

    check(
        result.answer_draft == "Already generated answer.",
        "assessment preserves the supplied draft answer",
    )

    check(
        technical_calls == draft.technical_claims,
        "assessment checks structured claims from the supplied draft",
    )

    check(
        result.release.safe_to_present is True,
        "assessment produces the normal release decision",
    )

    check(
        result.local_guidance is guidance,
        "assessment preserves application-owned methodological guidance",
    )


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll AcademicDraft assessment-boundary checks passed.")
