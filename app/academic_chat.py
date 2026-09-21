"""
Structured first-pass output for Academic Chat.

This module defines the boundary between model-generated academic content
and software-controlled verification.

The model may propose:
- an answer draft,
- bibliographic references,
- technical claims.

The model may NOT assign verification status. Bibliographic verification
and future technical verification are separate software-controlled steps.

Parsing is intentionally conservative. Valid JSON and a simple surrounding
Markdown JSON fence are accepted. Malformed or unexpected structures are
rejected rather than repaired.
"""

from dataclasses import asdict, dataclass
import json
from typing import Any

import llm_backend


class AcademicDraftError(ValueError):
    """Raised when model output does not satisfy the Academic Chat contract."""


@dataclass
class AcademicReference:
    title: str | None
    author: str | None
    year: int | None
    venue: str | None
    doi: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceClaim:
    claim: str
    reference_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TechnicalClaim:
    type: str
    concept: str
    statement: str
    parameterisation: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AcademicDraft:
    answer_draft: str
    references: list[AcademicReference]
    source_claims: list[SourceClaim]
    technical_claims: list[TechnicalClaim]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TOP_LEVEL_FIELDS = {
    "answer_draft",
    "references",
    "source_claims",
    "technical_claims",
}

_REFERENCE_FIELDS = {
    "title",
    "author",
    "year",
    "venue",
    "doi",
}

_SOURCE_CLAIM_FIELDS = {
    "claim",
    "reference_index",
}

_TECHNICAL_CLAIM_FIELDS = {
    "type",
    "concept",
    "statement",
    "parameterisation",
}


# Per-request constrained decoding for llama-server. This mirrors the parser's
# structural contract but deliberately leaves semantic validation to the
# parser below (for example, a reference must contain a title or DOI).
ACADEMIC_DRAFT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "academic_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer_draft": {
                    "type": "string",
                },
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": ["string", "null"],
                            },
                            "author": {
                                "type": ["string", "null"],
                            },
                            "year": {
                                "type": ["integer", "null"],
                            },
                            "venue": {
                                "type": ["string", "null"],
                            },
                            "doi": {
                                "type": ["string", "null"],
                            },
                        },
                        "required": [
                            "title",
                            "author",
                            "year",
                            "venue",
                            "doi",
                        ],
                        "additionalProperties": False,
                    },
                },
                "source_claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim": {
                                "type": "string",
                            },
                            "reference_index": {
                                "type": "integer",
                                "minimum": 0,
                            },
                        },
                        "required": [
                            "claim",
                            "reference_index",
                        ],
                        "additionalProperties": False,
                    },
                },
                "technical_claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                            },
                            "concept": {
                                "type": "string",
                            },
                            "statement": {
                                "type": "string",
                            },
                            "parameterisation": {
                                "type": ["string", "null"],
                            },
                        },
                        "required": [
                            "type",
                            "concept",
                            "statement",
                            "parameterisation",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "answer_draft",
                "references",
                "source_claims",
                "technical_claims",
            ],
            "additionalProperties": False,
        },
    },
}


def _strip_json_fence(text: str) -> str:
    """Remove one simple surrounding Markdown JSON fence, if present."""
    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 3:
        raise AcademicDraftError("Incomplete Markdown JSON fence.")

    opening = lines[0].strip().lower()
    if opening not in {"```", "```json"}:
        raise AcademicDraftError(
            "Only a plain or JSON-labelled Markdown fence is accepted."
        )

    if lines[-1].strip() != "```":
        raise AcademicDraftError("Markdown JSON fence is not closed.")

    return "\n".join(lines[1:-1]).strip()


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AcademicDraftError(
            f"{field} must be a string or null."
        )
    value = value.strip()
    return value or None


def _parse_reference(value: Any, index: int) -> AcademicReference:
    if not isinstance(value, dict):
        raise AcademicDraftError(
            f"references[{index}] must be an object."
        )

    unexpected = set(value) - _REFERENCE_FIELDS
    if unexpected:
        raise AcademicDraftError(
            f"references[{index}] contains unexpected fields: "
            f"{', '.join(sorted(unexpected))}."
        )

    title = _optional_string(
        value.get("title"),
        f"references[{index}].title",
    )
    author = _optional_string(
        value.get("author"),
        f"references[{index}].author",
    )
    venue = _optional_string(
        value.get("venue"),
        f"references[{index}].venue",
    )
    doi = _optional_string(
        value.get("doi"),
        f"references[{index}].doi",
    )

    year = value.get("year")
    if year is not None:
        if isinstance(year, bool) or not isinstance(year, int):
            raise AcademicDraftError(
                f"references[{index}].year must be an integer or null."
            )

    if not title and not doi:
        raise AcademicDraftError(
            f"references[{index}] must contain a title or DOI."
        )

    return AcademicReference(
        title=title,
        author=author,
        year=year,
        venue=venue,
        doi=doi,
    )


