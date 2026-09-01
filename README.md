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
| `LLAMA_REASONING_EFFORT` | `xhigh` | `low`, `medium` or `xhigh`, only when thinking is on |

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

    REVIEW_PASSES=3 ./scripts/qwen_service.sh restart

runs the final synthesis that many times and unions the concerns and
verification prompts, marking anything found only in a later pass. Each pass is
a full generation, so a review takes roughly that multiple of the time. The
default is 1.

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
