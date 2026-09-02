# Qwen review

A local manuscript peer-review pipeline that runs entirely on a Mac Studio.

The name carries no version number deliberately: the underlying model has moved
from Qwen3.5 to Qwen3.6 to Qwen3.8 and will move again. Swapping the model is a
configuration change, not a rewrite. It
parses documents, extracts typed evidence blocks, classifies the statistical
method used, critiques each section against method-specific expectations, and
synthesises a review report with an evidence appendix.

No manuscript text leaves the machine.

## Pipeline

1. **Document parsing** — PDF, docx, csv, xlsx, txt, md (optional Marker).
2. **Evidence structuring** — typed blocks: `TABLE`, `MODEL`, `DESIGN`,
   `RESULT`, `FIGURE_CAPTION`, `NARRATIVE`.
3. **Method classification** — rule-based detection of the analytic framework
   (Bayesian mixed effects, distributional/GAMLSS, cross-classified MCMC,
   frequentist profile models, and others).
4. **Method-aware critique** — the prompt for each section carries the
   expectations appropriate to the framework actually used, so a Bayesian
   analysis is not criticised for missing frequentist diagnostics.
5. **Synthesis and validation** — LLM synthesis followed by programmatic and
   LLM post-checks (contradiction correction, direction-of-effect checks,
   negative-constraint enforcement).
6. **Output** — a markdown review report plus an evidence appendix.

Manuscripts under review carry line numbers down the margin, and the PDF text
layer puts them inside the sentences: *"The number of clusters (K) 174 was
chosen based on the elbow heuristic"*. They are removed before anything reads
the text, and the report says how many were taken out. Only a run of trailing
integers that climbs through the document is removed, so a table row ending in
a count is left alone; a document that is not numbered comes back untouched.

This matters more than it sounds. On one submitted manuscript the line numbers
made every quotation spanning a line break fail the citation check — three
correct quotations reported as unverifiable, the reliability banner fired, and
sound concerns pushed down the evidence table — and line 129 was read as a count
of races. Published papers carry no line numbers, which is why a corpus of them
never showed it.

## What the report grades, and what it does not

Every concern carries a computed `Confidence:` line and the report ends with an
`Items by evidence` table ordered by it. Both come from the citation check,
which looks for each quotation in the extracted manuscript text: Verified means
every quotation was located, Inferred means the concern is reasoning rather than
quotation, Unverified means a quotation could not be found or the evidence cited
this pipeline's own summary. When no concern reaches Verified, a banner says so
at the top of the report.

The synthesis used to award each concern a severity of Critical, Substantive or
Editorial, and the table was ordered by it. That has been removed. Across the
reports we measured it used one of the three values for 82% of concerns, never
reached for Critical or Editorial at all, and on the one occasion it did
discriminate it placed its best-supported concern below its weakest. It was also
the only self-assessed grade left in a report otherwise built on deterministic
checks. How much a concern matters is the reviewer's judgement; what the report
can establish mechanically is whether the concern rests on the paper.

## Model backends

The pipeline was originally written against `mlx_lm`. It now reaches the LLM
through `app/llm_backend.py`, which exposes `load`, `generate` and
`make_sampler` with signatures identical to `mlx_lm`, and dispatches to one of
three backends:

| Backend | Used for | Notes |
| --- | --- | --- |
| `llama-server` | `.gguf` models (default) | OpenAI-compatible HTTP to llama.cpp. The model stays resident between runs. |
| `llama-cpp` | `.gguf` models | In-process `llama_cpp.Llama`. Needs `pip install llama-cpp-python`. |
| `mlx` | `mlx-community/...` repo ids | The original path, unchanged. |

The backend is inferred from the model id — anything ending in `.gguf` uses
`llama-server`, everything else uses `mlx` — and can be forced with
`--backend` or the `QWEN_LLM_BACKEND` environment variable.

### Default model

`Qwen3.8-27B-UD-Q4_K_XL.gguf` (Unsloth dynamic 4-bit quantisation), served by
llama.cpp:

```
~/.cache/huggingface/hub/models--unsloth--Qwen3.8-27B-GGUF/
  snapshots/4ca720788d1e01f1bff70c033e0d0028fd02e502/
  Qwen3.8-27B-UD-Q4_K_XL.gguf
```

This model uses the `qwen35` architecture, a hybrid attention/SSM design, so it
needs a llama.cpp build recent enough to know that architecture. If
`llama-server` reports an unknown architecture, run `brew upgrade llama.cpp`.

