from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_orchestrator
import academic_technical


fails = []


def check(condition, message):
    if condition:
        print(f"PASS: {message}")
    else:
        print(f"FAIL: {message}")
        fails.append(message)


def verification(status):
    return academic_technical.TechnicalVerification(
        status=status,
        verifier="synthetic_test_verifier",
        canonical_claim="canonical test claim",
        reasons=["Synthetic verification result."],
    )


def claim_result(status):
    return academic_orchestrator.TechnicalClaimResult(
        claim=__import__("academic_chat").TechnicalClaim(
            type="formula",
            concept="Synthetic technical concept",
            statement="x = y",
            parameterisation=None,
        ),
        verification=verification(status),
    )


print("\n[1] technical conflict blocks release")

release = academic_orchestrator.assess_academic_release(
    [claim_result(academic_technical.TECHNICAL_STATUS_CONFLICT)]
)

check(
    release.status == "blocked_technical_conflict",
    "technical conflict produces blocked release status",
)
check(
    release.safe_to_present is False,
    "technical conflict is not safe to present",
)
check(
    bool(release.reasons),
    "blocked release records a reason",
)


print("\n[2] verified claims permit release")

release = academic_orchestrator.assess_academic_release(
    [claim_result(academic_technical.TECHNICAL_STATUS_VERIFIED)]
)

check(
    release.status == "release_allowed",
    "verified technical claim permits release",
)
check(
    release.safe_to_present is True,
    "verified technical claim is safe to present",
)


print("\n[3] unverified claims do not become conflicts")

release = academic_orchestrator.assess_academic_release(
    [claim_result(academic_technical.TECHNICAL_STATUS_NOT_VERIFIED)]
)

check(
    release.status == "release_allowed_with_unverified_claims",
    "unverified claim is distinguished from conflict",
)
check(
    release.safe_to_present is True,
    "lack of deterministic coverage does not itself block release",
)
check(
    any("not technically verified" in reason.lower() for reason in release.reasons),
    "release assessment makes unverified technical claims visible",
)


print("\n[4] any conflict blocks a mixed result")

release = academic_orchestrator.assess_academic_release(
    [
        claim_result(academic_technical.TECHNICAL_STATUS_VERIFIED),
        claim_result(academic_technical.TECHNICAL_STATUS_NOT_VERIFIED),
        claim_result(academic_technical.TECHNICAL_STATUS_CONFLICT),
    ]
)

check(
    release.status == "blocked_technical_conflict",
    "one conflict blocks release despite other claim statuses",
)
check(
    release.safe_to_present is False,
    "mixed result containing conflict is not safe to present",
)


print("\n[5] no technical claims permit release")

release = academic_orchestrator.assess_academic_release([])

check(
    release.status == "release_allowed",
    "absence of technical claims does not block release",
)
check(
    release.safe_to_present is True,
    "answer without technical claims remains presentable",
)


print("\n[6] release assessment serialises independently")

payload = academic_orchestrator.assess_academic_release(
    [claim_result(academic_technical.TECHNICAL_STATUS_CONFLICT)]
).to_dict()

check(
    payload["status"] == "blocked_technical_conflict",
    "release status serialises",
)
check(
    payload["safe_to_present"] is False,
    "safe-to-present flag serialises",
)
check(
    isinstance(payload["reasons"], list) and bool(payload["reasons"]),
    "release reasons serialise",
)




def source_claim_result(assessment_status):
    evidence = [
        __import__("academic_claims").ClaimEvidence(
            text="Synthetic located evidence.",
            locator="https://example.invalid/article.pdf",
            source="synthetic",
            page_number=1,
        )
    ]

    assessment = None
    if assessment_status is not None:
        assessment = __import__("academic_claims").ClaimAssessmentResult(
            status=assessment_status,
            claim="Synthetic source-backed claim.",
            evidence=evidence,
            reasons=["Synthetic source assessment."],
        )

    return type(
        "SyntheticSourceClaimResult",
        (),
        {"claim_assessment": assessment},
    )()


print("\n[7] source contradiction blocks unchanged draft")

release = academic_orchestrator.assess_academic_release(
    [],
    [source_claim_result("claim_contradicted")],
)

check(
    release.status == "blocked_source_contradiction",
    "source contradiction produces its own blocked release status",
)
check(
    release.safe_to_present is False,
    "source contradiction is not safe to present unchanged",
)


print("\n[8] source non-support does not become contradiction")

for source_status in (
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
    None,
):
    release = academic_orchestrator.assess_academic_release(
        [],
        [source_claim_result(source_status)],
    )
    check(
        release.safe_to_present is True,
        f"{source_status!r} does not block release",
    )


print("\n[9] deterministic conflict retains precedence over source contradiction")

release = academic_orchestrator.assess_academic_release(
    [claim_result(academic_technical.TECHNICAL_STATUS_CONFLICT)],
    [source_claim_result("claim_contradicted")],
)

check(
    release.status == "blocked_technical_conflict",
    "deterministic technical conflict retains release precedence",
)
check(
    release.safe_to_present is False,
    "combined technical and source conflicts remain blocked",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat release-assessment checks passed.")
