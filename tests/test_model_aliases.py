#!/usr/bin/env python3
"""
The model aliases are listed in three places, and they diverged.

MODEL_ALIASES in app/review_pipeline.py is the canonical table. MODEL_CHOICES
in app/server.py builds the web UI switcher and folds the canonical table in.
resolve_model() in scripts/model_aliases.sh keeps its own copy, sourced by both
launchers, because aliases are resolved while parsing arguments, before the
virtual environment is active, so there is no Python available to ask.

That third copy is the problem. "flash" was added to the canonical table and to
the UI switcher but not to the launcher, so the dropdown offered a model the
launcher rejected. The failure is worse than a plain error: server.py exits
immediately after spawning the launcher, so a restart onto an alias the
launcher does not know leaves nothing running at all. Separately,
scripts/qwen_service.sh had no table at all and took --model verbatim, so an
alias there became a model id that does not end in .gguf and silently selected
the MLX backend.

This test fails if the tables disagree, in either direction.

    .venv/bin/python tests/test_model_aliases.py
"""
import re
import sys
import types
from pathlib import Path


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import review_pipeline as rp                                   # noqa: E402

LAUNCHER = ROOT / "scripts" / "model_aliases.sh"

# Shell variable in scripts/model_aliases.sh -> constant in review_pipeline. Kept
# explicit so that a model added to the launcher under a new variable name
# fails here rather than passing unnoticed.
SHELL_VAR_TO_CONSTANT = {
    "QWEN38_27B_GGUF": "QWEN38_27B_GGUF",
    "QWEN38_FLASH_NEXT_GGUF": "QWEN38_FLASH_NEXT_GGUF",
    "QWEN35_4BIT": "QWEN36_35B_MLX",
    "QWEN27_6BIT": "QWEN36_27B_MLX",
    "QWEN27_4BIT": "QWEN36_27B_4BIT_MLX",
    "QWEN27_8BIT": "QWEN36_27B_8BIT_MLX",
    "GEMMA4_26B_A4B_IT_4BIT": "GEMMA4_26B_MLX",
    "GEMMA4_31B_IT_4BIT": "GEMMA4_31B_MLX",
}

CASE_ARM_RE = re.compile(
    r"^\s{4}([a-z0-9|.\-]+)\)\s*\n\s*echo \"\$([A-Z0-9_]+)\"", re.M)


def launcher_alias_map() -> dict:
    """alias -> shell variable name, read from resolve_model()'s case arms."""
    source = LAUNCHER.read_text(encoding="utf-8")
    start = source.index("resolve_model() {")
    end = source.index("\n}", start)
    body = source[start:end]
    found = {}
    for patterns, variable in CASE_ARM_RE.findall(body):
        for alias in patterns.split("|"):
            found[alias] = variable
    return found


def ui_aliases() -> set:
    """Every string the web UI switcher can post as a model choice."""
    source = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    start = source.index("MODEL_CHOICES = [")
    end = source.index("\n]", start)
    block = source[start:end]
    names = set(re.findall(r'"id":\s*"([^"]+)"', block))
    for group in re.findall(r'"aliases":\s*\[([^\]]*)\]', block):
        names.update(re.findall(r'"([^"]+)"', group))
    return names


def main() -> int:
    failures = []
    launcher = launcher_alias_map()
    canonical = rp.MODEL_ALIASES

    unknown_vars = sorted(set(launcher.values()) - set(SHELL_VAR_TO_CONSTANT))
    if unknown_vars:
        failures.append(
            "scripts/model_aliases.sh resolves aliases to shell variables this test "
            f"does not know: {', '.join(unknown_vars)}. Add them to "
            "SHELL_VAR_TO_CONSTANT so the mapping stays checked.")

    missing = sorted(set(canonical) - set(launcher))
    if missing:
        failures.append(
            "These aliases are in MODEL_ALIASES but not in resolve_model() in "
            f"scripts/model_aliases.sh, so the launchers reject them: "
            f"{', '.join(missing)}")

    extra = sorted(set(launcher) - set(canonical))
    if extra:
        failures.append(
            "These aliases are in resolve_model() but not in MODEL_ALIASES, so "
            f"they work in the launcher only: {', '.join(extra)}")

    for alias, variable in sorted(launcher.items()):
        constant = SHELL_VAR_TO_CONSTANT.get(variable)
        if constant is None or alias not in canonical:
            continue
        expected = getattr(rp, constant, None)
        if expected is None:
            failures.append(
                f"review_pipeline has no constant named {constant}, mapped from "
                f"the shell variable {variable}")
        elif canonical[alias] != expected:
            failures.append(
                f"alias {alias!r} points at a different model in each table: "
                f"launcher ${variable}, canonical {constant}")

    for launcher_path in ("start_server.sh", "scripts/qwen_service.sh"):
        text = (ROOT / launcher_path).read_text(encoding="utf-8")
        # A mention in a comment is not a source. Look for the command.
        sourced = re.search(r"^\s*(?:source|\.)\s+\"?[^\"\n]*model_aliases\.sh",
                            text, re.M)
        if not sourced:
            failures.append(
                f"{launcher_path} does not source scripts/model_aliases.sh, so it "
                "has its own idea of what an alias means, or none at all. "
                "qwen_service.sh took --model verbatim for a while and an "
                "alias silently selected the MLX backend.")

    for alias in sorted(ui_aliases()):
        if alias not in launcher:
            failures.append(
                f"the web UI can post {alias!r}, which resolve_model() in "
                "scripts/model_aliases.sh does not know. A restart onto it "
                "would leave nothing running, because server.py exits before "
                "the launcher reports the error.")

    if failures:
        print("FAIL: the model alias tables disagree\n")
        for line in failures:
            print(f"  - {line}")
        return 1

    print(f"PASS: {len(canonical)} canonical aliases, "
          f"{len(launcher)} in the launcher, "
          f"{len(ui_aliases())} postable from the web UI, all in agreement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