Reasoning is disabled: the chat template embedded in the GGUF is applied by
llama.cpp with `enable_thinking=false`, and any `<think>` span that still gets
through is stripped before it can reach a review. This requires the `--jinja`
flag when starting `llama-server`; the launcher passes it.

### Previous MLX models

Still selectable, nothing was removed:

```bash
./start_server.sh --model 35b       # mlx-community/Qwen3.6-35B-A3B-4bit
./start_server.sh --model 27b       # mlx-community/Qwen3.6-27B-6bit
./start_server.sh --model gemma4    # mlx-community/gemma-4-26b-a4b-it-4bit
```

## Usage

### Web interface (chat + review)

```bash
./start_server.sh                 # Qwen3.8-27B GGUF, UI on http://localhost:8080
./start_server.sh --port 8090
./start_server.sh --list-models
```

`start_server.sh` starts `llama-server` on port 8081 if it is not already
running, waits for the model to load, then starts the FastAPI app. Both stop
together on Ctrl+C unless `--keep-llama` is passed.

### Command line

```bash
# Start the model server once and leave it resident
./start_llama_server.sh

# Then, in another terminal
./run_review.sh ~/papers/manuscript.pdf
./run_review.sh --chat
./run_review.sh --query "Summarise the assumptions of a GAMLSS model"
./run_review.sh --list-models
./run_review.sh --model 35b ~/papers/manuscript.pdf   # back to MLX
```

The same short aliases work everywhere — on the command line, in
`start_server.sh`, and in the web UI switcher. `review_pipeline.py`, which
`run_review.sh` calls, holds the canonical table in `MODEL_ALIASES`; the
launcher and `server.py` fold it in rather than keeping their own copies. An
alias that is not recognised is passed through unchanged, so full Hugging Face
repo ids and absolute `.gguf` paths still work.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_NAME` | the Qwen3.8-27B GGUF | Override the default model |
| `QWEN_LLM_BACKEND` | inferred | `llama-server`, `llama-cpp` or `mlx` |
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8081` | Where llama-server is listening |
| `LLAMA_SERVER_BIN` | `llama-server` | Binary name or path |
| `LLAMA_SERVER_AUTOSTART` | unset | `1` to have the pipeline start llama-server itself |
| `LLAMA_SERVER_CTX` | `32768` | Context size |
| `LLAMA_SERVER_NGL` | `99` | GPU layers to offload |
| `LLAMA_REQUEST_TIMEOUT` | `1800` | Per-request timeout, seconds |
| `LLAMA_ENABLE_THINKING` | off | `1` to let the model emit reasoning |
| `LLAMA_REASONING_EFFORT` | `medium` | `low`, `medium`, `high` or `xhigh`, only when thinking is on. `template` sends nothing, leaving the chat template's own default |

## Layout

```
app/
  review_pipeline.py    parsing, evidence extraction, classification, critique
  server.py             FastAPI app: chat, review upload, SSE progress
  llm_backend.py        backend abstraction over llama.cpp and mlx_lm
  chat.html             web interface
start_server.sh         launcher: llama-server + FastAPI app
start_llama_server.sh   llama-server on its own
run_review.sh           command-line entry point
scripts/
  qwen_service.sh       start, stop and inspect the service
tests/                  run any of these directly with .venv/bin/python;
                        they locate the project themselves
backups/                timestamped copies taken before significant edits
```

## Multiple synthesis passes

Findings rotate between runs: the same paper, the same code and the same model
can produce quite different sets of concerns, and a single pass tends to give
about half of what the model can see.

Three passes are the default. The service runs the final synthesis that many
times and unions the concerns and verification prompts, marking anything found
only in a later pass. Each pass is a full generation, so a review takes roughly
three times as long. For a quick triage pass:

    ./scripts/qwen_service.sh restart --passes 1

The setting is read when the app server starts, so it applies to every review
until the next restart. The report header carries a `Synthesis:` line whenever
more than one pass ran, so a report is never ambiguous about which it was.

The first pass uses the normal low temperature and is the base report; later
passes are sampled at `REPEAT_PASS_TEMPERATURE` (0.7 by default), because a
repeat at the same temperature largely reproduces the first and the union then
adds nothing. When more than one pass runs, the report header records what
happened, for example:

    Synthesis: 3 pass(es), each validated before merging; validation kept
    9/14 concerns and 8/12 checks across passes; 4 item(s) added to the base
    by later passes

