"""Regression tests for the combined Academic Chat first-stage endpoint."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import llm_backend
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
original_orchestrator = server.academic_orchestrator.run_academic_first_stage

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
    source_discoverer=None,
):
    orchestrator_calls.append(
        {
            "model": model,
            "tokenizer": tokenizer,
            "question": question,
            "source_discoverer": source_discoverer,
        }
    )
    return FakeResult()


try:
    server.ensure_model = fake_ensure_model
    server.academic_orchestrator.run_academic_first_stage = fake_orchestrator

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
        callable(orchestrator_calls[0]["source_discoverer"]),
        "production endpoint supplies a source discoverer",
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

    server.academic_orchestrator.run_academic_first_stage = malformed_orchestrator

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

    server.academic_orchestrator.run_academic_first_stage = backend_failure

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

    server.academic_orchestrator.run_academic_first_stage = reference_failure

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

finally:
    server.ensure_model = original_ensure_model
    server.academic_orchestrator.run_academic_first_stage = original_orchestrator


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll combined Academic Chat endpoint checks passed.")
