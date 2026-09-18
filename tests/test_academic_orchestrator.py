"""Regression tests for first-stage Academic Chat orchestration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import academic_orchestrator
import academic_technical
from academic_tools import AcademicReferenceResult, VerificationResult


fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


SECRET = "CONFIDENTIAL-QUESTION-TEXT-7F3A"

question = (
    "Explain the relationship between multiple-imputation efficiency and "
    f"missing information. Private marker: {SECRET}"
)

draft_calls = []
verification_calls = []
technical_calls = []


def fake_draft_generator(model, tokenizer, supplied_question):
    draft_calls.append(
        {
            "model": model,
            "tokenizer": tokenizer,
            "question": supplied_question,
        }
    )

    return academic_chat.AcademicDraft(
        answer_draft="A provisional local answer.",
        references=[
            academic_chat.AcademicReference(
                title="Example Academic Work",
                author="A. Researcher",
                year=2020,
                venue="Example Journal",
                doi="10.1234/example",
            ),
            academic_chat.AcademicReference(
                title="Second Work",
                author=None,
                year=None,
                venue=None,
                doi=None,
            ),
        ],
        technical_claims=[
            academic_chat.TechnicalClaim(
                type="formula",
                concept="Example relationship",
                statement="x = y / z",
                parameterisation="x = y / z",
            )
        ],
    )


def fake_reference_verifier(**kwargs):
    verification_calls.append(dict(kwargs))

    return AcademicReferenceResult(
        crossref_verification=VerificationResult(
            status="verified",
            candidate=None,
            reasons=["Synthetic offline test result."],
        ),
        doi_corroboration=None,
        related_corroboration=None,
        identity_conflict=False,
        reasons=["Synthetic offline test result."],
    )


def fake_technical_verifier(claim):
    technical_calls.append(claim)

    return academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_VERIFIED,
        verifier="synthetic_test_verifier",
        canonical_claim="x = y / z",
        reasons=["Synthetic deterministic technical verification."],
    )


model = object()
tokenizer = object()

result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=fake_reference_verifier,
    technical_verifier=fake_technical_verifier,
)


print("\n[1] complete question stays with local draft stage")

check(
    len(draft_calls) == 1,
    "local draft generator called exactly once",
)

check(
    draft_calls[0]["question"] == question,
    "complete question reaches local draft generator",
)

check(
    SECRET in draft_calls[0]["question"],
    "confidential marker reaches local draft generator",
)


print("\n[2] external verification boundary is bibliographic only")

check(
    len(verification_calls) == 2,
    "each proposed reference is verified exactly once",
)

expected_fields = {
    "title",
    "author",
    "year",
    "venue",
    "doi",
}

check(
    all(set(call) == expected_fields for call in verification_calls),
    "reference verifier receives exactly the five bibliographic fields",
)

serialized_verifier_calls = repr(verification_calls)

check(
    SECRET not in serialized_verifier_calls,
    "full-question confidential marker never reaches reference verifier",
)

check(
    question not in serialized_verifier_calls,
    "full question never reaches reference verifier",
)


print("\n[3] model proposal remains auditable beside verification")

check(
    len(result.references) == 2,
    "both proposed references retained",
)

check(
    result.references[0].proposed_reference.title
    == "Example Academic Work",
    "original proposed title retained",
)

check(
    result.references[0].proposed_reference.doi
    == "10.1234/example",
    "original proposed DOI retained",
)

check(
    result.references[0].verification.crossref_verification.status
    == "verified",
    "bibliographic verification result retained separately",
)

check(
    result.references[0].verification.claim_verified is False,
    "bibliographic result does not become claim verification",
)


print("\n[4] technical verifier receives structured claim only")

check(
    len(technical_calls) == 1,
    "technical verifier called exactly once for each technical claim",
)

check(
    isinstance(technical_calls[0], academic_chat.TechnicalClaim),
    "technical verifier receives a TechnicalClaim object",
)

check(
    technical_calls[0].statement == "x = y / z",
    "technical verifier receives original structured claim",
)

serialized_technical_calls = repr(
    [technical_claim.to_dict() for technical_claim in technical_calls]
)

check(
    SECRET not in serialized_technical_calls,
    "full-question confidential marker never reaches technical verifier",
)

check(
    question not in serialized_technical_calls,
    "full question never reaches technical verifier",
)


print("\n[5] technical claim remains auditable beside verification")

check(
    len(result.technical_claims) == 1,
    "technical claim retained",
)

check(
    result.technical_claims[0].claim.statement == "x = y / z",
    "technical claim statement retained unchanged",
)

check(
    result.technical_claims[0].verification.status
    == academic_technical.TECHNICAL_STATUS_VERIFIED,
    "technical verification status retained separately",
)

check(
    result.technical_claims[0].verification.verifier
    == "synthetic_test_verifier",
    "technical verifier identity retained",
)

check(
    result.technical_claims[0].verification.canonical_claim
    == "x = y / z",
    "canonical technical claim retained",
)


print("\n[6] serialised result preserves the same boundaries")

payload = result.to_dict()

check(
    payload["answer_draft"] == "A provisional local answer.",
    "answer draft serialises",
)

check(
    payload["references"][0]["proposed_reference"]["title"]
    == "Example Academic Work",
    "proposed reference serialises separately from verification",
)

check(
    payload["technical_claims"][0]["claim"]["statement"]
    == "x = y / z",
    "original technical claim serialises",
)

check(
    payload["technical_claims"][0]["verification"]["status"]
    == "technically_verified",
    "technical verification status serialises separately",
)

check(
    payload["technical_claims"][0]["verification"]["verifier"]
    == "synthetic_test_verifier",
    "technical verifier provenance serialises",
)



print("\n[7] orchestration includes release assessment")

check(
    result.release.status == "release_allowed",
    "verified technical claims produce release-allowed status",
)

check(
    result.release.safe_to_present is True,
    "verified technical claims are safe to present",
)

payload = result.to_dict()

check(
    payload["release"]["status"] == "release_allowed",
    "release status serialises with orchestration result",
)

check(
    payload["release"]["safe_to_present"] is True,
    "safe-to-present flag serialises with orchestration result",
)

print("\n[8] technical conflict propagates to blocked release")

def conflicting_technical_verifier(claim):
    return academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_CONFLICT,
        verifier="synthetic_conflict_verifier",
        canonical_claim="x = z",
        reasons=["Synthetic deterministic technical conflict."],
    )


conflict_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=fake_reference_verifier,
    technical_verifier=conflicting_technical_verifier,
)

check(
    conflict_result.release.status == "blocked_technical_conflict",
    "technical conflict propagates to blocked release",
)

check(
    conflict_result.release.safe_to_present is False,
    "technical conflict prevents presentation",
)

conflict_payload = conflict_result.to_dict()

check(
    conflict_payload["release"]["status"] == "blocked_technical_conflict",
    "blocked release status serialises",
)

check(
    conflict_payload["release"]["safe_to_present"] is False,
    "blocked safe-to-present flag serialises",
)

check(
    conflict_payload["answer_draft"] == "A provisional local answer.",
    "blocked draft remains available for auditability",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat orchestration checks passed.")