Each pass is validated on its own before the merge. Validating the merged
report instead nullified the exercise: on one run the merge contributed four
items and validation removed four, a net gain of nothing for three times the
generation. Validation checks a single coherent report against the evidence, so
it is given exactly that, and the union is taken of reports it has already
cleaned.

This costs one validation call per pass. The header and the app-server log
record how much validation removed in each pass and how much the merge added.

## Reasoning mode

Every generation so far has run in instruct (non-thinking) mode; thinking mode
has never been tested. The browser now offers the choice per review -- server
default, instruct, or thinking -- and the report header records which was used:

    Reasoning: instruct
    Reasoning check: no reasoning emitted, as expected (16 generations)

The second line matters more than the first. Asking for thinking and getting it
are different things, and three paths fail silently: llama-server can reject
`chat_template_kwargs`, in which case the request is retried without it; a chat
template can emit an empty `<think></think>` pair; and a server running
`--reasoning-format deepseek` returns reasoning in its own field rather than
inline. Each produces a report headed `thinking` containing no reasoning at
all. So the reasoning the model actually emitted is counted, and the header
says what happened rather than what was asked for:

    Reasoning: thinking
    Reasoning check: reasoning emitted in 14 of 16 generations (52,122 characters)

    Reasoning: thinking
    Reasoning check: no reasoning emitted in any of 16 generations, so this run
    behaved as instruct

A report of the second kind is grouped as `thinking-unproven` by the tally
below, and kept out of the thinking column: it is an instruct run in all but
the label, and counting it as thinking would corrupt the comparison.

Reasoning is generated inside `max_tokens`, not alongside it, and the
chunk-note cap of 900 tokens is already reached on most calls in instruct mode.
A thinking run therefore gets `QWEN_THINKING_EXTRA_TOKENS` (8000) added to every
generation, and the prompt budget gives the same room back so the request
cannot overrun the context window. Without it the two modes would be compared at
different answer lengths, with thinking the shorter of the two for a reason that
has nothing to do with its merits.

The 8,000 is measured, not guessed, and it took three attempts to measure. At
1,200 and again at 4,000 every generation filled its whole budget with reasoning
and returned no answer, and the first of those assembled into a report
containing nothing but a header. Run without a cap, the reasoning on the same
chunk ended by itself after about 3,200 tokens and a full answer followed -- but
the run truncated at 4,000 had already exceeded 5,000 tokens on that same chunk,
so the spread between runs is at least 1.6 times and the upper end is unknown.
`tests/probe_thinking_chunk.py` measures it on any paper; set the allowance from
that rather than from argument.

No fixed allowance is right for every prompt: on this paper the reasoning ended
by itself at 3,200 tokens on chunk 1 and overran 8,900 on chunk 4. So the
allowance is only a starting point. A generation that spends its whole budget
reasoning and returns nothing is retried with the budget doubled, up to what the
context window leaves once the prompt is in it, and finally in instruct mode so
that one difficult chunk cannot end the review. Retries and fallbacks are
counted and named in the `Reasoning check:` line -- a review that repaired
itself should say so, and a review with several fallbacks in it is not really a
thinking review.

Two further guards. A generation that returns an empty answer after emitting
reasoning raises rather than returning the empty string. An empty review is
refused outright rather than written out.

Budget the time as well: reasoning at 3,000 to 5,000 tokens across fourteen
generations is 40,000 to 70,000 extra tokens at about 22 tokens per second, so
a thinking review takes roughly half an hour to an hour longer than the same
paper in instruct mode.

A third option, `thinking: synthesis only`, is the hybrid. The eleven chunk
notes run in instruct and only the file synthesis, the report synthesis and the
validation think. Those three stages are where the pipeline's known weakness
lives -- evidence sourced from this pipeline's own summary rather than the
manuscript -- while the chunk notes are most of the wall-clock time and were
never the faulty stage. Reports from it are grouped as `thinking-synth` in the
tally, separately from full thinking runs, because pooling the two would hide
whichever of them helps.

