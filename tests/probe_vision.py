#!/usr/bin/env python3
"""
Ask the model to read a page of a manuscript as an image, and compare what it
sees with what the text extractor got.

Why this exists
---------------
Table extraction is this pipeline's most persistent weakness. One results table
lost its header row entirely and stranded eleven decimal fractions on
neighbouring rows; another produced the cell "s0", which six separate reports
had to raise as an extraction limit rather than read. Figures are worse: a
manuscript can declare two dozen of them and the pipeline sees none, so a
cluster count justified by an elbow plot cannot be audited at all.

Several models ship a vision encoder as a separate mmproj file, and llama.cpp
can serve it. Whether that helps here is a question about this model, this
build and this kind of page -- dense statistical tables in a submitted
manuscript -- and it is answerable in twenty minutes instead of a rewrite.

    .venv/bin/python tests/probe_vision.py paper.pdf --page 21
    .venv/bin/python tests/probe_vision.py paper.pdf --find "Kruskal-Wallis"

The server must be started with the projector for this to do anything:

    llama-server --model <model>.gguf --mmproj <mmproj>.gguf --jinja ...

If it was not, the probe says so rather than reporting a bad transcription.

READ THE RESULT AGAINST THE PDF. This measures difference, not correctness:
neither the text layer nor the transcription is ground truth, and a fluent
transcription of numbers that are not on the page is the failure mode that
would matter most.
"""

import argparse
import base64
import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

TRANSCRIBE = (
    "Transcribe every table on this page exactly as printed. Preserve the "
    "column headers, the row labels and every numeric cell, one row per line "
    "with columns separated by ' | '. Do not summarise, do not interpret, and "
    "do not correct anything that looks wrong. If a cell is empty, write an "
    "empty column. If there is no table on the page, say 'No table on this "
    "page' and nothing else."
)

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:e-?\d+)?")


def render_page(pdf_path: Path, page_number: int, dpi: int) -> bytes:
    """Render one 1-based page to PNG bytes."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise SystemExit(
            "pypdfium2 is needed to render the page:\n"
            "  .venv/bin/pip install pypdfium2"
        )
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        if not 1 <= page_number <= len(document):
            raise SystemExit(f"--page must be between 1 and {len(document)}")
        page = document[page_number - 1]
        image = page.render(scale=dpi / 72).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


def page_text(pdf_path: Path, page_number: int) -> str:
    """What the pipeline's text layer sees on that page."""
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return pdf.pages[page_number - 1].extract_text() or ""


def find_page(pdf_path: Path, needle: str) -> int:
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            if needle.lower() in (page.extract_text() or "").lower():
                return index
    raise SystemExit(f"{needle!r} was not found in the text layer of {pdf_path.name}")


def ask(base_url: str, png: bytes, max_tokens: int, timeout: int) -> str:
    """One vision request. The payload is deliberately minimal."""
    data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    payload = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": TRANSCRIBE},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "max_tokens": int(max_tokens),
        "temperature": 0.1,
        "stream": False,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(
            f"The server refused the image (HTTP {exc.code}):\n  {detail}\n\n"
            "Almost always this means llama-server was started without a "
            "projector. Restart it with --mmproj pointing at the model's\n"
            "mmproj file, then run this again."
        )
    except Exception as exc:                                # noqa: BLE001
        raise SystemExit(f"Could not reach {base_url}: {type(exc).__name__}: {exc}")

    choices = body.get("choices") or [{}]
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def looks_blind(reply: str) -> bool:
    """The model answering as though no image arrived."""
    lowered = reply.lower()
    return any(phrase in lowered for phrase in (
        "cannot see", "can't see", "no image", "unable to view",
        "i do not have access to", "as a text-based",
    ))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--page", type=int, help="1-based page number")
    ap.add_argument("--find", help="use the first page containing this text")
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--dpi", type=int, default=200,
                    help="render resolution; higher is clearer and much larger")
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", type=Path, default=ROOT / "logs" / "vision_sample.txt")
    args = ap.parse_args()

    if not args.pdf.exists():
        print(f"No such file: {args.pdf}")
        return 2
    if not args.page and not args.find:
        print("Give either --page N or --find TEXT")
        return 2

    page_number = args.page or find_page(args.pdf, args.find)
    print(f"{args.pdf.name}, page {page_number}, rendered at {args.dpi} dpi")

    # The projector the server would need, if it sits beside the model.
    try:
        import review_pipeline as rp
        model_dir = Path(rp.MODEL_NAME).parent
        projectors = sorted(model_dir.glob("*mmproj*.gguf"))
        if projectors:
            print(f"projector on disk: {projectors[0]}")
        elif model_dir.exists():
            print("no mmproj file found beside the model; the server cannot "
                  "have vision enabled")
    except Exception:                                       # noqa: BLE001
        pass

    extracted = page_text(args.pdf, page_number)
    png = render_page(args.pdf, page_number, args.dpi)
    print(f"image: {len(png) / 1024:.0f} KB; asking the model to transcribe "
          f"it (up to {args.max_tokens} tokens)...", flush=True)

    reply = ask(args.url, png, args.max_tokens, args.timeout)
    if not reply:
        print("\nThe server returned nothing at all.")
        return 1
    if looks_blind(reply):
        print("\nThe model answered as though no image arrived:\n  "
              + reply[:200])
        print("\nStart llama-server with --mmproj and try again.")
        return 1

    text_numbers = NUMBER_RE.findall(extracted)
    seen_numbers = NUMBER_RE.findall(reply)
    only_seen = [n for n in dict.fromkeys(seen_numbers) if n not in set(text_numbers)]
    only_text = [n for n in dict.fromkeys(text_numbers) if n not in set(seen_numbers)]

    print("\n--- result ---")
    print(f"text layer   : {len(extracted):,} characters, "
          f"{len(text_numbers)} numbers")
    print(f"transcription: {len(reply):,} characters, {len(seen_numbers)} numbers")
    print(f"numbers only the image gave : {len(only_seen)}  "
          f"{only_seen[:12]}{' ...' if len(only_seen) > 12 else ''}")
    print(f"numbers only the text gave  : {len(only_text)}  "
          f"{only_text[:12]}{' ...' if len(only_text) > 12 else ''}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        f"{args.pdf.name} page {page_number}, {args.dpi} dpi\n"
        f"{'=' * 70}\nTEXT LAYER (what the pipeline reads today)\n{'=' * 70}\n"
        f"{extracted}\n\n"
        f"{'=' * 70}\nVISION TRANSCRIPTION\n{'=' * 70}\n{reply}\n",
        encoding="utf-8")
    print(f"\nBoth written to {args.out}")
    print("Open the PDF at that page and read all three. Numbers the image "
          "gave and the text did not are the prize; numbers that are on "
          "neither the page nor in the text layer are the reason not to "
          "trust this without checking.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
