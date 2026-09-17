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
    technical_claims: list[TechnicalClaim]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TOP_LEVEL_FIELDS = {
    "answer_draft",
    "references",
    "technical_claims",
}

_REFERENCE_FIELDS = {
    "title",
    "author",
    "year",
    "venue",
    "doi",
}

_TECHNICAL_CLAIM_FIELDS = {
    "type",
    "concept",
    "statement",
    "parameterisation",
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

    technical_claims = payload["technical_claims"]
    if not isinstance(technical_claims, list):
        raise AcademicDraftError("technical_claims must be an array.")

    return AcademicDraft(
        answer_draft=answer_draft.strip(),
        references=[
            _parse_reference(value, index)
            for index, value in enumerate(references)
        ],
        technical_claims=[
            _parse_technical_claim(value, index)
            for index, value in enumerate(technical_claims)
        ],
    )