Passes and reasoning do not stack. `REVIEW_PASSES` repeats the synthesis, and
in a thinking review the synthesis is the stage that reasons, so three passes
means seven thinking generations before any retries -- hours, on the one run
measured. A thinking or hybrid review therefore takes a single pass whatever
`REVIEW_PASSES` says, and the reduction is announced in the progress log and
recorded in the `Reasoning check:` line. Set `QWEN_THINKING_PASSES` to ask for
more, which is worth doing only to test whether extra passes and reasoning add
anything to each other -- they may be two ways of buying the same thing, and
that has never been measured.

**Reasoning effort.** `reasoning_effort` was never sent until now, so every
thinking run used whatever the chat template defaults to. One measurement on
chunk 1 of the same paper, everything else equal:

| effort | reasoning | answer |
| --- | --- | --- |
| template default | 14,465 characters | 4,991 characters |
| `medium` | 7,616 characters | 6,641 characters |

Half the reasoning and a third more answer. A full hybrid review then repeated
it: 26,349 characters of reasoning per thinking generation against 51,270 at
the template default, one retry instead of four, and the strongest report the
pipeline has produced on that paper.

`medium` is therefore the default for thinking runs. `--effort low|high|xhigh`
changes it, `--effort template` sends nothing and restores the behaviour of
every run before this was measured, and the header records which effort produced
a report. `tests/probe_thinking.py` says whether the chat template has a
`reasoning_effort` branch to act on at all -- on a model whose template does
not, the setting changes nothing.

Two runs on one paper is not proof. It is cheaper, it is no worse on every
measure taken, and it is one flag to undo.

Before spending an hour on a thinking review, spend twenty seconds asking the
server whether the flag does anything at all:

    .venv/bin/python tests/probe_thinking.py

It reports whether the chat template baked into the GGUF has an
`enable_thinking` branch, then sends one short request each way and prints how
much reasoning came back. A template with no such branch accepts
`chat_template_kwargs` and ignores it, which is the quietest failure of the
three.

Alternate them over real reviews, then tally what you have:

    .venv/bin/python tests/report_tally.py reports/

This trades control for cost. A sweep runs the same paper twice and takes an
hour per comparison; this uses papers you had to review anyway and accumulates,
at the price of the papers differing between groups. An A/A test on this
pipeline varied by 3 in `high`, 9 in `self` and 6 in `quot` over four papers, so
ten reviews per mode is a sensible minimum before reading anything into it.

## Sampler settings

Sampling is set in `app/review_pipeline.py` and overridable from the
environment: `QWEN_TEMPERATURE` (0.2), `QWEN_TOP_P` (0.8), `QWEN_TOP_K` (20),
`QWEN_REPETITION_PENALTY` and `QWEN_PRESENCE_PENALTY` (both unset, so
llama-server's own defaults apply), and `QWEN_SYNTHESIS_MAX_TOKENS` (2000).

`top_p` and `top_k` already match Unsloth's published non-thinking values. The
temperature is deliberately lower for a factual task, with
`REPEAT_PASS_TEMPERATURE` (0.7) restoring their value for the extra passes.
`QWEN_REPETITION_PENALTY` is sent explicitly at 1.0, which is what
llama-server already defaults to -- stated rather than inherited, so a
llama.cpp upgrade cannot change it silently. `QWEN_PRESENCE_PENALTY` stays
unset (server default 0.0).

To compare configurations with measurement rather than argument:

    .venv/bin/python tests/sampler_sweep.py inputs/a.pdf inputs/b.pdf

It reviews each paper under each configuration and scores the reports on
figures the pipeline already computes -- concerns reaching High confidence,
self-citations, unverifiable quotations and numbers, echoed evidence. It needs
llama-server running, and every configuration is a full review, so budget the
time and close Unsloth first.

`a-a-control` is a duplicate of `current` and is included by default. Its gap
from `current` is this pipeline's noise at a fixed setting, and it is the only
honest yardstick for any other row: measured over four papers, that noise was 3
in `high`, 9 in `self` and 6 in `quot`, with one paper swinging from 2 to 8
unverifiable quotations with nothing changed at all.

`inputs/`, `reports/` and `reviews/` are excluded from version control: they
hold manuscripts and generated reviews.

The shell scripts resolve the project root from their own location, so the
working directory can be renamed or moved without editing anything. The local
folder is still named `qwen35-review` for historical reasons; the repository is
not.

## Requirements

- Apple silicon Mac with enough unified memory for a 17 GB model
- Python 3.13 in `.venv/`
- llama.cpp with `qwen35` architecture support, for the GGUF backend
- `mlx` and `mlx_lm`, for the MLX backend
