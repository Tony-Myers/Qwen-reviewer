from pathlib import Path

html = Path("app/chat.html").read_text()

fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[academic answer presentation honours release decision]")

check(
    "data.release?.safe_to_present === false" in html,
    "Academic Chat explicitly checks a blocked release before presentation",
)

check(
    "data.answer_draft" in html,
    "auditable draft remains available to the browser response path",
)

send_start = html.find("async function sendAcademicMessage()")
send_end = html.find("// --- File upload ---", send_start)
send_function = html[send_start:send_end]

check(
    send_start >= 0 and send_end > send_start,
    "Academic Chat send function is located",
)

check(
    'data.release?.status === "checking_incomplete"' in send_function,
    "incomplete checking has its own presentation branch",
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

incomplete_branch = send_function[
    send_function.find('data.release?.status === "checking_incomplete"'):
    send_function.find("data.release?.safe_to_present === false")
]

check(
    "data.check_further ? '' :" in incomplete_branch
    and "Checking incomplete" in incomplete_branch
    and "academicIncompleteExplanation()" in incomplete_branch,
    "the older notice appears beside the answer only without an evidence "
    "check, so the reader is told once",
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

checking_branch = send_function.find(
    'data.release?.status === "checking_incomplete"'
)
blocked_branch = send_function.find(
    "data.release?.safe_to_present === false",
    checking_branch + 1,
)
normal_branch = send_function.find(
    "fmtMd(data.answer_draft",
    blocked_branch + 1,
)

check(
    checking_branch >= 0
    and blocked_branch > checking_branch
    and normal_branch > blocked_branch,
    "incomplete, blocked-conflict, and normal presentation remain distinct",
)

check(
    "fmtMd(data.answer_draft" in send_function[checking_branch:blocked_branch],
    "draft remains visible when checking is incomplete",
)

check(
    "Answer withheld after checking." in send_function[blocked_branch:normal_branch],
    "established blocked release still withholds the draft",
)

check(
    "contains a conflict identified during verification" in (
        send_function[blocked_branch:normal_branch]
    ),
    "conflict wording remains confined to the established-block branch",
)

check(
    "fmtMd(data.answer_draft" in send_function[normal_branch:],
    "normal releasable answers still render the generated draft",
)


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
