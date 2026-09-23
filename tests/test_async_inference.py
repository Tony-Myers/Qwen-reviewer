#!/usr/bin/env python3
"""Regression checks for blocking model work in async HTTP endpoints."""

import asyncio
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import server  # noqa: E402


failures = 0


def ok(label, condition, detail=""):
    global failures
    if condition:
        print(f"  PASS  {label}")
    else:
        failures += 1
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")


print("\n[chat inference does not block the event loop]")

original_ensure_model = server.ensure_model
original_generate = server.generate
original_model = server.model
original_tokenizer = server.tokenizer

generation_entered = threading.Event()
release_generation = threading.Event()


class FakeTokenizer:
    chat_template = None


def fake_ensure_model():
    return None


def blocking_generate(*args, **kwargs):
    generation_entered.set()
    if not release_generation.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release generation")
    return "synthetic answer"


async def exercise():
    server.ensure_model = fake_ensure_model
    server.generate = blocking_generate
    server.model = object()
    server.tokenizer = FakeTokenizer()

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    # Release generation from outside the event loop. If generate() itself is
    # running on the event-loop thread, the loop remains blocked until this
    # helper thread releases it. If generation is offloaded, independent_work
    # can run while generation remains blocked.
    releaser = threading.Thread(
        target=lambda: (
            generation_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_generation.set(),
        ),
        daemon=True,
    )
    releaser.start()

    chat_task = asyncio.create_task(
        server.chat_completions({
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 8,
        })
    )
    other_task = asyncio.create_task(independent_work())

    try:
        # Give both tasks an opportunity to run. In the current implementation
        # this sleep itself cannot resume until synchronous generation has been
        # released by the helper thread.
        await asyncio.sleep(0.05)

        entered = generation_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_generation.is_set()
        )

        result = await asyncio.wait_for(chat_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_generation.set()
        releaser.join(timeout=1.0)
        server.ensure_model = original_ensure_model
        server.generate = original_generate
        server.model = original_model
        server.tokenizer = original_tokenizer


entered, responsive, result = asyncio.run(exercise())

ok(
    "chat generation started",
    entered,
    "the fake blocking generation should have been reached",
)
ok(
    "event loop remains responsive while generation is blocked",
    responsive,
    "synchronous generate() currently occupies the FastAPI event-loop thread",
)
ok(
    "chat still completes after generation is released",
    isinstance(result, dict)
    and result.get("choices", [{}])[0].get("message", {}).get("content")
    == "synthetic answer",
)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: async chat inference is offloaded from the event loop")

print("\n[Academic Chat draft does not block the event loop]")

original_ensure_model = server.ensure_model
original_generate_draft = server.academic_chat.generate_academic_draft
original_model = server.model
original_tokenizer = server.tokenizer

draft_entered = threading.Event()
release_draft = threading.Event()


def fake_ensure_model():
    return None


def blocking_generate_draft(*args, **kwargs):
    draft_entered.set()
    if not release_draft.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release Academic Chat draft")
    return type(
        "SyntheticDraft",
        (),
        {"to_dict": lambda self: {"answer": "synthetic academic draft"}},
    )()


async def exercise_academic_draft():
    server.ensure_model = fake_ensure_model
    server.academic_chat.generate_academic_draft = blocking_generate_draft
    server.model = object()
    server.tokenizer = object()

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    releaser = threading.Thread(
        target=lambda: (
            draft_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_draft.set(),
        ),
        daemon=True,
    )
    releaser.start()

    draft_task = asyncio.create_task(
        server.academic_chat_draft({"question": "test question"})
    )
    other_task = asyncio.create_task(independent_work())

    try:
        await asyncio.sleep(0.05)

        entered = draft_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_draft.is_set()
        )

        result = await asyncio.wait_for(draft_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_draft.set()
        releaser.join(timeout=1.0)
        server.ensure_model = original_ensure_model
        server.academic_chat.generate_academic_draft = original_generate_draft
        server.model = original_model
        server.tokenizer = original_tokenizer


entered, responsive, result = asyncio.run(exercise_academic_draft())

ok(
    "Academic Chat draft generation started",
    entered,
)
ok(
    "event loop remains responsive while Academic Chat draft is blocked",
    responsive,
    "generate_academic_draft() currently occupies the FastAPI event-loop thread",
)
ok(
    "Academic Chat draft still completes after release",
    isinstance(result, dict)
    and result.get("answer") == "synthetic academic draft",
)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: Academic Chat draft generation is offloaded from the event loop")

print("\n[Academic Chat orchestration does not block the event loop]")

original_ensure_model = server.ensure_model
original_orchestrator = server.academic_orchestrator.run_academic_first_stage
original_model = server.model
original_tokenizer = server.tokenizer

academic_entered = threading.Event()
release_academic = threading.Event()


def fake_ensure_model():
    return None


def blocking_orchestrator(*args, **kwargs):
    academic_entered.set()
    if not release_academic.wait(timeout=2.0):
        raise RuntimeError(
            "test timed out waiting to release Academic Chat orchestration"
        )
    return type(
        "SyntheticAcademicResult",
        (),
        {"to_dict": lambda self: {"answer": "synthetic academic result"}},
    )()


async def exercise_academic_first_stage():
    server.ensure_model = fake_ensure_model
    server.academic_orchestrator.run_academic_first_stage = blocking_orchestrator
    server.model = object()
    server.tokenizer = object()

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    releaser = threading.Thread(
        target=lambda: (
            academic_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_academic.set(),
        ),
        daemon=True,
    )
    releaser.start()

    academic_task = asyncio.create_task(
        server.academic_chat_first_stage({"question": "test question"})
    )
    other_task = asyncio.create_task(independent_work())

    try:
        await asyncio.sleep(0.05)

        entered = academic_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_academic.is_set()
        )

        result = await asyncio.wait_for(academic_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_academic.set()
        releaser.join(timeout=1.0)
        server.ensure_model = original_ensure_model
        server.academic_orchestrator.run_academic_first_stage = original_orchestrator
        server.model = original_model
        server.tokenizer = original_tokenizer


entered, responsive, result = asyncio.run(exercise_academic_first_stage())

ok(
    "Academic Chat orchestration started",
    entered,
)
ok(
    "event loop remains responsive while Academic Chat orchestration is blocked",
    responsive,
    "run_academic_first_stage() currently occupies the FastAPI event-loop thread",
)
ok(
    "Academic Chat orchestration still completes after release",
    isinstance(result, dict)
    and result.get("answer") == "synthetic academic result",
)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: Academic Chat orchestration is offloaded from the event loop")

print("\n[reviewer-notes Q&A does not block the event loop]")

original_ensure_model = server.ensure_model
original_answer_notes = server.answer_notes_question
original_jobs = server.review_jobs
original_model = server.model
original_tokenizer = server.tokenizer

notes_entered = threading.Event()
release_notes = threading.Event()


def fake_ensure_model():
    return None


def blocking_answer_notes(question, job_id=""):
    notes_entered.set()
    if not release_notes.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release reviewer-notes Q&A")
    return {
        "answer": "synthetic notes answer",
        "provenance": {},
        "check": "",
        "problems": [],
        "passages": 1,
    }


async def exercise_notes_qa():
    server.ensure_model = fake_ensure_model
    server.answer_notes_question = blocking_answer_notes
    server.review_jobs = {
        "async-test": {
            "status": "complete",
            "text": "synthetic manuscript text",
            "report": "",
            "filename": "synthetic.pdf",
        }
    }
    server.model = object()
    server.tokenizer = object()

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    releaser = threading.Thread(
        target=lambda: (
            notes_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_notes.set(),
        ),
        daemon=True,
    )
    releaser.start()

    qa_task = asyncio.create_task(
        server.ask_about_review(
            "async-test",
            {"question": "test question", "mode": server.SOURCE_NOTES},
        )
    )
    other_task = asyncio.create_task(independent_work())

    try:
        await asyncio.sleep(0.05)
        entered = notes_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_notes.is_set()
        )

        result = await asyncio.wait_for(qa_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_notes.set()
        releaser.join(timeout=1.0)
        server.ensure_model = original_ensure_model
        server.answer_notes_question = original_answer_notes
        server.review_jobs = original_jobs
        server.model = original_model
        server.tokenizer = original_tokenizer


entered, responsive, result = asyncio.run(exercise_notes_qa())

ok("reviewer-notes Q&A started", entered)
ok(
    "event loop remains responsive while reviewer-notes Q&A is blocked",
    responsive,
    "answer_notes_question() currently occupies the FastAPI event-loop thread",
)
ok(
    "reviewer-notes Q&A still completes after release",
    isinstance(result, dict)
    and result.get("answer") == "synthetic notes answer",
)


print("\n[manuscript Q&A does not block the event loop]")

original_ensure_model = server.ensure_model
original_answer_manuscript = server.rp.answer_manuscript_question
original_select_passages = server.rp.select_passages
original_jobs = server.review_jobs
original_model = server.model
original_tokenizer = server.tokenizer

manuscript_entered = threading.Event()
release_manuscript = threading.Event()


def blocking_answer_manuscript(*args, **kwargs):
    manuscript_entered.set()
    if not release_manuscript.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release manuscript Q&A")
    return "synthetic manuscript answer", []


async def exercise_manuscript_qa():
    server.ensure_model = fake_ensure_model
    server.rp.answer_manuscript_question = blocking_answer_manuscript
    server.rp.select_passages = lambda *args, **kwargs: []
    server.review_jobs = {
        "async-test": {
            "status": "complete",
            "text": "synthetic manuscript text",
            "report": "",
            "filename": "synthetic.pdf",
        }
    }
    server.model = object()
    server.tokenizer = object()

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    releaser = threading.Thread(
        target=lambda: (
            manuscript_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_manuscript.set(),
        ),
        daemon=True,
    )
    releaser.start()

    qa_task = asyncio.create_task(
        server.ask_about_review(
            "async-test",
            {"question": "test question", "mode": server.SOURCE_MANUSCRIPT},
        )
    )
    other_task = asyncio.create_task(independent_work())

    try:
        await asyncio.sleep(0.05)
        entered = manuscript_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_manuscript.is_set()
        )

        result = await asyncio.wait_for(qa_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_manuscript.set()
        releaser.join(timeout=1.0)
        server.ensure_model = original_ensure_model
        server.rp.answer_manuscript_question = original_answer_manuscript
        server.rp.select_passages = original_select_passages
        server.review_jobs = original_jobs
        server.model = original_model
        server.tokenizer = original_tokenizer


entered, responsive, result = asyncio.run(exercise_manuscript_qa())

ok("manuscript Q&A started", entered)
ok(
    "event loop remains responsive while manuscript Q&A is blocked",
    responsive,
    "answer_manuscript_question() currently occupies the FastAPI event-loop thread",
)
ok(
    "manuscript Q&A still completes after release",
    isinstance(result, dict)
    and result.get("answer") == "synthetic manuscript answer",
)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: review Q&A inference is offloaded from the event loop")

print("\n[model readiness does not block the event loop]")

original_ensure_model = server.ensure_model
original_generate = server.generate
original_model = server.model
original_tokenizer = server.tokenizer

ensure_entered = threading.Event()
release_ensure = threading.Event()


def blocking_ensure_model():
    ensure_entered.set()
    if not release_ensure.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release model readiness")
    server.model = object()
    server.tokenizer = object()


def immediate_generate(*args, **kwargs):
    return "synthetic readiness answer"


async def exercise_model_readiness():
    server.ensure_model = blocking_ensure_model
    server.generate = immediate_generate
    server.model = None
    server.tokenizer = None

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    releaser = threading.Thread(
        target=lambda: (
            ensure_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_ensure.set(),
        ),
        daemon=True,
    )
    releaser.start()

    chat_task = asyncio.create_task(
        server.chat_completions(
            {
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 8,
            }
        )
    )
    other_task = asyncio.create_task(independent_work())

    try:
        await asyncio.sleep(0.05)

        entered = ensure_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_ensure.is_set()
        )

        result = await asyncio.wait_for(chat_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_ensure.set()
        releaser.join(timeout=1.0)
        server.ensure_model = original_ensure_model
        server.generate = original_generate
        server.model = original_model
        server.tokenizer = original_tokenizer


entered, responsive, result = asyncio.run(exercise_model_readiness())

ok("model readiness started", entered)
ok(
    "event loop remains responsive while model readiness is blocked",
    responsive,
    "ensure_model() currently occupies the FastAPI event-loop thread",
)
ok(
    "request still completes after model readiness is released",
    isinstance(result, dict)
    and result.get("choices")
    and result["choices"][0]["message"]["content"]
        == "synthetic readiness answer",
)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: model readiness is offloaded from the event loop")
