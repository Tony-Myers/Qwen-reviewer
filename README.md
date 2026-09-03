# Local manuscript review

A peer-review assistant for quantitative manuscripts that runs entirely on your
own machine. It parses a paper, extracts typed evidence blocks, works out which
statistical framework the authors used, critiques each section against the
expectations appropriate to that framework, and writes a review report with an
evidence appendix.

**No manuscript text leaves the machine.** Everything runs against a local
model server; there are no API calls to anyone.

The project is named for the model family it was first built on, but carries no
version number: the underlying model has moved several times and will move
again. Changing model is a configuration change, not a rewrite.

---

## Requirements

- An Apple silicon Mac with enough unified memory to hold the model you choose
  (the default is about 17 GB), or any machine that can run `llama-server`
- Python 3.11 or newer
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — `brew install llama.cpp`
  on macOS
- A GGUF model file (see **Choosing a model**)

MLX is optional and only needed if you want to run MLX-format models instead of
GGUF.

## Installation

```bash
git clone <this repository>
cd <the repository>

python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn python-multipart pdfplumber python-docx openpyxl

# Optional, for MLX models rather than GGUF:
.venv/bin/pip install mlx mlx-lm
```

The shell scripts find the project from their own location, so the folder can
be renamed or moved without editing anything.

## Choosing a model

Any instruction-following model in GGUF format will run. The pipeline was
developed against a 27B model at 4-bit quantisation, which is a reasonable
balance of quality and memory on a 64 GB machine; smaller models work but
produce noticeably thinner reviews.

Download a GGUF (from Hugging Face, for example) and point the pipeline at it:

```bash
export MODEL_NAME=/path/to/your-model.gguf
```

`app/review_pipeline.py` holds a default path and a table of short aliases in
`MODEL_ALIASES`, which is the single source of truth — the launcher, the
command line and the web interface all fold it in, so the same alias means the
same model everywhere. Edit that table to add your own aliases. An alias that
is not recognised is passed through unchanged, so full Hugging Face repo ids
and absolute `.gguf` paths always work:

```bash
./run_review.sh --list-models              # what the aliases currently point at
./run_review.sh --model /path/to/a.gguf paper.pdf
./run_review.sh --model mlx-community/some-model paper.pdf
```

Two things to know about the model server. The pipeline sends
`chat_template_kwargs`, so `llama-server` must be started with `--jinja` — the
launchers pass it. And if `llama-server` reports an unknown architecture, your
llama.cpp build predates the model; `brew upgrade llama.cpp` usually fixes it.

## Quick start

```bash
./scripts/qwen_service.sh start      # starts llama-server and the web app
```

That starts `llama-server` on port 8081 if it is not already running, waits for
the model to load, then starts the review interface on
<http://localhost:8090>. Upload a PDF and watch the progress log; the report
and evidence appendix download when it finishes.

Two settings sit beside the **Start review** button and apply to that review
only, so neither needs a restart:

