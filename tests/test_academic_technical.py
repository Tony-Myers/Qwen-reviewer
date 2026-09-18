"""Regression tests for deterministic Academic Chat technical verification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat
import academic_technical as at


fails = []


def check(condition, message, detail=None):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message, detail if detail is not None else "")
        fails.append(message)


def claim(
    *,
    type,
    concept,
    statement,
    parameterisation,
):
    return academic_chat.TechnicalClaim(
        type=type,
        concept=concept,
        statement=statement,
        parameterisation=parameterisation,
    )


MI_PARAMETERISATION = (
    "lambda is fraction of missing information, "
    "M is number of imputations"
)


print("\n[1] unknown technical claims remain unverified")

unknown = claim(
    type="formula",
    concept="Example relationship",
    statement="x = y / z",
    parameterisation="x, y and z are arbitrary quantities",
)

unknown_result = at.verify_technical_claim(unknown)

check(
    unknown_result.status == at.TECHNICAL_STATUS_NOT_VERIFIED,
    "unknown claim is not technically verified",
    unknown_result.to_dict(),
)

check(
    unknown_result.verifier is None,
    "unknown claim has no verifier identity",
    unknown_result.to_dict(),
)


print("\n[2] standard MI relative-efficiency formula is verified")

formula_variants = [
    "RE = 1 / (1 + lambda/M)",
    "RE=(1+lambda/M)^-1",
    "RE = (1 + λ / M)^(-1)",
]

for statement in formula_variants:
    result = at.verify_technical_claim(
        claim(
            type="formula",
            concept="Relative Efficiency of Multiple Imputation",
            statement=statement,
            parameterisation=MI_PARAMETERISATION,
        )
    )

    check(
        result.status == at.TECHNICAL_STATUS_VERIFIED,
        f"recognised correct formula: {statement}",
        result.to_dict(),
    )

    check(
        result.verifier == "multiple_imputation_relative_efficiency_v1",
        f"MI verifier identity recorded: {statement}",
        result.to_dict(),
    )


print("\n[3] live-3 incorrect MI formula is a technical conflict")

wrong_formula_claim = claim(
    type="formula",
    concept="Relative Efficiency of Multiple Imputation",
    statement="RE = 1 + lambda/M",
    parameterisation=MI_PARAMETERISATION,
)

wrong_formula = at.verify_technical_claim(wrong_formula_claim)

check(
    wrong_formula.status == at.TECHNICAL_STATUS_CONFLICT,
    "missing reciprocal is detected as technical conflict",
    wrong_formula.to_dict(),
)

check(
    wrong_formula.canonical_claim == "RE = 1 / (1 + lambda/M)",
    "conflict reports canonical MI relationship",
    wrong_formula.to_dict(),
)


print("\n[4] exact 95% relative-efficiency threshold is verified")

threshold_variants = [
    "M >= 19 * lambda",
    "M>=19*lambda",
    "M ≥ 19 lambda",
    "M >= lambda * 19",
]

for statement in threshold_variants:
    result = at.verify_technical_claim(
        claim(
            type="threshold",
            concept="Imputation Count for 95% Efficiency",
            statement=statement,
            parameterisation="lambda is fraction of missing information",
        )
    )

    check(
        result.status == at.TECHNICAL_STATUS_VERIFIED,
        f"recognised exact 95% threshold: {statement}",
        result.to_dict(),
    )


print("\n[5] recognisably wrong 95% threshold is a conflict")

wrong_threshold = at.verify_technical_claim(
    claim(
        type="threshold",
        concept="Imputation Count for 95% Efficiency",
        statement="M >= 19 * lambda / (1 - lambda)",
        parameterisation="lambda is fraction of missing information",
    )
)

check(
    wrong_threshold.status == at.TECHNICAL_STATUS_CONFLICT,
    "incorrect lambda/(1-lambda) threshold is detected",
    wrong_threshold.to_dict(),
)


print("\n[6] conservative alternatives are not over-classified")

conservative_threshold = at.verify_technical_claim(
    claim(
        type="threshold",
        concept="Imputation Count for 95% Efficiency",
        statement="M >= 20 * lambda",
        parameterisation="lambda is fraction of missing information",
    )
)

check(
    conservative_threshold.status == at.TECHNICAL_STATUS_NOT_VERIFIED,
    "20*lambda rule is left unverified rather than called wrong",
    conservative_threshold.to_dict(),
)

unfamiliar_formula = at.verify_technical_claim(
    claim(
        type="formula",
        concept="Relative Efficiency of Multiple Imputation",
        statement="RE approximately depends on lambda and M",
        parameterisation=MI_PARAMETERISATION,
    )
)

check(
    unfamiliar_formula.status == at.TECHNICAL_STATUS_NOT_VERIFIED,
    "unrecognised MI expression remains unverified",
    unfamiliar_formula.to_dict(),
)


print("\n[7] incompatible parameterisation prevents verification")

wrong_parameterisation = at.verify_technical_claim(
    claim(
        type="formula",
        concept="Relative Efficiency of Multiple Imputation",
        statement="RE = 1 / (1 + lambda/M)",
        parameterisation=(
            "lambda is proportion of cases with missing values, "
            "M is number of imputations"
        ),
    )
)

check(
    wrong_parameterisation.status == at.TECHNICAL_STATUS_NOT_VERIFIED,
    "missing-case proportion is not treated as fraction of missing information",
    wrong_parameterisation.to_dict(),
)


print("\n[8] original model claim is not mutated")

original = claim(
    type="formula",
    concept="Relative Efficiency of Multiple Imputation",
    statement="RE = 1 + lambda/M",
    parameterisation=MI_PARAMETERISATION,
)

before = original.to_dict().copy()
result = at.verify_technical_claim(original)

check(
    original.to_dict() == before,
    "technical verifier leaves original claim unchanged",
    {
        "before": before,
        "after": original.to_dict(),
        "verification": result.to_dict(),
    },
)

check(
    bool(result.reasons),
    "deterministic verification records a reason",
    result.to_dict(),
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll academic technical-verification checks passed.")
