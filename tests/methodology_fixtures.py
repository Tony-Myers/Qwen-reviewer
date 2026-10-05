"""Schema-aware bounded model-output fixtures; no production behaviour is patched."""
import academic_methodology as am


def methodology_output(schema, status, reason="Synthetic judgement."):
    pairs = {
        am.METHODOLOGICAL_STATUS_CONSISTENT: ("yes", "yes"),
        am.METHODOLOGICAL_STATUS_CONFLICT: ("no", "no"),
        am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED: ("yes", "no"),
    }
    coexistence, establishment = pairs[status]
    if schema == am.methodological_coexistence_output_schema():
        field, value = "can_both_be_true", coexistence
    elif schema == am.methodological_establishment_output_schema():
        field, value = "guidance_establishes_claim", establishment
    else:
        raise AssertionError("Unexpected methodology schema")
    return {
        "claim_proposition": "Synthetic claim proposition.",
        "guidance_proposition": "Synthetic guidance proposition.",
        field: value,
        "reason": reason,
    }


def methodology_outputs(status, reason="Synthetic judgement."):
    return (
        methodology_output(am.methodological_coexistence_output_schema(), status, reason),
        methodology_output(am.methodological_establishment_output_schema(), status, reason),
    )
