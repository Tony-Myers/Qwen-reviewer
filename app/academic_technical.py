"""
Deterministic technical verification for Academic Chat.

Technical verification is deliberately conservative. A claim is verified only
when a local deterministic rule recognises both the technical concept and its
parameterisation. Unrecognised claims remain not technically verified; lack of
verification is not evidence that a claim is wrong.

This module performs no external network access.
"""

from dataclasses import asdict, dataclass
import re
from typing import Any

import academic_chat


TECHNICAL_STATUS_VERIFIED = "technically_verified"
TECHNICAL_STATUS_CONSISTENT = "technically_consistent"
TECHNICAL_STATUS_NOT_VERIFIED = "not_technically_verified"
TECHNICAL_STATUS_CONFLICT = "technical_conflict"

MI_RE_VERIFIER = "multiple_imputation_relative_efficiency_v1"

MI_FORMULA_CANONICAL = "RE = 1 / (1 + lambda/M)"
MI_THRESHOLD_CANONICAL = "M >= 19 * lambda"


@dataclass
class TechnicalVerification:
    status: str
    verifier: str | None
    canonical_claim: str | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_text(value: str | None) -> str:
    if not value:
        return ""

    text = value.lower()
    text = text.replace("λ", "lambda")
    text = text.replace("≥", ">=")
    text = text.replace("×", "*")
    text = text.replace("−", "-")
    text = text.replace("–", "-")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _normalise_expression(value: str | None) -> str:
    text = _normalise_text(value)

    # Normalise common exponent notation used by model output.
    text = text.replace("**(-1)", "^-1")
    text = text.replace("**-1", "^-1")
    text = text.replace("^(-1)", "^-1")

    # Multiplication is sometimes left implicit in simple threshold statements.
    text = re.sub(r"(?<=\d)\s+(?=lambda\b)", "*", text)
    text = re.sub(r"\blambda\s+\*\s+19\b", "lambda*19", text)

    return re.sub(r"\s+", "", text)


def _mi_parameterisation_compatible(
    parameterisation: str | None,
    *,
    require_m: bool,
) -> bool:
    text = _normalise_text(parameterisation)

    if not text:
        return False

    lambda_ok = (
        "fraction of missing information" in text
        or "fraction of the missing information" in text
    )

    if not lambda_ok:
        return False

    if not require_m:
        return True

    m_ok = (
        "m is number of imputations" in text
        or "m is the number of imputations" in text
    )

    return m_ok


def _looks_like_mi_formula(
    claim: academic_chat.TechnicalClaim,
) -> bool:
    claim_type = _normalise_text(claim.type)
    concept = _normalise_text(claim.concept)

    return (
        claim_type == "formula"
        and "relative efficiency" in concept
        and (
            "multiple imputation" in concept
            or "imputation" in concept
        )
    )


def _looks_like_mi_95_threshold(
    claim: academic_chat.TechnicalClaim,
) -> bool:
    claim_type = _normalise_text(claim.type)
    concept = _normalise_text(claim.concept)

    efficiency_marker = (
        "95%" in concept
        or "95 %" in concept
        or "95 percent" in concept
        or "95 per cent" in concept
    )

    return (
        claim_type == "threshold"
        and "imputation" in concept
        and "efficiency" in concept
        and efficiency_marker
    )


