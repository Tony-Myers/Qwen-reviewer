#!/usr/bin/env python3
"""
llm_backend.py — pluggable LLM backend for the manuscript review pipeline.

Purpose
-------
``review_pipeline.py`` and ``server.py`` were written against the ``mlx_lm``
API::

    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(MODEL_NAME)
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True,
                                           enable_thinking=False)
    out = generate(model, tokenizer, prompt=prompt,
                   max_tokens=N, sampler=sampler, verbose=False)

MLX cannot load a GGUF file, so this module re-exports ``load``, ``generate``
and ``make_sampler`` with the *same signatures*, dispatching to one of three
backends. Every existing call site in the pipeline keeps working unchanged.

Backends
--------
``llama-server``  (default for GGUF)
    Talks OpenAI-compatible HTTP to a running llama.cpp ``llama-server``.
    The server owns the model, so it stays resident between pipeline runs and
    the chat template baked into the GGUF is applied by llama.cpp itself
    rather than being re-implemented here.

``llama-cpp``
    In-process ``llama_cpp.Llama``. Requires ``pip install llama-cpp-python``.
    Kept as a fallback; note that llama-cpp-python wheels usually lag
    llama.cpp upstream, so a very new architecture may not load.

``mlx``
    The original ``mlx_lm`` path, unchanged. Selected automatically for
    ``mlx-community/...`` style model ids so the existing MLX models remain
    usable.

Selection
---------
1. ``QWEN_LLM_BACKEND`` environment variable, or an explicit
   :func:`set_backend` call, wins.
2. Otherwise the backend is inferred from the model id: anything ending in
   ``.gguf``, or any local path to a ``.gguf`` file, uses ``llama-server``;
   everything else uses ``mlx``.

Relevant environment variables
------------------------------
``QWEN_LLM_BACKEND``        llama-server | llama-cpp | mlx
``LLAMA_SERVER_URL``        default http://127.0.0.1:8081
``LLAMA_SERVER_BIN``        default "llama-server" (found on PATH)
``LLAMA_SERVER_AUTOSTART``  "1" to spawn llama-server if it is not running
``LLAMA_SERVER_CTX``        context size for an auto-started server (32768)
``LLAMA_SERVER_NGL``        GPU layers for an auto-started server (99)
``LLAMA_REQUEST_TIMEOUT``   per-request timeout in seconds (1800)
``LLAMA_READY_TIMEOUT``     how long to wait for a loading model (900)
``LLAMA_ENABLE_THINKING``   "1" to let the model emit reasoning (default off)
``LLAMA_REASONING_EFFORT``  low | medium | xhigh, only when thinking is on
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "load",
    "generate",
    "make_sampler",
    "set_backend",
    "current_backend",
    "resolve_backend",
    "strip_reasoning",
    "is_gguf_model",
    "BackendError",
    "Sampler",
    "ChatPrompt",
]


BACKEND_LLAMA_SERVER = "llama-server"
BACKEND_LLAMA_CPP = "llama-cpp"
BACKEND_MLX = "mlx"

VALID_BACKENDS = (BACKEND_LLAMA_SERVER, BACKEND_LLAMA_CPP, BACKEND_MLX)

DEFAULT_LLAMA_SERVER_URL = "http://127.0.0.1:8081"

# Backend forced by set_backend(); None means "infer from the model id".
_FORCED_BACKEND: Optional[str] = None

# Backend actually used by the most recent load(), for reporting.
_ACTIVE_BACKEND: Optional[str] = None


class BackendError(RuntimeError):
    """Raised when a backend cannot be reached or cannot serve a request."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def is_gguf_model(model_id: str) -> bool:
    """True if the model id names a GGUF file rather than an MLX repo."""
    if not model_id:
        return False
    return model_id.strip().lower().endswith(".gguf")


def resolve_backend(model_id: str) -> str:
    """Decide which backend should serve ``model_id``."""
    env_backend = os.environ.get("QWEN_LLM_BACKEND", "").strip().lower()
    if _FORCED_BACKEND:
        return _FORCED_BACKEND
    if env_backend:
        if env_backend not in VALID_BACKENDS:
            raise BackendError(
                f"Unknown backend {env_backend!r}. "
                f"Valid values: {', '.join(VALID_BACKENDS)}"
            )
        return env_backend
    return BACKEND_LLAMA_SERVER if is_gguf_model(model_id) else BACKEND_MLX


