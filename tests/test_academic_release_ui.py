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
    "data.release?.safe_to_present === false" in send_function,
    "presentation gate is enforced inside Academic Chat delivery",
)

check(
    "fmtMd(data.answer_draft" in send_function,
    "normal releasable answers still render the generated draft",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat release-UI checks passed.")