def _verify_mi_relative_efficiency(
    claim: academic_chat.TechnicalClaim,
) -> TechnicalVerification | None:
    if _looks_like_mi_formula(claim):
        if not _mi_parameterisation_compatible(
            claim.parameterisation,
            require_m=True,
        ):
            return TechnicalVerification(
                status=TECHNICAL_STATUS_NOT_VERIFIED,
                verifier=MI_RE_VERIFIER,
                canonical_claim=MI_FORMULA_CANONICAL,
                reasons=[
                    "The MI relative-efficiency concept was recognised, but "
                    "the stated parameterisation was not sufficiently "
                    "compatible for deterministic verification."
                ],
            )

        expression = _normalise_expression(claim.statement)

        correct = {
            "re=1/(1+lambda/m)",
            "re=(1+lambda/m)^-1",
        }

        known_conflicts = {
            "re=1+lambda/m",
        }

        if expression in correct:
            return TechnicalVerification(
                status=TECHNICAL_STATUS_VERIFIED,
                verifier=MI_RE_VERIFIER,
                canonical_claim=MI_FORMULA_CANONICAL,
                reasons=[
                    "The claim matches the standard finite-imputation "
                    "relative-efficiency relationship under the stated "
                    "parameterisation."
                ],
            )

        if expression in known_conflicts:
            return TechnicalVerification(
                status=TECHNICAL_STATUS_CONFLICT,
                verifier=MI_RE_VERIFIER,
                canonical_claim=MI_FORMULA_CANONICAL,
                reasons=[
                    "The recognised expression omits the reciprocal required "
                    "by the finite-imputation relative-efficiency relationship."
                ],
            )

        return TechnicalVerification(
            status=TECHNICAL_STATUS_NOT_VERIFIED,
            verifier=MI_RE_VERIFIER,
            canonical_claim=MI_FORMULA_CANONICAL,
            reasons=[
                "The MI relative-efficiency concept and parameterisation were "
                "recognised, but the expression is outside this verifier's "
                "supported deterministic forms."
            ],
        )

    if _looks_like_mi_95_threshold(claim):
        if not _mi_parameterisation_compatible(
            claim.parameterisation,
            require_m=False,
        ):
            return TechnicalVerification(
                status=TECHNICAL_STATUS_NOT_VERIFIED,
                verifier=MI_RE_VERIFIER,
                canonical_claim=MI_THRESHOLD_CANONICAL,
                reasons=[
                    "The 95% MI efficiency threshold was recognised, but the "
                    "stated parameterisation was not sufficiently compatible "
                    "for deterministic verification."
                ],
            )

        expression = _normalise_expression(claim.statement)

        correct = {
            "m>=19*lambda",
            "m>=lambda*19",
        }

        known_conflicts = {
            "m>=19*lambda/(1-lambda)",
        }

        if expression in correct:
            return TechnicalVerification(
                status=TECHNICAL_STATUS_VERIFIED,
                verifier=MI_RE_VERIFIER,
                canonical_claim=MI_THRESHOLD_CANONICAL,
                reasons=[
                    "The claim matches the exact threshold obtained from "
                    "RE >= 0.95 under the standard MI relative-efficiency "
                    "relationship."
                ],
            )

        if expression in known_conflicts:
            return TechnicalVerification(
                status=TECHNICAL_STATUS_CONFLICT,
                verifier=MI_RE_VERIFIER,
                canonical_claim=MI_THRESHOLD_CANONICAL,
                reasons=[
                    "The recognised threshold conflicts with the exact "
                    "solution M >= 19 * lambda for RE >= 0.95 under the "
                    "stated parameterisation."
                ],
            )

        return TechnicalVerification(
            status=TECHNICAL_STATUS_NOT_VERIFIED,
            verifier=MI_RE_VERIFIER,
            canonical_claim=MI_THRESHOLD_CANONICAL,
            reasons=[
                "The 95% MI efficiency threshold and parameterisation were "
                "recognised, but the expression is outside this verifier's "
                "supported deterministic forms."
            ],
        )

    return None


def verify_technical_claim(
    claim: academic_chat.TechnicalClaim,
) -> TechnicalVerification:
    """
    Dispatch a structured technical claim to deterministic local verifiers.

    A verifier returning None means that it does not cover the claim. Claims
    outside the supported deterministic rules remain explicitly unverified.
    """
    verifiers = (
        _verify_mi_relative_efficiency,
    )

    for verifier in verifiers:
        result = verifier(claim)
        if result is not None:
            return result

    return TechnicalVerification(
        status=TECHNICAL_STATUS_NOT_VERIFIED,
        verifier=None,
        canonical_claim=None,
        reasons=[
            "No deterministic technical verifier currently covers this claim."
        ],
    )
