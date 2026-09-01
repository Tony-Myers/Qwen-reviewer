#!/usr/bin/env python3
"""
Measure how much reasoning one real chunk review actually needs.

Why this exists
---------------
Two thinking runs both filled their entire generation budget with reasoning and
returned no answer: 8,965 characters against a 2,100-token cap, then 22,757
against 4,900. Both worked out at roughly 4.3 to 4.6 characters per token,
which is ordinary English prose -- in other words the reasoning was cut off by
the cap on both occasions, not finished. Raising the allowance again is a guess
unless we know where the reasoning would stop if left alone. It might terminate
at 6,000 tokens, or it might not terminate at all.

This runs the real chunk-review path on one chunk with a deliberately large
budget and reports what happened, so the allowance can be set from a
measurement rather than another guess.

    .venv/bin/python tests/probe_thinking_chunk.py path/to/paper.pdf
    .venv/bin/python tests/probe_thinking_chunk.py paper.pdf --chunk 1 --budget 24000

The reasoning is written to a file so it can be read. If it repeats itself,
the problem is not the budget.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import llm_backend                      # noqa: E402
import review_pipeline as rp            # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paper", type=Path)
    ap.add_argument("--chunk", type=int, default=1, help="1-based chunk number")
    ap.add_argument("--budget", type=int, default=24000,
                    help="total generation budget in tokens (default 24000)")
    ap.add_argument("--out", type=Path, default=ROOT / "logs" / "reasoning_sample.txt")
    args = ap.parse_args()

    if not args.paper.exists():
        print(f"No such file: {args.paper}")
        return 2

    print(f"Loading {args.paper.name}...")
    text, table_blocks = rp.load_document(args.paper)
    manifest = rp.structure_evidence(args.paper.name, text, table_blocks)
    method_expectations = rp.get_method_expectations(
        manifest.method_class, additional_classes=manifest.additional_method_classes)
    chunks = rp.split_text(text)
    if not chunks:
        print("No usable text extracted.")
        return 1
    if not 1 <= args.chunk <= len(chunks):
        print(f"--chunk must be between 1 and {len(chunks)}")
        return 2

    print(f"{len(chunks)} chunks; measuring chunk {args.chunk}")
    print(f"Method: {manifest.method_class.value}")
    effort = llm_backend.reasoning_effort()
    print(f"Reasoning effort: {effort or 'unset (the template default)'}")

    model, tokenizer = llm_backend.load(rp.MODEL_NAME)
    chunk = rp.DocChunk(source_name=args.paper.name, chunk_id=args.chunk,
                        text=chunks[args.chunk - 1])

    # The real path, with the cap lifted for this one call. The module constant
    # is restored afterwards so nothing else is affected.
    original_cap = rp.SECTION_MAX_TOKENS
    original_allowance = llm_backend.THINKING_EXTRA_TOKENS
    llm_backend.THINKING_EXTRA_TOKENS = 0
    rp.SECTION_MAX_TOKENS = args.budget
    llm_backend.reset_reasoning_stats()
    answer = ""
    failed = ""
    try:
        with llm_backend.thinking(True):
            print(f"Generating with a {args.budget}-token budget. This will take "
                  f"a while; {args.budget} tokens at about 22 per second is "
                  f"roughly {args.budget // 22 // 60} minutes at worst.",
                  flush=True)
            answer = rp.review_chunk(
                model, tokenizer, chunk,
                method_expectations=method_expectations,
                manifest_summary=manifest.summary_text(),
            )
    except llm_backend.BackendError as exc:
        failed = str(exc)
    finally:
        rp.SECTION_MAX_TOKENS = original_cap
        llm_backend.THINKING_EXTRA_TOKENS = original_allowance

    stats = llm_backend.reasoning_stats()
    chars = stats["chars"]
    print("\n--- result ---")
    print(f"budget given      : {args.budget} tokens")
    print(f"reasoning         : {chars:,} characters "
          f"(about {chars // 4.5:,.0f} tokens at 4.5 characters each)")
    print(f"answer            : {len(answer):,} characters")
    if failed:
        print("outcome           : NO ANSWER -- the budget ran out mid-thought")
        print(f"                    {failed.splitlines()[0]}")
    elif chars and answer:
        print("outcome           : reasoning finished on its own and an answer followed")
        print(f"                    an allowance of about {int(chars // 4.5 * 2):,} "
              f"tokens would cover this run twice over")
        print("                    one sample understates: the same chunk has "
              "varied by 1.6x between runs")
    else:
        print("outcome           : no reasoning was emitted at all")

    if chars:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # The pipeline discards reasoning by design, so this is the only place
        # it can be read. Whether it circles or progresses is the question a
        # token count cannot answer.
        args.out.write_text(
            f"budget {args.budget} tokens, reasoning {chars} characters\n"
            f"{'=' * 70}\nREASONING\n{'=' * 70}\n"
            f"{llm_backend.last_reasoning()}\n\n"
            f"{'=' * 70}\nANSWER\n{'=' * 70}\n"
            f"{answer or '(no answer returned)'}\n",
            encoding="utf-8")
        print(f"\nReasoning and answer written to {args.out}")
        print("Read the end of it. Reasoning that circles back over the same "
              "points will not be fixed by a larger allowance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