def _required_nonempty_string(
    value: dict[str, Any],
    field: str,
    index: int,
) -> str:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise AcademicDraftError(
            f"technical_claims[{index}].{field} "
            "must be a non-empty string."
        )
    return raw.strip()


def _parse_source_claim(value: Any, index: int) -> SourceClaim:
    if not isinstance(value, dict):
        raise AcademicDraftError(
            f"source_claims[{index}] must be an object."
        )

    unexpected = set(value) - _SOURCE_CLAIM_FIELDS
    if unexpected:
        raise AcademicDraftError(
            f"source_claims[{index}] contains unexpected fields: "
            f"{', '.join(sorted(unexpected))}."
        )

    claim = value.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        raise AcademicDraftError(
            f"source_claims[{index}].claim must be a non-empty string."
        )

    reference_index = value.get("reference_index")
    if isinstance(reference_index, bool) or not isinstance(reference_index, int):
        raise AcademicDraftError(
            f"source_claims[{index}].reference_index must be an integer."
        )

    return SourceClaim(
        claim=claim.strip(),
        reference_index=reference_index,
    )


def _parse_technical_claim(value: Any, index: int) -> TechnicalClaim:
    if not isinstance(value, dict):
        raise AcademicDraftError(
            f"technical_claims[{index}] must be an object."
        )

    unexpected = set(value) - _TECHNICAL_CLAIM_FIELDS
    if unexpected:
        raise AcademicDraftError(
            f"technical_claims[{index}] contains unexpected fields: "
            f"{', '.join(sorted(unexpected))}."
        )

    claim_type = _required_nonempty_string(value, "type", index)
    concept = _required_nonempty_string(value, "concept", index)
    statement = _required_nonempty_string(value, "statement", index)
    parameterisation = _optional_string(
        value.get("parameterisation"),
        f"technical_claims[{index}].parameterisation",
    )

    return TechnicalClaim(
        type=claim_type,
        concept=concept,
        statement=statement,
        parameterisation=parameterisation,
    )


def parse_academic_draft(text: str) -> AcademicDraft:
    """Parse and validate a model-generated Academic Chat first pass."""
    if not isinstance(text, str) or not text.strip():
        raise AcademicDraftError(
            "Academic Chat output must be non-empty text."
        )

    payload_text = _strip_json_fence(text)

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise AcademicDraftError(
            f"Academic Chat output is not valid JSON: {exc.msg}."
        ) from exc

    if not isinstance(payload, dict):
        raise AcademicDraftError(
            "Academic Chat output must be a JSON object."
        )

    unexpected = set(payload) - _TOP_LEVEL_FIELDS
    if unexpected:
        raise AcademicDraftError(
            "Academic Chat output contains unexpected fields: "
            f"{', '.join(sorted(unexpected))}."
        )

    missing = _TOP_LEVEL_FIELDS - set(payload)
    if missing:
        raise AcademicDraftError(
            "Academic Chat output is missing required fields: "
            f"{', '.join(sorted(missing))}."
        )

    answer_draft = payload["answer_draft"]
    if not isinstance(answer_draft, str) or not answer_draft.strip():
        raise AcademicDraftError(
            "answer_draft must be a non-empty string."
        )

    references = payload["references"]
    if not isinstance(references, list):
        raise AcademicDraftError("references must be an array.")

    source_claims = payload["source_claims"]
    if not isinstance(source_claims, list):
        raise AcademicDraftError("source_claims must be an array.")

    technical_claims = payload["technical_claims"]
    if not isinstance(technical_claims, list):
        raise AcademicDraftError("technical_claims must be an array.")

    parsed_references = [
        _parse_reference(value, index)
        for index, value in enumerate(references)
    ]

    parsed_source_claims = [
        _parse_source_claim(value, index)
        for index, value in enumerate(source_claims)
    ]

    for source_claim in parsed_source_claims:
        if not 0 <= source_claim.reference_index < len(parsed_references):
            raise AcademicDraftError(
                "source_claims reference_index must identify "
                "an existing reference."
            )

    return AcademicDraft(
        answer_draft=answer_draft.strip(),
        references=parsed_references,
        source_claims=parsed_source_claims,
        technical_claims=[
            _parse_technical_claim(value, index)
            for index, value in enumerate(technical_claims)
        ],
    )


