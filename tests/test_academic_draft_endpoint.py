#!/usr/bin/env python3
"""Offline regression tests for the Academic Chat draft endpoint."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

try:
    import server
    import academic_chat
except Exception as exc:
    print(f"SKIP: could not import app dependencies: {exc}")
    raise SystemExit(0)


fails = []


def check(label, condition, detail=None):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail is not None:
            print(f"        {detail}")
        fails.append(label)


class FakeDraft:
    def __init__(self):
        self.answer_draft = "A provisional academic answer."

    def to_dict(self):
        return {
            "answer_draft": self.answer_draft,
            "references": [],
            "technical_claims": [],
        }


original_ensure_model = server.ensure_model
original_generate_draft = server.academic_chat.generate_academic_draft
original_model = server.model
original_tokenizer = server.tokenizer

ensure_calls = []
draft_calls = []


def fake_ensure_model():
    ensure_calls.append(True)
    server.model = "existing-model"
    server.tokenizer = "existing-tokenizer"


def fake_generate_draft(model, tokenizer, question, **kwargs):
    draft_calls.append({
        "model": model,
        "tokenizer": tokenizer,
        "question": question,
        "kwargs": kwargs,
    })
    return FakeDraft()


print("\n[1] valid draft request uses existing local model boundary")

try:
    server.ensure_model = fake_ensure_model
    server.academic_chat.generate_academic_draft = fake_generate_draft

    result = asyncio.run(
        server.academic_chat_draft({
            "question": "What is the relative efficiency formula?"
        })
    )

finally:
    server.ensure_model = original_ensure_model
    server.academic_chat.generate_academic_draft = original_generate_draft
    server.model = original_model
    server.tokenizer = original_tokenizer


check("model lifecycle invoked once",
      len(ensure_calls) == 1,
      ensure_calls)

check("academic draft generator invoked once",
      len(draft_calls) == 1,
      draft_calls)

if draft_calls:
    call = draft_calls[0]
    check("existing model object reused",
          call["model"] == "existing-model",
          call)
    check("existing tokenizer object reused",
          call["tokenizer"] == "existing-tokenizer",
          call)
    check("complete question passed to local draft generator",
          call["question"] == "What is the relative efficiency formula?",
          call)
    check("no arbitrary request fields passed through",
          call["kwargs"] == {},
          call)

check("structured draft returned",
      isinstance(result, dict)
      and result.get("answer_draft") == "A provisional academic answer.",
      result)


print("\n[2] unexpected fields are rejected before model use")

ensure_calls.clear()
draft_calls.clear()

try:
    server.ensure_model = fake_ensure_model
    server.academic_chat.generate_academic_draft = fake_generate_draft

    result = asyncio.run(
        server.academic_chat_draft({
            "question": "A question",
            "messages": [{"role": "user", "content": "secret"}],
            "manuscript": "confidential manuscript text",
        })
    )

finally:
    server.ensure_model = original_ensure_model
    server.academic_chat.generate_academic_draft = original_generate_draft
    server.model = original_model
    server.tokenizer = original_tokenizer


check("unexpected fields return HTTP 400",
      getattr(result, "status_code", None) == 400,
      result)

check("unexpected request never loads model",
      ensure_calls == [],
      ensure_calls)

check("unexpected request never reaches draft generator",
      draft_calls == [],
      draft_calls)


print("\n[3] empty questions are rejected before model use")

ensure_calls.clear()
draft_calls.clear()

try:
    server.ensure_model = fake_ensure_model
    server.academic_chat.generate_academic_draft = fake_generate_draft

    result = asyncio.run(
        server.academic_chat_draft({"question": "   "})
    )

finally:
    server.ensure_model = original_ensure_model
    server.academic_chat.generate_academic_draft = original_generate_draft
    server.model = original_model
    server.tokenizer = original_tokenizer


check("empty question returns HTTP 400",
      getattr(result, "status_code", None) == 400,
      result)

check("empty question never loads model",
      ensure_calls == [],
      ensure_calls)

check("empty question never reaches draft generator",
      draft_calls == [],
      draft_calls)


print("\n[4] malformed local-model structure becomes HTTP 502")


def malformed_draft(*args, **kwargs):
    raise academic_chat.AcademicDraftError("Model output is not valid JSON.")


try:
    server.ensure_model = fake_ensure_model
    server.academic_chat.generate_academic_draft = malformed_draft

    result = asyncio.run(
        server.academic_chat_draft({"question": "A valid question"})
    )

finally:
    server.ensure_model = original_ensure_model
    server.academic_chat.generate_academic_draft = original_generate_draft
    server.model = original_model
    server.tokenizer = original_tokenizer


check("invalid model structure returns HTTP 502",
      getattr(result, "status_code", None) == 502,
      result)


print("\n[5] backend failure becomes HTTP 502")


def failed_backend(*args, **kwargs):
    raise server.BackendError("local backend failed")


try:
    server.ensure_model = fake_ensure_model
    server.academic_chat.generate_academic_draft = failed_backend

    result = asyncio.run(
        server.academic_chat_draft({"question": "A valid question"})
    )

finally:
    server.ensure_model = original_ensure_model
    server.academic_chat.generate_academic_draft = original_generate_draft
    server.model = original_model
    server.tokenizer = original_tokenizer


check("backend failure returns HTTP 502",
      getattr(result, "status_code", None) == 502,
      result)


print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    raise SystemExit(1)

print("All Academic Chat draft endpoint tests passed.")
