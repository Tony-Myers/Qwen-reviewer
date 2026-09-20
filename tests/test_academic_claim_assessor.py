#!/usr/bin/env python3
"""Deterministic tests for the local semantic claim-assessor adapter."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_claim_assessor


print("[77] local claim assessor uses constrained non-thinking generation")

captured = {}


def fake_make_sampler(**kwargs):
    captured["sampler_kwargs"] = kwargs
    return ("fake-sampler", kwargs)


class FakeThinking:
    def __init__(self, enabled):
        captured["thinking"] = enabled

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def fake_thinking(enabled):
    return FakeThinking(enabled)


def fake_generate(
    model,
    tokenizer,
    messages,
    *,
    max_tokens,
    sampler,
    verbose,
):
    captured["model"] = model
    captured["tokenizer"] = tokenizer
    captured["messages"] = messages
    captured["max_tokens"] = max_tokens
    captured["sampler"] = sampler
    captured["verbose"] = verbose

    return json.dumps(
        {
            "status": "claim_supported",
            "reason": "The supplied evidence directly supports the claim.",
        }
    )


academic_claim_assessor.llm_backend.make_sampler = fake_make_sampler
academic_claim_assessor.llm_backend.thinking = fake_thinking
academic_claim_assessor.llm_backend.generate = fake_generate


inner_schema = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": [
                "claim_supported",
                "claim_partially_supported",
                "claim_not_supported",
                "claim_contradicted",
            ],
        },
        "reason": {
            "type": "string",
            "minLength": 1,
        },
    },
    "required": ["status", "reason"],
    "additionalProperties": False,
}

result = academic_claim_assessor.generate_claim_assessor_output(
    model="fake-model",
    tokenizer="fake-tokenizer",
    prompt="Assess only this supplied evidence.",
    schema=inner_schema,
)

assert result == {
    "status": "claim_supported",
    "reason": "The supplied evidence directly supports the claim.",
}

print("PASS: adapter returns decoded assessor output")


assert captured["sampler_kwargs"]["temp"] == 0.1
assert captured["sampler_kwargs"]["top_p"] == 0.8
assert captured["sampler_kwargs"]["top_k"] == 20

response_format = captured["sampler_kwargs"]["response_format"]

assert response_format["type"] == "json_schema"
assert response_format["json_schema"]["name"] == "claim_assessment"
assert response_format["json_schema"]["strict"] is True
assert response_format["json_schema"]["schema"] is inner_schema

print("PASS: adapter uses conservative structured sampling")
print("PASS: inner assessment schema is wrapped for llama-server")


assert captured["thinking"] is False
assert captured["max_tokens"] == 512
assert captured["verbose"] is False

print("PASS: semantic assessment runs with thinking disabled")
print("PASS: assessor has a bounded output budget")


assert captured["messages"] == [
    {
        "role": "user",
        "content": "Assess only this supplied evidence.",
    }
]

print("PASS: adapter sends only the supplied evidence-bounded prompt")


for malformed in (
    "",
    "not json",
    "[]",
    '"claim_supported"',
    '{"status": "claim_supported"',
):
    def malformed_generate(
        model,
        tokenizer,
        messages,
        *,
        max_tokens,
        sampler,
        verbose,
        _raw=malformed,
    ):
        return _raw

    academic_claim_assessor.llm_backend.generate = malformed_generate

    try:
        academic_claim_assessor.generate_claim_assessor_output(
            model="fake-model",
            tokenizer="fake-tokenizer",
            prompt="Synthetic prompt.",
            schema=inner_schema,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            f"Malformed model output was accepted: {malformed!r}"
        )

print("PASS: malformed and non-object model output is rejected")


def backend_failure(
    model,
    tokenizer,
    messages,
    *,
    max_tokens,
    sampler,
    verbose,
):
    raise RuntimeError("synthetic backend failure")


academic_claim_assessor.llm_backend.generate = backend_failure

try:
    academic_claim_assessor.generate_claim_assessor_output(
        model="fake-model",
        tokenizer="fake-tokenizer",
        prompt="Synthetic prompt.",
        schema=inner_schema,
    )
except RuntimeError as exc:
    assert str(exc) == "synthetic backend failure"
else:
    raise AssertionError("Backend failure was converted into assessor output")

print("PASS: backend failure propagates instead of becoming an evidence state")
print("PASS: local assessor adapter preserves the trust boundary")
