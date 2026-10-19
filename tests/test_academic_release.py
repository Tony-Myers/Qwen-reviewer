from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_claim_coverage
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


def contextual_claim_assessment(status):
    academic_chat = __import__("academic_chat")
    academic_methodology = __import__("academic_methodology")

    claim = academic_chat.TechnicalClaim(
        type="interpretation",
        concept="Synthetic contextual concept",
        statement="Synthetic contextual claim.",
        parameterisation=None,
    )
    source_context = academic_claim_coverage.ClaimSourceContext(
        source_sentence="Synthetic contextual claim.",
        source_sentence_start=0,
        source_sentence_end=27,
        context_excerpt="Synthetic contextual claim.",
        context_start=0,
        context_end=27,
    )
    methodology = (
        academic_methodology.ContextualMethodologicalConsistencyResult(
            status=status,
            claim=claim,
            source_context=source_context,
            passages=[],
            reasons=["Synthetic contextual methodology result."],
        )
    )

    return academic_orchestrator.DiscoveredClaimAssessment(
        discovered_claim=academic_claim_coverage.DiscoveredClaim(
            claim=claim,
            source_anchor=claim.statement,
            source_start=0,
            source_end=len(claim.statement),
        ),
        source_context=source_context,
        material_restriction=(
            academic_claim_coverage.MaterialRestrictionAssessment(
                material_restriction_omitted=True,
            )
        ),
        contextual_methodological_consistency=methodology,
    )


print("\n[10] contextual methodological conflict is evidence, not a block")

release = academic_orchestrator.assess_academic_release(
    [],
    [],
    [contextual_claim_assessment("methodological_conflict")],
)

check(
    release.status == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
    "contextual methodological conflict keeps its own status",
)
check(
    release.safe_to_present is True,
    "contextual methodological conflict no longer withholds the answer",
)


print("\n[11] contextual non-conflict does not block release")

for methodology_status in (
    "methodologically_consistent",
    "methodological_consistency_not_established",
):
    release = academic_orchestrator.assess_academic_release(
        [],
        [],
        [contextual_claim_assessment(methodology_status)],
    )

    check(
        release.status == "release_allowed",
        f"contextual {methodology_status!r} permits release",
    )
    check(
        release.safe_to_present is True,
        f"contextual {methodology_status!r} is non-blocking",
    )



print("\n[12] unavailable claim coverage makes checking incomplete")

unavailable_coverage = academic_claim_coverage.ClaimCoverageAssessment.unavailable(
    "Synthetic claim-coverage failure."
)

release = academic_orchestrator.assess_academic_release(
    [],
    [],
    [],
    unavailable_coverage,
)

check(
    release.status == "checking_incomplete",
    "unavailable coverage produces explicit incomplete-check status",
)
check(
    release.safe_to_present is False,
    "incomplete claim checking is not automatically releasable",
)
check(
    any(
        "could not be completed" in reason.lower()
        for reason in release.reasons
    ),
    "incomplete release explains that checking could not be completed",
)


print("\n[13] established conflict retains precedence over unavailable coverage")

release = academic_orchestrator.assess_academic_release(
    [claim_result(academic_technical.TECHNICAL_STATUS_CONFLICT)],
    [],
    [],
    unavailable_coverage,
)

check(
    release.status == "blocked_technical_conflict",
    "established technical conflict retains precedence",
)
check(
    release.safe_to_present is False,
    "conflict plus incomplete coverage remains non-releasable",
)


print("\n[14] omitted coverage argument preserves legacy release contract")

release = academic_orchestrator.assess_academic_release([])

check(
    release.status == "release_allowed",
    "release callers that do not adjudicate coverage remain compatible",
)
check(
    release.safe_to_present is True,
    "omitted coverage state does not become an invented failure",
)


print(
    "\n[15] contextual assessment supersedes context-poor standalone methodology"
)

academic_chat = __import__("academic_chat")
academic_methodology = __import__("academic_methodology")

qualified_claim = academic_chat.TechnicalClaim(
    type="interpretation",
    concept="covariate adjustment in randomised trials",
    statement=(
        "Covariates should be adjusted for regardless of their baseline "
        "p-values."
    ),
    parameterisation=None,
)

standalone_conflict = academic_orchestrator.TechnicalClaimResult(
    claim=qualified_claim,
    verification=verification(
        academic_technical.TECHNICAL_STATUS_NOT_VERIFIED
    ),
    methodological_consistency=(
        academic_methodology.MethodologicalConsistencyResult(
            status=academic_methodology.METHODOLOGICAL_STATUS_CONFLICT,
            claim=qualified_claim,
            passages=[],
            reasons=["Synthetic context-poor conflict."],
        )
    ),
)


