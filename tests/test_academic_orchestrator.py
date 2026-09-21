"""Regression tests for first-stage Academic Chat orchestration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import academic_claims
import academic_orchestrator
import academic_technical
from academic_tools import (
    AcademicReferenceResult,
    CorroborationResult,
    ReferenceCandidate,
    VerificationResult,
)


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
        source_claims=[
            academic_chat.SourceClaim(
                claim="Second Work reports the synthetic literature finding.",
                reference_index=1,
            )
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

check(
    len(verification_calls) == len(result.references),
    "source-claim resolution causes no additional reference verification",
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


print("\n[9] source claim resolves to its verified reference proposal")

check(
    len(result.source_claims) == 1,
    "source claim retained by orchestration",
)

check(
    result.source_claims[0].claim.claim
    == "Second Work reports the synthetic literature finding.",
    "original source claim retained unchanged",
)

check(
    result.source_claims[0].reference.proposed_reference.title
    == "Second Work",
    "source claim resolves to intended proposed reference",
)

check(
    result.source_claims[0].reference.verification
    is result.references[1].verification,
    "source claim carries intended bibliographic verification",
)


check(
    result.source_claims[0].retrieval_identity.status == "not_eligible",
    "source claim carries retrieval identity",
)

check(
    result.source_claims[0].retrieval_identity.doi is None,
    "source claim with uncorroborated reference exposes no retrieval DOI",
)

source_claim_payload = result.to_dict()["source_claims"][0]


check(
    source_claim_payload["retrieval_identity"]["status"] == "not_eligible",
    "retrieval identity status serialises",
)

check(
    source_claim_payload["retrieval_identity"]["doi"] is None,
    "ineligible retrieval identity serialises without DOI",
)

check(
    source_claim_payload["claim"]["claim"]
    == "Second Work reports the synthetic literature finding.",
    "source claim serialises unchanged",
)

check(
    source_claim_payload["reference"]["proposed_reference"]["title"]
    == "Second Work",
    "resolved source reference serialises explicitly",
)

check(
    "support_status" not in source_claim_payload
    and "claim_verified" not in source_claim_payload
    and "verified" not in source_claim_payload,
    "orchestration does not invent claim-support status",
)

check(
    result.source_claims[0].claim.reference_index == 1,
    "original model-proposed reference index remains auditable",
)


print("\n[10] conflicting bibliographic identities block retrieval")

doi_candidate = ReferenceCandidate(
    title="DOI Identity",
    authors=["A. Author"],
    year=2020,
    venue="Journal A",
    doi="10.1234/doi-identity",
    work_type="journal-article",
)

title_candidate = ReferenceCandidate(
    title="Title Identity",
    authors=["B. Author"],
    year=2021,
    venue="Journal B",
    doi="10.1234/title-identity",
    work_type="journal-article",
)

conflicting_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="metadata_conflict",
        candidate=doi_candidate,
        reasons=["Synthetic DOI/title metadata conflict."],
        related_candidate=title_candidate,
    ),
    doi_corroboration=CorroborationResult(
        status="corroborated",
        crossref=doi_candidate,
        openalex=doi_candidate,
        same_doi=True,
        title_similarity=1.0,
        author_agreement=True,
        venue_similarity=1.0,
        year_difference=0,
        reasons=["Synthetic DOI identity corroboration."],
    ),
    related_corroboration=CorroborationResult(
        status="corroborated",
        crossref=title_candidate,
        openalex=title_candidate,
        same_doi=True,
        title_similarity=1.0,
        author_agreement=True,
        venue_similarity=1.0,
        year_difference=0,
        reasons=["Synthetic title identity corroboration."],
    ),
    identity_conflict=True,
    reasons=["Synthetic identity conflict."],
)

retrieval_identity = academic_orchestrator.resolve_retrieval_identity(
    conflicting_reference
)

check(
    retrieval_identity.status == "not_eligible",
    "identity conflict blocks automatic source retrieval",
)

check(
    retrieval_identity.doi is None,
    "identity conflict exposes no DOI for automatic retrieval",
)


print("\n[11] coherent verified identity permits retrieval")

coherent_candidate = ReferenceCandidate(
    title="Coherent Work",
    authors=["A. Author"],
    year=2020,
    venue="Journal A",
    doi="10.1234/coherent",
    work_type="journal-article",
)

coherent_corroboration = CorroborationResult(
    status="corroborated",
    crossref=coherent_candidate,
    openalex=coherent_candidate,
    same_doi=True,
    title_similarity=1.0,
    author_agreement=True,
    venue_similarity=1.0,
    year_difference=0,
    reasons=["Synthetic coherent identity corroboration."],
)

coherent_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="verified",
        candidate=coherent_candidate,
        reasons=["Synthetic verified bibliographic identity."],
    ),
    doi_corroboration=coherent_corroboration,
    related_corroboration=coherent_corroboration,
    identity_conflict=False,
    reasons=["Synthetic coherent bibliographic identity."],
)

coherent_identity = academic_orchestrator.resolve_retrieval_identity(
    coherent_reference
)

check(
    coherent_identity.status == "eligible",
    "coherent verified identity permits automatic source retrieval",
)

check(
    coherent_identity.doi == "10.1234/coherent",
    "coherent retrieval identity exposes corroborated DOI",
)


print("\n[12] inconsistent corroboration blocks retrieval")

crossref_candidate = ReferenceCandidate(
    title="Inconsistent Work",
    authors=["A. Author"],
    year=2020,
    venue="Journal A",
    doi="10.1234/crossref-identity",
    work_type="journal-article",
)

openalex_candidate = ReferenceCandidate(
    title="Inconsistent Work",
    authors=["A. Author"],
    year=2020,
    venue="Journal A",
    doi="10.1234/openalex-identity",
    work_type="journal-article",
    source="openalex",
)

inconsistent_corroboration = CorroborationResult(
    status="corroborated",
    crossref=crossref_candidate,
    openalex=openalex_candidate,
    same_doi=True,
    title_similarity=1.0,
    author_agreement=True,
    venue_similarity=1.0,
    year_difference=0,
    reasons=["Synthetic internally inconsistent corroboration."],
)

inconsistent_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="verified",
        candidate=crossref_candidate,
        reasons=["Synthetic verified bibliographic identity."],
    ),
    doi_corroboration=inconsistent_corroboration,
    related_corroboration=None,
    identity_conflict=False,
    reasons=["Synthetic inconsistent corroboration fixture."],
)

inconsistent_identity = academic_orchestrator.resolve_retrieval_identity(
    inconsistent_reference
)

check(
    inconsistent_identity.status == "not_eligible",
    "mismatched underlying DOIs override corroborated status",
)

check(
    inconsistent_identity.doi is None,
    "inconsistent corroboration exposes no DOI for retrieval",
)


print("\n[13] DOI-only verified identity permits retrieval")

doi_only_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="verified",
        candidate=coherent_candidate,
        reasons=["Synthetic DOI-only verification."],
    ),
    doi_corroboration=coherent_corroboration,
    related_corroboration=None,
    identity_conflict=False,
    reasons=["Synthetic DOI-only corroborated identity."],
)

doi_only_identity = academic_orchestrator.resolve_retrieval_identity(
    doi_only_reference
)

check(
    doi_only_identity.status == "eligible",
    "verified DOI-only identity permits automatic source retrieval",
)

check(
    doi_only_identity.doi == "10.1234/coherent",
    "DOI-only retrieval uses cross-database corroborated DOI",
)


print("\n[14] title-only verified identity permits retrieval")

title_only_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="verified",
        candidate=coherent_candidate,
        reasons=["Synthetic title-only verification."],
    ),
    doi_corroboration=None,
    related_corroboration=coherent_corroboration,
    identity_conflict=False,
    reasons=["Synthetic title-only corroborated identity."],
)

title_only_identity = academic_orchestrator.resolve_retrieval_identity(
    title_only_reference
)

check(
    title_only_identity.status == "eligible",
    "verified title-only identity permits automatic source retrieval",
)

check(
    title_only_identity.doi == "10.1234/coherent",
    "title-only retrieval uses title-derived corroborated DOI",
)


print("\n[15] probable identity remains ineligible")

probable_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="probable",
        candidate=coherent_candidate,
        reasons=["Synthetic probable bibliographic identity."],
    ),
    doi_corroboration=coherent_corroboration,
    related_corroboration=coherent_corroboration,
    identity_conflict=False,
    reasons=["Synthetic probable identity with strong corroboration."],
)

probable_identity = academic_orchestrator.resolve_retrieval_identity(
    probable_reference
)

check(
    probable_identity.status == "not_eligible",
    "probable bibliographic identity does not permit automatic retrieval",
)

check(
    probable_identity.doi is None,
    "probable identity exposes no DOI despite corroboration",
)


print("\n[16] eligible retrieval identity propagates through orchestration")

def eligible_reference_verifier(**kwargs):
    if kwargs["title"] == "Second Work":
        return AcademicReferenceResult(
            crossref_verification=VerificationResult(
                status="verified",
                candidate=coherent_candidate,
                reasons=["Synthetic verified source-claim identity."],
            ),
            doi_corroboration=None,
            related_corroboration=coherent_corroboration,
            identity_conflict=False,
            reasons=["Synthetic eligible source-claim identity."],
        )

    return AcademicReferenceResult(
        crossref_verification=VerificationResult(
            status="verified",
            candidate=None,
            reasons=["Synthetic unrelated reference result."],
        ),
        doi_corroboration=None,
        related_corroboration=None,
        identity_conflict=False,
        reasons=["Synthetic unrelated reference result."],
    )


eligible_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
)

eligible_source_claim = eligible_result.source_claims[0]

check(
    eligible_source_claim.reference.proposed_reference.title == "Second Work",
    "eligible retrieval identity remains attached to intended source reference",
)

check(
    eligible_source_claim.retrieval_identity.status == "eligible",
    "eligible retrieval identity propagates to source claim",
)

check(
    eligible_source_claim.retrieval_identity.doi == "10.1234/coherent",
    "source claim carries safe corroborated retrieval DOI",
)

eligible_source_payload = eligible_result.to_dict()["source_claims"][0]

check(
    eligible_source_payload["retrieval_identity"]["status"] == "eligible",
    "eligible retrieval status serialises",
)

check(
    eligible_source_payload["retrieval_identity"]["doi"]
    == "10.1234/coherent",
    "eligible retrieval DOI serialises",
)

check(
    "support_status" not in eligible_source_payload
    and "claim_verified" not in eligible_source_payload
    and "verified" not in eligible_source_payload,
    "retrieval eligibility does not become claim-support verification",
)


print("\n[17] ineligible identity never reaches source discovery")

discovery_calls = []


def fake_source_discoverer(doi):
    discovery_calls.append(doi)
    raise AssertionError("Ineligible identity must not reach source discovery.")


ineligible_discovery_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=fake_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_source_discoverer,
)

check(
    discovery_calls == [],
    "ineligible retrieval identity causes no source-discovery call",
)

ineligible_source_claim = ineligible_discovery_result.source_claims[0]

check(
    ineligible_source_claim.source_discovery.status == "not_attempted",
    "ineligible source claim records discovery as not attempted",
)

check(
    ineligible_source_claim.source_discovery.location is None,
    "unattempted discovery has no source location",
)

ineligible_discovery_payload = (
    ineligible_discovery_result.to_dict()["source_claims"][0]["source_discovery"]
)

check(
    ineligible_discovery_payload["status"] == "not_attempted",
    "not-attempted discovery status serialises",
)

check(
    ineligible_discovery_payload["location"] is None,
    "not-attempted discovery serialises without a location",
)


print("\n[18] eligible identity reaches source discovery by DOI only")

eligible_discovery_calls = []


def fake_eligible_source_discoverer(doi):
    eligible_discovery_calls.append(doi)
    return academic_claims.SourceLocation(
        status="location_found",
        doi=doi,
        source="openalex",
        landing_page_url="https://example.org/coherent",
        pdf_url="https://example.org/coherent.pdf",
        is_oa=True,
        reasons=["Synthetic discovered source location."],
    )


eligible_discovery_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
)

check(
    eligible_discovery_calls == ["10.1234/coherent"],
    "eligible source discovery receives exactly the corroborated DOI",
)

check(
    SECRET not in repr(eligible_discovery_calls),
    "confidential question content never reaches source discovery",
)

check(
    "Second Work reports the synthetic literature finding."
    not in repr(eligible_discovery_calls),
    "source-claim text never reaches source discovery",
)

eligible_discovered_claim = eligible_discovery_result.source_claims[0]

check(
    eligible_discovered_claim.source_discovery.status == "attempted",
    "eligible source claim records discovery as attempted",
)

check(
    eligible_discovered_claim.source_discovery.location is not None,
    "attempted discovery retains discovered source location",
)

check(
    eligible_discovered_claim.source_discovery.location.doi
    == "10.1234/coherent",
    "discovered location retains safe retrieval DOI",
)

eligible_discovery_payload = (
    eligible_discovery_result.to_dict()["source_claims"][0]["source_discovery"]
)

check(
    eligible_discovery_payload["status"] == "attempted",
    "attempted discovery status serialises",
)

check(
    eligible_discovery_payload["location"]["doi"] == "10.1234/coherent",
    "discovered location DOI serialises",
)

check(
    eligible_discovery_payload["location"]["pdf_url"]
    == "https://example.org/coherent.pdf",
    "discovered PDF location serialises",
)

check(
    "support_status" not in eligible_discovery_payload
    and "claim_verified" not in eligible_discovery_payload,
    "source discovery does not become claim-support verification",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat orchestration checks passed.")
