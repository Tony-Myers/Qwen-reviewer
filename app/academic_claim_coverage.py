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

from dataclasses import dataclass, field
from typing import Any, Callable

import academic_chat


class ClaimCoverageOutputError(ValueError):
    """Raised when untrusted claim-coverage assessor output is invalid."""



@dataclass
class ClaimRepresentation:
    """Application-owned assessment of whether one candidate is represented."""

    represented: bool
    represented_by: int | None


@dataclass
class ClaimCoverageResult:
    """Application-owned result of independent technical-claim coverage."""

    missing_claims: list[academic_chat.TechnicalClaim]
    discovered_claims: list[academic_chat.TechnicalClaim] = field(
        default_factory=list
    )

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




def claim_representation_output_schema() -> dict[str, Any]:
    """Return the strict structured-output schema for representation."""
    return {
        "type": "object",
        "properties": {
            "represented": {
                "type": "boolean",
            },
            "represented_by": {
                "type": ["integer", "null"],
            },
        },
        "required": [
            "represented",
            "represented_by",
        ],
        "additionalProperties": False,
    }


def build_claim_representation_prompt(
    *,
    candidate_claim: academic_chat.TechnicalClaim,
    existing_claims: list[academic_chat.TechnicalClaim],
) -> str:
    """Build a prompt limited to proposition representation assessment."""
    if not isinstance(candidate_claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Candidate claim must be a TechnicalClaim object."
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

    candidate_parameterisation = (
        candidate_claim.parameterisation
        if candidate_claim.parameterisation is not None
        else "not specified"
    )

    candidate_text = "\n".join(
        [
            f"type: {candidate_claim.type}",
            f"concept: {candidate_claim.concept}",
            f"statement: {candidate_claim.statement}",
            f"parameterisation: {candidate_parameterisation}",
        ]
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

    return f"""Decide whether the candidate proposition is already represented
by one of the existing technical claims.

CANDIDATE PROPOSITION
{candidate_text}

EXISTING TECHNICAL CLAIMS
{existing_text}

RULES
Use only the candidate proposition and existing technical claims supplied.
Do not use outside knowledge.
Do not judge whether any proposition is true or false.
Do not verify, correct, support, contradict, or assess methodological
consistency.
Return represented=true only when an existing claim expresses the same material
proposition as the candidate.
Sharing the same topic, concept, conclusion, or general subject is not enough.
A broader related claim does not represent a narrower proposition merely
because both concern the same phenomenon.
Preserve distinctions involving qualifiers, frequency, direction, conditions,
populations, parameterisation, comparisons, interpretations, mechanisms, and
recommendations whenever they change what is being asserted.

If represented=true, represented_by must be the 1-based index of the existing
claim that expresses the same material proposition.
If represented=false, represented_by must be null.

Return only the required represented and represented_by fields. Do not return
verification status, confidence, provenance, reasoning, commentary, or any
additional fields.
"""


def claim_discovery_output_schema() -> dict[str, Any]:
    """Return the strict structured-output schema for proposition discovery."""
    return {
        "type": "object",
        "properties": {
            "discovered_claims": {
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
        "required": ["discovered_claims"],
        "additionalProperties": False,
    }


def build_claim_discovery_prompt(
    *,
    answer_draft: str,
) -> str:
    """Build a prompt limited to proposition discovery."""
    if not isinstance(answer_draft, str) or not answer_draft.strip():
        raise ValueError(
            "Claim discovery requires a non-empty answer draft."
        )

    return f"""Identify material, independently checkable statistical,
mathematical, or methodological propositions stated in the answer.

ANSWER DRAFT
{answer_draft.strip()}

RULES
Use only the answer draft supplied above.
Do not use outside knowledge.
Do not judge whether any proposition is true or false.
Do not verify, correct, support, contradict, or assess methodological
consistency.
Identify only material, checkable statistical, mathematical, or methodological
propositions whose independent checking could matter to the substantive answer.
Explanatory prose can contain material, checkable propositions. Do not ignore a
proposition merely because it appears inside an explanation rather than as a
standalone technical statement.
Inspect separately for:
- definitions;
- qualifiers or frequency statements such as often, sometimes, usually,
  necessarily, always, or rarely;
- comparative or conditional statements;
- explanatory, inferential, causal, or mechanistic links;
- interpretive conclusions;
- recommendations or preferences.
Keep each discovered claim atomic and self-contained. Keep propositions separate
when they could independently differ in support or correctness. Do not bundle
them merely because they occur in the same sentence, explanation, or support
the same overall conclusion.
Preserve important qualifiers, direction, conditions, populations, and
parameterisation from the answer.
Do not promote genuinely rhetorical, stylistic, or non-checkable wording into
technical claims.
Do not impose an arbitrary numerical limit on discovered claims.

For each material proposition return exactly:
- type
- concept
- statement
- parameterisation

Use null when parameterisation is not specified.

If the answer contains no material checkable proposition, return an empty
discovered_claims array.

Return only the required discovered_claims object. Do not return verification
status, coverage status, confidence, provenance, reasoning, commentary, or the
answer draft.
"""


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
Explanatory prose can contain material, checkable propositions. Do not ignore a
proposition merely because it appears inside an explanation rather than as a
standalone technical statement.
Inspect separately for:
- qualifiers or frequency statements such as often, sometimes, usually,
  necessarily, always, or rarely;
- comparative or conditional statements;
- explanatory, inferential, causal, or mechanistic links;
- interpretive conclusions;
- recommendations or preferences.
Keep each missing claim atomic and self-contained. Keep propositions separate
when they could independently differ in support or correctness. Do not bundle
them merely because they occur in the same sentence, explanation, or support
the same overall conclusion.
Preserve important qualifiers, direction, conditions, and parameterisation from
the answer.
Do not promote genuinely rhetorical, stylistic, or non-checkable wording into
technical claims.
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
        raise ClaimCoverageOutputError(
            f"missing_claims[{index}] must be an object."
        )

    expected = {
        "type",
        "concept",
        "statement",
        "parameterisation",
    }

    if set(value) != expected:
        raise ClaimCoverageOutputError(
            f"missing_claims[{index}] must contain exactly "
            "type, concept, statement, and parameterisation."
        )

    parsed = {}

    for field in ("type", "concept", "statement"):
        raw = value[field]
        if not isinstance(raw, str) or not raw.strip():
            raise ClaimCoverageOutputError(
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
            raise ClaimCoverageOutputError(
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
        raise ClaimCoverageOutputError(
            "Claim coverage assessor output must be an object."
        )

    if set(assessor_output) != {"missing_claims"}:
        raise ClaimCoverageOutputError(
            "Claim coverage assessor output must contain exactly "
            "'missing_claims'."
        )

    raw_missing = assessor_output["missing_claims"]

    if not isinstance(raw_missing, list):
        raise ClaimCoverageOutputError(
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



def build_claim_representation(
    *,
    candidate_claim: academic_chat.TechnicalClaim,
    existing_claims: list[academic_chat.TechnicalClaim],
    assessor_output: Any,
) -> ClaimRepresentation:
    """Validate an untrusted proposition-representation decision."""
    if not isinstance(candidate_claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Candidate claim must be a TechnicalClaim object."
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
        raise ClaimCoverageOutputError(
            "Claim representation assessor output must be an object."
        )

    if set(assessor_output) != {
        "represented",
        "represented_by",
    }:
        raise ClaimCoverageOutputError(
            "Claim representation assessor output must contain exactly "
            "'represented' and 'represented_by'."
        )

    represented = assessor_output["represented"]
    represented_by = assessor_output["represented_by"]

    if not isinstance(represented, bool):
        raise ClaimCoverageOutputError(
            "Claim representation represented must be boolean."
        )

    if represented:
        if (
            not isinstance(represented_by, int)
            or isinstance(represented_by, bool)
            or represented_by < 1
            or represented_by > len(existing_claims)
        ):
            raise ClaimCoverageOutputError(
                "A represented claim requires a valid 1-based "
                "represented_by index."
            )
    elif represented_by is not None:
        raise ClaimCoverageOutputError(
            "A non-represented claim requires represented_by=null."
        )

    return ClaimRepresentation(
        represented=represented,
        represented_by=represented_by,
    )


def discover_answer_claims(
    *,
    answer_draft: str,
    assessor: Callable[..., Any],
) -> list[academic_chat.TechnicalClaim]:
    """Discover material atomic propositions without representation filtering."""
    prompt = build_claim_discovery_prompt(
        answer_draft=answer_draft,
    )
    schema = claim_discovery_output_schema()
    assessor_output = assessor(
        prompt=prompt,
        schema=schema,
    )

    if not isinstance(assessor_output, dict):
        raise ClaimCoverageOutputError(
            "Claim discovery assessor output must be an object."
        )

    if set(assessor_output) != {"discovered_claims"}:
        raise ClaimCoverageOutputError(
            "Claim discovery assessor output must contain exactly "
            "'discovered_claims'."
        )

    raw_discovered = assessor_output["discovered_claims"]

    if not isinstance(raw_discovered, list):
        raise ClaimCoverageOutputError(
            "Claim discovery discovered_claims must be an array."
        )

    discovered = []
    discovered_keys = set()

    for index, value in enumerate(raw_discovered):
        claim = _parse_missing_claim(value, index)
        key = _claim_key(claim)

        if key in discovered_keys:
            continue

        discovered.append(claim)
        discovered_keys.add(key)

    return discovered


def assess_claim_representation(
    *,
    candidate_claim: academic_chat.TechnicalClaim,
    existing_claims: list[academic_chat.TechnicalClaim],
    assessor: Callable[..., Any],
) -> ClaimRepresentation:
    """Assess whether one candidate is represented by existing claims."""
    prompt = build_claim_representation_prompt(
        candidate_claim=candidate_claim,
        existing_claims=existing_claims,
    )
    schema = claim_representation_output_schema()

    assessor_output = assessor(
        prompt=prompt,
        schema=schema,
    )

    return build_claim_representation(
        candidate_claim=candidate_claim,
        existing_claims=existing_claims,
        assessor_output=assessor_output,
    )


def filter_discovered_claims(
    *,
    discovered_claims: list[academic_chat.TechnicalClaim],
    existing_claims: list[academic_chat.TechnicalClaim],
    representation_assessor: Callable[..., ClaimRepresentation],
) -> list[academic_chat.TechnicalClaim]:
    """Retain discovered claims whose representation is not established."""
    if (
        not isinstance(discovered_claims, list)
        or not all(
            isinstance(claim, academic_chat.TechnicalClaim)
            for claim in discovered_claims
        )
    ):
        raise TypeError(
            "Discovered claims must be a list of TechnicalClaim objects."
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

    if not callable(representation_assessor):
        raise TypeError(
            "Representation assessor must be callable."
        )

    existing_keys = {
        _claim_key(claim)
        for claim in existing_claims
    }

    retained = []
    retained_keys = set()

    for candidate in discovered_claims:
        key = _claim_key(candidate)

        # Exact application-owned duplication needs no semantic assessment.
        if key in existing_keys or key in retained_keys:
            continue

        try:
            representation = representation_assessor(
                candidate_claim=candidate,
                existing_claims=existing_claims,
            )
        except ClaimCoverageOutputError:
            # Failure to establish semantic duplication must not suppress
            # a discovered proposition from downstream checking.
            retained.append(candidate)
            retained_keys.add(key)
            continue

        if not isinstance(representation, ClaimRepresentation):
            raise TypeError(
                "Representation assessor must return a ClaimRepresentation."
            )

        if representation.represented:
            continue

        retained.append(candidate)
        retained_keys.add(key)

    return retained


def assess_claim_coverage_two_stage(
    *,
    answer_draft: str,
    existing_claims: list[academic_chat.TechnicalClaim],
    assessor: Callable[..., Any],
) -> ClaimCoverageResult:
    """Discover answer propositions, then remove established representations."""
    discovered_claims = discover_answer_claims(
        answer_draft=answer_draft,
        assessor=assessor,
    )

    def representation_assessor(
        *,
        candidate_claim: academic_chat.TechnicalClaim,
        existing_claims: list[academic_chat.TechnicalClaim],
    ) -> ClaimRepresentation:
        return assess_claim_representation(
            candidate_claim=candidate_claim,
            existing_claims=existing_claims,
            assessor=assessor,
        )

    missing_claims = filter_discovered_claims(
        discovered_claims=discovered_claims,
        existing_claims=existing_claims,
        representation_assessor=representation_assessor,
    )

    return ClaimCoverageResult(
        missing_claims=missing_claims,
        discovered_claims=discovered_claims,
    )
