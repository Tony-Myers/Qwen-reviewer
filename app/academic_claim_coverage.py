"""
Technical-claim coverage discovery for Academic Chat.

This module identifies material, independently checkable statistical,
mathematical, or methodological propositions stated in an Academic Chat answer
that are not already represented by its structured TechnicalClaim objects.

Coverage discovery does not judge whether a proposition is true, supported,
verified, or methodologically consistent. Model output is an untrusted proposal.
This module validates that proposal and converts accepted omissions into
application-owned TechnicalClaim objects for later independent checking.
"""

from dataclasses import dataclass
from typing import Any, Callable

import academic_chat


@dataclass
class ClaimCoverageResult:
    """Application-owned technical claims proposed as missing from an answer."""

    missing_claims: list[academic_chat.TechnicalClaim]

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_claims": [
                claim.to_dict()
                for claim in self.missing_claims
            ]
        }


COVERAGE_STATUS_MISSING_FOUND = "missing_claims_found"
COVERAGE_STATUS_NO_MISSING_PROPOSED = "no_missing_claims_proposed"
COVERAGE_STATUS_UNAVAILABLE = "coverage_assessment_unavailable"
COVERAGE_STATUS_NOT_ATTEMPTED = "coverage_not_attempted"


@dataclass
class ClaimCoverageAssessment:
    """Application-owned state of one technical-claim coverage assessment."""

    status: str
    result: ClaimCoverageResult | None
    reasons: list[str]

    @classmethod
    def from_result(
        cls,
        result: ClaimCoverageResult,
    ) -> "ClaimCoverageAssessment":
        """Represent a successfully established coverage proposal."""
        if not isinstance(result, ClaimCoverageResult):
            raise TypeError(
                "Coverage assessment requires a ClaimCoverageResult."
            )

        status = (
            COVERAGE_STATUS_MISSING_FOUND
            if result.missing_claims
            else COVERAGE_STATUS_NO_MISSING_PROPOSED
        )

        return cls(
            status=status,
            result=result,
            reasons=[],
        )

    @classmethod
    def not_attempted(
        cls,
        reason: str,
    ) -> "ClaimCoverageAssessment":
        """Represent coverage that was not attempted."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "Unattempted coverage requires a non-empty reason."
            )

        return cls(
            status=COVERAGE_STATUS_NOT_ATTEMPTED,
            result=None,
            reasons=[reason.strip()],
        )

    @classmethod
    def unavailable(
        cls,
        reason: str,
    ) -> "ClaimCoverageAssessment":
        """Represent coverage that could not be established."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "Unavailable coverage requires a non-empty reason."
            )

        return cls(
            status=COVERAGE_STATUS_UNAVAILABLE,
            result=None,
            reasons=[reason.strip()],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise coverage state without claiming verified completeness."""
        return {
            "status": self.status,
            "missing_claims": (
                None
                if self.result is None
                else [
                    claim.to_dict()
                    for claim in self.result.missing_claims
                ]
            ),
            "reasons": list(self.reasons),
        }


def claim_coverage_output_schema() -> dict[str, Any]:
    """Return the strict structured-output schema for coverage discovery."""
    return {
        "type": "object",
        "properties": {
            "missing_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "concept": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "statement": {
                            "type": "string",
                            "minLength": 1,
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
            }
        },
        "required": ["missing_claims"],
        "additionalProperties": False,
    }


def build_claim_coverage_prompt(
    *,
    answer_draft: str,
    existing_claims: list[academic_chat.TechnicalClaim],
) -> str:
    """Build a prompt limited to claim-coverage discovery."""
    if not isinstance(answer_draft, str) or not answer_draft.strip():
        raise ValueError(
            "Claim coverage requires a non-empty answer draft."
        )

    if (
        not isinstance(existing_claims, list)
        or not all(
            isinstance(claim, academic_chat.TechnicalClaim)
            for claim in existing_claims
        )
    ):
        raise TypeError(
            "Existing claims must be a list of TechnicalClaim objects."
        )

    if existing_claims:
        existing_blocks = []

        for index, claim in enumerate(existing_claims, start=1):
            parameterisation = (
                claim.parameterisation
                if claim.parameterisation is not None
                else "not specified"
            )
            existing_blocks.append(
                "\n".join(
                    [
                        f"EXISTING CLAIM {index}",
                        f"type: {claim.type}",
                        f"concept: {claim.concept}",
                        f"statement: {claim.statement}",
                        f"parameterisation: {parameterisation}",
                    ]
                )
            )

        existing_text = "\n\n".join(existing_blocks)
    else:
        existing_text = "(none)"

    return f"""Identify material, independently checkable statistical,
mathematical, or methodological propositions stated in the answer that are
not already represented by the existing technical claims.

ANSWER DRAFT
{answer_draft.strip()}

EXISTING TECHNICAL CLAIMS
{existing_text}

RULES
Use only the answer draft and existing technical claims supplied above.
Do not use outside knowledge.
Do not judge whether any proposition is true or false.
Do not verify, correct, support, contradict, or assess methodological
consistency.
Do not return propositions that are already represented by an existing claim.
A proposition is already represented only when an existing claim expresses the
same material proposition. Sharing the same topic or concept is not enough.
Treat materially different qualifiers, frequency or prevalence statements,
direction, conditions, populations, parameterisations, or causal or mechanistic
assertions as distinct propositions when they change what is being asserted.
Identify only material, checkable statistical, mathematical, or methodological
propositions whose independent checking could matter to the substantive answer.
Do not promote ordinary explanatory wording, rhetorical statements, or purely
stylistic text into technical claims.
Keep each missing claim atomic and self-contained.
Preserve important qualifiers, direction, conditions, and parameterisation from
the answer.
Do not impose an arbitrary numerical limit on missing claims.

For each genuinely missing proposition return exactly:
- type
- concept
- statement
- parameterisation

Use null when parameterisation is not specified.

If no material checkable proposition is missing, return an empty
missing_claims array.

Return only the required missing_claims object. Do not return verification
status, coverage status, confidence, provenance, reasoning, commentary, the
answer draft, or the existing claims.
"""


def _parse_missing_claim(
    value: Any,
    index: int,
) -> academic_chat.TechnicalClaim:
    if not isinstance(value, dict):
        raise ValueError(
            f"missing_claims[{index}] must be an object."
        )

    expected = {
        "type",
        "concept",
        "statement",
        "parameterisation",
    }

    if set(value) != expected:
        raise ValueError(
            f"missing_claims[{index}] must contain exactly "
            "type, concept, statement, and parameterisation."
        )

    parsed = {}

    for field in ("type", "concept", "statement"):
        raw = value[field]
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(
                f"missing_claims[{index}].{field} "
                "must be non-empty text."
            )
        parsed[field] = raw.strip()

    parameterisation = value["parameterisation"]

    if parameterisation is not None:
        if (
            not isinstance(parameterisation, str)
            or not parameterisation.strip()
        ):
            raise ValueError(
                f"missing_claims[{index}].parameterisation "
                "must be non-empty text or null."
            )
        parameterisation = parameterisation.strip()

    return academic_chat.TechnicalClaim(
        type=parsed["type"],
        concept=parsed["concept"],
        statement=parsed["statement"],
        parameterisation=parameterisation,
    )


def _claim_key(
    claim: academic_chat.TechnicalClaim,
) -> tuple[str, str, str, str | None]:
    """Return an exact normalized key without claiming semantic equivalence."""
    return (
        claim.type.strip(),
        claim.concept.strip(),
        claim.statement.strip(),
        (
            claim.parameterisation.strip()
            if claim.parameterisation is not None
            else None
        ),
    )


def build_claim_coverage(
    *,
    answer_draft: str,
    existing_claims: list[academic_chat.TechnicalClaim],
    assessor_output: Any,
) -> ClaimCoverageResult:
    """Validate an untrusted coverage proposal and attach application ownership."""
    if not isinstance(answer_draft, str) or not answer_draft.strip():
        raise ValueError(
            "Claim coverage requires a non-empty answer draft."
        )

    if (
        not isinstance(existing_claims, list)
        or not all(
            isinstance(claim, academic_chat.TechnicalClaim)
            for claim in existing_claims
        )
    ):
        raise TypeError(
            "Existing claims must be a list of TechnicalClaim objects."
        )

    if not isinstance(assessor_output, dict):
        raise ValueError(
            "Claim coverage assessor output must be an object."
        )

    if set(assessor_output) != {"missing_claims"}:
        raise ValueError(
            "Claim coverage assessor output must contain exactly "
            "'missing_claims'."
        )

    raw_missing = assessor_output["missing_claims"]

    if not isinstance(raw_missing, list):
        raise ValueError(
            "Claim coverage missing_claims must be an array."
        )

    existing_keys = {
        _claim_key(claim)
        for claim in existing_claims
    }

    accepted = []
    accepted_keys = set()

    for index, value in enumerate(raw_missing):
        claim = _parse_missing_claim(value, index)
        key = _claim_key(claim)

        if key in existing_keys or key in accepted_keys:
            continue

        accepted.append(claim)
        accepted_keys.add(key)

    return ClaimCoverageResult(
        missing_claims=accepted,
    )


def assess_claim_coverage(
    *,
    answer_draft: str,
    existing_claims: list[academic_chat.TechnicalClaim],
    assessor: Callable[..., Any],
) -> ClaimCoverageResult:
    """Discover missing technical claims through an injected local assessor."""
    prompt = build_claim_coverage_prompt(
        answer_draft=answer_draft,
        existing_claims=existing_claims,
    )
    schema = claim_coverage_output_schema()

    assessor_output = assessor(
        prompt=prompt,
        schema=schema,
    )

    return build_claim_coverage(
        answer_draft=answer_draft,
        existing_claims=existing_claims,
        assessor_output=assessor_output,
    )
