"""Regression tests for the combined Academic Chat first-stage endpoint."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import academic_claim_coverage
import academic_claims
import academic_methodology
import llm_backend
import reviewer_notes
import server


fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


def response_payload(response):
    """Decode JSONResponse bodies while leaving ordinary dicts unchanged."""
    if isinstance(response, dict):
        return response
    return json.loads(response.body.decode("utf-8"))


class FakeResult:
    def to_dict(self):
        return {
            "answer_draft": "Synthetic provisional answer.",
            "references": [],
            "technical_claims": [],
            "release": {
                "status": "blocked_technical_conflict",
                "safe_to_present": False,
                "reasons": [
                    "Synthetic deterministic technical conflict."
                ],
            },
        }


original_ensure_model = server.ensure_model
original_orchestrator = server.academic_reconciliation_orchestrator.run_academic_reconciliation

ensure_calls = []
orchestrator_calls = []


def fake_ensure_model():
    ensure_calls.append(True)
    server.model = "LOCAL-MODEL"
    server.tokenizer = "LOCAL-TOKENIZER"


def fake_orchestrator(
    model,
    tokenizer,
    question,
    *,
    first_stage_runner=None,
    correction_extractor=None,
    revision_generator=None,
    draft_assessor=None,
):
    orchestrator_calls.append(
        {
            "model": model,
            "tokenizer": tokenizer,
            "question": question,
            "first_stage_runner": first_stage_runner,
            "correction_extractor": correction_extractor,
            "revision_generator": revision_generator,
            "draft_assessor": draft_assessor,
        }
    )

    initial = FakeResult()
    revised = FakeResult()

    return server.academic_reconciliation_orchestrator.AcademicReconciliationResult(
        initial=initial,
        revised=revised,
        revision_attempted=True,
    )


try:
    server.ensure_model = fake_ensure_model
    server.academic_reconciliation_orchestrator.run_academic_reconciliation = fake_orchestrator

    print("\n[1] valid request uses combined orchestrator")

    response = asyncio.run(
        server.academic_chat_first_stage(
            {"question": "What is relative efficiency in multiple imputation?"}
        )
    )

    check(
        len(ensure_calls) == 1,
        "model lifecycle invoked once",
    )

    check(
        len(orchestrator_calls) == 1,
        "combined orchestrator invoked once",
    )

    check(
        orchestrator_calls[0]["model"] == "LOCAL-MODEL",
        "existing model object passed to orchestrator",
    )

    check(
        orchestrator_calls[0]["tokenizer"] == "LOCAL-TOKENIZER",
        "existing tokenizer object passed to orchestrator",
    )

    check(
        orchestrator_calls[0]["question"]
        == "What is relative efficiency in multiple imputation?",
        "complete question passed to orchestrator",
    )

    check(
        callable(orchestrator_calls[0]["first_stage_runner"]),
        "production endpoint supplies the first-stage runner",
    )

    check(
        orchestrator_calls[0]["correction_extractor"]
        is server.academic_reconciliation.extract_academic_corrections,
        "production endpoint supplies bounded correction extraction",
    )

    check(
        orchestrator_calls[0]["revision_generator"]
        is server.academic_reconciliation.revise_academic_draft,
        "production endpoint supplies bounded local revision",
    )

    check(
        callable(orchestrator_calls[0]["draft_assessor"]),
        "production endpoint supplies fresh revised-draft assessment",
    )

    check(
        response["answer_draft"] == "Synthetic provisional answer.",
        "combined structured result returned",
    )


    check(
        response["release"]["status"] == "blocked_technical_conflict",
        "blocked release status survives HTTP boundary",
    )

    check(
        response["release"]["safe_to_present"] is False,
        "unsafe-to-present flag survives HTTP boundary",
    )

    check(
        response["answer_draft"] == "Synthetic provisional answer.",
        "blocked draft remains available through endpoint for auditability",
    )


    check(
        response.get("reconciliation", {}).get("revision_attempted") is True,
        "HTTP response exposes whether reconciliation attempted a revision",
    )

    check(
        response.get("reconciliation", {}).get("initial", {}).get(
            "answer_draft"
        ) == "Synthetic provisional answer.",
        "HTTP response preserves the initial checked result for audit",
    )

    check(
        response.get("reconciliation", {}).get("revised", {}).get(
            "answer_draft"
        ) == "Synthetic provisional answer.",
        "HTTP response preserves the revised checked result separately",
    )


    print("\n[1b] endpoint lifecycle closures preserve production checking")

    original_first_stage = server.academic_orchestrator.run_academic_first_stage
    original_assess_draft = server.academic_orchestrator.assess_academic_draft

    first_stage_calls = []
    reassessment_calls = []

    first_stage_sentinel = object()
    reassessment_sentinel = object()
    revised_draft_sentinel = object()
    guidance_sentinel = object()

    def capture_first_stage(
        model,
        tokenizer,
        question,
        **kwargs,
    ):
        first_stage_calls.append(
            {
                "model": model,
                "tokenizer": tokenizer,
                "question": question,
                "kwargs": kwargs,
            }
        )
        return first_stage_sentinel

    def capture_reassessment(
        draft,
        *,
        local_guidance,
        **kwargs,
    ):
        reassessment_calls.append(
            {
                "draft": draft,
                "local_guidance": local_guidance,
                "kwargs": kwargs,
            }
        )
        return reassessment_sentinel

    try:
        server.academic_orchestrator.run_academic_first_stage = (
            capture_first_stage
        )
        server.academic_orchestrator.assess_academic_draft = (
            capture_reassessment
        )

        supplied_first_stage = orchestrator_calls[0]["first_stage_runner"]
        supplied_reassessment = orchestrator_calls[0]["draft_assessor"]

        first_stage_value = supplied_first_stage(
            "MODEL-2",
            "TOKENIZER-2",
            "CONFIDENTIAL QUESTION",
        )

        reassessment_value = supplied_reassessment(
            revised_draft_sentinel,
            local_guidance=guidance_sentinel,
        )

        check(
            first_stage_value is first_stage_sentinel,
            "first-stage closure delegates to ordinary production orchestration",
        )

        check(
            first_stage_calls
            and first_stage_calls[0]["question"]
            == "CONFIDENTIAL QUESTION",
            "complete question enters only the first-stage closure",
        )

        first_kwargs = first_stage_calls[0]["kwargs"]

        check(
            first_kwargs["source_discoverer"]
            is server.discover_academic_source,
            "first stage receives production source discovery",
        )

        check(
            first_kwargs["source_retriever"]
            is server.retrieve_academic_source,
            "first stage receives production substantive retrieval",
        )

        check(
            first_kwargs["claim_locator"]
            is academic_claims.prepare_claim_support,
            "first stage receives production claim location",
        )

        check(
            first_kwargs["claim_assessor"]
            is server.assess_academic_claim,
            "first stage receives production semantic assessment",
        )

        check(
            first_kwargs["methodological_assessor"]
            is server.assess_academic_methodology,
            "first stage receives production methodological assessment",
        )

        check(
            first_kwargs["coverage_assessor"]
            is server.assess_academic_claim_coverage,
            "first stage receives production claim-coverage assessment",
        )

        check(
            first_kwargs["material_restriction_assessor"]
            is server.assess_academic_material_restriction,
            "first stage receives production material-restriction assessment",
        )

        check(
            reassessment_value is reassessment_sentinel,
            "reassessment closure delegates to ordinary draft assessment",
        )

        check(
            reassessment_calls
            and reassessment_calls[0]["draft"]
            is revised_draft_sentinel,
            "reassessment receives only the revised AcademicDraft",
        )

        check(
            reassessment_calls[0]["local_guidance"]
            is guidance_sentinel,
            "reassessment receives retained local guidance",
        )

        reassess_kwargs = reassessment_calls[0]["kwargs"]

        check(
            reassess_kwargs["source_discoverer"]
            is server.discover_academic_source,
            "reassessment repeats production source discovery",
        )

        check(
            reassess_kwargs["source_retriever"]
            is server.retrieve_academic_source,
            "reassessment repeats production substantive retrieval",
        )

        check(
            reassess_kwargs["claim_locator"]
            is academic_claims.prepare_claim_support,
            "reassessment repeats production claim location",
        )

        check(
            reassess_kwargs["claim_assessor"]
            is server.assess_academic_claim,
            "reassessment repeats production semantic assessment",
        )

        check(
            reassess_kwargs["coverage_assessor"]
            is server.assess_academic_claim_coverage,
            "reassessment repeats production claim-coverage assessment",
        )

        check(
            reassess_kwargs["methodological_assessor"]
            is server.assess_academic_methodology,
            "reassessment repeats production methodological assessment",
        )

        check(
            reassess_kwargs["material_restriction_assessor"]
            is server.assess_academic_material_restriction,
            "reassessment repeats production material-restriction assessment",
        )

        check(
            "question" not in reassess_kwargs,
            "original question is absent from revised-draft reassessment",
        )

    finally:
        server.academic_orchestrator.run_academic_first_stage = (
            original_first_stage
        )
        server.academic_orchestrator.assess_academic_draft = (
            original_assess_draft
        )



    print("\n[1c] unavailable coverage remains incomplete through HTTP boundary")

    # Exercise the real reconciliation coordinator and real draft assessment,
    # while controlling only first-stage generation and coverage availability.
    saved_endpoint_orchestrator = (
        server.academic_reconciliation_orchestrator.run_academic_reconciliation
    )
    saved_first_stage = server.academic_orchestrator.run_academic_first_stage
    saved_coverage_assessor = server.assess_academic_claim_coverage

    incomplete_lifecycle = []

    def controlled_first_stage(
        model,
        tokenizer,
        question,
        **kwargs,
    ):
        draft = academic_chat.AcademicDraft(
            answer_draft=(
                "A substantive synthetic answer whose independent claim "
                "coverage cannot be completed."
            ),
            references=[],
            source_claims=[],
            technical_claims=[],
        )

        result = server.academic_orchestrator.assess_academic_draft(
            draft,
            local_guidance=server.academic_orchestrator.LocalGuidanceResult(
                passages=[]
            ),
            coverage_assessor=kwargs["coverage_assessor"],
        )
        incomplete_lifecycle.append(result)
        return result

    def unavailable_endpoint_coverage(*, answer_draft, existing_claims):
        check(
            existing_claims == [],
            "endpoint regression begins with no declared technical claims",
        )
        return academic_claim_coverage.ClaimCoverageAssessment.unavailable(
            "Synthetic endpoint claim-coverage failure."
        )

    try:
        server.academic_reconciliation_orchestrator.run_academic_reconciliation = (
            original_orchestrator
        )
        server.academic_orchestrator.run_academic_first_stage = (
            controlled_first_stage
        )
        server.assess_academic_claim_coverage = unavailable_endpoint_coverage

        response = asyncio.run(
            server.academic_chat_first_stage(
                {"question": "Synthetic incomplete-coverage question"}
            )
        )
        payload = response_payload(response)

        check(
            payload["claim_coverage"]["status"]
            == academic_claim_coverage.COVERAGE_STATUS_UNAVAILABLE,
            "coverage failure survives the HTTP boundary",
        )
        check(
            payload["claim_coverage"]["missing_claims"] is None,
            "unavailable coverage does not serialize invented missing claims",
        )
        check(
            payload["release"]["status"] == "checking_incomplete",
            "HTTP response distinguishes incomplete checking from release",
        )
        check(
            payload["release"]["safe_to_present"] is False,
            "incomplete checking is not automatically presentable through HTTP",
        )
        check(
            len(incomplete_lifecycle) == 1,
            "incomplete checking does not trigger an invented revision",
        )
        check(
            payload["reconciliation"]["revision_attempted"] is False,
            "HTTP audit records that incomplete checking triggered no revision",
        )
        check(
            payload["reconciliation"]["revised"] is None,
            "HTTP audit represents absent revised assessment explicitly",
        )
        check(
            payload["reconciliation"]["initial"]["release"]["status"]
            == "checking_incomplete",
            "HTTP audit preserves the incomplete initial assessment",
        )
        check(
            payload["answer_draft"].startswith(
                "A substantive synthetic answer"
            ),
            "unchecked draft remains available for audit rather than disappearing",
        )
    finally:
        server.academic_reconciliation_orchestrator.run_academic_reconciliation = (
            saved_endpoint_orchestrator
        )
        server.academic_orchestrator.run_academic_first_stage = saved_first_stage
        server.assess_academic_claim_coverage = saved_coverage_assessor



    print("\n[1d] malformed methodology output no longer withholds the answer")

    saved_methodology_orchestrator = (
        server.academic_reconciliation_orchestrator.run_academic_reconciliation
    )
    saved_methodology_first_stage = (
        server.academic_orchestrator.run_academic_first_stage
    )
    saved_methodology_output = (
        server.academic_claim_assessor.generate_claim_assessor_output
    )

    methodology_claim = academic_chat.TechnicalClaim(
        type="methodological",
        concept="synthetic methodology claim",
        statement="Synthetic methodological proposition.",
        parameterisation=None,
    )

    methodology_guidance = server.academic_orchestrator.LocalGuidanceResult(
        passages=[
            reviewer_notes.Passage(
                note="Synthetic reviewer note",
                heading="Synthetic methodological guidance",
                text="Synthetic guidance addressing the methodological proposition.",
                score=0.5,
            )
        ]
    )

    def controlled_methodology_first_stage(
        model,
        tokenizer,
        question,
        **kwargs,
    ):
        draft = academic_chat.AcademicDraft(
            answer_draft="Synthetic answer containing a methodological claim.",
            references=[],
            source_claims=[],
            technical_claims=[methodology_claim],
        )
        return server.academic_orchestrator.assess_academic_draft(
            draft,
            local_guidance=methodology_guidance,
            methodological_assessor=kwargs["methodological_assessor"],
        )

    malformed_methodology_cases = [
        (
            "31-word reason",
            {
                "claim_proposition": "Synthetic claim proposition.",
                "guidance_proposition": "Synthetic guidance proposition.",
                "relationship": 'supports',
                "reason": " ".join(["word"] * 31),
            },
        ),
        (
            "invalid status",
            {
                "status": "verified",
                "reason": "Synthetic otherwise valid reason.",
            },
        ),
    ]

    try:
        server.academic_reconciliation_orchestrator.run_academic_reconciliation = (
            original_orchestrator
        )
        server.academic_orchestrator.run_academic_first_stage = (
            controlled_methodology_first_stage
        )

        for case_name, malformed_output in malformed_methodology_cases:
            def malformed_methodology_output(
                model,
                tokenizer,
                prompt,
                schema,
                *,
                _output=malformed_output,
                **kwargs,
            ):
                return _output

            server.academic_claim_assessor.generate_claim_assessor_output = (
                malformed_methodology_output
            )

            response = asyncio.run(
                server.academic_chat_first_stage(
                    {"question": f"Synthetic methodology case: {case_name}"}
                )
            )
            payload = response_payload(response)

            # Since 1 October 2026 an unusable judgement makes that claim
            # "not established" instead of failing the request; see
            # tests/test_academic_methodology_assessment_failure.py.
            check(
                isinstance(response, dict)
                and payload["release"]["safe_to_present"] is True,
                f"{case_name} is presented rather than returning HTTP 502",
            )
            methodology = (
                payload["initial_assessment"]["technical_claims"][0]
                ["methodological_consistency"]
                if "initial_assessment" in payload
                else payload["technical_claims"][0]["methodological_consistency"]
            )
            check(
                methodology["status"]
                == academic_methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED
                and "MethodologicalAssessmentOutputError"
                in methodology.get("assessment_error", ""),
                f"{case_name} is recorded as not established, with the error kept",
            )

        print(
            "\n[1e] unrelated methodology programming errors are not swallowed"
        )

        def methodology_programming_error(
            model,
            tokenizer,
            prompt,
            schema,
            **kwargs,
        ):
            raise TypeError("synthetic methodology programming error")

        server.academic_claim_assessor.generate_claim_assessor_output = (
            methodology_programming_error
        )

        try:
            asyncio.run(
                server.academic_chat_first_stage(
                    {"question": "Synthetic methodology programming error"}
                )
            )
        except TypeError as exc:
            check(
                str(exc) == "synthetic methodology programming error",
                "unrelated TypeError propagates unchanged",
            )
        else:
            check(
                False,
                "unrelated TypeError propagates unchanged",
            )

    finally:
        server.academic_reconciliation_orchestrator.run_academic_reconciliation = (
            saved_methodology_orchestrator
        )
        server.academic_orchestrator.run_academic_first_stage = (
            saved_methodology_first_stage
        )
        server.academic_claim_assessor.generate_claim_assessor_output = (
            saved_methodology_output
        )


    print("\n[2] unexpected fields are rejected before model use")

    ensure_before = len(ensure_calls)
    orchestrator_before = len(orchestrator_calls)

    response = asyncio.run(
        server.academic_chat_first_stage(
            {
                "question": "Test",
                "manuscript_text": "CONFIDENTIAL",
            }
        )
    )

    payload = response_payload(response)

    check(
        response.status_code == 400,
        "unexpected fields return HTTP 400",
    )

    check(
        payload["unexpected_fields"] == ["manuscript_text"],
        "unexpected field is identified",
    )

    check(
        len(ensure_calls) == ensure_before,
        "unexpected request never loads model",
    )

    check(
        len(orchestrator_calls) == orchestrator_before,
        "unexpected request never reaches orchestrator",
    )


    print("\n[3] empty questions are rejected before model use")

    ensure_before = len(ensure_calls)
    orchestrator_before = len(orchestrator_calls)

    response = asyncio.run(
        server.academic_chat_first_stage({"question": "   "})
    )

    check(
        response.status_code == 400,
        "empty question returns HTTP 400",
    )

    check(
        len(ensure_calls) == ensure_before,
        "empty question never loads model",
    )

    check(
        len(orchestrator_calls) == orchestrator_before,
        "empty question never reaches orchestrator",
    )


    print("\n[4] malformed local-model structure becomes HTTP 502")

    def malformed_orchestrator(model, tokenizer, question, **kwargs):
        raise academic_chat.AcademicDraftError("synthetic malformed output")

    server.academic_reconciliation_orchestrator.run_academic_reconciliation = malformed_orchestrator

    response = asyncio.run(
        server.academic_chat_first_stage({"question": "Test"})
    )

    payload = response_payload(response)

    check(
        response.status_code == 502,
        "invalid local-model structure returns HTTP 502",
    )

    check(
        "invalid structured output" in payload["error"],
        "invalid structure is identified as model-output failure",
    )


    print("\n[5] local backend failure becomes HTTP 502")

    def backend_failure(model, tokenizer, question, **kwargs):
        raise llm_backend.BackendError("synthetic backend failure")

    server.academic_reconciliation_orchestrator.run_academic_reconciliation = backend_failure

    response = asyncio.run(
        server.academic_chat_first_stage({"question": "Test"})
    )

    payload = response_payload(response)

    check(
        response.status_code == 502,
        "local backend failure returns HTTP 502",
    )

    check(
        payload["error"] == "Academic Chat local model unavailable.",
        "local backend failure is distinguished",
    )


    print("\n[6] reference-service failure becomes HTTP 502")

    def reference_failure(model, tokenizer, question, **kwargs):
        raise RuntimeError("synthetic Crossref/OpenAlex failure")

    server.academic_reconciliation_orchestrator.run_academic_reconciliation = reference_failure

    response = asyncio.run(
        server.academic_chat_first_stage({"question": "Test"})
    )

    payload = response_payload(response)

    check(
        response.status_code == 502,
        "reference-service failure returns HTTP 502",
    )

    check(
        payload["error"] == "Academic reference service unavailable.",
        "reference-service failure is distinguished from local-model failure",
    )

    print("\n[7] production source discoverer uses DOI-only OpenAlex lookup")

    original_openalex_getter = server.get_openalex_work_by_doi
    openalex_calls = []

    def fake_openalex_getter(doi):
        openalex_calls.append(doi)
        return {
            "doi": "https://doi.org/10.1234/example",
            "best_oa_location": {
                "landing_page_url": "https://example.org/article",
                "pdf_url": "https://example.org/article.pdf",
                "is_oa": True,
            },
        }

    try:
        server.get_openalex_work_by_doi = fake_openalex_getter

        discovered = server.discover_academic_source(
            "10.1234/example"
        )

        check(
            openalex_calls == ["10.1234/example"],
            "production source discoverer sends exactly the DOI to OpenAlex",
        )

        check(
            discovered.status == "location_found",
            "production source discoverer returns discovered location",
        )

        check(
            discovered.doi == "10.1234/example",
            "production source discovery retains normalised DOI",
        )

        check(
            discovered.pdf_url == "https://example.org/article.pdf",
            "production source discovery retains discovered PDF URL",
        )

    finally:
        server.get_openalex_work_by_doi = original_openalex_getter


    print("\n[8] production source retriever delegates to validated PDF retrieval")

    original_pdf_retriever = (
        server.academic_claims.retrieve_pdf_source_from_location
    )
    pdf_retrieval_calls = []

    source_location = server.academic_claims.SourceLocation(
        status="location_found",
        doi="10.1234/example",
        source="openalex",
        landing_page_url="https://example.org/article",
        pdf_url="https://example.org/article.pdf",
        is_oa=True,
        reasons=["Synthetic discovered source location."],
    )

    expected_retrieved = server.academic_claims.RetrievedSource(
        status="retrieved",
        doi="10.1234/example",
        source="openalex",
        text="Synthetic extracted scholarly PDF text.",
        locator="https://example.org/article.pdf",
        reasons=["Synthetic PDF retrieval."],
    )

    def fake_pdf_retriever(location):
        pdf_retrieval_calls.append(location)
        return expected_retrieved

    try:
        server.academic_claims.retrieve_pdf_source_from_location = (
            fake_pdf_retriever
        )

        retrieved = server.retrieve_academic_source(source_location)

        check(
            len(pdf_retrieval_calls) == 1,
            "production source retriever delegates exactly once",
        )

        check(
            len(pdf_retrieval_calls) == 1
            and pdf_retrieval_calls[0] is source_location,
            "production source retriever passes discovered location unchanged",
        )

        check(
            retrieved is expected_retrieved,
            "production source retriever returns PDF retrieval result unchanged",
        )

    finally:
        server.academic_claims.retrieve_pdf_source_from_location = (
            original_pdf_retriever
        )


    print("\n[9] production semantic assessor preserves application-owned evidence")

    original_claim_assessor = (
        server.academic_claim_assessor.generate_claim_assessor_output
    )
    claim_assessor_calls = []

    evidence = [
        academic_claims.ClaimEvidence(
            text="Synthetic located scholarly evidence.",
            locator="https://example.org/article.pdf",
            source="openalex",
            page_number=7,
        )
    ]

    def fake_claim_assessor_output(
        model,
        tokenizer,
        prompt,
        schema,
        *,
        max_tokens=512,
    ):
        claim_assessor_calls.append(
            {
                "model": model,
                "tokenizer": tokenizer,
                "prompt": prompt,
                "schema": schema,
            }
        )
        return {
            "status": "claim_supported",
            "reason": "The supplied evidence directly supports the claim.",
        }

    try:
        server.academic_claim_assessor.generate_claim_assessor_output = (
            fake_claim_assessor_output
        )
        server.model = "LOCAL-MODEL"
        server.tokenizer = "LOCAL-TOKENIZER"

        assessment = server.assess_academic_claim(
            "Synthetic atomic source claim.",
            evidence,
        )

        check(
            len(claim_assessor_calls) == 1,
            "production semantic assessor invokes local model adapter exactly once",
        )

        check(
            claim_assessor_calls[0]["model"] == "LOCAL-MODEL"
            and claim_assessor_calls[0]["tokenizer"] == "LOCAL-TOKENIZER",
            "semantic assessment uses the configured local model",
        )

        check(
            "Synthetic atomic source claim."
            in claim_assessor_calls[0]["prompt"],
            "semantic assessor prompt contains the atomic source claim",
        )

        check(
            "Synthetic located scholarly evidence."
            in claim_assessor_calls[0]["prompt"],
            "semantic assessor prompt contains only supplied located evidence",
        )

        check(
            assessment.status == "claim_supported",
            "validated semantic judgement is returned",
        )

        check(
            assessment.evidence is evidence,
            "semantic assessment retains application-owned evidence",
        )

        check(
            assessment.evidence[0].page_number == 7,
            "application-owned physical page provenance survives assessment",
        )

    finally:
        server.academic_claim_assessor.generate_claim_assessor_output = (
            original_claim_assessor
        )


    print(
        "\n[9b] production material-restriction assessor "
        "preserves structured-output contract"
    )

    material_restriction_calls = []
    material_restriction_schema = (
        academic_claim_coverage.material_restriction_output_schema()
    )

    def fake_material_restriction_output(
        model,
        tokenizer,
        prompt,
        schema,
        *,
        max_tokens=512,
    ):
        material_restriction_calls.append(
            {
                "model": model,
                "tokenizer": tokenizer,
                "prompt": prompt,
                "schema": schema,
                "max_tokens": max_tokens,
            }
        )
        return {"material_restriction_omitted": True}

    try:
        server.academic_claim_assessor.generate_claim_assessor_output = (
            fake_material_restriction_output
        )
        server.model = "LOCAL-MODEL"
        server.tokenizer = "LOCAL-TOKENIZER"

        material_restriction_output = (
            server.assess_academic_material_restriction(
                prompt="Synthetic bounded restriction prompt.",
                schema=material_restriction_schema,
            )
        )

        check(
            len(material_restriction_calls) == 1,
            "material-restriction assessor invokes local model adapter exactly once",
        )

        check(
            material_restriction_calls[0]["model"] == "LOCAL-MODEL"
            and material_restriction_calls[0]["tokenizer"]
            == "LOCAL-TOKENIZER",
            "material-restriction assessment uses the configured local model",
        )

        check(
            material_restriction_calls[0]["prompt"]
            == "Synthetic bounded restriction prompt.",
            "material-restriction prompt is forwarded unchanged",
        )

        check(
            material_restriction_calls[0]["schema"]
            == material_restriction_schema,
            "material-restriction schema is forwarded unchanged",
        )

        check(
            material_restriction_output
            == {"material_restriction_omitted": True},
            "material-restriction model output is returned unchanged",
        )

    finally:
        server.academic_claim_assessor.generate_claim_assessor_output = (
            original_claim_assessor
        )


    print("\n[10] production coverage uses the bounded local pipeline")

    coverage_calls = []
    existing_claim = academic_chat.TechnicalClaim(
        type="definition",
        concept="equal-tailed interval",
        statement="A 95% ETI leaves 2.5% probability in each tail.",
        parameterisation=None,
    )

    def fake_two_stage_output(
        model,
        tokenizer,
        prompt,
        schema,
        *,
        max_tokens=512,
        diagnostic_raw_output=None,
    ):
        coverage_calls.append(
            {
                "model": model,
                "tokenizer": tokenizer,
                "prompt": prompt,
                "schema": schema,
                "max_tokens": max_tokens,
            }
        )

        if (
            schema == academic_claim_coverage.claim_discovery_output_schema()
            and "ANSWER DRAFT" in prompt
        ):
            return {
                "discovered_claims": [
                    {
                        "type": "definition",
                        "concept": "equal-tailed interval",
                        "statement": (
                            "A 95% ETI leaves 2.5% probability in each tail."
                        ),
                        "parameterisation": None,
                        "source_anchor": (
                            "A 95% ETI leaves 2.5% probability in each tail"
                        ),
                    },
                    {
                        "type": "methodological",
                        "concept": "HDI width",
                        "statement": (
                            "For many skewed distributions, the HDI may be "
                            "narrower than the ETI."
                        ),
                        "parameterisation": None,
                        "source_anchor": (
                            "For many skewed distributions, the HDI may be "
                            "narrower than the ETI"
                        ),
                    },
                ]
            }

        if (
            schema == academic_claim_coverage.claim_discovery_output_schema()
            and "SOURCE SENTENCE" in prompt
        ):
            return {"discovered_claims": []}

        if schema == academic_claim_coverage.claim_decomposition_output_schema():
            return {
                "requires_decomposition": False,
                "atomic_claims": [],
            }

        if schema == academic_claim_coverage.claim_representation_output_schema():
            return {
                "represented": False,
                "represented_by": None,
            }

        raise AssertionError("Unexpected coverage schema.")

    original_coverage_output = (
        server.academic_claim_assessor.generate_claim_assessor_output
    )

    try:
        server.academic_claim_assessor.generate_claim_assessor_output = (
            fake_two_stage_output
        )
        server.model = "LOCAL-MODEL"
        server.tokenizer = "LOCAL-TOKENIZER"

        coverage_assessment = server.assess_academic_claim_coverage(
            answer_draft=(
                "A 95% ETI leaves 2.5% probability in each tail. "
                "For many skewed distributions, the HDI may be narrower "
                "than the ETI."
            ),
            existing_claims=[existing_claim],
        )

        check(
            len(coverage_calls) == 6,
            (
                "production coverage performs global discovery, two sentence "
                "audits, two decomposition checks, and representation"
            ),
        )
        check(
            all(
                call["model"] == "LOCAL-MODEL"
                and call["tokenizer"] == "LOCAL-TOKENIZER"
                for call in coverage_calls
            ),
            "all coverage stages use the configured local model",
        )
        check(
            coverage_calls[0]["schema"]
            == academic_claim_coverage.claim_discovery_output_schema(),
            "first coverage call is pure discovery",
        )
        check(
            coverage_calls[0]["max_tokens"]
            == server.ACADEMIC_COVERAGE_DISCOVERY_MAX_TOKENS
            == 2000,
            "discovery has its own high-recall token budget",
        )
        check(
            (
                "For many skewed distributions, the HDI may be narrower "
                "than the ETI."
            )
            in coverage_calls[0]["prompt"]
            and "ANSWER DRAFT" in coverage_calls[0]["prompt"]
            and "EXISTING TECHNICAL CLAIMS" not in coverage_calls[0]["prompt"],
            "discovery sees the answer but not existing claims",
        )
        audit_calls = [
            call
            for call in coverage_calls
            if (
                call["schema"]
                == academic_claim_coverage.claim_discovery_output_schema()
                and "SOURCE SENTENCE" in call["prompt"]
            )
        ]
        decomposition_calls = [
            call
            for call in coverage_calls
            if (
                call["schema"]
                == academic_claim_coverage.claim_decomposition_output_schema()
            )
        ]
        representation_calls = [
            call
            for call in coverage_calls
            if (
                call["schema"]
                == academic_claim_coverage.claim_representation_output_schema()
            )
        ]

        check(
            len(audit_calls) == 2
            and all(
                call["max_tokens"]
                == server.ACADEMIC_COVERAGE_DISCOVERY_MAX_TOKENS
                == 2000
                for call in audit_calls
            ),
            "each sentence receives the discovery-budget audit pass",
        )
        check(
            len(decomposition_calls) == 2
            and all(
                call["max_tokens"]
                == server.ACADEMIC_COVERAGE_DECOMPOSITION_MAX_TOKENS
                == 1000
                for call in decomposition_calls
            ),
            "each discovered proposition receives bounded decomposition",
        )
        check(
            len(representation_calls) == 1
            and representation_calls[0]["max_tokens"]
            == server.ACADEMIC_COVERAGE_REPRESENTATION_MAX_TOKENS
            == 256,
            "novel proposition receives bounded representation assessment",
        )
        check(
            existing_claim.statement in representation_calls[0]["prompt"],
            "representation sees existing structured claims",
        )
        check(
            coverage_assessment.status
            == academic_claim_coverage.COVERAGE_STATUS_MISSING_FOUND,
            "novel discovered proposition becomes successful coverage result",
        )
        check(
            coverage_assessment.result is not None
            and len(coverage_assessment.result.missing_claims) == 1,
            "exact duplicate is removed and novel proposition is retained",
        )

    finally:
        server.academic_claim_assessor.generate_claim_assessor_output = (
            original_coverage_output
        )


    print("\n[11] discovery failures make coverage unavailable")

    discovery_failure_factories = [
        lambda: llm_backend.BackendError("synthetic backend unavailable"),
        lambda: server.academic_claim_assessor.ClaimAssessorOutputError(
            "synthetic malformed JSON"
        ),
        lambda: server.academic_claim_coverage.ClaimCoverageOutputError(
            "synthetic invalid discovery proposal"
        ),
    ]

    for failure_factory in discovery_failure_factories:
        original_coverage_output = (
            server.academic_claim_assessor.generate_claim_assessor_output
        )

        def failing_discovery_output(
            model,
            tokenizer,
            prompt,
            schema,
            *,
            max_tokens=512,
            diagnostic_raw_output=None,
            _factory=failure_factory,
        ):
            if schema == academic_claim_coverage.claim_discovery_output_schema():
                raise _factory()
            raise AssertionError(
                "Representation should not run after discovery failure."
            )

        try:
            server.academic_claim_assessor.generate_claim_assessor_output = (
                failing_discovery_output
            )

            coverage_assessment = server.assess_academic_claim_coverage(
                answer_draft="Synthetic answer.",
                existing_claims=[],
            )

            check(
                coverage_assessment.status
                == academic_claim_coverage.COVERAGE_STATUS_UNAVAILABLE,
                (
                    f"{failure_factory().__class__.__name__} during discovery "
                    "makes coverage unavailable"
                ),
            )
            check(
                coverage_assessment.result is None,
                "failed discovery invents no coverage result",
            )
        finally:
            server.academic_claim_assessor.generate_claim_assessor_output = (
                original_coverage_output
            )


    print("\n[12] representation inference failures retain discovered claims")

    representation_failure_factories = [
        lambda: llm_backend.BackendError(
            "synthetic representation backend unavailable"
        ),
        lambda: server.academic_claim_assessor.ClaimAssessorOutputError(
            "synthetic representation malformed JSON"
        ),
    ]

    for failure_factory in representation_failure_factories:
        original_coverage_output = (
            server.academic_claim_assessor.generate_claim_assessor_output
        )

        def failing_representation_output(
            model,
            tokenizer,
            prompt,
            schema,
            *,
            max_tokens=512,
            diagnostic_raw_output=None,
            _factory=failure_factory,
        ):
            if (
                schema == academic_claim_coverage.claim_discovery_output_schema()
                and "ANSWER DRAFT" in prompt
            ):
                return {
                    "discovered_claims": [
                        {
                            "type": "interpretive",
                            "concept": "interval precision",
                            "statement": (
                                "A narrower HDI is not automatically "
                                "more precise."
                            ),
                            "parameterisation": None,
                            "source_anchor": (
                                "A narrower HDI is not automatically "
                                "more precise"
                            ),
                        }
                    ]
                }

            if (
                schema == academic_claim_coverage.claim_discovery_output_schema()
                and "SOURCE SENTENCE" in prompt
            ):
                return {"discovered_claims": []}

            if schema == academic_claim_coverage.claim_decomposition_output_schema():
                return {
                    "requires_decomposition": False,
                    "atomic_claims": [],
                }

            if schema == academic_claim_coverage.claim_representation_output_schema():
                raise _factory()

            raise AssertionError("Unexpected coverage schema.")

        try:
            server.academic_claim_assessor.generate_claim_assessor_output = (
                failing_representation_output
            )

            coverage_assessment = server.assess_academic_claim_coverage(
                answer_draft=(
                    "A narrower HDI is not automatically more precise."
                ),
                existing_claims=[existing_claim],
            )

            check(
                coverage_assessment.status
                == academic_claim_coverage.COVERAGE_STATUS_MISSING_FOUND,
                (
                    f"{failure_factory().__class__.__name__} during "
                    "representation does not erase discovered claim"
                ),
            )
            check(
                coverage_assessment.result is not None
                and len(coverage_assessment.result.missing_claims) == 1,
                "representation failure fails open into downstream checking",
            )
        finally:
            server.academic_claim_assessor.generate_claim_assessor_output = (
                original_coverage_output
            )


    print("\n[13] unexpected coverage programming failures still propagate")

    original_coverage_function = (
        server.academic_claim_coverage.assess_claim_coverage_two_stage
    )

    def programming_failure(**kwargs):
        raise TypeError("synthetic programming failure")

    try:
        server.academic_claim_coverage.assess_claim_coverage_two_stage = (
            programming_failure
        )

        try:
            server.assess_academic_claim_coverage(
                answer_draft="Synthetic answer.",
                existing_claims=[],
            )
        except TypeError as exc:
            check(
                str(exc) == "synthetic programming failure",
                "unexpected programming failure propagates unchanged",
            )
        else:
            check(
                False,
                "unexpected programming failure was incorrectly swallowed",
            )
    finally:
        server.academic_claim_coverage.assess_claim_coverage_two_stage = (
            original_coverage_function
        )


finally:
    server.ensure_model = original_ensure_model
    server.academic_reconciliation_orchestrator.run_academic_reconciliation = original_orchestrator


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll combined Academic Chat endpoint checks passed.")
