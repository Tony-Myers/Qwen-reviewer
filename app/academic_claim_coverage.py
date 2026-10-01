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
import re
from typing import Any, Callable

import academic_chat


class ClaimCoverageOutputError(ValueError):
    """Raised when untrusted claim-coverage assessor output is invalid."""


class MaterialRestrictionOutputError(ValueError):
    """Raised when untrusted material-restriction output is invalid."""


@dataclass
class DiscoveredClaim:
    """Application-owned proposition with verified answer provenance."""

    claim: academic_chat.TechnicalClaim
    source_anchor: str
    source_start: int
    source_end: int


@dataclass
class ClaimSourceContext:
    """Application-owned source sentence and bounded preceding context."""

    source_sentence: str
    source_sentence_start: int
    source_sentence_end: int
    context_excerpt: str
    context_start: int
    context_end: int


@dataclass
class MaterialRestrictionAssessment:
    """Application-owned material-restriction omission decision."""

    material_restriction_omitted: bool


@dataclass
class ClaimRepresentation:
    """Application-owned assessment of whether one candidate is represented."""

    represented: bool
    represented_by: int | None


@dataclass
class ClaimCoverageResult:
    """Application-owned result of independent technical-claim coverage."""

    missing_claims: list[academic_chat.TechnicalClaim]
    discovered_claims: list[DiscoveredClaim] = field(
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




def material_restriction_output_schema() -> dict[str, Any]:
    """Return the strict schema for material-restriction omission."""
    return {
        "type": "object",
        "properties": {
            "material_restriction_omitted": {
                "type": "boolean",
            },
        },
        "required": ["material_restriction_omitted"],
        "additionalProperties": False,
    }


def build_material_restriction_prompt(
    *,
    candidate_claim: academic_chat.TechnicalClaim,
    source_context: ClaimSourceContext,
) -> str:
    """Build a prompt limited to material-restriction omission."""
    if not isinstance(candidate_claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Candidate claim must be a TechnicalClaim object."
        )

    if not isinstance(source_context, ClaimSourceContext):
        raise TypeError(
            "Source context must be a ClaimSourceContext object."
        )

    parameterisation = (
        candidate_claim.parameterisation
        if candidate_claim.parameterisation is not None
        else "not specified"
    )

    return f"""Compare the SOURCE SENTENCE and STANDALONE TECHNICAL CLAIM using
the supplied LOCAL ANSWER CONTEXT.

STANDALONE TECHNICAL CLAIM
statement: {candidate_claim.statement}
parameterisation: {parameterisation}

SOURCE SENTENCE
{source_context.source_sentence}

LOCAL ANSWER CONTEXT
{source_context.context_excerpt}

RULES
Decide only whether the standalone technical claim omits a material restriction
expressed by the source sentence or established by the local answer context as
governing the source proposition.
A material restriction can include scope, condition, population, study design,
referent, modality, direction, parameterisation, causal status, or another
qualification that changes what is asserted.
Do not treat information as a restriction merely because it appears in the
preceding context. It must govern or supply meaning to the source proposition.
Resolving a pronoun, shorthand, or implicit referent from the source sentence
into its explicit antecedent in the standalone claim is not an omitted
restriction when the same material proposition, including its qualifications,
is preserved.
A difference in wording or referential explicitness is not itself an omission.
Return true only when the standalone claim actually loses a material
qualification that changes what the source proposition asserts.
Use only the technical claim, source sentence, and local answer context supplied
above.
Do not use outside knowledge.
Do not judge whether either statement is scientifically correct.
Do not assess methodological correctness, evidential support, or source
verification.
Do not rewrite, repair, strengthen, weaken, or explain the claim.

Return exactly:
- material_restriction_omitted
"""


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


def claim_decomposition_output_schema() -> dict[str, Any]:
    """Return the bounded schema for atomic claim decomposition."""

    return {
        "type": "object",
        "properties": {
            "requires_decomposition": {
                "type": "boolean",
            },
            "atomic_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "concept": {"type": "string"},
                        "statement": {"type": "string"},
                        "parameterisation": {
                            "type": ["string", "null"],
                        },
                        "source_anchor": {"type": "string"},
                    },
                    "required": [
                        "type",
                        "concept",
                        "statement",
                        "parameterisation",
                        "source_anchor",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "requires_decomposition",
            "atomic_claims",
        ],
        "additionalProperties": False,
    }


def build_claim_decomposition_prompt(
    *,
    claim: academic_chat.TechnicalClaim,
    source_sentence: str,
) -> str:
    """Build a bounded prompt for decomposing a compound proposition."""

    if not isinstance(source_sentence, str) or not source_sentence.strip():
        raise ValueError(
            "Claim decomposition requires a non-empty source sentence."
        )

    parameterisation = (
        claim.parameterisation
        if claim.parameterisation is not None
        else "(none)"
    )

    return f"""Decide whether one extracted technical claim combines multiple
independently checkable statistical, mathematical, or methodological
propositions from its source sentence.

SOURCE SENTENCE
{source_sentence.strip()}

EXTRACTED CLAIM
statement: {claim.statement}
parameterisation: {parameterisation}

RULES
Use only the source sentence and extracted claim supplied above.
Do not use outside knowledge.
Do not judge whether any proposition is true or false.
Do not verify, correct, support, contradict, or assess methodological
consistency.
Do not add propositions that are absent from the extracted claim.
Do not recover propositions that the extracted claim omitted; omission
recovery is handled separately.

Set requires_decomposition=true only when the extracted claim itself combines
two or more independently checkable propositions that could differ in support
or correctness.
A claim is not compound merely because it contains multiple phrases,
qualifiers, conditions, definitions, or parameterisation needed to express one
material proposition.
A condition and the proposition it qualifies should remain together when the
condition defines the scope of that proposition.
A comparison should remain intact when its compared quantities together form
one proposition.
If separate assertions are joined by words such as and, but, while, whereas,
because, therefore, or consequently, consider whether each assertion could be
assessed independently.

When requires_decomposition=false, return an empty atomic_claims array.

When requires_decomposition=true:
- return every material atomic proposition contained in the extracted claim;
- preserve important qualifiers, frequency, direction, conditions,
  populations, comparisons, and parameterisation;
- do not strengthen or weaken modal or frequency language such as may, can,
  often, generally, typically, usually, necessarily, always, primarily, or
  rarely;
- each atomic claim must be self-contained;
- do not retain the original compound claim as an additional atomic claim.

For each atomic claim return exactly:
- type
- concept
- statement
- parameterisation
- source_anchor

Use null when parameterisation is not specified.
source_anchor must be a short verbatim contiguous span from the SOURCE SENTENCE
that identifies where that atomic proposition is stated. Do not paraphrase,
insert ellipses, or combine non-contiguous text in source_anchor.

Return only requires_decomposition and atomic_claims. Do not return reasoning,
confidence, verification, methodological assessment, provenance commentary, or
a rewritten answer.
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
                        "source_anchor": {
                            "type": "string",
                            "minLength": 1,
                        },
                    },
                    "required": [
                        "type",
                        "concept",
                        "statement",
                        "parameterisation",
                        "source_anchor",
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
- source_anchor

Use null when parameterisation is not specified.
source_anchor must be a short verbatim contiguous span from the answer that
uniquely identifies where the proposition is stated. Prefer the shortest span
that is unique within the answer. Do not paraphrase, insert ellipses, or combine
non-contiguous text in source_anchor.

If the answer contains no material checkable proposition, return an empty
discovered_claims array.

Return only the required discovered_claims object. source_anchor is the only
permitted model-proposed provenance. Do not return verification status,
coverage status, confidence, reasoning, commentary, or the answer draft.
"""


def build_claim_sentence_audit_prompt(
    *,
    source_sentence: str,
    discovered_claims: list[academic_chat.TechnicalClaim],
) -> str:
    """Build a bounded prompt for recovering propositions missed in one sentence."""

    if not isinstance(source_sentence, str) or not source_sentence.strip():
        raise ValueError("Claim sentence audit requires a non-empty sentence.")

    represented = "\n".join(
        f"{index}. {claim.statement}"
        + (
            f" [parameterisation: {claim.parameterisation}]"
            if claim.parameterisation is not None
            else ""
        )
        for index, claim in enumerate(discovered_claims, start=1)
    )
    if not represented:
        represented = "(none)"

    return f"""Inspect one answer sentence for material, independently checkable
statistical, mathematical, or methodological propositions that were not
already extracted.

SOURCE SENTENCE
{source_sentence.strip()}

ALREADY EXTRACTED FROM THIS SENTENCE
{represented}

RULES
Use only the source sentence supplied above.
Do not use outside knowledge.
Do not judge whether any proposition is true or false.
Do not verify, correct, support, contradict, or assess methodological
consistency.
Return only additional material propositions that are not already represented
by the extracted propositions above.
A proposition is already represented only when the same material assertion,
including important qualifiers, direction, conditions, populations,
comparisons, and parameterisation, has been preserved.
Do not return a proposition merely because it can be phrased differently.
Inspect explicitly for independently checkable propositions joined by words
such as and, but, while, whereas, because, therefore, or consequently.
Preserve frequency and strength qualifiers such as may, can, often, generally,
typically, usually, necessarily, always, primarily, or rarely.
Keep independently checkable propositions separate when they could differ in
support or correctness.
Do not combine separate propositions merely because they occur in the same
sentence.
Do not promote rhetorical, stylistic, or non-checkable wording into technical
claims.

For each additional proposition return exactly:
- type
- concept
- statement
- parameterisation
- source_anchor

Use null when parameterisation is not specified.
source_anchor must be a short verbatim contiguous span from the SOURCE SENTENCE
that identifies where the additional proposition is stated. Do not paraphrase,
insert ellipses, or combine non-contiguous text in source_anchor.

If no additional material proposition is present, return an empty
discovered_claims array.

Return only the required discovered_claims object.
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


# Abbreviations whose full stop is not a sentence boundary. Kept to the
# forms that occur in Academic Chat answers; anything else is unchanged.
# "i.e.", "e.g.", "vs." and "cf." do not end sentences in practice, and
# "vs." is routinely followed by a capital ("ETI vs. HDI"), so they never
# split. "et al." can end a sentence, so it splits only when the next word
# starts with a capital ("... Kruschke et al. The HDI ...") and not before a
# year, bracket or lower-case word ("Makowski et al. (2019)").
_NEVER_BOUNDARY_ABBREVIATION = re.compile(
    r"(?<![A-Za-z.])(?:i\.e|e\.g|vs|cf)\.$",
    re.IGNORECASE,
)
_ET_AL = re.compile(r"(?<![A-Za-z])et al\.$", re.IGNORECASE)


def _is_abbreviation_stop(answer_draft: str, stop_end: int) -> bool:
    """True when the full stop ending at stop_end belongs to an abbreviation."""

    preceding = answer_draft[max(0, stop_end - 8):stop_end]

    if _NEVER_BOUNDARY_ABBREVIATION.search(preceding):
        return True

    if _ET_AL.search(preceding):
        following = answer_draft[stop_end:].lstrip()
        return not (following[:1].isupper())

    return False


def answer_sentence_spans(
    answer_draft: str,
) -> list[tuple[int, int]]:
    """Return application-owned sentence spans for an answer draft."""

    if not isinstance(answer_draft, str):
        raise TypeError("Answer draft must be text.")

    sentence_spans: list[tuple[int, int]] = []
    sentence_start = 0

    for match in re.finditer(r"[.!?](?=\s|$)", answer_draft):
        sentence_end = match.end()

        if (
            match.group() == "."
            and _is_abbreviation_stop(answer_draft, sentence_end)
        ):
            continue

        while (
            sentence_start < sentence_end
            and answer_draft[sentence_start].isspace()
        ):
            sentence_start += 1

        if sentence_start < sentence_end:
            sentence_spans.append((sentence_start, sentence_end))

        sentence_start = sentence_end

    while (
        sentence_start < len(answer_draft)
        and answer_draft[sentence_start].isspace()
    ):
        sentence_start += 1

    if sentence_start < len(answer_draft):
        sentence_spans.append((sentence_start, len(answer_draft)))

    return sentence_spans


def resolve_claim_source_context(
    *,
    answer_draft: str,
    source_start: int,
    source_end: int,
) -> ClaimSourceContext:
    """Resolve the containing sentence and one preceding sentence."""

    if (
        source_start < 0
        or source_end <= source_start
        or source_end > len(answer_draft)
    ):
        raise ValueError("Source span is outside the answer draft.")

    sentence_spans = answer_sentence_spans(answer_draft)
    source_index = None

    for index, (start, end) in enumerate(sentence_spans):
        if start <= source_start and source_end <= end:
            source_index = index
            break

    if source_index is None:
        raise ValueError("Source span does not resolve to one sentence.")

    source_sentence_start, source_sentence_end = sentence_spans[source_index]

    context_index = max(0, source_index - 1)
    context_start = sentence_spans[context_index][0]
    context_end = source_sentence_end

    return ClaimSourceContext(
        source_sentence=answer_draft[
            source_sentence_start:source_sentence_end
        ],
        source_sentence_start=source_sentence_start,
        source_sentence_end=source_sentence_end,
        context_excerpt=answer_draft[context_start:context_end],
        context_start=context_start,
        context_end=context_end,
    )


def _parse_discovered_claim(
    value: Any,
    index: int,
    *,
    answer_draft: str,
) -> DiscoveredClaim:
    """Parse one discovered proposition and resolve unique answer provenance."""
    if not isinstance(value, dict):
        raise ClaimCoverageOutputError(
            f"discovered_claims[{index}] must be an object."
        )

    expected = {
        "type",
        "concept",
        "statement",
        "parameterisation",
        "source_anchor",
    }

    if set(value) != expected:
        raise ClaimCoverageOutputError(
            f"discovered_claims[{index}] must contain exactly "
            "type, concept, statement, parameterisation, and source_anchor."
        )

    claim_value = {
        field: value[field]
        for field in (
            "type",
            "concept",
            "statement",
            "parameterisation",
        )
    }
    claim = _parse_missing_claim(claim_value, index)

    source_anchor = value["source_anchor"]
    if not isinstance(source_anchor, str) or not source_anchor.strip():
        raise ClaimCoverageOutputError(
            f"discovered_claims[{index}].source_anchor "
            "must be non-empty text."
        )

    source_anchor = source_anchor.strip()
    source_start = answer_draft.find(source_anchor)

    if source_start < 0:
        raise ClaimCoverageOutputError(
            f"discovered_claims[{index}].source_anchor "
            "must be a verbatim contiguous span from the answer draft."
        )

    if answer_draft.find(source_anchor, source_start + 1) >= 0:
        raise ClaimCoverageOutputError(
            f"discovered_claims[{index}].source_anchor "
            "must occur exactly once in the answer draft."
        )

    return DiscoveredClaim(
        claim=claim,
        source_anchor=source_anchor,
        source_start=source_start,
        source_end=source_start + len(source_anchor),
    )

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



def build_material_restriction_assessment(
    *,
    candidate_claim: academic_chat.TechnicalClaim,
    source_context: ClaimSourceContext,
    assessor_output: Any,
) -> MaterialRestrictionAssessment:
    """Validate an untrusted material-restriction omission decision."""
    if not isinstance(candidate_claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Candidate claim must be a TechnicalClaim object."
        )

    if not isinstance(source_context, ClaimSourceContext):
        raise TypeError(
            "Source context must be a ClaimSourceContext object."
        )

    if not isinstance(assessor_output, dict):
        raise MaterialRestrictionOutputError(
            "Material restriction assessor output must be an object."
        )

    if set(assessor_output) != {"material_restriction_omitted"}:
        raise MaterialRestrictionOutputError(
            "Material restriction assessor output must contain exactly "
            "'material_restriction_omitted'."
        )

    material_restriction_omitted = assessor_output[
        "material_restriction_omitted"
    ]

    if not isinstance(material_restriction_omitted, bool):
        raise MaterialRestrictionOutputError(
            "Material restriction material_restriction_omitted "
            "must be boolean."
        )

    return MaterialRestrictionAssessment(
        material_restriction_omitted=material_restriction_omitted,
    )


def assess_material_restriction(
    *,
    candidate_claim: academic_chat.TechnicalClaim,
    source_context: ClaimSourceContext,
    assessor: Callable[..., Any],
) -> MaterialRestrictionAssessment:
    """Assess whether an atomic claim omits a material source restriction."""
    prompt = build_material_restriction_prompt(
        candidate_claim=candidate_claim,
        source_context=source_context,
    )
    schema = material_restriction_output_schema()

    assessor_output = assessor(
        prompt=prompt,
        schema=schema,
    )

    return build_material_restriction_assessment(
        candidate_claim=candidate_claim,
        source_context=source_context,
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
) -> list[DiscoveredClaim]:
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
        discovered_claim = _parse_discovered_claim(
            value,
            index,
            answer_draft=answer_draft,
        )
        key = _claim_key(discovered_claim.claim)

        if key in discovered_keys:
            continue

        discovered.append(discovered_claim)
        discovered_keys.add(key)

    return discovered


def audit_discovered_claims_by_sentence(
    *,
    answer_draft: str,
    discovered_claims: list[DiscoveredClaim],
    assessor: Callable[..., Any],
) -> list[DiscoveredClaim]:
    """Recover material propositions omitted by the global discovery pass."""

    recovered: list[DiscoveredClaim] = []
    known_keys = {
        _claim_key(discovered.claim)
        for discovered in discovered_claims
    }

    for sentence_start, sentence_end in answer_sentence_spans(answer_draft):
        source_sentence = answer_draft[sentence_start:sentence_end]

        claims_in_sentence = []
        for discovered in discovered_claims:
            if (
                sentence_start <= discovered.source_start
                and discovered.source_end <= sentence_end
            ):
                claims_in_sentence.append(discovered.claim)

        prompt = build_claim_sentence_audit_prompt(
            source_sentence=source_sentence,
            discovered_claims=claims_in_sentence,
        )
        schema = claim_discovery_output_schema()

        try:
            assessor_output = assessor(
                prompt=prompt,
                schema=schema,
            )

            if not isinstance(assessor_output, dict):
                raise ClaimCoverageOutputError(
                    "Claim sentence-audit assessor output must be an object."
                )

            if set(assessor_output) != {"discovered_claims"}:
                raise ClaimCoverageOutputError(
                    "Claim sentence-audit assessor output must contain exactly "
                    "'discovered_claims'."
                )

            raw_recovered = assessor_output["discovered_claims"]

            if not isinstance(raw_recovered, list):
                raise ClaimCoverageOutputError(
                    "Claim sentence-audit discovered_claims must be an array."
                )

        except ClaimCoverageOutputError:
            # Sentence audit is additive. Failure to establish additional
            # propositions for one sentence must not erase valid global
            # discovery or prevent other sentences from being audited.
            continue

        for index, value in enumerate(raw_recovered):
            try:
                local = _parse_discovered_claim(
                    value,
                    index,
                    answer_draft=source_sentence,
                )
            except ClaimCoverageOutputError:
                continue

            claim = local.claim
            key = _claim_key(claim)

            if key in known_keys:
                continue

            recovered.append(
                DiscoveredClaim(
                    claim=claim,
                    source_anchor=local.source_anchor,
                    source_start=sentence_start + local.source_start,
                    source_end=sentence_start + local.source_end,
                )
            )
            known_keys.add(key)

    return [*discovered_claims, *recovered]


def decompose_discovered_claims(
    *,
    answer_draft: str,
    discovered_claims: list[DiscoveredClaim],
    assessor: Callable[..., Any],
) -> list[DiscoveredClaim]:
    """Replace valid compound claims with application-validated atomic claims."""

    decomposed: list[DiscoveredClaim] = []
    known_keys: set[tuple[str, str | None]] = set()

    for discovered in discovered_claims:
        source_context = resolve_claim_source_context(
            answer_draft=answer_draft,
            source_start=discovered.source_start,
            source_end=discovered.source_end,
        )
        source_sentence = source_context.source_sentence
        sentence_start = source_context.source_sentence_start

        prompt = build_claim_decomposition_prompt(
            claim=discovered.claim,
            source_sentence=source_sentence,
        )
        schema = claim_decomposition_output_schema()

        try:
            assessor_output = assessor(
                prompt=prompt,
                schema=schema,
            )
        except ClaimCoverageOutputError:
            assessor_output = None

        replacements: list[DiscoveredClaim] = []

        if isinstance(assessor_output, dict):
            if set(assessor_output) == {
                "requires_decomposition",
                "atomic_claims",
            }:
                requires_decomposition = assessor_output[
                    "requires_decomposition"
                ]
                raw_atomic_claims = assessor_output["atomic_claims"]

                if (
                    requires_decomposition is True
                    and isinstance(raw_atomic_claims, list)
                ):
                    replacement_keys: set[
                        tuple[str, str | None]
                    ] = set()

                    for index, value in enumerate(raw_atomic_claims):
                        try:
                            local = _parse_discovered_claim(
                                value,
                                index,
                                answer_draft=source_sentence,
                            )
                        except ClaimCoverageOutputError:
                            continue

                        key = _claim_key(local.claim)
                        if key in replacement_keys:
                            continue

                        replacements.append(
                            DiscoveredClaim(
                                claim=local.claim,
                                source_anchor=local.source_anchor,
                                source_start=(
                                    sentence_start + local.source_start
                                ),
                                source_end=(
                                    sentence_start + local.source_end
                                ),
                            )
                        )
                        replacement_keys.add(key)

        candidates = (
            replacements
            if len(replacements) >= 2
            else [discovered]
        )

        for candidate in candidates:
            key = _claim_key(candidate.claim)
            if key in known_keys:
                continue
            decomposed.append(candidate)
            known_keys.add(key)

    return decomposed


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
    discovered_claims = audit_discovered_claims_by_sentence(
        answer_draft=answer_draft,
        discovered_claims=discovered_claims,
        assessor=assessor,
    )
    discovered_claims = decompose_discovered_claims(
        answer_draft=answer_draft,
        discovered_claims=discovered_claims,
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

    discovered_technical_claims = [
        discovered.claim
        for discovered in discovered_claims
    ]

    missing_claims = filter_discovered_claims(
        discovered_claims=discovered_technical_claims,
        existing_claims=existing_claims,
        representation_assessor=representation_assessor,
    )

    return ClaimCoverageResult(
        missing_claims=missing_claims,
        discovered_claims=discovered_claims,
    )
