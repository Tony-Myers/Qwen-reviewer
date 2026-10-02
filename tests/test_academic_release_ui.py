import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

html = Path("app/chat.html").read_text()

fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[academic answer presentation renders the server's decision]")

send_start = html.find("async function sendAcademicMessage()")
send_end = html.find("// --- File upload ---", send_start)
send_function = html[send_start:send_end]

check(
    send_start >= 0 and send_end > send_start,
    "Academic Chat send function is located",
)

check(
    "presentation.mode" in send_function
    and "safe_to_present" not in send_function
    and "release?.status" not in send_function,
    "presentation follows presentation.mode alone; the page does not "
    "re-derive it from the release",
)

check(
    "data.answer_draft" in html,
    "auditable draft remains available to the browser response path",
)

incomplete_start = html.find("function academicIncompleteExplanation")
incomplete_explanation = html[
    incomplete_start:html.find("}", incomplete_start)
]

check(
    "could not be completed" in incomplete_explanation,
    "incomplete-check explanation says that checking did not complete",
)

check(
    "does not establish that the answer is wrong" in incomplete_explanation,
    "incomplete-check explanation does not reinterpret uncertainty as error",
)

evidence_start = html.find("function renderAcademicEvidence")
evidence_renderer = html[
    evidence_start:html.find("return renderAcademicCheckFurther", evidence_start)
]

check(
    "data.check_further && data.release?.status === 'checking_incomplete'"
    in evidence_renderer
    and "academicIncompleteExplanation()" in evidence_renderer
    and evidence_renderer.find("academicIncompleteExplanation()")
    < evidence_renderer.find("renderAcademicAudit(data)"),
    "with an evidence check, the older explanation sits in the technical "
    "checking details",
)

node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run.")
else:
    page_functions = re.findall(r"^function \w+\(.*?\n}\n", html, re.S | re.M)
    constants = re.findall(r"^const ACADEMIC_\w+ =\n?.*?;\n", html, re.S | re.M)

    def shown(payload):
        """The answer area sendAcademicMessage renders for this response."""
        script = """
const element = () => ({innerHTML: '', style: {}, value: '', disabled: false,
                        textContent: '', focus() {}});
const ids = {};
const document = {getElementById: id => (ids[id] = ids[id] || element())};
const academicInput = element(); academicInput.value = 'q';
const academicSendBtn = element();
let academicGenerating = false;
const BASE = '';
const PAYLOAD = %s;
async function fetch() { return {ok: true, status: 200, json: async () => PAYLOAD}; }
class AcademicUserError extends Error {}
%s
%s
%s
sendAcademicMessage().then(() => process.stdout.write(ids['academicAnswer'].innerHTML));
""" % (json.dumps(payload), "\n".join(constants), "\n".join(page_functions),
               send_function)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
        run = subprocess.run([node, f.name], capture_output=True, text=True,
                             timeout=30)
        Path(f.name).unlink()
        if run.returncode != 0:
            print(run.stderr)
        return run.stdout

    ANSWER = "The relative efficiency is approximately 1 / (1 + lambda/M)."

    def payload(mode, reason, *, status=None, safe=None, check_further=None):
        body = {
            "answer_draft": ANSWER,
            "release": {"status": status or reason, "safe_to_present": safe,
                        "reasons": []},
            "presentation": {"mode": mode, "reason": reason},
        }
        if check_further is not None:
            body["check_further"] = check_further
        return body

    page = shown(payload("release", "release_allowed", safe=True))
    check(ANSWER in page and "withheld" not in page,
          "release: the answer is displayed")

    page = shown(payload("qualified", "checking_incomplete", safe=False))
    check(ANSWER in page and "Checking incomplete." in page
          and "does not establish that the answer is wrong" in page,
          "qualified without an evidence check: the answer, with the older "
          "incomplete-checking note beside it")

    page = shown(payload("qualified", "checking_incomplete", safe=False,
                         check_further={"state": "incomplete"}))
    check(ANSWER in page and "Checking incomplete." not in page,
          "qualified with an evidence check: the answer, and the evidence "
          "check tells the reader once")

    page = shown(payload("withheld", "checking_incomplete", safe=False))
    check(ANSWER not in page
          and "A problem was found in the original answer" in page
          and "checking of it could not be completed" in page
          and "Trying again may help." in page
          and "checking_incomplete" not in page,
          "withheld revision with incomplete checking: not displayed, and "
          "explained without internal names")

    page = shown(payload("withheld", "blocked_technical_conflict", safe=False))
    check(ANSWER not in page and "Answer withheld after checking." in page
          and "contains a conflict identified during verification" in page,
          "withheld for an established conflict: the existing wording")

    page = shown(payload("withheld", "blocked_source_contradiction", safe=False))
    check(ANSWER not in page and "Answer withheld after checking." in page,
          "withheld for a source contradiction: the existing wording")

    page = shown(payload("withheld", "blocked_unresolved_source_contradiction",
                         safe=False))
    check(ANSWER not in page
          and "could not be confirmed against that source" in page,
          "withheld for an unresolved source contradiction: its own wording")

    page = shown(payload("release", "release_allowed",
                         status="checking_incomplete", safe=False))
    check(ANSWER in page,
          "the page follows the decision even when the release disagrees")

    page = shown(payload("withheld", "checking_incomplete",
                         status="checking_incomplete", safe=False))
    check(ANSWER not in page,
          "no status exception can display a withheld revision whose "
          "checking was incomplete")

    no_decision = payload("release", "release_allowed", safe=True)
    del no_decision["presentation"]
    check(ANSWER not in shown(no_decision),
          "a response without a presentation decision is not displayed")


print("\n[Academic Chat failures separate user messages from diagnostics]")

check(
    "data.error || ACADEMIC_INTERNAL_ERROR" in send_function,
    "a structured user-safe server error takes precedence over the generic message",
)

check(
    "'Academic Chat could not complete this request because of an internal "
    "error. ' +\n  'Please try again.'" in html,
    "the generic failure message is plain language",
)

check(
    "Server error" not in send_function
    and "Academic Chat error:" not in send_function,
    "the reader never sees a bare 'Server error' status or an error label",
)

check(
    "console.error('Academic Chat request failed: HTTP ' + r.status" in send_function,
    "the HTTP status is kept for the console",
)

check(
    "e instanceof AcademicUserError" in send_function
    and "console.error('Academic Chat failure:', e)" in send_function,
    "an unexpected browser-side failure is logged and shown as the generic message",
)

check(
    "data.detail ? ' ' + data.detail : ''" not in send_function,
    "internal diagnostic detail is not appended to the user-facing error",
)

check(
    "console.error" in send_function
    and "data.detail" in send_function,
    "internal diagnostic detail remains available to developers",
)

check(
    "+ esc(message) +" in send_function,
    "the reader's message is escaped before display",
)


print("\n[claim coverage is visible in verification details]")

audit_start = html.find("function renderAcademicAudit")
audit_end = html.find("function renderAcademicEvidence", audit_start)
audit_renderer = html[audit_start:audit_end]

check(
    "data.claim_coverage" in audit_renderer,
    "detailed audit consumes public claim-coverage state",
)

check(
    "Claim coverage:" in audit_renderer,
    "claim coverage is labelled explicitly in the detailed audit",
)

check(
    "academicReasons(claimCoverage.reasons)" in audit_renderer,
    "coverage failure reasons remain visible in the detailed audit",
)

check(
    "coverage_assessment_unavailable: 'Coverage assessment unavailable'"
    in html,
    "unavailable coverage has a human-readable status label",
)

check(
    "coverage_not_attempted: 'Coverage assessment not attempted'"
    in html,
    "unattempted coverage has a human-readable status label",
)

check(
    "missing_claims_found: 'Additional claims found for checking'"
    in html,
    "discovered missing claims are described without implying error",
)

check(
    "no_missing_claims_proposed: 'No additional claims proposed'"
    in html,
    "successful empty discovery avoids claiming exhaustive completeness",
)

check(
    "checking_incomplete: 'Checking incomplete'" in html,
    "release-level incomplete checking has a human-readable status label",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat release-UI checks passed.")
