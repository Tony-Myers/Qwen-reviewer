from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import academic_claims
import academic_methodology
import academic_orchestrator
import academic_technical
import reviewer_notes

try:
    import academic_reconciliation
except ImportError:
    academic_reconciliation = None


fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[academic reconciliation correction extraction]")

check(
    academic_reconciliation is not None,
    "academic reconciliation module exists",
)

if academic_reconciliation is not None:
    technical_claim = academic_chat.TechnicalClaim(
        type="formula",
        concept="multiple imputation relative efficiency",
        statement="RE = 1 + lambda/M",
        parameterisation=(
            "lambda is the fraction of missing information; "
            "M is the number of imputations"
        ),
    )

    technical_conflict = academic_orchestrator.TechnicalClaimResult(
        claim=technical_claim,
        verification=academic_technical.TechnicalVerification(
            status=academic_technical.TECHNICAL_STATUS_CONFLICT,
            verifier="synthetic_deterministic_verifier",
            canonical_claim="RE = 1 / (1 + lambda/M)",
            reasons=["MODEL MUST NOT RECEIVE THIS TECHNICAL AUDIT REASON"],
        ),
        methodological_consistency=None,
    )

    methodological_claim = academic_chat.TechnicalClaim(
        type="interpretation",
        concept="highest-density interval",
        statement="A skewed posterior necessarily has a narrower HDI than ETI.",
        parameterisation=None,
    )

    passage = reviewer_notes.Passage(
        note="Bayesian guidance",
        heading="Credible intervals",
        text=(
            "An HDI should not be assumed to be narrower than an ETI "
            "merely because the posterior is skewed."
        ),
        score=0.42,
    )

    methodological_conflict = academic_orchestrator.TechnicalClaimResult(
        claim=methodological_claim,
        verification=academic_technical.TechnicalVerification(
            status=academic_technical.TECHNICAL_STATUS_NOT_VERIFIED,
            verifier=None,
            canonical_claim=None,
            reasons=["Not deterministically checked."],
        ),
        methodological_consistency=(
            academic_methodology.MethodologicalConsistencyResult(
                status=academic_methodology.METHODOLOGICAL_STATUS_CONFLICT,
                claim=methodological_claim,
                passages=[passage],
                reasons=[
                    "MODEL MUST NOT RECEIVE THIS METHODOLOGY ASSESSOR REASON"
                ],
            )
        ),
    )

    evidence = academic_claims.ClaimEvidence(
        text="The reported effect was smaller than the generated claim states.",
        locator="synthetic.pdf#page=4",
        source="synthetic_source",
        page_number=4,
    )

    source_claim = academic_chat.SourceClaim(
        claim="The study reported a large effect.",
        reference_index=0,
    )

    source_conflict = object.__new__(
        academic_orchestrator.SourceClaimResult
    )
    source_conflict.claim = source_claim
    source_conflict.reference = None
    source_conflict.retrieval_identity = None
    source_conflict.source_discovery = None
    source_conflict.source_retrieval = None
    source_conflict.claim_location = None
    source_conflict.claim_assessment = academic_claims.ClaimAssessmentResult(
        status="claim_contradicted",
        claim=source_claim.claim,
        evidence=[evidence],
        reasons=["MODEL MUST NOT RECEIVE THIS SOURCE ASSESSOR REASON"],
    )

    corrections = academic_reconciliation.extract_academic_corrections(
        technical_claims=[
            technical_conflict,
            methodological_conflict,
        ],
        source_claims=[source_conflict],
    )

    check(
        len(corrections.technical) == 1,
        "deterministic technical conflict becomes one correction",
    )
    check(
        corrections.technical[0].claim is technical_claim,
        "technical correction retains original structured claim",
    )
    check(
        corrections.technical[0].canonical_claim
        == "RE = 1 / (1 + lambda/M)",
        "technical correction exposes canonical deterministic claim",
    )

    check(
        len(corrections.methodological) == 1,
        "methodological conflict becomes one correction",
    )
    check(
        corrections.methodological[0].claim is methodological_claim,
        "methodological correction retains original structured claim",
    )
    check(
        corrections.methodological[0].passages == [passage],
        "methodological correction retains application-owned guidance",
    )

    check(
        len(corrections.source) == 1,
        "source contradiction becomes one correction",
    )
    check(
        corrections.source[0].claim == source_claim.claim,
        "source correction retains original atomic source claim",
    )
    check(
        corrections.source[0].evidence == [evidence],
        "source correction retains application-owned located evidence",
    )

    payload = corrections.to_dict()
    payload_text = repr(payload)

    check(
        "MODEL MUST NOT RECEIVE THIS TECHNICAL AUDIT REASON"
        not in payload_text,
        "technical verifier reason is excluded from correction payload",
    )
    check(
        "MODEL MUST NOT RECEIVE THIS METHODOLOGY ASSESSOR REASON"
        not in payload_text,
        "methodology assessor reason is excluded from correction payload",
    )
    check(
        "MODEL MUST NOT RECEIVE THIS SOURCE ASSESSOR REASON"
        not in payload_text,
        "source assessor reason is excluded from correction payload",
    )

    nonblocking_technical = academic_orchestrator.TechnicalClaimResult(
        claim=technical_claim,
        verification=academic_technical.TechnicalVerification(
            status=academic_technical.TECHNICAL_STATUS_NOT_VERIFIED,
            verifier=None,
            canonical_claim=None,
            reasons=["No deterministic verification."],
        ),
        methodological_consistency=(
            academic_methodology.MethodologicalConsistencyResult(
                status=(
                    academic_methodology
                    .METHODOLOGICAL_STATUS_NOT_ESTABLISHED
                ),
                claim=technical_claim,
                passages=[passage],
                reasons=["Insufficient guidance."],
            )
        ),
    )

    nonblocking_source = object.__new__(
        academic_orchestrator.SourceClaimResult
    )
    nonblocking_source.claim = source_claim
    nonblocking_source.reference = None
    nonblocking_source.retrieval_identity = None
    nonblocking_source.source_discovery = None
    nonblocking_source.source_retrieval = None
    nonblocking_source.claim_location = None
    nonblocking_source.claim_assessment = academic_claims.ClaimAssessmentResult(
        status="claim_not_supported",
        claim=source_claim.claim,
        evidence=[evidence],
        reasons=["Evidence does not substantiate the claim."],
    )

    empty = academic_reconciliation.extract_academic_corrections(
        technical_claims=[nonblocking_technical],
        source_claims=[nonblocking_source],
    )

    check(
        not empty.technical
        and not empty.methodological
        and not empty.source,
        "non-blocking uncertainty and lack of support create no corrections",
    )


