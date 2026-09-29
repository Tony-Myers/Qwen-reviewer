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


print("\n[original AcademicDraft retention]")

retained_draft = academic_chat.AcademicDraft(
    answer_draft="Retained original answer.",
    references=[],
    source_claims=[],
    technical_claims=[],
)

retained_guidance = academic_orchestrator.LocalGuidanceResult(
    passages=[]
)

retained_result = academic_orchestrator.assess_academic_draft(
    retained_draft,
    local_guidance=retained_guidance,
)

check(
    retained_result.draft is retained_draft,
    "assessment retains exact original AcademicDraft object",
)

check(
    retained_result.answer_draft == retained_draft.answer_draft,
    "answer_draft remains available through compatibility property",
)

retained_payload = retained_result.to_dict()

check(
    "draft" not in retained_payload,
    "internal AcademicDraft is not added to serialized API payload",
)

check(
    retained_payload["answer_draft"] == retained_draft.answer_draft,
    "serialized answer_draft remains unchanged",
)

expected_payload_keys = {
    "answer_draft",
    "local_guidance",
    "references",
    "source_claims",
    "technical_claims",
    "claim_context_assessments",
    "release",
}

check(
    set(retained_payload) == expected_payload_keys,
    "first-stage serialized API exposes only bounded public fields",
)

check(
    retained_payload["claim_context_assessments"] == [],
    "first-stage payload exposes no invented claim context",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll AcademicDraft assessment-boundary checks passed.")