# ---------------------------------------------------------------------------
# Local-model first pass
# ---------------------------------------------------------------------------

ACADEMIC_DRAFT_SYSTEM_PROMPT = """\
You are the first-pass reasoning component of Academic Chat.

Your task is to produce a concise provisional proposal for later verification,
not a polished final answer. References and technical claims will be checked by
later software stages.

Return exactly one JSON object and no explanatory text outside it.

The object must have exactly these top-level fields:
- "answer_draft": a non-empty string containing your provisional answer.
- "references": an array of bibliographic reference proposals.
- "source_claims": an array associating claims with proposed references.
- "technical_claims": an array of checkable technical claims.

Keep "answer_draft" concise: no more than 150 words. State each proposition
once. Do not debate, reconsider, repeatedly correct, or repeat propositions
inside "answer_draft".

If you are uncertain about a formula, quantitative rule, threshold,
parameterisation, assumption, or other technical proposition, do not resolve,
debate, or repeatedly revise it in "answer_draft". Omit the uncertain technical
detail from "answer_draft" and place the proposed claim once in
"technical_claims" for later verification. Uncertainty about a technical detail
is a reason to externalise it for verification, not to reason through competing
versions inside "answer_draft".

Use plain-text mathematical notation in all JSON strings. Do not use LaTeX
commands or backslashes. Prefer forms such as lambda, >=, <=, *, /, ^ and
parentheses.

Each reference object must contain exactly:
- "title": string or null
- "author": string or null
- "year": integer or null
- "venue": string or null
- "doi": string or null

A reference must contain at least a title or DOI.
Propose no more than 3 references.

References are proposals, not verified references. Do not include fields such
as "verified", "reference_verified", "claim_verified", or confidence scores.
If you are uncertain about a bibliographic field, use null rather than inventing
a value. Do not invent a DOI.

Each source claim object must contain exactly:
- "claim": non-empty string
- "reference_index": non-negative integer

Use reference_index to identify the entry in the references array proposed to
support that claim. Source claims are proposals, not verified support. Do not
include verification status, support status, or confidence scores in a source
claim. If no source-supported claims are proposed, return an empty
source_claims array.

Source claims should be specific, self-contained propositions that materially
depend on the cited literature. Keep each source claim atomic: do not combine
multiple factual propositions into one claim merely because they share a
reference. Do not create source claims for statements that do not require
external source support.

Each technical claim object must contain exactly:
- "type": non-empty string
- "concept": non-empty string
- "statement": non-empty string
- "parameterisation": string or null

Technical claims are assertions that may require independent checking. Include
statistical or mathematical formulae, quantitative rules of thumb, thresholds,
parameterisations, assumptions with technical consequences, and similar
checkable methodological statements when they materially support the answer.
Propose no more than 5 technical claims.

Do not state or imply that a technical claim has been verified. The application,
not you, controls verification status.

If no references are proposed, return an empty references array.
If no technical claims require checking, return an empty technical_claims array.

Use null for unknown optional values. Do not use placeholder bibliographic
details merely to satisfy the schema.
"""


def generate_academic_draft(
    model: Any,
    tokenizer: Any,
    question: str,
    *,
    max_tokens: int = 2400,
) -> AcademicDraft:
    """
    Generate and parse Academic Chat's local first pass.

    The complete user question is sent only to the already-configured local
    model backend. This function performs no bibliographic or other external
    network lookup.

    Thinking is disabled for this structural pass: the output is a constrained
    machine-readable proposal that will be checked by later software stages.
    """
    if not isinstance(question, str) or not question.strip():
        raise AcademicDraftError(
            "Academic Chat question must be non-empty text."
        )

    messages = [
        {
            "role": "system",
            "content": ACADEMIC_DRAFT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": question.strip(),
        },
    ]

    sampler = llm_backend.make_sampler(
        temp=0.1,
        top_p=0.8,
        top_k=20,
        response_format=ACADEMIC_DRAFT_RESPONSE_FORMAT,
    )

    with llm_backend.thinking(False):
        raw = llm_backend.generate(
            model,
            tokenizer,
            messages,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )

    return parse_academic_draft(raw)
