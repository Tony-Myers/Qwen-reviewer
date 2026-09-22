"""Regression checks for the local application's browser/network boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
CHAT = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")
START_SERVER = (ROOT / "start_server.sh").read_text(encoding="utf-8")
START_LLAMA = (ROOT / "start_llama_server.sh").read_text(encoding="utf-8")
SERVICE = (ROOT / "scripts" / "qwen_service.sh").read_text(encoding="utf-8")

fails = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        fails.append(label)


print("\n[same-origin browser API]")
check(
    "browser API uses the page origin",
    "const BASE = window.location.origin;" in CHAT,
)
check(
    "server does not install CORS middleware",
    "CORSMiddleware" not in SERVER,
)
check(
    "server does not grant wildcard browser origins",
    'allow_origins=["*"]' not in SERVER,
)


print("\n[loopback application defaults]")
check(
    "server.py defaults to loopback",
    'parser.add_argument("--host", default="127.0.0.1"' in SERVER,
)
check(
    "start_server.sh defaults the app to loopback",
    'DEFAULT_HOST="127.0.0.1"' in START_SERVER,
)
check(
    "qwen_service.sh defaults the app to loopback",
    'APP_HOST="${QWEN_APP_HOST:-127.0.0.1}"' in SERVICE,
)


print("\n[loopback model-server defaults]")
check(
    "standalone llama launcher defaults to loopback",
    'HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"' in START_LLAMA,
)
check(
    "unified launcher defaults llama-server to loopback",
    'LLAMA_HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"' in START_SERVER,
)
check(
    "service launcher defaults llama-server to loopback",
    'LLAMA_HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"' in SERVICE,
)


if fails:
    print(f"\nFAILED: {len(fails)} check(s)")
    raise SystemExit(1)

print("\nPASS: browser and server defaults preserve the local-only boundary")