def set_backend(name: Optional[str]) -> None:
    """Force a backend for subsequent load() calls. None restores inference."""
    global _FORCED_BACKEND
    if name is None or not str(name).strip():
        _FORCED_BACKEND = None
        return
    name = str(name).strip().lower()
    if name not in VALID_BACKENDS:
        raise BackendError(
            f"Unknown backend {name!r}. Valid values: {', '.join(VALID_BACKENDS)}"
        )
    _FORCED_BACKEND = name


def current_backend() -> Optional[str]:
    """The backend used by the most recent load(), or None before any load."""
    return _ACTIVE_BACKEND


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_DANGLING_THINK_OPEN_RE = re.compile(r"^\s*<think>.*?(?=\n\n|\Z)", re.DOTALL | re.IGNORECASE)
_STRAY_THINK_TAG_RE = re.compile(r"</?think>", re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """
    Remove Qwen-style reasoning spans from generated text.

    Thinking is disabled by default (the chat template then emits an empty
    ``<think></think>`` pair), but this is applied unconditionally so that a
    server or template that leaks reasoning cannot contaminate a review.
    """
    if not text:
        return text
    text = _THINK_BLOCK_RE.sub("", text)
    if "<think>" in text.lower():
        # An unterminated reasoning span: drop it up to the first blank line.
        text = _DANGLING_THINK_OPEN_RE.sub("", text)
    text = _STRAY_THINK_TAG_RE.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------

@dataclass
class Sampler:
    """
    Backend-neutral sampling settings.

    ``make_sampler`` returns one of these regardless of backend; ``generate``
    converts it to a real ``mlx_lm`` sampler when the MLX backend is in use.
    """
    temperature: float = 0.2
    top_p: float = 0.8
    top_k: int = 20
    min_p: float = 0.0
    repetition_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    extra: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.extra is None:
            self.extra = {}


def make_sampler(temp: float = 0.2, top_p: float = 0.8, top_k: int = 20,
                 min_p: float = 0.0, repetition_penalty: Optional[float] = None,
                 presence_penalty: Optional[float] = None,
                 **kwargs: Any) -> Sampler:
    """
    Signature-compatible replacement for ``mlx_lm.sample_utils.make_sampler``.

    Note that mlx_lm's first positional parameter is the temperature, which is
    how every existing call site in the pipeline passes it.
    """
    return Sampler(
        temperature=float(temp),
        top_p=float(top_p),
        top_k=int(top_k),
        min_p=float(min_p),
        repetition_penalty=(None if repetition_penalty is None
                            else float(repetition_penalty)),
        presence_penalty=(None if presence_penalty is None
                          else float(presence_penalty)),
        extra=dict(kwargs),
    )


def _to_mlx_sampler(sampler: Optional[Sampler]):
    from mlx_lm.sample_utils import make_sampler as _mlx_make_sampler  # noqa: WPS433

    if sampler is None:
        return _mlx_make_sampler(0.2, top_p=0.8, top_k=20)
    if not isinstance(sampler, Sampler):
        # Already a native mlx sampler (callable) — pass it straight through.
        return sampler
    return _mlx_make_sampler(
        sampler.temperature,
        top_p=sampler.top_p,
        top_k=sampler.top_k,
    )


# ---------------------------------------------------------------------------
# Chat prompt carrier
# ---------------------------------------------------------------------------

class ChatPrompt(str):
    """
    A prompt that still knows the messages it came from.

    The pipeline builds prompts by calling ``tokenizer.apply_chat_template``
    and then passes the resulting string to ``generate``. For the GGUF
    backends the messages themselves are wanted, so that llama.cpp can apply
    the chat template embedded in the GGUF instead of this module guessing at
    it. Subclassing ``str`` keeps every existing type expectation satisfied
    (``len``, slicing, logging) while carrying the structured form alongside.
    """

    messages: List[Dict[str, Any]]
    enable_thinking: bool

    def __new__(cls, text: str, messages: List[Dict[str, Any]],
                enable_thinking: bool = False) -> "ChatPrompt":
        obj = super().__new__(cls, text)
        obj.messages = list(messages)
        obj.enable_thinking = bool(enable_thinking)
        return obj


# Per-run override of the thinking default, so a single review can be run one
# way while the process default stays the other. Generation is serialised under
# the app server's model lock, so a process-wide switch held for the duration of
# one review is safe; the context manager restores it even on failure, which a
# bare setter would not.
_THINKING_OVERRIDE: Optional[bool] = None


def _thinking_default() -> bool:
    if _THINKING_OVERRIDE is not None:
        return _THINKING_OVERRIDE
    return _env_flag("LLAMA_ENABLE_THINKING", False)


def thinking_enabled() -> bool:
    """Whether generations will currently emit reasoning."""
    return _thinking_default()


@contextlib.contextmanager
def thinking(enabled: Optional[bool]):
    """Run a block with thinking forced on or off. None leaves it alone."""
    global _THINKING_OVERRIDE
    previous = _THINKING_OVERRIDE
    if enabled is not None:
        _THINKING_OVERRIDE = bool(enabled)
    try:
        yield
    finally:
        _THINKING_OVERRIDE = previous


def _plain_text_preview(messages: List[Dict[str, Any]]) -> str:
    """A readable stand-in for the templated prompt string."""
    parts = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content)
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


