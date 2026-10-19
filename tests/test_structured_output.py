"""Regression tests for optional llama-server structured output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import llm_backend


fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


model = llm_backend.LlamaServerModel(
    model_path="/tmp/test-model.gguf",
    base_url="http://127.0.0.1:8081",
)

captured = []


def fake_post_json(path, payload):
    captured.append((path, payload))
    return {
        "choices": [
            {
                "message": {"content": '{"answer":"ok"}'},
                "finish_reason": "stop",
            }
        ]
    }


model._post_json = fake_post_json

schema_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "test_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    },
}


# Explicit structured output.
sampler = llm_backend.make_sampler(
    temp=0.1,
    top_p=0.8,
    top_k=20,
    response_format=schema_format,
)

model.complete(
    [{"role": "user", "content": "test"}],
    max_tokens=100,
    sampler=sampler,
    enable_thinking=False,
)

payload = captured[-1][1]

check(
    payload.get("response_format") == schema_format,
    "explicit response_format reaches llama-server payload",
)


# Ordinary generation remains unchanged.
ordinary_sampler = llm_backend.make_sampler(
    temp=0.1,
    top_p=0.8,
    top_k=20,
)

model.complete(
    [{"role": "user", "content": "test"}],
    max_tokens=100,
    sampler=ordinary_sampler,
    enable_thinking=False,
)

ordinary_payload = captured[-1][1]

check(
    "response_format" not in ordinary_payload,
    "ordinary generation does not send response_format",
)


# Arbitrary sampler.extra values must not become API fields.
guarded_sampler = llm_backend.make_sampler(
    temp=0.1,
    arbitrary_internal_value="must-not-leak",
)

model.complete(
    [{"role": "user", "content": "test"}],
    max_tokens=100,
    sampler=guarded_sampler,
    enable_thinking=False,
)

guarded_payload = captured[-1][1]

check(
    "arbitrary_internal_value" not in guarded_payload,
    "unapproved sampler.extra values do not reach llama-server",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll structured-output backend checks passed.")
