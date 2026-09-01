#!/usr/bin/env python3
"""
Unit checks for the sampler sweep's scoring, and for the settings it varies.

The sweep itself needs a running model and takes hours; this does not. It
checks that a report is scored correctly and that every configuration the sweep
offers actually reaches the pipeline -- an environment variable the pipeline
does not read would produce a comparison of a setting against itself, which
would look like a result.
"""
import importlib.util
import os
import subprocess
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent


def _stub(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)
sys.path.insert(0, str(ROOT / "app"))

spec = importlib.util.spec_from_file_location("sweep", ROOT / "tests" / "sampler_sweep.py")
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)

F = 0


def ok(label, cond, detail=""):
    global F
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"   {detail}" if not cond and detail else ""))
    if not cond:
        F += 1


REPORT = """
# Directly supported concerns
* Concern: One.
* Confidence: High — every quotation was located in the manuscript.
* Concern: Two.
* Confidence: High — the cited values were located in the extracted tables.
* Concern: Three.
* Confidence: Moderate — the concern is an inference.
* Concern: Four.
* Confidence: Low — the evidence cites this pipeline's own summary rather than the manuscript.

# Citation check
* Cites this pipeline's own summary rather than the manuscript: ...notes
* Cites this pipeline's own summary rather than the manuscript: ...flags
* Quotation not found in the manuscript: "a thing"
* Quotation only partly found: "another" -- this part is not in the manuscript: "bit"
* Number 0.999 does not appear in the manuscript. If it is a value you calculated, say so.
* The Evidence line restates the concern rather than citing the manuscript, so the concern is unsupported: "Four"
"""

print("[scoring a report]")
sc = sweep.score(REPORT)
ok("counts High", sc["high"] == 2, str(sc["high"]))
ok("counts Moderate", sc["mod"] == 1, str(sc["mod"]))
ok("counts Low", sc["low"] == 1, str(sc["low"]))
ok("counts self-citations", sc["self-cite"] == 2, str(sc["self-cite"]))
ok("counts both kinds of bad quotation", sc["bad-quote"] == 2, str(sc["bad-quote"]))
ok("counts bad numbers", sc["bad-num"] == 1, str(sc["bad-num"]))
ok("counts echoed evidence", sc["echo"] == 1, str(sc["echo"]))
ok("notices no banner", sc["banner"] == 0)
ok("notices a banner",
   sweep.score("No concern in this report is supported by evidence")["banner"] == 1)
ok("an empty report scores zero",
   sweep.score("") == {"high": 0, "mod": 0, "low": 0, "self-cite": 0,
                       "bad-quote": 0, "bad-num": 0, "echo": 0,
                       "banner": 0, "chars": 0})

print("\n[the baseline must be the shipped settings]")
ok("'current' overrides nothing", sweep.CONFIGS["current"] == {})
ok("an A/A control exists", "a-a-control" in sweep.CONFIGS)
ok("the control is identical to current",
   sweep.CONFIGS["a-a-control"] == sweep.CONFIGS["current"])
ok("the control is on by default", "a-a-control" in
   __import__("subprocess").run(
       [sys.executable, str(ROOT / "tests" / "sampler_sweep.py"), "--help"],
       capture_output=True, text=True).stdout)

print("\n[every varied setting actually reaches the pipeline]")
VARIED = sorted({k for cfg in sweep.CONFIGS.values() for k in cfg})
pipeline_src = (ROOT / "app" / "review_pipeline.py").read_text()
backend_src = (ROOT / "app" / "llm_backend.py").read_text()
for key in VARIED:
    ok(f"{key} is read somewhere",
       key in pipeline_src or key in backend_src)

print("\n[the settings take effect when set]")
probe = (
    "import sys, types\n"
    "m=types.ModuleType('docx'); m.Document=object; sys.modules['docx']=m\n"
    "n=types.ModuleType('openpyxl'); n.load_workbook=lambda *a,**k: None; sys.modules['openpyxl']=n\n"
    f"sys.path.insert(0, {str(ROOT / 'app')!r})\n"
    "import review_pipeline as rp\n"
    "s = rp.make_default_sampler()\n"
    "print(rp.TEMPERATURE, rp.TOP_P, s.repetition_penalty, s.presence_penalty, rp.SYNTHESIS_MAX_TOKENS)\n"
)
env = dict(os.environ)
base = subprocess.run([sys.executable, "-c", probe], env=env,
                      capture_output=True, text=True).stdout.split()
ok("the default temperature is 0.2", base[0] == "0.2", str(base))
# 1.0 is what llama-server reports as its own default, so stating it changes
# nothing; it is sent so the setting cannot shift under a llama.cpp upgrade.
ok("the repetition penalty is stated, not inherited", base[2] == "1.0", str(base))
ok("no presence penalty is sent", base[3] == "None", str(base))

env.update({"QWEN_TEMPERATURE": "0.7", "QWEN_REPETITION_PENALTY": "1.0",
            "QWEN_PRESENCE_PENALTY": "1.5", "QWEN_SYNTHESIS_MAX_TOKENS": "4000"})
tuned = subprocess.run([sys.executable, "-c", probe], env=env,
                       capture_output=True, text=True).stdout.split()
ok("temperature follows the environment", tuned[0] == "0.7", str(tuned))
ok("repetition penalty is carried to the sampler", tuned[2] == "1.0", str(tuned))
ok("presence penalty is carried to the sampler", tuned[3] == "1.5", str(tuned))
ok("the synthesis limit follows too", tuned[4] == "4000", str(tuned))

print("\n[bad input is refused before any model is loaded]")
r = subprocess.run([sys.executable, str(ROOT / "tests" / "sampler_sweep.py"),
                    "/nonexistent.pdf"], capture_output=True, text=True, timeout=60)
ok("a missing paper is refused", r.returncode == 2 and "No such file" in r.stdout)
r = subprocess.run([sys.executable, str(ROOT / "tests" / "sampler_sweep.py"),
                    str(ROOT / "tests" / "sampler_sweep.py"), "--configs", "nope"],
                   capture_output=True, text=True, timeout=60)
ok("an unknown configuration is refused",
   r.returncode == 2 and "Unknown configuration" in r.stdout)
ok("and the available ones are listed", "vendor" in r.stdout)

print()
if F:
    print(f"{F} FAILURE(S)")
    sys.exit(1)
print("All sampler-sweep checks passed.")