print("\n[academic reconciliation extraction boundaries]")

empty_input = academic_reconciliation.extract_academic_corrections(
    technical_claims=[],
    source_claims=[],
)

check(
    not empty_input.technical
    and not empty_input.methodological
    and not empty_input.source,
    "empty checked results produce an empty correction set",
)

second_technical_claim = academic_chat.TechnicalClaim(
    type="threshold",
    concept="multiple imputation 95% efficiency threshold",
    statement="M >= 10 * lambda",
    parameterisation="lambda is the fraction of missing information",
)

second_technical_conflict = academic_orchestrator.TechnicalClaimResult(
    claim=second_technical_claim,
    verification=academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_CONFLICT,
        verifier="synthetic_deterministic_verifier",
        canonical_claim="M >= 19 * lambda",
        reasons=["Second synthetic conflict."],
    ),
    methodological_consistency=None,
)

multiple = academic_reconciliation.extract_academic_corrections(
    technical_claims=[
        technical_conflict,
        second_technical_conflict,
    ],
    source_claims=[],
)

check(
    len(multiple.technical) == 2,
    "all deterministic technical conflicts are retained",
)

check(
    [
        item.canonical_claim
        for item in multiple.technical
    ]
    == [
        "RE = 1 / (1 + lambda/M)",
        "M >= 19 * lambda",
    ],
    "multiple technical corrections preserve input order",
)

missing_canonical = academic_orchestrator.TechnicalClaimResult(
    claim=technical_claim,
    verification=academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_CONFLICT,
        verifier="synthetic_deterministic_verifier",
        canonical_claim=None,
        reasons=["Synthetic malformed deterministic conflict."],
    ),
    methodological_consistency=None,
)

try:
    academic_reconciliation.extract_academic_corrections(
        technical_claims=[missing_canonical],
        source_claims=[],
    )
except ValueError as exc:
    missing_canonical_failed_closed = (
        "requires a canonical claim" in str(exc)
    )
else:
    missing_canonical_failed_closed = False

check(
    missing_canonical_failed_closed,
    "technical conflict without canonical correction fails closed",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll academic reconciliation boundary checks passed.")