def paired_contextual_assessment(status):
    discovered = academic_claim_coverage.DiscoveredClaim(
        claim=qualified_claim,
        source_anchor=qualified_claim.statement,
        source_start=0,
        source_end=len(qualified_claim.statement),
    )
    source_context = academic_claim_coverage.ClaimSourceContext(
        source_sentence=(
            "The primary analysis should typically adjust for covariates "
            "used to stratify randomisation or known to be strongly "
            "prognostic, regardless of their baseline p-values."
        ),
        source_sentence_start=0,
        source_sentence_end=170,
        context_excerpt=(
            "Adjustment should be based on design or prognostic value, "
            "not selected according to baseline significance tests."
        ),
        context_start=0,
        context_end=140,
    )
    methodology = (
        academic_methodology.ContextualMethodologicalConsistencyResult(
            status=status,
            claim=qualified_claim,
            source_context=source_context,
            passages=[],
            reasons=["Synthetic occurrence-aware assessment."],
        )
    )

    return academic_orchestrator.DiscoveredClaimAssessment(
        discovered_claim=discovered,
        source_context=source_context,
        material_restriction=(
            academic_claim_coverage.MaterialRestrictionAssessment(
                material_restriction_omitted=True,
            )
        ),
        contextual_methodological_consistency=methodology,
    )


for contextual_status in (
    academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT,
    academic_methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
):
    release = academic_orchestrator.assess_academic_release(
        [standalone_conflict],
        [],
        [paired_contextual_assessment(contextual_status)],
    )

    check(
        release.safe_to_present is True,
        (
            "paired occurrence-aware "
            f"{contextual_status!r} keeps methodology advisory"
        ),
    )
    check(
        release.status == (
            "release_allowed_with_unverified_claims"
            if contextual_status == academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
            else academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT
        ),
        "only positive contextual consistency clears the standalone concern",
    )


print("\n[16] contextual conflict is still reported for a superseded standalone claim")

release = academic_orchestrator.assess_academic_release(
    [standalone_conflict],
    [],
    [
        paired_contextual_assessment(
            academic_methodology.METHODOLOGICAL_STATUS_CONFLICT
        )
    ],
)

check(
    release.status == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
    "occurrence-aware methodological conflict is still reported",
)
check(
    release.safe_to_present is True,
    "contextual conflict is presentable evidence, not a block",
)


print("\n[17] standalone conflict is still reported without contextual assessment")

unassessed_occurrence = paired_contextual_assessment(
    academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
)
unassessed_occurrence.contextual_methodological_consistency = None

release = academic_orchestrator.assess_academic_release(
    [standalone_conflict],
    [],
    [unassessed_occurrence],
)

check(
    release.status == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
    "standalone conflict is still reported when contextual checking is absent",
)
check(
    release.safe_to_present is True,
    "missing contextual assessment cannot neutralise a standalone conflict, "
    "which is reported without withholding the answer",
)



print(
    "\n[18] one assessed occurrence cannot supersede another unassessed occurrence"
)

assessed_occurrence = paired_contextual_assessment(
    academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
)

second_discovered = academic_claim_coverage.DiscoveredClaim(
    claim=qualified_claim,
    source_anchor=qualified_claim.statement,
    source_start=200,
    source_end=200 + len(qualified_claim.statement),
)

second_source_context = academic_claim_coverage.ClaimSourceContext(
    source_sentence=(
        "Eligible covariates should be selected for adjustment regardless "
        "of baseline significance testing."
    ),
    source_sentence_start=200,
    source_sentence_end=298,
    context_excerpt=(
        "A second occurrence of the same proposition requires its own "
        "occurrence-aware assessment."
    ),
    context_start=180,
    context_end=310,
)

unassessed_second_occurrence = academic_orchestrator.DiscoveredClaimAssessment(
    discovered_claim=second_discovered,
    source_context=second_source_context,
    material_restriction=(
        academic_claim_coverage.MaterialRestrictionAssessment(
            material_restriction_omitted=True,
        )
    ),
    contextual_methodological_consistency=None,
)

release = academic_orchestrator.assess_academic_release(
    [standalone_conflict],
    [],
    [
        assessed_occurrence,
        unassessed_second_occurrence,
    ],
)

check(
    release.status == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
    "one assessed occurrence does not suppress standalone conflict while "
    "another restricted occurrence remains unassessed",
)
check(
    release.safe_to_present is True,
    "the unsuppressed conflict is reported without withholding the answer",
)


print("\n[19] a contextual assessment that could not be completed supersedes nothing")

for contextual_status in (
    academic_methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
    academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT,
):
    failed_occurrence = paired_contextual_assessment(contextual_status)
    failed_occurrence.contextual_methodological_consistency.assessment_error = (
        "ClaimAssessorOutputError: synthetic unusable contextual judgement"
    )

    check(
        academic_orchestrator.reconcile_methodological_assessments(
            qualified_claim, standalone_conflict.methodological_consistency,
            [failed_occurrence],
        ).retain_standalone,
        f"a failed {contextual_status!r} contextual assessment does not count "
        "as completed",
    )

    release = academic_orchestrator.assess_academic_release(
        [standalone_conflict],
        [],
        [failed_occurrence],
    )

    check(
        release.status
        == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
        "the standalone conflict is still reported",
    )
    check(
        release.safe_to_present is True,
        "and it remains advisory: the answer is not withheld",
    )

check(
    academic_orchestrator.reconcile_methodological_assessments(
        qualified_claim, standalone_conflict.methodological_consistency,
        [
            paired_contextual_assessment(
                academic_methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED
            )
        ],
    ).retain_standalone,
    "completed not-established context leaves the conflict unresolved",
)


if fails:
    print(f"\n{len(fails)} release test(s) failed.")
    raise SystemExit(1)

print("\nAll academic release tests passed.")
