#!/usr/bin/env python3
"""
Ask the running llama-server whether thinking mode actually does anything.

Why this exists
---------------
A review can request thinking mode, the server can accept the request, and the
model can emit no reasoning at all. That happened: review8 was headed
``Reasoning: thinking``, the app-server log shows no HTTP 400, and the
generated token counts were indistinguishable from instruct runs. The header
recorded the request, not the outcome, so the run could not be interpreted.

The pipeline now counts reasoning per review, which settles it going forward.
This settles it in twenty seconds instead of an hour-long review, and says
*why* if the answer is no.

    .venv/bin/python tests/probe_thinking.py
    .venv/bin/python tests/probe_thinking.py --url http://127.0.0.1:8081

Three things are checked:

1. Does the chat template baked into the GGUF mention ``enable_thinking``?
   If it does not, ``chat_template_kwargs`` is accepted and ignored, which is
   the quietest of the failure modes.
2. Does a request with ``enable_thinking: false`` come back without reasoning?
   (The control. If this one produces reasoning, the flag is not being read.)
3. Does a request with ``enable_thinking: true`` come back with any?
   Reasoning arrives either in ``message.reasoning_content`` or as a
   ``<think>`` span inside the content, depending on ``--reasoning-format``;
   both are counted.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

# Deliberately a question with a little work in it: a model given nothing to
# think about may legitimately emit an empty reasoning span.
QUESTION = ("A study reports an odds ratio of 0.62 with a 95% interval of "
            "0.31 to 1.24. State in one sentence whether that interval "
            "excludes the null, and why.")


def post(url: str, payload: dict, timeout: int = 180):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get(url: str, timeout: int = 15):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def probe(base: str, enable_thinking: bool, max_tokens: int) -> dict:
    payload = {
        "messages": [{"role": "user", "content": QUESTION}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "top_p": 0.8,
        "top_k": 20,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }
    try:
        response = post(base + "/v1/chat/completions", payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        return {"error": f"HTTP {exc.code}: {body}"}
    except Exception as exc:                                # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}

    message = (response.get("choices") or [{}])[0].get("message") or {}
    content = message.get("content") or ""
    separate = (message.get("reasoning_content") or "").strip()
    inline = "".join(m.group(1) for m in THINK_RE.finditer(content)).strip()
    answer = THINK_RE.sub("", content).strip()
    return {
        "separate": len(separate),
        "inline": len(inline),
        "answer": " ".join(answer.split())[:120],
        "generated": (response.get("usage") or {}).get("completion_tokens"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--max-tokens", type=int, default=600)
    args = ap.parse_args()
    base = args.url.rstrip("/")

    try:
        props = get(base + "/props")
    except Exception as exc:                                # noqa: BLE001
        print(f"Cannot reach llama-server at {base}: {type(exc).__name__}: {exc}")
        print("Start it with ./scripts/qwen_service.sh start, then run this again.")
        return 2

    template = props.get("chat_template") or ""
    wired = "enable_thinking" in template
    print(f"[template] {'mentions' if wired else 'does NOT mention'} "
          f"enable_thinking ({len(template)} characters)")
    if not wired:
        print("           chat_template_kwargs will be accepted and ignored: "
              "the template has no branch to switch.")
    for key in ("reasoning_format", "reasoning_budget"):
        if key in props:
            print(f"[server]   {key} = {props[key]!r}")

    results = {}
    for label, flag in (("instruct (control)", False), ("thinking", True)):
        print(f"\n[{label}] asking...", flush=True)
        found = probe(base, flag, args.max_tokens)
        results[flag] = found
        if "error" in found:
            print(f"  {found['error']}")
            continue
        print(f"  reasoning_content: {found['separate']} characters")
        print(f"  <think> in content: {found['inline']} characters")
        print(f"  tokens generated: {found['generated']}")
        print(f"  answer: {found['answer']}")

    off, on = results.get(False, {}), results.get(True, {})
    if "error" in on:
        verdict = "Thinking could not be tested: the request failed (above)."
    else:
        on_chars = on.get("separate", 0) + on.get("inline", 0)
        off_chars = off.get("separate", 0) + off.get("inline", 0)
        if on_chars and not off_chars:
            verdict = (f"Thinking works and the flag is read: {on_chars} "
                       f"characters of reasoning with it on, none with it off.")
        elif on_chars and off_chars:
            verdict = (f"Reasoning appears either way ({on_chars} on, "
                       f"{off_chars} off), so enable_thinking is not switching "
                       f"anything. Reasoning may be on by default for this "
                       f"build; --reasoning-budget 0 turns it off.")
        elif not wired:
            verdict = ("No reasoning either way, and the template has no "
                       "enable_thinking branch. This GGUF cannot be switched "
                       "into thinking mode by that flag; the reasoning-mode "
                       "dropdown has nothing to act on.")
        else:
            verdict = ("No reasoning either way, although the template does "
                       "have an enable_thinking branch. Check --reasoning-budget "
                       "and --reasoning-format on the llama-server command line: "
                       "a budget of 0 disables reasoning whatever is requested.")
    print("\n" + verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
