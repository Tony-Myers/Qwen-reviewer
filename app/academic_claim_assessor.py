"""
Local-model adapter for semantic academic claim assessment.

This module owns model invocation and JSON decoding only. Model output remains
untrusted; academic_claims owns semantic validation and evidence provenance.
"""

import json
from typing import Any

import llm_backend


def generate_claim_assessor_output(
    model: Any,
    tokenizer: Any,
    prompt: str,
    schema: dict[str, Any],
    *,
    max_tokens: int = 512,
) -> dict[str, Any]:
    """Generate and decode one untrusted semantic-assessment proposal."""
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "claim_assessment",
            "strict": True,
            "schema": schema,
        },
    }

    sampler = llm_backend.make_sampler(
        temp=0.1,
        top_p=0.8,
        top_k=20,
        response_format=response_format,
    )

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    with llm_backend.thinking(False):
        raw = llm_backend.generate(
            model,
            tokenizer,
            messages,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )

    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(
            "Claim assessor did not return valid JSON."
        ) from exc

    if not isinstance(decoded, dict):
        raise ValueError(
            "Claim assessor output must decode to a JSON object."
        )

    return decoded
