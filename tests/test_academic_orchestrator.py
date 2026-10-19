"""Regression tests for first-stage Academic Chat orchestration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
from methodology_fixtures import methodology_output
import academic_claim_coverage
import academic_claims
import academic_methodology
import academic_orchestrator
import academic_technical
import reviewer_notes
from academic_tools import (
    AcademicReferenceResult,
    CorroborationResult,
    ReferenceCandidate,
    VerificationResult,
)


fails = []


def empty_methodological_retriever(question):
    """Keep existing orchestration tests independent of reviewer-note content."""
    return academic_orchestrator.LocalGuidanceResult(passages=[])


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[0] methodological retrieval recovers split headed sections")

methodological_context = (
    academic_orchestrator.retrieve_methodological_context(
        "What is the difference between a 95% ETI and a 95% HDI?",
        k=3,
    )
)

check(
    len(methodological_context.passages) == 4,
    "top-three methodological anchors recover one split section sibling",
)

check(
    any(
        "do not generalise the minimum-width hdi relationship"
        in passage.text.lower()
        for passage in methodological_context.passages
    ),
    "methodological context includes guidance beyond the chunk boundary",
)

check(
    sum(
        passage.heading == "Are all 95% credible intervals the same?"
        for passage in methodological_context.passages
    ) == 2,
    "both chunks of the retrieved ETI/HDI section remain attached",
)


print(
    "\n[0b] methodological retrieval query uses substantive claim content"
)

contextual_claim = academic_chat.TechnicalClaim(
    type="GENERATED-TYPE-ALPHA-7F3A",
    concept="GENERATED-CONCEPT-ALPHA-7F3A",
    statement=(
        "Adjusting for baseline variables that strongly predict the outcome "
        "reduces residual variation."
    ),
    parameterisation="baseline prognostic covariates",
)

metadata_variant_claim = academic_chat.TechnicalClaim(
    type="GENERATED-TYPE-BETA-8C4B",
    concept="GENERATED-CONCEPT-BETA-8C4B",
    statement=contextual_claim.statement,
    parameterisation=contextual_claim.parameterisation,
)

contextual_source = academic_claim_coverage.ClaimSourceContext(
    source_sentence=(
        "Adjusting for baseline variables that strongly predict the outcome "
        "reduces residual variation."
    ),
    source_sentence_start=112,
    source_sentence_end=224,
    context_excerpt=(
        "In randomised trials, the primary rationale for covariate adjustment "
        "is statistical efficiency, not confounding control. Adjusting for "
        "baseline variables that strongly predict the outcome reduces residual "
        "variation."
    ),
    context_start=0,
    context_end=224,
)

claim_query = academic_orchestrator._technical_claim_methodological_query(
    contextual_claim
)
metadata_variant_query = (
    academic_orchestrator._technical_claim_methodological_query(
        metadata_variant_claim
    )
)

check(
    contextual_claim.statement in claim_query
    and contextual_claim.parameterisation in claim_query,
    "claim query retains statement and parameterisation",
)

check(
    contextual_claim.type not in claim_query
    and contextual_claim.concept not in claim_query,
    "claim query excludes generated classification metadata",
)

check(
    claim_query == metadata_variant_query,
    "claim query is invariant to generated type and concept",
)

contextual_query = academic_orchestrator._contextual_claim_methodological_query(
    contextual_claim,
    contextual_source,
)

metadata_variant_contextual_query = (
    academic_orchestrator._contextual_claim_methodological_query(
        metadata_variant_claim,
        contextual_source,
    )
)

check(
    contextual_claim.statement in contextual_query
    and contextual_claim.parameterisation in contextual_query,
    "contextual query retains substantive claim content",
)

check(
    contextual_claim.type not in contextual_query
    and contextual_claim.concept not in contextual_query,
    "contextual query excludes generated classification metadata",
)

check(
    contextual_source.source_sentence in contextual_query,
    "contextual query retains the verified source sentence",
)

check(
    contextual_source.context_excerpt in contextual_query,
    "contextual query retains the bounded answer context",
)

check(
    contextual_query == metadata_variant_contextual_query,
    "contextual query is invariant to generated type and concept",
)

check(
    contextual_query
    == academic_orchestrator._contextual_claim_methodological_query(
        contextual_claim,
        contextual_source,
    ),
    "contextual methodological query is deterministic",
)


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
    methodological_retriever=empty_methodological_retriever,
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
    methodological_retriever=empty_methodological_retriever,
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


print("\n[10b] incomplete corroboration blocks retrieval")

incomplete_candidate = ReferenceCandidate(
    title="Incomplete Work",
    authors=["A. Author"],
    year=2020,
    venue="Journal A",
    doi="10.1234/incomplete",
    work_type="journal-article",
)

incomplete_corroboration = CorroborationResult(
    status="corroborated",
    crossref=incomplete_candidate,
    openalex=incomplete_candidate,
    same_doi=True,
    title_similarity=1.0,
    author_agreement=True,
    venue_similarity=1.0,
    year_difference=0,
    reasons=["Synthetic completed DOI corroboration."],
)

incomplete_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="verified",
        candidate=incomplete_candidate,
        reasons=["Synthetic verified bibliographic identity."],
    ),
    doi_corroboration=incomplete_corroboration,
    related_corroboration=None,
    identity_conflict=False,
    reasons=[
        "Synthetic title corroboration unavailable."
    ],
    corroboration_status="unavailable",
)

incomplete_identity = academic_orchestrator.resolve_retrieval_identity(
    incomplete_reference
)

check(
    incomplete_identity.status == "not_eligible",
    "incomplete corroboration blocks automatic source retrieval",
)

check(
    incomplete_identity.doi is None,
    "incomplete corroboration exposes no DOI for automatic retrieval",
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
    methodological_retriever=empty_methodological_retriever,
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
    methodological_retriever=empty_methodological_retriever,
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


print("\n[17b] unavailable bibliographic corroboration preserves academic result")

unavailable_discovery_calls = []


def unavailable_reference_verifier(**kwargs):
    if kwargs["title"] == "Second Work":
        return AcademicReferenceResult(
            crossref_verification=VerificationResult(
                status="verified",
                candidate=coherent_candidate,
                reasons=["Synthetic verified Crossref identity."],
            ),
            doi_corroboration=coherent_corroboration,
            related_corroboration=None,
            identity_conflict=False,
            reasons=[
                "OpenAlex title corroboration was unavailable; completed "
                "bibliographic evidence was preserved."
            ],
            corroboration_status="unavailable",
        )

    return fake_reference_verifier(**kwargs)


def unavailable_source_discoverer(doi):
    unavailable_discovery_calls.append(doi)
    raise AssertionError(
        "Incomplete bibliographic corroboration must not reach source discovery."
    )


unavailable_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=unavailable_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=unavailable_source_discoverer,
    methodological_retriever=empty_methodological_retriever,
)

unavailable_source_claim = unavailable_result.source_claims[0]

check(
    unavailable_result.answer_draft == result.answer_draft,
    "academic draft survives unavailable bibliographic corroboration",
)

check(
    unavailable_source_claim.reference.verification.corroboration_status
    == "unavailable",
    "unavailable corroboration remains explicit on verified reference",
)

check(
    unavailable_source_claim.retrieval_identity.status == "not_eligible",
    "unavailable corroboration remains retrieval-ineligible",
)

check(
    unavailable_source_claim.retrieval_identity.doi is None,
    "unavailable corroboration exposes no retrieval DOI",
)

check(
    unavailable_discovery_calls == [],
    "unavailable corroboration never reaches source discovery",
)

check(
    unavailable_source_claim.source_discovery.status == "not_attempted",
    "source discovery remains explicitly unattempted",
)

check(
    unavailable_source_claim.source_discovery.location is None,
    "unavailable corroboration produces no source location",
)

check(
    unavailable_source_claim.source_retrieval is None,
    "unavailable corroboration produces no substantive source retrieval",
)

check(
    unavailable_source_claim.claim_assessment is None,
    "unavailable corroboration produces no source semantic assessment",
)

unavailable_payload = unavailable_result.to_dict()
unavailable_source_payload = unavailable_payload["source_claims"][0]

check(
    unavailable_source_payload["reference"]["verification"][
        "corroboration_status"
    ]
    == "unavailable",
    "unavailable corroboration status serialises",
)

check(
    unavailable_source_payload["retrieval_identity"]["status"]
    == "not_eligible",
    "unavailable retrieval state serialises",
)

check(
    "support_status" not in unavailable_source_payload,
    "service unavailability does not become a source-support conclusion",
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
    methodological_retriever=empty_methodological_retriever,
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


print("\n[19] source-discovery service failure preserves academic result")

unavailable_discovery_calls = []

def unavailable_source_discoverer(doi):
    unavailable_discovery_calls.append(doi)
    raise RuntimeError("Synthetic OpenAlex service failure.")

try:
    unavailable_discovery_result = academic_orchestrator.run_academic_first_stage(
        model,
        tokenizer,
        question,
        draft_generator=fake_draft_generator,
        reference_verifier=eligible_reference_verifier,
        technical_verifier=fake_technical_verifier,
        source_discoverer=unavailable_source_discoverer,
        methodological_retriever=empty_methodological_retriever,
    )
except RuntimeError:
    unavailable_discovery_result = None

check(
    unavailable_discovery_calls == ["10.1234/coherent"],
    "failed source discovery still receives only the eligible DOI",
)

check(
    unavailable_discovery_result is not None,
    "source-discovery service failure does not destroy academic result",
)

if unavailable_discovery_result is not None:
    unavailable_claim = unavailable_discovery_result.source_claims[0]

    check(
        unavailable_claim.source_discovery.status == "unavailable",
        "source-discovery service failure is recorded as unavailable",
    )

    check(
        unavailable_claim.source_discovery.location is None,
        "unavailable source discovery exposes no source location",
    )

    unavailable_payload = unavailable_discovery_result.to_dict()
    unavailable_discovery_payload = (
        unavailable_payload["source_claims"][0]["source_discovery"]
    )

    check(
        unavailable_discovery_payload["status"] == "unavailable",
        "unavailable discovery status serialises",
    )

    check(
        unavailable_discovery_payload["location"] is None,
        "unavailable discovery serialises without a location",
    )

    check(
        unavailable_payload["answer_draft"]
        == unavailable_discovery_result.answer_draft,
        "academic draft survives source-discovery service failure",
    )

    check(
        "support_status" not in unavailable_discovery_payload
        and "claim_verified" not in unavailable_discovery_payload,
        "discovery failure does not become a claim-support conclusion",
    )


print("\n[20] discovered source location reaches substantive retrieval")

retrieval_calls = []

def fake_source_retriever(location):
    retrieval_calls.append(location)
    return academic_claims.RetrievedSource(
        status="retrieved",
        doi=location.doi,
        source=location.source,
        text="Synthetic substantive scholarly source text.",
        locator="https://example.org/coherent.pdf",
        reasons=["Synthetic source retrieval."],
    )

retrieval_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_source_retriever,
    methodological_retriever=empty_methodological_retriever,
)

check(
    len(retrieval_calls) == 1,
    "successful discovery invokes substantive retrieval exactly once",
)

check(
    len(retrieval_calls) == 1
    and retrieval_calls[0].doi == "10.1234/coherent",
    "retriever receives discovered source location",
)

retrieved_claim = retrieval_result.source_claims[0]

check(
    retrieved_claim.source_retrieval.status == "retrieved",
    "retrieved source is retained on source claim",
)

check(
    retrieved_claim.source_retrieval.text
    == "Synthetic substantive scholarly source text.",
    "retrieved substantive text remains auditable",
)

retrieval_payload = retrieval_result.to_dict()["source_claims"][0]

check(
    retrieval_payload["source_retrieval"]["status"] == "retrieved",
    "retrieval status serialises with source claim",
)

check(
    "support_status" not in retrieval_payload
    and "claim_verified" not in retrieval_payload,
    "successful retrieval does not become claim-support verification",
)


print("\n[21] retrieval requires a successfully discovered location")

blocked_retrieval_calls = []

def retrieval_must_not_run(location):
    blocked_retrieval_calls.append(location)
    raise AssertionError(
        "retrieval must not run without a successfully discovered location"
    )

# Ineligible bibliographic identity: discovery itself is not attempted.
ineligible_retrieval_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=fake_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=retrieval_must_not_run,
    methodological_retriever=empty_methodological_retriever,
)

check(
    blocked_retrieval_calls == [],
    "ineligible identity never reaches substantive retrieval",
)

check(
    ineligible_retrieval_result.source_claims[0].source_retrieval is None,
    "unattempted discovery has no retrieval result",
)

# Eligible identity, but discovery service fails.
unavailable_retrieval_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=unavailable_source_discoverer,
    source_retriever=retrieval_must_not_run,
    methodological_retriever=empty_methodological_retriever,
)

check(
    blocked_retrieval_calls == [],
    "unavailable discovery never reaches substantive retrieval",
)

check(
    unavailable_retrieval_result.source_claims[0].source_retrieval is None,
    "unavailable discovery has no retrieval result",
)

# Eligible identity, successful discovery operation, but no location.
def no_location_source_discoverer(doi):
    return academic_claims.SourceLocation(
        status="location_not_found",
        doi=doi,
        source="openalex",
        landing_page_url=None,
        pdf_url=None,
        is_oa=None,
        reasons=["Synthetic source location not found."],
    )

no_location_retrieval_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=no_location_source_discoverer,
    source_retriever=retrieval_must_not_run,
    methodological_retriever=empty_methodological_retriever,
)

check(
    blocked_retrieval_calls == [],
    "missing source location never reaches substantive retrieval",
)

check(
    no_location_retrieval_result.source_claims[0].source_retrieval is None,
    "missing source location has no retrieval result",
)

check(
    no_location_retrieval_result.to_dict()["source_claims"][0]
    ["source_retrieval"] is None,
    "unattempted retrieval serialises explicitly as null",
)


print("\n[22] failed substantive retrieval remains auditable")

failed_retrieval_calls = []

def fake_failed_source_retriever(location):
    failed_retrieval_calls.append(location)
    return academic_claims.RetrievedSource(
        status="not_retrieved",
        doi=location.doi,
        source=location.source,
        text=None,
        locator=None,
        reasons=["Synthetic PDF retrieval failure."],
    )

failed_retrieval_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_failed_source_retriever,
    methodological_retriever=empty_methodological_retriever,
)

check(
    len(failed_retrieval_calls) == 1,
    "failed substantive retrieval was attempted exactly once",
)

failed_claim = failed_retrieval_result.source_claims[0]

check(
    failed_claim.source_retrieval is not None,
    "attempted failed retrieval remains distinct from unattempted retrieval",
)

check(
    failed_claim.source_retrieval is not None
    and failed_claim.source_retrieval.status == "not_retrieved",
    "failed retrieval retains not-retrieved status",
)

failed_payload = failed_retrieval_result.to_dict()["source_claims"][0]

check(
    failed_payload["source_retrieval"]["status"] == "not_retrieved",
    "failed retrieval status serialises",
)

check(
    failed_payload["source_retrieval"]["reasons"]
    == ["Synthetic PDF retrieval failure."],
    "failed retrieval reason remains auditable",
)

check(
    "support_status" not in failed_payload
    and "claim_verified" not in failed_payload,
    "failed retrieval does not become a claim-support conclusion",
)


print("\n[23] claim location is gated by successful substantive retrieval")

claim_location_calls = []

def fake_claim_locator(retrieved, claim):
    claim_location_calls.append((retrieved, claim))
    return academic_claims.ClaimSupportResult(
        status="claim_located",
        source_status="retrieved",
        claim_status="located",
        doi=retrieved.doi,
        evidence=[
            academic_claims.ClaimEvidence(
                text="Synthetic candidate evidence.",
                locator=retrieved.locator,
                source=retrieved.source,
                page_number=7,
            )
        ],
        reasons=[
            "Synthetic candidate claim passage located."
        ],
    )

located_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_source_retriever,
    claim_locator=fake_claim_locator,
    methodological_retriever=empty_methodological_retriever,
)

check(
    len(claim_location_calls) == 1,
    "successful substantive retrieval reaches claim location exactly once",
)

located_retrieved, located_claim_text = claim_location_calls[0]

check(
    located_retrieved is located_result.source_claims[0].source_retrieval,
    "claim locator receives the application-owned retrieved source",
)

check(
    located_claim_text == located_result.source_claims[0].claim.claim,
    "claim locator receives only the source claim selected for location",
)

check(
    located_result.source_claims[0].claim_location.status == "claim_located",
    "claim-location result is retained separately from retrieval",
)

located_payload = located_result.to_dict()["source_claims"][0]

check(
    located_payload["claim_location"]["evidence"][0]["page_number"] == 7,
    "claim-location provenance serialises",
)

blocked_claim_location_calls = []

def claim_locator_must_not_run(retrieved, claim):
    blocked_claim_location_calls.append((retrieved, claim))
    raise AssertionError(
        "Claim locator must not run without successful substantive retrieval."
    )

failed_location_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_failed_source_retriever,
    claim_locator=claim_locator_must_not_run,
    methodological_retriever=empty_methodological_retriever,
)

check(
    blocked_claim_location_calls == [],
    "failed substantive retrieval never reaches claim location",
)

check(
    failed_location_result.source_claims[0].claim_location is None,
    "unattempted claim location remains explicit after failed retrieval",
)

check(
    failed_location_result.to_dict()["source_claims"][0]
    ["claim_location"] is None,
    "unattempted claim location serialises explicitly as null",
)


print("\n[24] semantic assessment is gated by located evidence")

claim_assessment_calls = []

def fake_claim_assessor(claim, evidence):
    claim_assessment_calls.append((claim, evidence))
    return academic_claims.ClaimAssessmentResult(
        status="claim_supported",
        claim=claim,
        evidence=evidence,
        reasons=["Synthetic semantic assessment."],
    )

assessed_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_source_retriever,
    claim_locator=fake_claim_locator,
    claim_assessor=fake_claim_assessor,
    methodological_retriever=empty_methodological_retriever,
)

check(
    len(claim_assessment_calls) == 1,
    "located claim reaches semantic assessment exactly once",
)

assessed_claim, assessed_evidence = claim_assessment_calls[0]

check(
    assessed_claim == assessed_result.source_claims[0].claim.claim,
    "semantic assessor receives only the atomic source claim",
)

check(
    assessed_evidence
    is assessed_result.source_claims[0].claim_location.evidence,
    "semantic assessor receives application-owned located evidence",
)

check(
    assessed_result.source_claims[0].claim_assessment.status
    == "claim_supported",
    "semantic assessment is retained separately from claim location",
)

check(
    assessed_result.source_claims[0]
    .claim_assessment.evidence[0].page_number == 7,
    "semantic assessment retains physical page provenance",
)

assessed_payload = assessed_result.to_dict()["source_claims"][0]

check(
    assessed_payload["claim_assessment"]["status"]
    == "claim_supported",
    "semantic assessment status serialises",
)

check(
    assessed_payload["claim_assessment"]["evidence"][0]["page_number"] == 7,
    "semantic assessment provenance serialises",
)


print("\n[24a] assessed source contradiction blocks unchanged draft")

def contradictory_claim_assessor(claim, evidence):
    return academic_claims.ClaimAssessmentResult(
        status="claim_contradicted",
        claim=claim,
        evidence=evidence,
        reasons=[
            "Synthetic located evidence clearly contradicts the claim."
        ],
    )

contradicted_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_source_retriever,
    claim_locator=fake_claim_locator,
    claim_assessor=contradictory_claim_assessor,
    methodological_retriever=empty_methodological_retriever,
)

check(
    contradicted_result.source_claims[0].claim_assessment.status
    == "claim_contradicted",
    "source contradiction survives the complete source-assessment chain",
)

check(
    contradicted_result.release.status
    == "blocked_source_contradiction",
    "assessed source contradiction reaches the release gate",
)

check(
    contradicted_result.release.safe_to_present is False,
    "source-contradicted draft is not safe to present unchanged",
)

contradicted_payload = contradicted_result.to_dict()

check(
    contradicted_payload["release"]["status"]
    == "blocked_source_contradiction",
    "source-contradiction release status serialises",
)

check(
    contradicted_payload["release"]["safe_to_present"] is False,
    "source-contradiction presentation block serialises",
)

blocked_claim_assessment_calls = []

def claim_assessor_must_not_run(claim, evidence):
    blocked_claim_assessment_calls.append((claim, evidence))
    raise AssertionError(
        "Semantic assessor must not run without located evidence."
    )

unlocated_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_failed_source_retriever,
    claim_locator=claim_locator_must_not_run,
    claim_assessor=claim_assessor_must_not_run,
    methodological_retriever=empty_methodological_retriever,
)

check(
    blocked_claim_assessment_calls == [],
    "claim without located evidence never reaches semantic assessment",
)

check(
    unlocated_result.source_claims[0].claim_assessment is None,
    "unattempted semantic assessment remains explicit",
)

check(
    unlocated_result.to_dict()["source_claims"][0]
    ["claim_assessment"] is None,
    "unattempted semantic assessment serialises explicitly as null",
)


def fake_not_located_claim_locator(retrieved, claim):
    return academic_claims.ClaimSupportResult(
        status="claim_not_located",
        source_status="retrieved",
        claim_status="not_located",
        doi=retrieved.doi,
        evidence=[],
        reasons=["Synthetic meaningful search found no candidate evidence."],
    )

not_located_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=fake_eligible_source_discoverer,
    source_retriever=fake_source_retriever,
    claim_locator=fake_not_located_claim_locator,
    claim_assessor=claim_assessor_must_not_run,
    methodological_retriever=empty_methodological_retriever,
)

check(
    blocked_claim_assessment_calls == [],
    "retrieved source without located evidence never reaches semantic assessment",
)

check(
    not_located_result.source_claims[0].claim_location.status
    == "claim_not_located",
    "claim-not-located state remains distinct from semantic assessment",
)

check(
    not_located_result.source_claims[0].claim_assessment is None,
    "claim-not-located state has no semantic assessment",
)


print("\n[15b] corroborated different paper cannot replace verified identity")

verified_a = ReferenceCandidate(
    title="Treatment efficacy: a randomized trial",
    authors=["A. Author"],
    year=2025,
    venue="Trial Journal",
    doi="10.1234/trial",
    work_type="journal-article",
)

related_b_crossref = ReferenceCandidate(
    title="Treatment efficacy: a systematic review",
    authors=["B. Author"],
    year=2025,
    venue="Review Journal",
    doi="10.1234/review",
    work_type="journal-article",
)

related_b_openalex = ReferenceCandidate(
    title="Treatment efficacy: a systematic review",
    authors=["B. Author"],
    year=2025,
    venue="Review Journal",
    doi="10.1234/review",
    work_type="journal-article",
    source="openalex",
)

related_b_corroboration = CorroborationResult(
    status="corroborated",
    crossref=related_b_crossref,
    openalex=related_b_openalex,
    same_doi=True,
    title_similarity=1.0,
    author_agreement=True,
    venue_similarity=1.0,
    year_difference=0,
    reasons=["Synthetic related-paper corroboration."],
)

substitution_reference = AcademicReferenceResult(
    crossref_verification=VerificationResult(
        status="verified",
        candidate=verified_a,
        reasons=["Synthetic verified paper A."],
    ),
    doi_corroboration=None,
    related_corroboration=related_b_corroboration,
    identity_conflict=False,
    reasons=[
        "Synthetic verified A with independently corroborated related B."
    ],
)

substitution_identity = academic_orchestrator.resolve_retrieval_identity(
    substitution_reference
)

check(
    substitution_identity.status == "not_eligible",
    "corroborated paper B cannot replace verified paper A",
)

check(
    substitution_identity.doi is None,
    "different corroborated DOI is not exposed for retrieval",
)


substitution_discovery_calls = []


def substitution_reference_verifier(**kwargs):
    if kwargs["title"] == "Second Work":
        return substitution_reference
    return fake_reference_verifier(**kwargs)


def substitution_source_discoverer(doi):
    substitution_discovery_calls.append(doi)
    raise AssertionError(
        "Corroborated different paper must not reach source discovery."
    )


substitution_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=substitution_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=substitution_source_discoverer,
    methodological_retriever=empty_methodological_retriever,
)

substitution_source_claim = substitution_result.source_claims[0]

check(
    substitution_discovery_calls == [],
    "different corroborated paper never reaches source discovery",
)

check(
    substitution_source_claim.retrieval_identity.status == "not_eligible",
    "substituted identity remains ineligible through orchestration",
)

check(
    substitution_source_claim.source_discovery.status == "not_attempted",
    "source discovery remains unattempted for substituted identity",
)

check(
    substitution_source_claim.source_retrieval is None,
    "substituted identity never reaches source retrieval",
)

check(
    substitution_source_claim.claim_location is None,
    "substituted identity never reaches claim location",
)

check(
    substitution_source_claim.claim_assessment is None,
    "substituted identity never reaches semantic assessment",
)


print("\n[25] discovery must preserve authorised bibliographic identity")

discovery_identity_retrieval_calls = []


def mismatched_identity_discoverer(doi):
    return academic_claims.SourceLocation(
        status="location_found",
        doi="10.1234/paper-b",
        source="openalex",
        landing_page_url="https://example.org/paper-b",
        pdf_url="https://example.org/paper-b.pdf",
        is_oa=True,
        reasons=["Synthetic mismatched discovery identity."],
    )


def discovery_identity_retriever(location):
    discovery_identity_retrieval_calls.append(location)
    return academic_claims.RetrievedSource(
        status="retrieved",
        doi=location.doi,
        source=location.source,
        text="Paper B substantive text.",
        locator=location.pdf_url,
        reasons=["Synthetic retrieval that must not occur."],
    )


mismatched_discovery_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=mismatched_identity_discoverer,
    source_retriever=discovery_identity_retriever,
    methodological_retriever=empty_methodological_retriever,
)

mismatched_discovery_claim = mismatched_discovery_result.source_claims[0]

check(
    discovery_identity_retrieval_calls == [],
    "discovery DOI mismatch never reaches substantive retrieval",
)

check(
    mismatched_discovery_claim.source_discovery.status != "attempted"
    or mismatched_discovery_claim.source_discovery.location is None
    or mismatched_discovery_claim.source_discovery.location.status
    != "location_found",
    "discovery DOI mismatch is not accepted as a usable location",
)

check(
    mismatched_discovery_claim.source_discovery.status == "identity_mismatch",
    "discovery DOI mismatch is reported explicitly",
)

check(
    mismatched_discovery_claim.source_discovery.location is None,
    "discovery DOI mismatch exposes no source location",
)

check(
    any(
        "identity" in reason.lower()
        and "match" in reason.lower()
        for reason in mismatched_discovery_claim.source_discovery.reasons
    ),
    "discovery DOI mismatch retains an explicit reason",
)

check(
    mismatched_discovery_claim.to_dict()["source_discovery"]["status"]
    == "identity_mismatch",
    "discovery DOI mismatch status survives serialisation",
)

check(
    mismatched_discovery_claim.source_retrieval is None,
    "discovery DOI mismatch produces no retrieved source",
)

check(
    mismatched_discovery_claim.claim_location is None,
    "discovery DOI mismatch never reaches claim location",
)

check(
    mismatched_discovery_claim.claim_assessment is None,
    "discovery DOI mismatch never reaches semantic assessment",
)


missing_identity_retrieval_calls = []


def missing_identity_discoverer(doi):
    return academic_claims.SourceLocation(
        status="location_found",
        doi=None,
        source="openalex",
        landing_page_url="https://example.org/unidentified",
        pdf_url="https://example.org/unidentified.pdf",
        is_oa=True,
        reasons=["Synthetic discovery result without DOI identity."],
    )


def missing_identity_retriever(location):
    missing_identity_retrieval_calls.append(location)
    return academic_claims.RetrievedSource(
        status="retrieved",
        doi=location.doi,
        source=location.source,
        text="Unidentified substantive text.",
        locator=location.pdf_url,
        reasons=["Synthetic retrieval that must not occur."],
    )


missing_identity_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=missing_identity_discoverer,
    source_retriever=missing_identity_retriever,
    methodological_retriever=empty_methodological_retriever,
)

missing_identity_claim = missing_identity_result.source_claims[0]

check(
    missing_identity_retrieval_calls == [],
    "discovery without DOI identity never reaches substantive retrieval",
)

check(
    missing_identity_claim.source_discovery.status == "identity_mismatch",
    "discovery without DOI identity is reported explicitly",
)

check(
    missing_identity_claim.source_discovery.location is None,
    "discovery without DOI identity exposes no source location",
)

check(
    missing_identity_claim.to_dict()["source_discovery"]["status"]
    == "identity_mismatch",
    "missing discovery identity status survives serialisation",
)

check(
    missing_identity_claim.source_retrieval is None,
    "discovery without DOI identity produces no retrieved source",
)

check(
    missing_identity_claim.claim_location is None,
    "discovery without DOI identity never reaches claim location",
)

check(
    missing_identity_claim.claim_assessment is None,
    "discovery without DOI identity never reaches semantic assessment",
)


equivalent_identity_retrieval_calls = []


def equivalent_identity_discoverer(doi):
    return academic_claims.SourceLocation(
        status="location_found",
        doi="HTTPS://DOI.ORG/10.1234/COHERENT",
        source="openalex",
        landing_page_url="https://example.org/coherent-normalised",
        pdf_url="https://example.org/coherent-normalised.pdf",
        is_oa=True,
        reasons=["Synthetic equivalent DOI representation."],
    )


def equivalent_identity_retriever(location):
    equivalent_identity_retrieval_calls.append(location)
    return academic_claims.RetrievedSource(
        status="retrieved",
        doi="10.1234/coherent",
        source=location.source,
        text="Synthetic coherent scholarly source text.",
        locator=location.pdf_url,
        reasons=["Synthetic coherent retrieval."],
    )


equivalent_identity_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=eligible_reference_verifier,
    technical_verifier=fake_technical_verifier,
    source_discoverer=equivalent_identity_discoverer,
    source_retriever=equivalent_identity_retriever,
    methodological_retriever=empty_methodological_retriever,
)

check(
    len(equivalent_identity_retrieval_calls) == 1,
    "equivalent normalised discovery DOI remains retrieval-eligible",
)


print("\n[methodological context] local guidance reaches generation only")

METHOD_NOTE = (
    "LOCAL-METHOD-NOTE-91C2: interpretation depends on the statistical "
    "model and its assumptions."
)

methodological_retrieval_calls = []
context_draft_calls = []
context_reference_calls = []
context_technical_calls = []


def synthetic_methodological_retriever(supplied_question):
    methodological_retrieval_calls.append(supplied_question)
    return academic_orchestrator.LocalGuidanceResult(
        passages=[
            reviewer_notes.Passage(
                note="Synthetic Method Note",
                heading="Interpretation",
                text=METHOD_NOTE,
                score=1.0,
            )
        ]
    )


def context_draft_generator(
    model,
    tokenizer,
    supplied_question,
    *,
    methodological_context=None,
):
    context_draft_calls.append(
        {
            "question": supplied_question,
            "methodological_context": methodological_context,
        }
    )
    return academic_chat.AcademicDraft(
        answer_draft="A context-informed provisional answer.",
        references=[
            academic_chat.AcademicReference(
                title="Context Test Work",
                author="A. Researcher",
                year=2020,
                venue="Example Journal",
                doi=None,
            )
        ],
        source_claims=[],
        technical_claims=[
            academic_chat.TechnicalClaim(
                type="interpretation",
                concept="context test",
                statement="A structured methodological proposition.",
                parameterisation=None,
            )
        ],
    )


def context_reference_verifier(**kwargs):
    context_reference_calls.append(dict(kwargs))
    return fake_reference_verifier(**kwargs)


def context_technical_verifier(claim):
    context_technical_calls.append(claim)
    return fake_technical_verifier(claim)


context_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=context_technical_verifier,
    methodological_retriever=synthetic_methodological_retriever,
)

check(
    methodological_retrieval_calls == [question],
    "methodological retriever receives the complete question locally",
)

check(
    len(context_draft_calls) == 1
    and METHOD_NOTE in context_draft_calls[0]["methodological_context"],
    "retrieved methodological context reaches local draft generation",
)

check(
    context_draft_calls[0]["question"] == question,
    "original question remains separate from methodological context",
)

check(
    METHOD_NOTE not in repr(context_reference_calls),
    "methodological context never reaches bibliographic verification",
)

check(
    METHOD_NOTE not in repr(
        [claim.to_dict() for claim in context_technical_calls]
    ),
    "methodological context never reaches deterministic technical verification",
)

check(
    context_result.answer_draft == "A context-informed provisional answer.",
    "context-informed draft continues through normal orchestration",
)


check(
    len(context_result.local_guidance.passages) == 1,
    "local methodological guidance remains attached to orchestration result",
)

check(
    context_result.local_guidance.passages[0].note
    == "Synthetic Method Note",
    "local guidance retains reviewer-note provenance",
)

context_serialised = context_result.to_dict()

check(
    context_serialised["local_guidance"]["source"] == "reviewer_notes",
    "local guidance serialises as a distinct reviewer-notes source",
)

check(
    context_serialised["local_guidance"]["passages"][0]["heading"]
    == "Interpretation",
    "local guidance heading survives serialisation",
)

check(
    context_serialised["local_guidance"]["passages"][0]["score"] == 1.0,
    "local guidance retrieval score survives serialisation",
)

check(
    METHOD_NOTE not in repr(context_serialised["local_guidance"]),
    "full local guidance passage text is not exposed by serialisation",
)



print("\n[methodological consistency] guidance gates semantic assessment")

methodological_assessment_calls = []


def synthetic_methodological_assessor(*, prompt, schema):
    methodological_assessment_calls.append(
        {
            "prompt": prompt,
            "schema": schema,
        }
    )
    return methodology_output(schema, 'methodologically_consistent', "The supplied guidance directly addresses the same "
            "methodological proposition.")


assessed_context_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=context_technical_verifier,
    methodological_retriever=synthetic_methodological_retriever,
    claim_methodological_retriever=synthetic_methodological_retriever,
    methodological_assessor=synthetic_methodological_assessor,
)

check(
    len(methodological_assessment_calls) == 2,
    "retrieved guidance and a technical claim trigger two bounded methodological judgements",
)

assessment_call = methodological_assessment_calls[0]

check(
    "A structured methodological proposition." in assessment_call["prompt"],
    "methodological assessor receives the structured technical claim",
)

check(
    METHOD_NOTE in assessment_call["prompt"],
    "methodological assessor receives the retrieved local guidance",
)

check(
    SECRET not in assessment_call["prompt"],
    "original confidential question does not reach methodological assessment",
)

check(
    "Context Test Work" not in assessment_call["prompt"],
    "bibliographic proposal does not reach methodological assessment",
)

check(
    "synthetic_test_verifier" not in assessment_call["prompt"],
    "deterministic verifier result does not reach methodological assessment",
)

methodological_result = (
    assessed_context_result.technical_claims[0].methodological_consistency
)

check(
    methodological_result is not None
    and methodological_result.status == "methodologically_consistent",
    "methodological assessment remains attached to its technical claim",
)

assessed_payload = assessed_context_result.to_dict()

check(
    assessed_payload["technical_claims"][0]["methodological_consistency"][
        "status"
    ] == "methodologically_consistent",
    "methodological consistency serialises separately from technical verification",
)

check(
    assessed_payload["technical_claims"][0]["verification"]["status"]
    == academic_technical.TECHNICAL_STATUS_VERIFIED,
    "deterministic technical verification remains a distinct result",
)

check(
    METHOD_NOTE not in repr(
        assessed_payload["technical_claims"][0]["methodological_consistency"]
    ),
    "methodological consistency serialisation omits full guidance text",
)


print("\n[methodological consistency] claim-specific guidance is used for assessment")

CLAIM_METHOD_NOTE = (
    "CLAIM-METHOD-NOTE-4A71: guidance retrieved specifically for the "
    "structured technical claim."
)

claim_methodological_retrieval_calls = []


def synthetic_claim_methodological_retriever(query):
    claim_methodological_retrieval_calls.append(query)
    return academic_orchestrator.LocalGuidanceResult(
        passages=[
            reviewer_notes.Passage(
                note="Claim-Specific Method Note",
                heading="Claim interpretation",
                text=CLAIM_METHOD_NOTE,
                score=0.9,
            )
        ]
    )


claim_specific_assessment_calls = []


def claim_specific_methodological_assessor(*, prompt, schema):
    claim_specific_assessment_calls.append(
        {
            "prompt": prompt,
            "schema": schema,
        }
    )
    return methodology_output(schema, 'methodologically_consistent', "Claim-specific guidance directly addresses the proposition.")


claim_specific_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=context_technical_verifier,
    methodological_retriever=synthetic_methodological_retriever,
    claim_methodological_retriever=synthetic_claim_methodological_retriever,
    methodological_assessor=claim_specific_methodological_assessor,
)

check(
    len(claim_methodological_retrieval_calls) == 1,
    "each technical claim triggers claim-specific methodological retrieval",
)

check(
    "A structured methodological proposition."
    in claim_methodological_retrieval_calls[0],
    "claim-specific retrieval query contains the structured claim statement",
)

check(
    SECRET not in claim_methodological_retrieval_calls[0]
    and question not in claim_methodological_retrieval_calls[0],
    "claim-specific retrieval receives no original confidential question",
)

check(
    len(claim_specific_assessment_calls) == 2
    and CLAIM_METHOD_NOTE in claim_specific_assessment_calls[0]["prompt"],
    "methodological assessor receives claim-specific guidance",
)

check(
    METHOD_NOTE not in claim_specific_assessment_calls[0]["prompt"],
    "question-level guidance is not reused for claim assessment",
)

claim_specific_methodology = (
    claim_specific_result.technical_claims[0].methodological_consistency
)

check(
    claim_specific_methodology is not None
    and claim_specific_methodology.passages[0].note
    == "Claim-Specific Method Note",
    "claim result retains exact claim-specific guidance provenance",
)

check(
    claim_specific_result.local_guidance.passages[0].note
    == "Synthetic Method Note",
    "question-level guidance remains separately attached to the result",
)


print("\n[methodological consistency] claim guidance can exist without question guidance")

independent_claim_retrieval_calls = []
independent_assessment_calls = []


def independent_claim_retriever(query):
    independent_claim_retrieval_calls.append(query)
    return academic_orchestrator.LocalGuidanceResult(
        passages=[
            reviewer_notes.Passage(
                note="Independent Claim Note",
                heading="Specific claim guidance",
                text=(
                    "INDEPENDENT-CLAIM-GUIDANCE-8D31: this guidance is "
                    "available for the structured claim."
                ),
                score=0.8,
            )
        ]
    )


def independent_methodological_assessor(*, prompt, schema):
    independent_assessment_calls.append(
        {
            "prompt": prompt,
            "schema": schema,
        }
    )
    return methodology_output(schema, 'methodologically_consistent', "Claim-specific guidance directly addresses the proposition.")


independent_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=context_technical_verifier,
    methodological_retriever=empty_methodological_retriever,
    claim_methodological_retriever=independent_claim_retriever,
    methodological_assessor=independent_methodological_assessor,
)

check(
    independent_result.local_guidance.passages == [],
    "question-level methodological retrieval can remain empty",
)

check(
    context_draft_calls[-1]["methodological_context"] is None,
    "empty question-level guidance does not add methodological context to generation",
)

check(
    len(independent_claim_retrieval_calls) == 1,
    "structured claim still triggers independent methodological retrieval",
)

check(
    len(independent_assessment_calls) == 2
    and "INDEPENDENT-CLAIM-GUIDANCE-8D31"
    in independent_assessment_calls[0]["prompt"],
    "claim-specific guidance still reaches methodological assessment",
)

check(
    independent_result.technical_claims[0].methodological_consistency
    is not None,
    "claim can be methodologically assessed without question-level guidance",
)

print("\n[methodological consistency] no guidance means no assessment")

no_guidance_assessment_calls = []


def should_not_assess_methodology(*, prompt, schema):
    no_guidance_assessment_calls.append(
        {
            "prompt": prompt,
            "schema": schema,
        }
    )
    raise AssertionError(
        "Methodological assessor must not run without retrieved guidance."
    )


no_guidance_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=fake_draft_generator,
    reference_verifier=fake_reference_verifier,
    technical_verifier=fake_technical_verifier,
    methodological_retriever=empty_methodological_retriever,
    claim_methodological_retriever=empty_methodological_retriever,
    methodological_assessor=should_not_assess_methodology,
)

check(
    no_guidance_assessment_calls == [],
    "absence of retrieved guidance prevents methodological assessment",
)

check(
    no_guidance_result.technical_claims[0].methodological_consistency is None,
    "unattempted methodological assessment remains explicit as None",
)

check(
    no_guidance_result.to_dict()["technical_claims"][0][
        "methodological_consistency"
    ] is None,
    "unattempted methodological assessment serialises explicitly as null",
)


print("\n[methodological release] conflict is reported without withholding")


def conflicting_methodological_assessor(*, prompt, schema):
    return methodology_output(schema, 'methodological_conflict', "The structured claim materially contradicts the supplied "
            "methodological guidance.")


methodological_conflict_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=context_technical_verifier,
    methodological_retriever=synthetic_methodological_retriever,
    methodological_assessor=conflicting_methodological_assessor,
)

check(
    methodological_conflict_result.release.status
    == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
    "methodological conflict keeps its own release status",
)

check(
    methodological_conflict_result.release.safe_to_present is True,
    "a semantic methodological conflict does not prevent presentation",
)

check(
    methodological_conflict_result.answer_draft
    == "A context-informed provisional answer.",
    "draft with a methodological conflict remains available",
)


print("\n[methodological release] not established does not block")


def unestablished_methodological_assessor(*, prompt, schema):
    return methodology_output(schema, 'methodological_consistency_not_established', "The supplied guidance does not establish the same "
            "methodological proposition.")


not_established_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=context_technical_verifier,
    methodological_retriever=synthetic_methodological_retriever,
    methodological_assessor=unestablished_methodological_assessor,
)

check(
    not_established_result.release.status == "release_allowed",
    "methodological consistency not established does not itself block release",
)

check(
    not_established_result.release.safe_to_present is True,
    "absence of established methodological consistency is not treated as conflict",
)


print("\n[methodological release] consistency does not become verification")


def unverified_context_technical_verifier(claim):
    return academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_NOT_VERIFIED,
        verifier=None,
        canonical_claim=None,
        reasons=["Synthetic claim is outside deterministic verifier coverage."],
    )


consistent_but_unverified_result = (
    academic_orchestrator.run_academic_first_stage(
        model,
        tokenizer,
        question,
        draft_generator=context_draft_generator,
        reference_verifier=context_reference_verifier,
        technical_verifier=unverified_context_technical_verifier,
        methodological_retriever=synthetic_methodological_retriever,
        methodological_assessor=synthetic_methodological_assessor,
    )
)

check(
    consistent_but_unverified_result.release.status
    == "release_allowed_with_unverified_claims",
    "methodological consistency does not convert an unverified claim into verification",
)

check(
    consistent_but_unverified_result.technical_claims[0].verification.status
    == academic_technical.TECHNICAL_STATUS_NOT_VERIFIED,
    "deterministic verification status remains unverified",
)


print("\n[methodological release] deterministic conflict has precedence")


both_conflicts_result = academic_orchestrator.run_academic_first_stage(
    model,
    tokenizer,
    question,
    draft_generator=context_draft_generator,
    reference_verifier=context_reference_verifier,
    technical_verifier=conflicting_technical_verifier,
    methodological_retriever=synthetic_methodological_retriever,
    methodological_assessor=conflicting_methodological_assessor,
)

check(
    both_conflicts_result.technical_claims[0].verification.status
    == academic_technical.TECHNICAL_STATUS_CONFLICT,
    "simultaneous-conflict case retains deterministic technical conflict",
)

check(
    both_conflicts_result.technical_claims[0].methodological_consistency.status
    == "methodological_conflict",
    "simultaneous-conflict case retains methodological conflict",
)

check(
    both_conflicts_result.release.status == "blocked_technical_conflict",
    "deterministic technical conflict has release precedence",
)

check(
    both_conflicts_result.release.safe_to_present is False,
    "simultaneous conflicts remain blocked",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)


print("\n[claim coverage] discovered claims enter ordinary technical checking")

coverage_draft = academic_chat.AcademicDraft(
    answer_draft=(
        "The broad claim is represented already. "
        "A second material proposition also appears in the answer."
    ),
    references=[],
    source_claims=[],
    technical_claims=[
        academic_chat.TechnicalClaim(
            type="methodological",
            concept="existing proposition",
            statement="The broad claim is represented already.",
            parameterisation=None,
        )
    ],
)

coverage_guidance = academic_orchestrator.LocalGuidanceResult(
    passages=[]
)

coverage_calls = []
technical_calls = []


def fake_coverage_assessor(*, answer_draft, existing_claims):
    coverage_calls.append(
        {
            "answer_draft": answer_draft,
            "existing_claims": list(existing_claims),
        }
    )
    return academic_claim_coverage.ClaimCoverageAssessment.from_result(
        academic_claim_coverage.ClaimCoverageResult(
            missing_claims=[
                academic_chat.TechnicalClaim(
                    type="methodological",
                    concept="missing proposition",
                    statement=(
                        "A second material proposition also appears in the answer."
                    ),
                    parameterisation=None,
                )
            ]
        )
    )


def fake_technical_verifier(claim):
    technical_calls.append(claim)
    return academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_NOT_VERIFIED,
        verifier=None,
        canonical_claim=None,
        reasons=[
            "Synthetic verifier does not cover this proposition."
        ],
    )


coverage_result = academic_orchestrator.assess_academic_draft(
    coverage_draft,
    local_guidance=coverage_guidance,
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_coverage_assessor,
)

assert len(coverage_calls) == 1
assert coverage_calls[0]["answer_draft"] == coverage_draft.answer_draft
assert coverage_calls[0]["existing_claims"] == coverage_draft.technical_claims

assert len(technical_calls) == 2
assert technical_calls[0] is coverage_draft.technical_claims[0]
assert technical_calls[1].statement == (
    "A second material proposition also appears in the answer."
)

assert len(coverage_result.technical_claims) == 2
assert coverage_result.technical_claims[0].claim is technical_calls[0]
assert coverage_result.technical_claims[1].claim is technical_calls[1]

assert coverage_result.draft is coverage_draft
assert len(coverage_result.draft.technical_claims) == 1

print("PASS: coverage receives only answer and existing technical claims")
print("PASS: discovered claim enters the same technical-verification path")
print("PASS: original AcademicDraft is retained without mutation")

print("\n[claim coverage] discovered claims enter methodological assessment")

coverage_method_note = (
    "Synthetic local guidance for testing coverage-discovered claims."
)

coverage_method_guidance = academic_orchestrator.LocalGuidanceResult(
    passages=[
        reviewer_notes.Passage(
            note="synthetic-method-note",
            heading="Coverage methodology",
            text=coverage_method_note,
            score=1.0,
        )
    ]
)

coverage_method_calls = []


def fake_coverage_methodological_assessor(*, prompt, schema):
    coverage_method_calls.append(
        {
            "prompt": prompt,
            "schema": schema,
        }
    )
    return methodology_output(schema, 'methodologically_consistent', "The supplied guidance addresses this proposition.")


coverage_method_result = academic_orchestrator.assess_academic_draft(
    coverage_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_technical_verifier,
    methodological_assessor=fake_coverage_methodological_assessor,
    coverage_assessor=fake_coverage_assessor,
)

assert len(coverage_method_calls) == 4

assert (
    "The broad claim is represented already."
    in coverage_method_calls[0]["prompt"]
)
assert (
    "A second material proposition also appears in the answer."
    in coverage_method_calls[2]["prompt"]
)

assert coverage_method_note in coverage_method_calls[0]["prompt"]
assert coverage_method_note in coverage_method_calls[2]["prompt"]

assert (
    coverage_method_result.technical_claims[0]
    .methodological_consistency.status
    == "methodologically_consistent"
)
assert (
    coverage_method_result.technical_claims[1]
    .methodological_consistency.status
    == "methodologically_consistent"
)

assert (
    coverage_method_result.technical_claims[1]
    .methodological_consistency.claim
    is coverage_method_result.technical_claims[1].claim
)

print("PASS: original claim enters methodological assessment")
print("PASS: coverage-discovered claim enters the same methodological path")
print("PASS: discovered claim retains its methodological assessment")


print("\n[claim coverage] atomic discovery prevents compound-claim masking")

compound_cca_claim = academic_chat.TechnicalClaim(
    type="conditional statement",
    concept="complete-case analysis",
    statement=(
        "Complete-case analysis is generally biased unless the missing data "
        "mechanism is Missing Completely at Random (MCAR). MCAR is sufficient "
        "for unbiased estimation in many settings but not universally "
        "necessary; under some Missing at Random (MAR) mechanisms, "
        "complete-case estimates can remain unbiased depending on the "
        "analysis model and estimand."
    ),
    parameterisation=None,
)

atomic_mcar_claim = academic_chat.TechnicalClaim(
    type="conditional statement",
    concept="complete-case analysis",
    statement=(
        "Complete-case analysis is generally biased unless the missing data "
        "mechanism is Missing Completely at Random (MCAR)."
    ),
    parameterisation=None,
)

atomic_mar_claim = academic_chat.TechnicalClaim(
    type="conditional statement",
    concept="complete-case analysis",
    statement=(
        "Under some Missing at Random (MAR) mechanisms, complete-case "
        "estimates can remain unbiased."
    ),
    parameterisation=None,
)

compound_cca_draft = academic_chat.AcademicDraft(
    answer_draft=(
        compound_cca_claim.statement
    ),
    references=[],
    source_claims=[],
    technical_claims=[compound_cca_claim],
)


def fake_atomic_coverage(*, answer_draft, existing_claims):
    assert answer_draft == compound_cca_draft.answer_draft
    assert existing_claims == [compound_cca_claim]
    return academic_claim_coverage.ClaimCoverageAssessment.from_result(
        academic_claim_coverage.ClaimCoverageResult(
            missing_claims=[],
            discovered_claims=[
                academic_claim_coverage.DiscoveredClaim(
                    claim=atomic_mcar_claim,
                    source_anchor="Missing Completely at Random (MCAR)",
                    source_start=compound_cca_draft.answer_draft.index(
                        "Missing Completely at Random (MCAR)"
                    ),
                    source_end=(
                        compound_cca_draft.answer_draft.index(
                            "Missing Completely at Random (MCAR)"
                        )
                        + len("Missing Completely at Random (MCAR)")
                    ),
                ),
                academic_claim_coverage.DiscoveredClaim(
                    claim=atomic_mar_claim,
                    source_anchor="complete-case estimates can remain unbiased",
                    source_start=compound_cca_draft.answer_draft.index(
                        "complete-case estimates can remain unbiased"
                    ),
                    source_end=(
                        compound_cca_draft.answer_draft.index(
                            "complete-case estimates can remain unbiased"
                        )
                        + len("complete-case estimates can remain unbiased")
                    ),
                ),
            ],
        )
    )


atomic_method_calls = []


def fake_atomic_methodological_assessor(*, prompt, schema):
    atomic_method_calls.append(prompt)

    if atomic_mcar_claim.statement in prompt:
        return methodology_output(schema, 'methodological_conflict', "The supplied guidance states that MCAR is not universally "
                "necessary for unbiased complete-case estimation.")

    return methodology_output(schema, 'methodologically_consistent', "Synthetic guidance is consistent with this proposition.")


atomic_masking_result = academic_orchestrator.assess_academic_draft(
    compound_cca_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_technical_verifier,
    methodological_assessor=fake_atomic_methodological_assessor,
    coverage_assessor=fake_atomic_coverage,
)

assert [
    result.claim.statement
    for result in atomic_masking_result.technical_claims
] == [
    compound_cca_claim.statement,
    atomic_mcar_claim.statement,
    atomic_mar_claim.statement,
]

assert len(atomic_method_calls) == 6

assert atomic_masking_result.release.status == (
    academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT
)
assert atomic_masking_result.release.safe_to_present is True

print("PASS: independently discovered atomic claims are checked separately")
print("PASS: atomic methodological conflict cannot be masked by compound claim")
print("PASS: the unmasked conflict is reported without withholding the answer")


print(
    "\n[claim coverage] restriction assessment survives proposition deduplication"
)

duplicate_context_sentence = (
    "The following statement concerns complete-case analysis."
)
duplicate_occurrence_draft = academic_chat.AcademicDraft(
    answer_draft=(
        duplicate_context_sentence
        + " "
        + atomic_mcar_claim.statement
    ),
    references=[],
    source_claims=[],
    technical_claims=[atomic_mcar_claim],
)

duplicate_anchor = "Missing Completely at Random (MCAR)"
duplicate_start = duplicate_occurrence_draft.answer_draft.index(
    duplicate_anchor
)

duplicate_discovered = academic_claim_coverage.DiscoveredClaim(
    claim=atomic_mcar_claim,
    source_anchor=duplicate_anchor,
    source_start=duplicate_start,
    source_end=duplicate_start + len(duplicate_anchor),
)


def fake_duplicate_coverage(*, answer_draft, existing_claims):
    assert answer_draft == duplicate_occurrence_draft.answer_draft
    assert existing_claims == [atomic_mcar_claim]
    return academic_claim_coverage.ClaimCoverageAssessment.from_result(
        academic_claim_coverage.ClaimCoverageResult(
            missing_claims=[],
            discovered_claims=[duplicate_discovered],
        )
    )


restriction_calls = []


def fake_material_restriction_assessor(*, prompt, schema):
    restriction_calls.append((prompt, schema))
    return {"material_restriction_omitted": False}


duplicate_technical_calls = []


def fake_duplicate_technical_verifier(claim):
    duplicate_technical_calls.append(claim)
    return fake_technical_verifier(claim)


duplicate_occurrence_result = academic_orchestrator.assess_academic_draft(
    duplicate_occurrence_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_duplicate_technical_verifier,
    coverage_assessor=fake_duplicate_coverage,
    material_restriction_assessor=fake_material_restriction_assessor,
)

assert len(restriction_calls) == 1
restriction_prompt, restriction_schema = restriction_calls[0]

assert restriction_schema == (
    academic_claim_coverage.material_restriction_output_schema()
)
assert atomic_mcar_claim.statement in restriction_prompt
assert duplicate_context_sentence in restriction_prompt

resolved_duplicate_context = (
    academic_claim_coverage.resolve_claim_source_context(
        answer_draft=duplicate_occurrence_draft.answer_draft,
        source_start=duplicate_discovered.source_start,
        source_end=duplicate_discovered.source_end,
    )
)
assert (
    resolved_duplicate_context.source_sentence
    in restriction_prompt
)
assert (
    resolved_duplicate_context.context_excerpt
    in restriction_prompt
)

assert len(duplicate_technical_calls) == 1
assert [
    result.claim
    for result in duplicate_occurrence_result.technical_claims
] == [atomic_mcar_claim]

assert len(
    duplicate_occurrence_result.discovered_claim_assessments
) == 1

duplicate_occurrence_assessment = (
    duplicate_occurrence_result.discovered_claim_assessments[0]
)

assert (
    duplicate_occurrence_assessment.discovered_claim
    == duplicate_discovered
)
assert (
    duplicate_occurrence_assessment.source_context
    == resolved_duplicate_context
)
assert (
    duplicate_occurrence_assessment
    .material_restriction
    .material_restriction_omitted
    is False
)
assert (
    duplicate_occurrence_assessment
    .contextual_methodological_consistency
    is None
)

print("PASS: discovered occurrence reaches restriction assessment")
print("PASS: verified occurrence resolves to bounded source context")
print("PASS: restriction assessor receives claim, source sentence, and context")
print("PASS: occurrence-level restriction state is retained")
print("PASS: proposition deduplication still prevents duplicate technical checking")


print(
    "\n[claim coverage] omitted restriction triggers contextual methodology"
)

contextual_retrieval_queries = []
contextual_methodology_prompts = []


def fake_omitted_restriction_assessor(*, prompt, schema):
    return {"material_restriction_omitted": True}


def fake_contextual_methodological_retriever(query):
    contextual_retrieval_queries.append(query)
    return coverage_method_guidance


def fake_contextual_methodological_assessor(*, prompt, schema):
    contextual_methodology_prompts.append((prompt, schema))

    if "BOUNDED ANSWER CONTEXT" in prompt:
        return methodology_output(schema, 'methodologically_consistent', "The context-qualified proposition is compatible with the "
                "supplied guidance.")

    return methodology_output(schema, 'methodological_consistency_not_established', "The standalone proposition is broader than the supplied guidance.")


contextual_occurrence_result = academic_orchestrator.assess_academic_draft(
    duplicate_occurrence_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_duplicate_coverage,
    material_restriction_assessor=fake_omitted_restriction_assessor,
    claim_methodological_retriever=(
        fake_contextual_methodological_retriever
    ),
    methodological_assessor=fake_contextual_methodological_assessor,
)

contextual_occurrence = (
    contextual_occurrence_result.discovered_claim_assessments[0]
)

assert (
    contextual_occurrence.material_restriction
    .material_restriction_omitted
    is True
)

assert (
    contextual_occurrence.contextual_methodological_consistency.status
    == academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
)

expected_contextual_query = (
    academic_orchestrator._contextual_claim_methodological_query(
        duplicate_discovered.claim,
        contextual_occurrence.source_context,
    )
)

# Since 1 October 2026 the standalone search for a claim with a verified
# answer location uses that location too (see
# tests/test_academic_claim_context_retrieval.py), so both searches use the
# contextual query. The standalone judgement still concerns the claim alone:
# only the contextual prompt carries the answer context (checked below).
assert contextual_retrieval_queries.count(expected_contextual_query) == 2
assert (
    academic_orchestrator._technical_claim_methodological_query(
        duplicate_discovered.claim
    )
    not in contextual_retrieval_queries
)

contextual_prompts = [
    prompt
    for prompt, _schema in contextual_methodology_prompts
    if "BOUNDED ANSWER CONTEXT" in prompt
]

assert len(contextual_prompts) == 2
assert duplicate_discovered.claim.statement in contextual_prompts[0]
assert (
    contextual_occurrence.source_context.context_excerpt
    in contextual_prompts[0]
)

standalone_duplicate_result = next(
    result
    for result in contextual_occurrence_result.technical_claims
    if result.claim == duplicate_discovered.claim
)

assert (
    standalone_duplicate_result.methodological_consistency.status
    == academic_methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED
)

assert contextual_occurrence_result.release.safe_to_present is True

print("PASS: omitted restriction triggers occurrence-specific retrieval")
print("PASS: contextual methodology receives verified occurrence context")
print("PASS: contextual and standalone methodology remain distinct")
print("PASS: contextual methodological consistency does not block release")


print(
    "\n[claim coverage] contextual methodological conflict is reported, not blocking"
)


def fake_contextual_conflict_assessor(*, prompt, schema):
    if "BOUNDED ANSWER CONTEXT" in prompt:
        return methodology_output(schema, 'methodological_conflict', "The occurrence-specific proposition materially conflicts "
                "with the supplied methodological guidance.")

    return methodology_output(schema, 'methodological_consistency_not_established', "The standalone proposition is not established by the supplied "
            "guidance.")


contextual_conflict_result = academic_orchestrator.assess_academic_draft(
    duplicate_occurrence_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_duplicate_coverage,
    material_restriction_assessor=fake_omitted_restriction_assessor,
    claim_methodological_retriever=(
        fake_contextual_methodological_retriever
    ),
    methodological_assessor=fake_contextual_conflict_assessor,
)

contextual_conflict_occurrence = (
    contextual_conflict_result.discovered_claim_assessments[0]
)

assert (
    contextual_conflict_occurrence
    .contextual_methodological_consistency
    .status
    == academic_methodology.METHODOLOGICAL_STATUS_CONFLICT
)

assert contextual_conflict_result.release.status == (
    academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT
)
assert contextual_conflict_result.release.safe_to_present is True

print("PASS: contextual methodological conflict remains occurrence-specific")
print("PASS: contextual methodological conflict is reported without withholding")


print(
    "\n[claim coverage] occurrence context crosses public boundary narrowly"
)

contextual_serialised = contextual_occurrence_result.to_dict()

assert "claim_context_assessments" in contextual_serialised
assert len(contextual_serialised["claim_context_assessments"]) == 1

public_context = contextual_serialised["claim_context_assessments"][0]

assert (
    public_context["claim_statement"]
    == duplicate_discovered.claim.statement
)
assert (
    public_context["source_sentence"]
    == contextual_occurrence.source_context.source_sentence
)
assert (
    public_context["context_excerpt"]
    == contextual_occurrence.source_context.context_excerpt
)
assert public_context["material_restriction_omitted"] is True

public_contextual_methodology = (
    public_context["contextual_methodological_consistency"]
)

assert (
    public_contextual_methodology["status"]
    == academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
)
assert public_contextual_methodology["reasons"]
assert public_contextual_methodology["passages"]

public_passage = public_contextual_methodology["passages"][0]
assert set(public_passage) == {"note", "heading", "score"}

assert set(public_context) == {
    "claim_statement",
    "source_sentence",
    "context_excerpt",
    "material_restriction_omitted",
    "contextual_methodological_consistency",
}

public_context_text = repr(public_context)

assert "GENERATED-TYPE" not in public_context_text
assert "GENERATED-CONCEPT" not in public_context_text
assert "source_anchor" not in public_context
assert "source_start" not in public_context
assert "source_end" not in public_context
assert "source_sentence_start" not in public_context
assert "source_sentence_end" not in public_context
assert "context_start" not in public_context
assert "context_end" not in public_context
assert "text" not in public_passage

print("PASS: public context retains the discovered claim statement")
print("PASS: public context retains verified answer context")
print("PASS: public context retains material-restriction state")
print("PASS: public context retains contextual methodology provenance")
print("PASS: public context withholds internal provenance machinery")


print(
    "\n[claim coverage] contextual retrieval silence remains unassessed"
)

empty_contextual_queries = []
empty_contextual_assessor_calls = []


def fake_empty_contextual_retriever(query):
    empty_contextual_queries.append(query)
    return academic_orchestrator.LocalGuidanceResult(passages=[])


def fake_should_not_assess_contextual_methodology(*, prompt, schema):
    empty_contextual_assessor_calls.append((prompt, schema))
    raise AssertionError(
        "Contextual methodology assessor must not run without guidance."
    )


empty_contextual_result = academic_orchestrator.assess_academic_draft(
    duplicate_occurrence_draft,
    local_guidance=academic_orchestrator.LocalGuidanceResult(passages=[]),
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_duplicate_coverage,
    material_restriction_assessor=fake_omitted_restriction_assessor,
    claim_methodological_retriever=fake_empty_contextual_retriever,
    methodological_assessor=fake_should_not_assess_contextual_methodology,
)

empty_contextual_occurrence = (
    empty_contextual_result.discovered_claim_assessments[0]
)

assert (
    empty_contextual_occurrence.material_restriction
    .material_restriction_omitted
    is True
)
assert (
    empty_contextual_occurrence.contextual_methodological_consistency
    is None
)

expected_empty_contextual_query = (
    academic_orchestrator._contextual_claim_methodological_query(
        duplicate_discovered.claim,
        empty_contextual_occurrence.source_context,
    )
)

assert expected_empty_contextual_query in empty_contextual_queries
assert empty_contextual_assessor_calls == []

print("PASS: contextual retrieval is attempted after restriction omission")
print("PASS: empty guidance produces no contextual methodology conclusion")
print("PASS: semantic assessor is not called without retrieved guidance")


print(
    "\n[claim coverage] occurrence provenance survives absent restriction assessor"
)

no_restriction_assessor_result = academic_orchestrator.assess_academic_draft(
    duplicate_occurrence_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_duplicate_coverage,
)

assert len(
    no_restriction_assessor_result.discovered_claim_assessments
) == 1

no_restriction_occurrence = (
    no_restriction_assessor_result.discovered_claim_assessments[0]
)

assert (
    no_restriction_occurrence.discovered_claim
    == duplicate_discovered
)
assert (
    no_restriction_occurrence.source_context
    == resolved_duplicate_context
)
assert no_restriction_occurrence.material_restriction is None
assert (
    no_restriction_occurrence.contextual_methodological_consistency
    is None
)

print("PASS: discovered occurrence remains retained without semantic assessor")
print("PASS: deterministic source context remains retained without semantic assessor")
print("PASS: absent restriction assessment remains explicit as None")


print(
    "\n[claim coverage] duplicate proposition retains occurrence-specific context"
)

shared_statement = atomic_mcar_claim.statement
scoped_prefix = (
    "In randomised trials, this effect concerns statistical efficiency. "
)
multi_occurrence_answer = (
    scoped_prefix
    + shared_statement
    + " "
    + shared_statement
)

multi_occurrence_draft = academic_chat.AcademicDraft(
    answer_draft=multi_occurrence_answer,
    references=[],
    source_claims=[],
    technical_claims=[atomic_mcar_claim],
)

first_start = multi_occurrence_answer.find(shared_statement)
second_start = multi_occurrence_answer.find(
    shared_statement,
    first_start + len(shared_statement),
)

first_discovered = academic_claim_coverage.DiscoveredClaim(
    claim=atomic_mcar_claim,
    source_anchor=shared_statement,
    source_start=first_start,
    source_end=first_start + len(shared_statement),
)

second_discovered = academic_claim_coverage.DiscoveredClaim(
    claim=atomic_mcar_claim,
    source_anchor=shared_statement,
    source_start=second_start,
    source_end=second_start + len(shared_statement),
)


def fake_multi_occurrence_coverage(*, answer_draft, existing_claims):
    assert answer_draft == multi_occurrence_answer
    return academic_claim_coverage.ClaimCoverageAssessment.from_result(
        academic_claim_coverage.ClaimCoverageResult(
            missing_claims=[],
            discovered_claims=[
                first_discovered,
                second_discovered,
            ],
        )
    )


multi_restriction_calls = []


def fake_multi_restriction_assessor(*, prompt, schema):
    multi_restriction_calls.append(prompt)

    return {
        "material_restriction_omitted": (
            "In randomised trials" in prompt
        )
    }


multi_contextual_queries = []


def fake_multi_contextual_retriever(query):
    multi_contextual_queries.append(query)
    return coverage_method_guidance


def fake_multi_methodological_assessor(*, prompt, schema):
    if "BOUNDED ANSWER CONTEXT" in prompt:
        return methodology_output(schema, 'methodologically_consistent', "The occurrence is consistent in its verified context.")

    return methodology_output(schema, 'methodological_consistency_not_established', "The standalone proposition lacks the contextual restriction.")


multi_technical_calls = []


def fake_multi_technical_verifier(claim):
    multi_technical_calls.append(claim)
    return fake_technical_verifier(claim)


multi_occurrence_result = academic_orchestrator.assess_academic_draft(
    multi_occurrence_draft,
    local_guidance=coverage_method_guidance,
    technical_verifier=fake_multi_technical_verifier,
    coverage_assessor=fake_multi_occurrence_coverage,
    material_restriction_assessor=fake_multi_restriction_assessor,
    claim_methodological_retriever=fake_multi_contextual_retriever,
    methodological_assessor=fake_multi_methodological_assessor,
)

assert len(multi_occurrence_result.discovered_claim_assessments) == 2
assert len(multi_restriction_calls) == 2

first_occurrence, second_occurrence = (
    multi_occurrence_result.discovered_claim_assessments
)

assert (
    first_occurrence.material_restriction.material_restriction_omitted
    is True
)
assert (
    second_occurrence.material_restriction.material_restriction_omitted
    is False
)

assert (
    first_occurrence.contextual_methodological_consistency.status
    == academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
)
assert (
    second_occurrence.contextual_methodological_consistency
    is None
)

assert len(multi_technical_calls) == 1
assert len(multi_occurrence_result.technical_claims) == 1

expected_first_contextual_query = (
    academic_orchestrator._contextual_claim_methodological_query(
        first_discovered.claim,
        first_occurrence.source_context,
    )
)
assert expected_first_contextual_query in multi_contextual_queries

expected_second_contextual_query = (
    academic_orchestrator._contextual_claim_methodological_query(
        second_discovered.claim,
        second_occurrence.source_context,
    )
)
assert expected_second_contextual_query not in multi_contextual_queries

print("PASS: duplicate proposition retains two occurrence records")
print("PASS: restriction state remains occurrence-specific")
print("PASS: contextual methodology runs only for eligible occurrence")
print("PASS: proposition-level technical assessment remains deduplicated")


print(
    "\n[claim coverage] generated metadata does not duplicate proposition checking"
)

metadata_variant_claim = academic_chat.TechnicalClaim(
    type="GENERATED-TYPE-DIFFERENT",
    concept="GENERATED-CONCEPT-DIFFERENT",
    statement=first_discovered.claim.statement,
    parameterisation=first_discovered.claim.parameterisation,
)

assert metadata_variant_claim.type != first_discovered.claim.type
assert metadata_variant_claim.concept != first_discovered.claim.concept
assert metadata_variant_claim.statement == first_discovered.claim.statement
assert (
    metadata_variant_claim.parameterisation
    == first_discovered.claim.parameterisation
)

metadata_variant_discovered = academic_claim_coverage.DiscoveredClaim(
    claim=metadata_variant_claim,
    source_anchor=first_discovered.source_anchor,
    source_start=first_discovered.source_start,
    source_end=first_discovered.source_end,
)


def fake_metadata_variant_coverage(*, answer_draft, existing_claims):
    assert answer_draft == multi_occurrence_draft.answer_draft
    assert existing_claims == multi_occurrence_draft.technical_claims
    return academic_claim_coverage.ClaimCoverageAssessment.from_result(
        academic_claim_coverage.ClaimCoverageResult(
            missing_claims=[],
            discovered_claims=[metadata_variant_discovered],
        )
    )


metadata_variant_technical_calls = []


def fake_metadata_variant_verifier(claim):
    metadata_variant_technical_calls.append(claim)
    return fake_technical_verifier(claim)


metadata_variant_result = academic_orchestrator.assess_academic_draft(
    multi_occurrence_draft,
    local_guidance=coverage_guidance,
    technical_verifier=fake_metadata_variant_verifier,
    coverage_assessor=fake_metadata_variant_coverage,
)

assert len(metadata_variant_result.discovered_claim_assessments) == 1
assert (
    metadata_variant_result.discovered_claim_assessments[0]
    .discovered_claim.claim
    is metadata_variant_claim
)

assert len(metadata_variant_technical_calls) == 1
assert len(metadata_variant_result.technical_claims) == 1

assert (
    metadata_variant_result.technical_claims[0].claim
    is multi_occurrence_draft.technical_claims[0]
)
assert (
    metadata_variant_result.technical_claims[0].claim
    is not metadata_variant_claim
)

print("PASS: metadata-variant occurrence remains separately auditable")
print("PASS: type/concept variation does not duplicate proposition checking")
print("PASS: first structured proposition remains the checked representation")


print(
    "\n[claim coverage] first-stage runner propagates restriction assessor"
)

first_stage_restriction_calls = []


def first_stage_duplicate_generator(
    model,
    tokenizer,
    question,
    *,
    methodological_context=None,
):
    return duplicate_occurrence_draft


def first_stage_restriction_assessor(*, prompt, schema):
    first_stage_restriction_calls.append((prompt, schema))
    return {"material_restriction_omitted": False}


first_stage_restriction_result = (
    academic_orchestrator.run_academic_first_stage(
        model,
        tokenizer,
        question,
        draft_generator=first_stage_duplicate_generator,
        technical_verifier=fake_technical_verifier,
        methodological_retriever=lambda question: coverage_method_guidance,
        coverage_assessor=fake_duplicate_coverage,
        material_restriction_assessor=first_stage_restriction_assessor,
    )
)

assert len(first_stage_restriction_calls) == 1
assert len(
    first_stage_restriction_result.discovered_claim_assessments
) == 1
assert (
    first_stage_restriction_result
    .discovered_claim_assessments[0]
    .material_restriction
    .material_restriction_omitted
    is False
)

print("PASS: first-stage runner propagates restriction assessor")
print("PASS: first-stage result retains occurrence-level restriction state")


print("\n[claim coverage] assessment state remains explicit")

no_missing_calls = []


def fake_no_missing_coverage(*, answer_draft, existing_claims):
    no_missing_calls.append((answer_draft, list(existing_claims)))
    return academic_claim_coverage.ClaimCoverageAssessment.from_result(
        academic_claim_coverage.ClaimCoverageResult(
            missing_claims=[]
        )
    )


no_missing_result = academic_orchestrator.assess_academic_draft(
    coverage_draft,
    local_guidance=coverage_guidance,
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_no_missing_coverage,
)

assert no_missing_result.claim_coverage.status == (
    academic_claim_coverage.COVERAGE_STATUS_NO_MISSING_PROPOSED
)
assert no_missing_result.claim_coverage.result is not None
assert no_missing_result.claim_coverage.result.missing_claims == []
assert len(no_missing_result.technical_claims) == 1

print("PASS: successful empty coverage remains explicit")


unavailable_calls = []


def fake_unavailable_coverage(*, answer_draft, existing_claims):
    unavailable_calls.append((answer_draft, list(existing_claims)))
    return academic_claim_coverage.ClaimCoverageAssessment.unavailable(
        "Synthetic local coverage assessment unavailable."
    )


unavailable_result = academic_orchestrator.assess_academic_draft(
    coverage_draft,
    local_guidance=coverage_guidance,
    technical_verifier=fake_technical_verifier,
    coverage_assessor=fake_unavailable_coverage,
)

assert unavailable_result.claim_coverage.status == (
    academic_claim_coverage.COVERAGE_STATUS_UNAVAILABLE
)
assert unavailable_result.claim_coverage.result is None
assert unavailable_result.claim_coverage.reasons == [
    "Synthetic local coverage assessment unavailable."
]

# Unavailable coverage adds no invented claims, but it is not represented
# as a successful empty assessment.
assert len(unavailable_result.technical_claims) == 1
assert (
    unavailable_result.claim_coverage.status
    != no_missing_result.claim_coverage.status
)

print("PASS: unavailable coverage cannot masquerade as successful empty coverage")
print("PASS: unavailable coverage invents no technical claims")

assert unavailable_result.release.status == "checking_incomplete"
assert unavailable_result.release.safe_to_present is False

unavailable_payload = unavailable_result.to_dict()

assert unavailable_payload["claim_coverage"]["status"] == (
    academic_claim_coverage.COVERAGE_STATUS_UNAVAILABLE
)
assert unavailable_payload["claim_coverage"]["missing_claims"] is None
assert unavailable_payload["claim_coverage"]["reasons"] == [
    "Synthetic local coverage assessment unavailable."
]
assert unavailable_payload["release"]["status"] == "checking_incomplete"
assert unavailable_payload["release"]["safe_to_present"] is False

print("PASS: unavailable coverage makes incomplete checking public")
print("PASS: unavailable coverage prevents ordinary automatic release")


# Successful coverage state also crosses the public Academic Chat boundary.
assert coverage_result.claim_coverage.status == (
    academic_claim_coverage.COVERAGE_STATUS_MISSING_FOUND
)

coverage_payload = coverage_result.to_dict()

assert coverage_payload["claim_coverage"] == (
    coverage_result.claim_coverage.to_dict()
)
assert set(coverage_payload) == {
    "answer_draft",
    "local_guidance",
    "claim_coverage",
    "references",
    "source_claims",
    "technical_claims",
    "claim_context_assessments",
    "release",
}

print("PASS: successful coverage state is explicit at the public boundary")


# Absence of a restriction assessor remains distinct from an assessed
# negative result at the public boundary.
no_restriction_payload = no_restriction_assessor_result.to_dict()
assert len(no_restriction_payload["claim_context_assessments"]) == 1

unassessed_public_context = (
    no_restriction_payload["claim_context_assessments"][0]
)

assert (
    unassessed_public_context["material_restriction_omitted"]
    is None
)
assert (
    unassessed_public_context[
        "contextual_methodological_consistency"
    ]
    is None
)

print("PASS: unattempted restriction assessment serialises as null")
print("PASS: unattempted contextual methodology serialises as null")
print("\n[claim coverage] bare coverage result is rejected")

def fake_bare_coverage_result(*, answer_draft, existing_claims):
    return academic_claim_coverage.ClaimCoverageResult(
        missing_claims=[]
    )


try:
    academic_orchestrator.assess_academic_draft(
        coverage_draft,
        local_guidance=coverage_guidance,
        technical_verifier=fake_technical_verifier,
        coverage_assessor=fake_bare_coverage_result,
    )
except TypeError as exc:
    assert "ClaimCoverageAssessment" in str(exc)
else:
    raise AssertionError(
        "Bare ClaimCoverageResult was accepted as a coverage assessment."
    )

print("PASS: orchestrator requires explicit coverage assessment state")


print("\n[claim coverage] absent assessor remains explicitly unattempted")

not_attempted_result = academic_orchestrator.assess_academic_draft(
    coverage_draft,
    local_guidance=coverage_guidance,
    technical_verifier=fake_technical_verifier,
)

assert not_attempted_result.claim_coverage.status == (
    academic_claim_coverage.COVERAGE_STATUS_NOT_ATTEMPTED
)
assert not_attempted_result.claim_coverage.result is None
assert not_attempted_result.claim_coverage.reasons == [
    "No claim-coverage assessor was supplied."
]

print("PASS: absence of coverage assessor is not reported as assessment failure")


print("\nAll Academic Chat orchestration checks passed.")