class GGUFTokenizer:
    """
    Minimal tokenizer stand-in for the GGUF backends.

    It exposes the two attributes the pipeline actually uses — a truthy
    ``chat_template`` and an ``apply_chat_template`` method — and returns a
    :class:`ChatPrompt` so the real templating can be deferred to llama.cpp.
    """

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        # Truthy so apply_chat_template_compat() takes the templating branch.
        self.chat_template = "gguf-embedded"
        self.eos_token = "<|im_end|>"

    def apply_chat_template(self, messages, tokenize=False,
                            add_generation_prompt=True,
                            enable_thinking=None, **kwargs) -> ChatPrompt:
        if tokenize:
            raise BackendError(
                "GGUFTokenizer.apply_chat_template does not support tokenize=True; "
                "the GGUF backends template server-side."
            )
        if enable_thinking is None:
            enable_thinking = _thinking_default()
        normalised: List[Dict[str, Any]] = []
        for message in messages:
            normalised.append({
                "role": message.get("role", "user"),
                "content": message.get("content", ""),
            })
        return ChatPrompt(
            _plain_text_preview(normalised),
            normalised,
            enable_thinking=bool(enable_thinking),
        )

    # Rough helper so callers that want a size estimate do not crash.
    def encode(self, text: str):
        return list(range(max(1, len(text) // 4)))


def _as_messages(prompt: Any) -> Tuple[List[Dict[str, Any]], bool]:
    """Recover messages and the thinking flag from whatever ``generate`` got."""
    if isinstance(prompt, ChatPrompt):
        return prompt.messages, prompt.enable_thinking
    if isinstance(prompt, list):
        return list(prompt), _thinking_default()
    return [{"role": "user", "content": str(prompt)}], _thinking_default()


# ---------------------------------------------------------------------------
# Backend: llama.cpp llama-server over HTTP
# ---------------------------------------------------------------------------

class LlamaServerModel:
    """Handle for a llama.cpp ``llama-server`` reachable over HTTP."""

    def __init__(self, model_path: str, base_url: Optional[str] = None) -> None:
        self._context_size: Optional[int] = None
        self.model_path = model_path
        self.base_url = (base_url or os.environ.get("LLAMA_SERVER_URL")
                         or DEFAULT_LLAMA_SERVER_URL).rstrip("/")
        self.timeout = _env_int("LLAMA_REQUEST_TIMEOUT", 1800)
        # Set to False once the server has rejected chat_template_kwargs, so
        # older llama-server builds are only probed once.
        self.supports_template_kwargs = True
        self._process: Optional[subprocess.Popen] = None

    # -- plumbing ----------------------------------------------------------

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:2000]
            if "exceed_context_size" in body or "exceeds the available context" in body:
                raise BackendError(
                    "The prompt is larger than the context window llama-server "
                    "was started with.\n"
                    f"Server said: {body.strip()[:220]}\n"
                    "Either restart with a larger context "
                    "(LLAMA_SERVER_CTX=65536 ./scripts/qwen_service.sh restart) "
                    "or review a shorter document. A submission that bundles a "
                    "long supplementary appendix with the article is the usual "
                    "cause."
                ) from exc
            raise BackendError(
                f"llama-server returned HTTP {exc.code} for {path}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise BackendError(
                f"Cannot reach llama-server at {self.base_url} ({exc.reason}).\n"
                f"{start_command_hint(self.model_path, self.base_url)}"
            ) from exc

    def probe(self, timeout: float = 3.0) -> str:
        """
        Report the server as "ready", "loading" or "down".

        While llama.cpp is reading a model its /health answers 503 with
        {"error": {"message": "Loading model", ...}}. That is emphatically not
        the same as nothing listening: a 17 GB model can take minutes, and
        treating it as "down" makes the pipeline give up on a server that is
        seconds away from being usable.
        """
        for path in ("/health", "/props"):
            try:
                with urllib.request.urlopen(f"{self.base_url}{path}", timeout=timeout) as response:
                    if 200 <= getattr(response, "status", 200) < 300:
                        return "ready"
                    return "loading"
            except urllib.error.HTTPError as exc:
                # Something is listening, it just cannot serve us yet.
                return "loading" if exc.code in (500, 502, 503, 504) else "ready"
            except Exception:
                continue
        return "down"

    def is_up(self, timeout: float = 3.0) -> bool:
        return self.probe(timeout) == "ready"

    def context_size(self, timeout: float = 3.0) -> Optional[int]:
        """
        The context window the server was actually started with.

        A 127-page submission -- a 22-page article bound together with 105
        pages of supplementary tables -- built a 45,904-token prompt against a
        32,768-token server and the review died with a raw traceback. The
        pipeline could not budget its prompts because it never knew the limit.
        Ask the server once and remember the answer.
        """
        if self._context_size is not None:
            return self._context_size or None
        found = None
        try:
            with urllib.request.urlopen(f"{self.base_url}/props", timeout=timeout) as response:
                props = json.loads(response.read().decode("utf-8", "replace"))
            for candidate in (props.get("n_ctx"),
                              (props.get("default_generation_settings") or {}).get("n_ctx"),
                              (props.get("default_generation_settings") or {}).get("n_ctx_train")):
                if isinstance(candidate, int) and candidate > 0:
                    found = candidate
                    break
        except Exception:
            found = None
        self._context_size = found or 0
        return found

    def wait_until_up(self, timeout: Optional[float] = None,
                      interval: float = 2.0, announce: bool = False) -> bool:
        """Block until the server reports ready, or the wait runs out."""
        if timeout is None:
            timeout = float(_env_int("LLAMA_READY_TIMEOUT", 900))
        deadline = time.time() + timeout
        announced = False
        while time.time() < deadline:
            state = self.probe()
            if state == "ready":
                return True
            if state == "loading" and announce and not announced:
                print(f"Waiting for llama-server at {self.base_url} to finish "
                      f"loading the model...")
                announced = True
            if self._process is not None and self._process.poll() is not None:
                return False
            time.sleep(interval)
        return False

    def autostart(self) -> None:
        """Spawn llama-server in the background if it is not already running."""
        binary = os.environ.get("LLAMA_SERVER_BIN", "llama-server")
        resolved = shutil.which(binary)
        if resolved is None:
            raise BackendError(
                f"llama-server binary {binary!r} not found on PATH.\n"
                f"{start_command_hint(self.model_path, self.base_url)}"
            )
        host, port = _split_host_port(self.base_url)
        command = [
            resolved,
            "--model", self.model_path,
            "--host", host,
            "--port", str(port),
            "--ctx-size", str(_env_int("LLAMA_SERVER_CTX", 32768)),
            "--n-gpu-layers", str(_env_int("LLAMA_SERVER_NGL", 99)),
            "--jinja",
        ]
        print(f"Starting llama-server: {' '.join(command)}")
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        if not self.wait_until_up(announce=True):
            raise BackendError(
                "llama-server was started but did not become ready in time. "
                "Run the command above in a terminal to see its output."
            )

    # -- generation --------------------------------------------------------

    def complete(self, messages: List[Dict[str, Any]], max_tokens: int,
                 sampler: Optional[Sampler], enable_thinking: bool) -> str:
        sampler = sampler or Sampler()
        payload: Dict[str, Any] = {
            "model": Path(self.model_path).name,
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": sampler.temperature,
            "top_p": sampler.top_p,
            "top_k": sampler.top_k,
            "stream": False,
        }
        if sampler.min_p:
            payload["min_p"] = sampler.min_p
        # Sent only when explicitly set, so an unset value keeps llama-server's
        # own default rather than silently imposing one of ours.
        if sampler.repetition_penalty is not None:
            payload["repeat_penalty"] = sampler.repetition_penalty
        if sampler.presence_penalty is not None:
            payload["presence_penalty"] = sampler.presence_penalty

        if self.supports_template_kwargs:
            template_kwargs: Dict[str, Any] = {"enable_thinking": bool(enable_thinking)}
            if enable_thinking:
                effort = os.environ.get("LLAMA_REASONING_EFFORT", "").strip().lower()
                if effort in {"low", "medium", "xhigh"}:
                    template_kwargs["reasoning_effort"] = effort
            payload["chat_template_kwargs"] = template_kwargs

        try:
            response = self._post_json("/v1/chat/completions", payload)
        except BackendError as exc:
            # Older llama-server builds reject chat_template_kwargs with a 400.
            if self.supports_template_kwargs and "HTTP 400" in str(exc):
                self.supports_template_kwargs = False
                payload.pop("chat_template_kwargs", None)
                response = self._post_json("/v1/chat/completions", payload)
            else:
                raise

        return _extract_chat_text(response)


def available_context(default: int = 32768) -> int:
    """
    The running server's context window, or a stated default.

    Falls back to LLAMA_SERVER_CTX and then to the given default, so a pipeline
    that cannot reach the server still budgets against something sane rather
    than assuming it has unlimited room.
    """
    model = _LAST_LOADED_MODEL
    if isinstance(model, LlamaServerModel):
        found = model.context_size()
        if found:
            return found
    return _env_int("LLAMA_SERVER_CTX", default)


def _extract_chat_text(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise BackendError(f"llama-server returned no choices: {response!r}"[:500])
    message = choices[0].get("message") or {}
    content = message.get("content")
    if content is None:
        content = choices[0].get("text", "")
    return content or ""


def _split_host_port(base_url: str) -> Tuple[str, int]:
    remainder = base_url.split("://", 1)[-1]
    remainder = remainder.split("/", 1)[0]
    if ":" in remainder:
        host, _, port = remainder.rpartition(":")
        try:
            return host or "127.0.0.1", int(port)
        except ValueError:
            return remainder, 8081
    return remainder or "127.0.0.1", 8081


def start_command_hint(model_path: str, base_url: str) -> str:
    host, port = _split_host_port(base_url)
    return (
        "Start it first, for example:\n"
        f"  llama-server --model {model_path} \\\n"
        f"      --host {host} --port {port} \\\n"
        "      --ctx-size 32768 --n-gpu-layers 99 --jinja\n"
        "The --jinja flag is required: it makes llama.cpp use the chat template "
        "embedded in the GGUF, which is what disables the reasoning block."
    )


# ---------------------------------------------------------------------------
# Backend: in-process llama-cpp-python
# ---------------------------------------------------------------------------

class LlamaCppModel:
    """Handle for an in-process ``llama_cpp.Llama`` instance."""

    def __init__(self, model_path: str) -> None:
        try:
            from llama_cpp import Llama  # noqa: WPS433
        except ImportError as exc:
            raise BackendError(
                "The llama-cpp backend needs llama-cpp-python:\n"
                "  pip install llama-cpp-python\n"
                "If the model fails to load afterwards, its architecture is "
                "probably newer than the bundled llama.cpp; use the "
                "llama-server backend instead."
            ) from exc

        self.model_path = model_path
        self.llama = Llama(
            model_path=model_path,
            n_ctx=_env_int("LLAMA_SERVER_CTX", 32768),
            n_gpu_layers=_env_int("LLAMA_SERVER_NGL", -1),
            verbose=False,
        )

    def complete(self, messages: List[Dict[str, Any]], max_tokens: int,
                 sampler: Optional[Sampler], enable_thinking: bool) -> str:
        sampler = sampler or Sampler()
        result = self.llama.create_chat_completion(
            messages=messages,
            max_tokens=int(max_tokens),
            temperature=sampler.temperature,
            top_p=sampler.top_p,
            top_k=sampler.top_k,
        )
        return _extract_chat_text(result)


# ---------------------------------------------------------------------------
# Public API: load / generate
# ---------------------------------------------------------------------------

def _resolve_model_path(model_id: str) -> str:
    path = Path(model_id).expanduser()
    if path.exists():
        return str(path)
    raise BackendError(
        f"GGUF model file not found: {model_id}\n"
        "Check the path, or point MODEL_NAME at an MLX repo id to use the "
        "MLX backend instead."
    )


# The handle most recently returned by load(), so available_context() can ask
# the running server how much room it has without every caller threading a
# model object through to reach it.
_LAST_LOADED_MODEL: Any = None


def load(model_id: str, *args: Any, **kwargs: Any):
    """
    Signature-compatible replacement for ``mlx_lm.load``.

    Returns ``(model, tokenizer)``. For the GGUF backends the "model" is a
    backend handle and the "tokenizer" is a :class:`GGUFTokenizer`.
    """
    global _ACTIVE_BACKEND, _LAST_LOADED_MODEL

    backend = resolve_backend(model_id)

    if backend == BACKEND_MLX:
        from mlx_lm import load as _mlx_load  # noqa: WPS433
        _ACTIVE_BACKEND = BACKEND_MLX
        return _mlx_load(model_id, *args, **kwargs)

    model_path = _resolve_model_path(model_id)

    if backend == BACKEND_LLAMA_CPP:
        _ACTIVE_BACKEND = BACKEND_LLAMA_CPP
        return LlamaCppModel(model_path), GGUFTokenizer(model_path)

    handle = LlamaServerModel(model_path)
    _LAST_LOADED_MODEL = handle
    state = handle.probe()

    if state == "loading":
        # The server is up but still reading the model. Wait rather than
        # failing: this is the normal race when the launcher starts
        # llama-server and the app server moments apart.
        print(f"llama-server at {handle.base_url} is loading the model; waiting...")
        if not handle.wait_until_up(announce=False):
            raise BackendError(
                f"llama-server at {handle.base_url} is running but did not "
                f"finish loading in time.\n"
                "Raise the wait with LLAMA_READY_TIMEOUT (seconds), or check "
                "the llama-server log."
            )
    elif state == "down":
        if _env_flag("LLAMA_SERVER_AUTOSTART", False):
            handle.autostart()
        else:
            raise BackendError(
                f"No llama-server is listening at {handle.base_url}.\n"
                f"{start_command_hint(model_path, handle.base_url)}\n"
                "Alternatively set LLAMA_SERVER_AUTOSTART=1 to have this "
                "pipeline start it automatically."
            )
    _ACTIVE_BACKEND = BACKEND_LLAMA_SERVER
    return handle, GGUFTokenizer(model_path)


def generate(model: Any, tokenizer: Any, prompt: Any = None,
             max_tokens: int = 1200, sampler: Any = None,
             verbose: bool = False, **kwargs: Any) -> str:
    """
    Signature-compatible replacement for ``mlx_lm.generate``.

    Returns the generated text with any reasoning span removed.
    """
    if prompt is None:
        prompt = kwargs.pop("prompt", "")

    if isinstance(model, (LlamaServerModel, LlamaCppModel)):
        messages, enable_thinking = _as_messages(prompt)
        if isinstance(sampler, Sampler) or sampler is None:
            resolved_sampler = sampler
        else:
            resolved_sampler = None  # an mlx sampler is meaningless here
        text = model.complete(
            messages=messages,
            max_tokens=max_tokens,
            sampler=resolved_sampler,
            enable_thinking=enable_thinking,
        )
        return strip_reasoning(text)

    from mlx_lm import generate as _mlx_generate  # noqa: WPS433
    text = _mlx_generate(
        model, tokenizer,
        prompt=str(prompt),
        max_tokens=max_tokens,
        sampler=_to_mlx_sampler(sampler),
        verbose=verbose,
        **kwargs,
    )
    return strip_reasoning(text)