| Control | What it does |
| --- | --- |
| **Reasoning** | `instruct`, `thinking`, or `thinking: synthesis only` — the hybrid, which reasons in the synthesis and validation but not in the chunk notes. See [Reasoning mode](#reasoning-mode). |
| **Vision** | whether a table whose text layer looks damaged is re-read from the page image. See [Reading damaged tables from the page image](#reading-damaged-tables-from-the-page-image). |

Once a review has finished, an **Ask about this manuscript** box appears below
it. See [Asking about a reviewed manuscript](#asking-about-a-reviewed-manuscript).

```bash
./scripts/qwen_service.sh status     # what is running, and on which code
./scripts/qwen_service.sh logs app   # follow the app-server log
./scripts/qwen_service.sh stop       # stop both processes
```

The service script accepts `--model ALIAS`, `--passes N` and
`--effort low|medium|high|xhigh`; settings are read when the app server starts,
so a change needs `restart`, not `start`.

### Command line

```bash
./start_llama_server.sh                              # model server, resident
./run_review.sh ~/papers/manuscript.pdf              # review a paper
./run_review.sh --chat                               # interactive chat
./run_review.sh --query "Explain a GAMLSS model"     # one-shot question
```

`./start_server.sh` is an alternative launcher that runs both processes in one
terminal with the interface on port 8080, stopping them together on Ctrl+C
unless `--keep-llama` is given.

---

## How it works

1. **Document parsing** — PDF, docx, csv, xlsx, txt, md.
2. **Evidence structuring** — typed blocks: `TABLE`, `MODEL`, `DESIGN`,
   `RESULT`, `FIGURE_CAPTION`, `NARRATIVE`.
3. **Method classification** — rule-based detection of the analytic framework
   (Bayesian mixed effects, distributional/GAMLSS, cross-classified MCMC,
   frequentist profile models, and others).
4. **Study-design classification** — separately from the method, and reported
   beside it: a meta-analysis pooling with a Bayesian model is both an evidence
   synthesis and a Bayesian analysis, and the two expectations are different.
   Where the design is recognised, the report gains an **Expected reporting
   elements** section listing what a study of that kind normally reports and
   could not be found — with the search terms printed, because an absence check
   accuses where a quotation check merely misses.
5. **Method-aware critique** — the prompt for each chunk carries the
   expectations appropriate to the framework actually used, so a Bayesian
   analysis is not criticised for missing frequentist diagnostics.
6. **Synthesis and validation** — synthesis into a single report, followed by
   programmatic and model-driven post-checks: contradiction correction,
   direction-of-effect checks, negative-constraint enforcement, and arithmetic
   checks that need no model at all — an estimate lying outside its own
   confidence interval, a fit index failing a threshold the manuscript itself
   declared, a set of category percentages that does not sum, a value the text
   attributes to one table that appears only in another.
7. **Output** — a markdown review report plus an evidence appendix showing
   exactly what was extracted and fed to the model.

### Manuscripts under review

Papers in peer review carry line numbers down the margin, and the PDF text
layer puts them inside the sentences: *"The number of clusters (K) 174 was
chosen based on the elbow heuristic"*. They are removed before anything reads
the text, and the report header says how many were taken out.

Only a run of trailing integers that climbs through the document is removed, so
a table row ending in a count is left alone and a document that is not numbered
comes back untouched.

This matters more than it sounds. On one submitted manuscript the line numbers
made every quotation spanning a line break fail the citation check — correct
quotations reported as unverifiable, the reliability banner fired on a report
that deserved none — and a line number was read as a sample size. Published
papers carry no line numbers, so a corpus of published papers will never show
this.

### Reading damaged tables from the page image

Text extraction recovers the numbers in a table more often than it recovers the
shape. Two measured examples: a results table kept every value but scattered
its column headers onto orphan lines and split the row labels away from the
rows they label; another broke "Parabolic" into "Paraboli" and "c" on separate
lines. Reports could then only refer to "the first men's block" rather than
naming the event.

If your model has a vision encoder — a separate `mmproj` file beside the
model — the pipeline can re-read those pages as images:

```bash
./scripts/qwen_service.sh restart --vision
```

That starts `llama-server` with `--mmproj` and `--image-min-tokens 1024`
(upstream's minimum for placing things correctly on a page, which is exactly
what reading a table cell depends on) and turns on `QWEN_VISION_TABLES` for the
app server. Without a projector beside the model the flag warns and carries on
without it.

### Asking about a reviewed manuscript

Under a finished review there is an **Ask about this manuscript** box. It answers
from that paper's extracted text and nothing else: the question selects passages
by term overlap, the model sees only those passages, and every answer goes
through the same citation check the report does, against the same text. The
result travels with the answer — every quotation located, a quotation that could
not be found, or a note that the answer quoted nothing and so was not checked at
all.

It is a lookup instrument, not a second opinion. It will not judge the paper, and
where the retrieved passages do not settle a question it is told to say so rather
than to infer. That matters because a report's concerns are labelled by whether
their quotations resolved, which is not the same as whether they are right;
asking where the paper says something is the cheapest way to find out.

The flag now sets only the default. A single review can override it from the
**Vision** selector in the browser, next to the reasoning mode, so vision can be
turned on or off for one paper without restarting the server. The projector is
loaded whenever one sits beside the model, whether or not `--vision` was passed,
because otherwise the selector would have nothing to switch on; set
`QWEN_LOAD_MMPROJ=0` to keep it out of memory. The report header says which of
three things happened — vision off, vision on with no damaged table found, or
the pages that were re-read — so a silent header no longer has two possible
meanings.

Only tables that look structurally damaged are re-read, and damage means one of
three things actually observed: a word broken across lines, a malformed cell
such as `s0`, or a third or more of the rows carrying no numbers at all so that
headers and labels have come away from their data. A clean table is left alone,
because rendering a page and asking a model to read it costs about a minute.

**The transcription is added beside the text-layer version, never in place of
it,** labelled `Source: vision` in the evidence appendix. Two reasons. A reader
can see which reading a concern rests on. And because the transcription joins
the source text, the citation check verifies quotations against it like any
other evidence — a reading with nothing behind it is the thing this pipeline
exists to remove.

What was measured before this was built: on two damaged tables the
transcription recovered the structure completely, invented no numbers at all,
and preserved a garbled cell (`s0`) rather than tidying it away. That last
point is what makes it usable — the garbled cell turned out to be what the
paper prints. `tests/probe_vision.py` runs the same comparison on any page.

---

## Reading a report

A report opens with a header recording exactly what produced it:

```
Generated: 2026-09-02T04:21:47
Model: your-model.gguf
Pipeline: c01c8e16
Extraction: 684 marginal line number(s) removed before analysis
Reasoning: thinking (synthesis and validation only)
Reasoning check: reasoning emitted in 3 of 17 generations (47,852 characters)
```

`Pipeline` is a hash of the three files that shape a review
(`review_pipeline.py`, `server.py`, `llm_backend.py`), so a report can always be
traced to the code that wrote it, and the service warns you when the running
process is older than the files on disk.

### What the report grades, and what it does not

Every concern carries a computed `Confidence:` line, and the report ends with an
`Items by evidence` table ordered by it:

| Label | Meaning |
| --- | --- |
| Quoted | every quotation in the item was located in the extracted text |
| Reasoned | the item argues from the evidence rather than quoting it |
| Unquoted | a quotation could not be located, or the evidence cited the pipeline's own summary rather than the paper |
| Question | a check to settle, not an established fault |

**This orders provenance, not correctness.** An Unquoted item may be right and a
Quoted one wrong. The labels record how an item is worded and evidenced, which
is a useful signal and not a verdict: across the manuscripts this pipeline has
been measured against, concerns that human reviewers raised independently have
arrived Unquoted, because the model paraphrased rather than quoted. Read the
label as "how far can I check this without opening the paper", not as "is this
right".

When no concern reaches Quoted, a banner at the top of the report says so, in
the same terms.

These labels are computed by the citation check, not asserted by the model.
There is deliberately no severity grade: an earlier version asked the model to
rate its own concerns Critical, Substantive or Editorial, and across the
reports measured it used one value for 82% of them and, on the one occasion it
discriminated, ranked its best-supported concern below its weakest. How much a
concern matters is the reviewer's judgement. What the report can establish
mechanically is whether the concern rests on the paper.

Two further sections are computed directly from the text, independently of
anything the model said:

- **Data consistency check** — unresolved cross-references
  (`Error! Reference source not found.`), display-item counts, sample-size
  arithmetic, and similar.
- **Citation check** — every quotation searched for in the extracted text, and
  every number checked against it. A report containing no quotations at all is
  called out rather than congratulated.

### What the citation check cannot tell you

**It verifies that a quotation matches the extracted text, not that it matches
the manuscript.** Everything downstream of extraction — the model, the citation
check, and the question box — reads the same extracted text, so a value that
extraction corrupted is confirmed rather than caught, and it is confirmed
consistently by all three.

This is not hypothetical. A line-numbered manuscript under review reported a
sample size as `n = 173`, and the marginal line number for that line was glued
to the end of the text with no space before it, so the extracted text read
`n =116 173`. The report asked the reviewer to resolve the ambiguity, the
citation check confirmed the quotation, and the question box confirmed it again.
All three were right about the text and wrong about the paper. The stripper now
removes numbers in that position, but the general point stands.

So:

- **Check numeric values against the PDF before using them.** Sample sizes,
  coefficients, degrees of freedom, p-values and confidence limits are the
  values most often disturbed by extraction and the least self-evident when they
  are wrong. A figure that looks odd usually is odd, in one direction or the
  other.
- **Read the `Extraction:` header lines.** They say how many marginal line
  numbers were removed, which tables were re-read from the page image, and
  whether vision was on at all. A manuscript with hundreds of line numbers
  removed is one where a stray number surviving is plausible.
- **Graphical figures are never read.** Anything that exists only in a figure —
  a flow diagram, a directed acyclic graph, a plotted distribution — is invisible
  to the pipeline, and a report cannot notice a fault it cannot see. Where a
  concern turns on a figure, the report should be saying it could not look; if it
  says anything stronger, treat that as the model overreaching.

---

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_NAME` | see `review_pipeline.py` | Model path, repo id or alias |
| `QWEN_LLM_BACKEND` | inferred | `llama-server`, `llama-cpp` or `mlx` |
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8081` | Where llama-server is listening |
| `LLAMA_SERVER_BIN` | `llama-server` | Binary name or path |
| `LLAMA_SERVER_AUTOSTART` | unset | `1` to have the pipeline start llama-server itself |
| `LLAMA_SERVER_CTX` | `32768` | Context size |
| `LLAMA_SERVER_NGL` | `99` | GPU layers to offload |
| `LLAMA_REQUEST_TIMEOUT` | `1800` | Per-request timeout, seconds |
| `LLAMA_ENABLE_THINKING` | off | `1` to let the model emit reasoning |
| `LLAMA_REASONING_EFFORT` | `medium` | `low`, `medium`, `high`, `xhigh`; `template` sends nothing |
| `REVIEW_PASSES` | 1 (the service sets 3) | Synthesis passes |
| `QWEN_THINKING_PASSES` | 1 | Passes when thinking is on |
| `QWEN_VISION_TABLES` | off | `1` to re-read damaged tables from the page image |
| `QWEN_VISION_DPI` | `200` | Render resolution for those pages |
| `QWEN_VISION_MAX_PAGES` | `6` | Most pages to re-read in one review |
| `QWEN_THINKING_EXTRA_TOKENS` | 8000 | Generation budget added for reasoning |
| `QWEN_TEMPERATURE` | 0.2 | Sampling temperature |
| `QWEN_TOP_P` | 0.8 | Nucleus sampling |
| `QWEN_TOP_K` | 20 | Top-k sampling |
| `QWEN_REPETITION_PENALTY` | unset | Server default applies |
| `QWEN_PRESENCE_PENALTY` | unset | Server default applies |
| `QWEN_SYNTHESIS_MAX_TOKENS` | 2000 | Cap on the final synthesis |
| `REPEAT_PASS_TEMPERATURE` | 0.7 | Temperature for passes after the first |

The backend is inferred from the model id — anything ending in `.gguf` uses
`llama-server`, everything else uses `mlx` — and can be forced with `--backend`
or `QWEN_LLM_BACKEND`.

The temperature is deliberately low for a factual task. `top_p` and `top_k`
match the model publisher's recommended non-thinking values. The penalties are
left unset so the server's own defaults apply rather than ours.

### Backends

| Backend | Used for | Notes |
| --- | --- | --- |
| `llama-server` | `.gguf` models (default) | OpenAI-compatible HTTP to llama.cpp; the model stays resident between runs |
| `llama-cpp` | `.gguf` models | In-process `llama_cpp.Llama`; needs `pip install llama-cpp-python` |
| `mlx` | `mlx-community/...` repo ids | Requires `mlx` and `mlx-lm` |

`app/llm_backend.py` exposes `load`, `generate` and `make_sampler` with the same
signatures as `mlx_lm`, so every call site in the pipeline is backend-agnostic.

---

## Synthesis passes

Findings rotate between runs: the same paper, the same code and the same model
can produce quite different sets of concerns, and a single pass tends to give
about half of what the model can see. The service therefore runs the final
synthesis three times by default and unions the concerns and verification
prompts, marking anything found only in a later pass.

Each pass is a full generation, so a review takes roughly three times as long.
For a quick pass:

    ./scripts/qwen_service.sh restart --passes 1

The first pass uses the normal low temperature and becomes the base report;
later passes are sampled warmer (`REPEAT_PASS_TEMPERATURE`), because a repeat at
the same temperature largely reproduces the first and the union then adds
nothing.

Each pass is validated on its own *before* the merge. Validating the merged
report instead nullifies the exercise — on one run the merge contributed four
items and validation removed four, a net gain of nothing for three times the
generation. The header records what happened:

    Synthesis: 3 pass(es), each validated before merging; validation kept
    9/14 concerns and 8/12 checks across passes; 4 item(s) added to the base
    by later passes

---

## Reasoning mode

The browser offers a choice per review:

| Choice | What reasons |
| --- | --- |
| instruct | nothing; the default, and the fastest |
| thinking | every generation, including the chunk notes |
| thinking: synthesis only | the file synthesis, report synthesis and validation |

The third is the hybrid, and on the evidence so far it is the one worth using
when a paper matters: the chunk notes stay in instruct mode, which keeps their
quotations for the synthesis to pass through, while the stages that exercise
judgement reason. Full thinking tends to paraphrase in the chunk notes, leaving
the synthesis to reconstruct quotations from memory — which produces reports
that read well and cite badly.

### What the header records

Asking for thinking and getting it are different things, and several paths fail
silently: the server can reject `chat_template_kwargs` and retry without it; a
chat template can emit an empty `<think></think>` pair; a server running
`--reasoning-format deepseek` returns reasoning in its own field rather than
inline. Each produces a report headed `thinking` containing no reasoning at all.

So the reasoning actually emitted is counted, and the header says what happened
rather than what was asked for:

    Reasoning check: reasoning emitted in 14 of 16 generations (52,122 characters)
    Reasoning check: no reasoning emitted in any of 16 generations, so this run
    behaved as instruct

A report of the second kind is grouped separately by the tally, because it is an
instruct run in all but the label.

### Budgets

Reasoning is generated inside `max_tokens`, not alongside it, so a thinking
generation gets `QWEN_THINKING_EXTRA_TOKENS` added to its budget and the prompt
budget gives the same room back. No fixed allowance is right for every prompt —
on one manuscript the reasoning ended by itself at 3,200 tokens on the first
chunk and overran 8,900 on the fourth — so the allowance is only a starting
point. A generation that spends its whole budget reasoning and returns nothing,
or an answer cut off mid-sentence, is retried with the budget doubled up to what
the context window allows, and finally in instruct mode so one difficult chunk
cannot end an hour-long review. Retries and fallbacks are counted in the
`Reasoning check:` line: a review with several fallbacks is not really a
thinking review.

Two further guards: a generation that returns an empty answer after emitting
reasoning raises rather than returning the empty string, and a report that never
reaches its final heading is refused rather than written out. Half a report is
still valid markdown and reads as though it were meant to end where it does.

### Reasoning effort

`LLAMA_REASONING_EFFORT` defaults to `medium`, which is measured rather than
assumed. On one chunk of one manuscript, everything else equal:

| effort | reasoning | answer |
| --- | --- | --- |
| template default | 14,465 characters | 4,991 characters |
| `medium` | 7,616 characters | 6,641 characters |

Half the reasoning and a third more answer. A full hybrid review then halved the
reasoning per generation and cut its retries from four to one. Two runs on one
paper is not proof; it is cheaper, no worse on every measure taken, and
`--effort template` restores the previous behaviour.

Not every chat template has a `reasoning_effort` branch. Before spending an hour
on a thinking review, spend twenty seconds finding out whether the flag does
anything on your model:

    .venv/bin/python tests/probe_thinking.py

### Passes and reasoning do not stack

`REVIEW_PASSES` repeats the synthesis, and in a thinking review the synthesis is
the stage that reasons, so three passes means seven thinking generations before
any retries. A thinking or hybrid review therefore takes a single pass whatever
`REVIEW_PASSES` says; the reduction is announced in the progress log and
recorded in the header. `QWEN_THINKING_PASSES` overrides it, which is worth
doing only to test whether extra passes and reasoning add anything to each
other — they may be two ways of buying the same thing.

---

## Measuring changes

Every default here was set by measurement, and the tools are in the repository
so you can repeat them on your own papers and your own model.

```bash
.venv/bin/python tests/probe_thinking.py           # does thinking work at all?
.venv/bin/python tests/probe_thinking_chunk.py paper.pdf   # how much does it reason?
.venv/bin/python tests/sampler_sweep.py a.pdf b.pdf        # compare configurations
.venv/bin/python tests/report_tally.py reports/            # tally reports you have
```

`sampler_sweep.py` reviews each paper under each configuration and scores the
reports on figures the pipeline already computes: concerns reaching High
confidence, self-citations, unverifiable quotations and numbers, echoed
evidence. Every configuration is a full review, so budget the time and close
anything else holding a large model in memory.

**Know the noise floor before reading anything into a difference.** The sweep
includes an `a-a-control` row that is a duplicate of `current`; the gap between
them is this pipeline's variation at a fixed setting. Measured over four papers,
that noise was 3 in `high`, 9 in `self` and 6 in `quot`, with one paper swinging
from 2 to 8 unverifiable quotations with nothing changed at all. Ten reviews per
configuration is a sensible minimum.

`report_tally.py` groups reports you have already run — by reasoning mode, pass
count or pipeline version — so alternating settings over real work accumulates
into an evaluation rather than an impression.

The test suites run directly and locate the project themselves:

```bash
for t in tests/test_*.py; do .venv/bin/python "$t"; done
```

---

## Layout

```
app/
  review_pipeline.py    parsing, evidence extraction, classification, critique
  server.py             FastAPI app: chat, review upload, progress stream
  llm_backend.py        backend abstraction over llama.cpp and mlx_lm
  chat.html             web interface
scripts/
  qwen_service.sh       start, stop and inspect the service
tests/                  test suites and measurement tools
start_server.sh         single-terminal launcher
start_llama_server.sh   model server on its own
run_review.sh           command-line entry point
```

`inputs/`, `reports/` and `reviews/` are excluded from version control: they
hold manuscripts and generated reviews.

## Troubleshooting

**"unknown architecture" from llama-server.** Your llama.cpp build predates the
model. `brew upgrade llama.cpp`.

**Thinking mode produces no reasoning.** Run `tests/probe_thinking.py`. It
reports whether the chat template has an `enable_thinking` branch to act on;
a template without one accepts `chat_template_kwargs` and ignores it.

**A review dies partway through with a context-window error.** The prompt is
budgeted against the server's context, but a very large supplementary file can
still overrun it. Raise `LLAMA_SERVER_CTX` if memory allows.

**The report says the code changed.** The app server imports the pipeline at
start-up, so edits need `./scripts/qwen_service.sh restart` to take effect. The
service tells you when the running process is older than the files on disk.
