"""Human-facing evidence appendix helpers.

Evidence cards begin with deterministic identity for substantive final findings.

This module does not perform model inference, source matching, evidence
assessment, or methodological interpretation. It extracts already-written
final concerns and verification questions and assigns stable identifiers in
report order.

Upstream lineage is deliberately left unresolved unless it is established
elsewhere by application-owned state.
"""

from __future__ import annotations

import re
from typing import Any


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_CONCERN_RE = re.compile(r"^\s*[-*]\s+Concern:\s*(.*)$", re.IGNORECASE)
_CHECK_RE = re.compile(r"^\s*[-*]\s+Check:\s*(.*)$", re.IGNORECASE)

_INLINE_EVIDENCE_RE = re.compile(
    r"^(.*?)\.\s+Evidence:\s+(.*?)(?:\.\s+Why it matters:\s+(.*))?$",
    re.IGNORECASE,
)
_INLINE_REASON_RE = re.compile(
    r"^(.*?)\.\s+Reason:\s+(.*)$",
    re.IGNORECASE,
)


def _split_inline_concern(
    text: str,
) -> tuple[str, str | None, str | None]:
    """Separate inline Concern/Evidence/Why fields (older report layout)."""
    match = _INLINE_EVIDENCE_RE.match(text)
    if not match:
        return text, None, None

    finding = match.group(1).strip() + "."
    evidence = match.group(2).strip()
    interpretation = match.group(3)

    if interpretation is not None:
        evidence += "."
        interpretation = interpretation.strip()

    return finding, evidence, interpretation


def _split_inline_check(
    text: str,
) -> tuple[str, str | None]:
    """Separate inline Check/Reason fields (older report layout)."""
    match = _INLINE_REASON_RE.match(text)
    if not match:
        return text, None

    return match.group(1).strip() + ".", match.group(2).strip()


def _normalise_heading(text: str) -> str:
    """Return a conservative comparison form for a Markdown heading."""
    return " ".join(text.strip().lower().split())


def extract_final_findings(report_text: str) -> list[dict[str, Any]]:
    """Extract final concerns/questions and assign deterministic IDs.

    IDs are assigned independently by finding type:

    - concerns: C1, C2, ...
    - verification questions: Q1, Q2, ...

    Finding text is preserved exactly apart from removing the existing
    Markdown bullet and ``Concern:`` / ``Check:`` marker.

    This function does not infer candidate lineage. ``upstream_lineage`` is
    therefore ``None`` unless a later, separately validated application layer
    establishes that relationship.
    """
    if not report_text:
        return []

    findings: list[dict[str, Any]] = []
    section: str | None = None
    concern_number = 0
    question_number = 0

    for line in report_text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            section = _normalise_heading(heading_match.group(1))
            continue

        if section == "directly supported concerns":
            match = _CONCERN_RE.match(line)
            if match:
                concern_number += 1
                finding_text, _, _ = _split_inline_concern(match.group(1))
                findings.append(
                    {
                        "finding_id": f"C{concern_number}",
                        "review_status": "concern",
                        "text": finding_text,
                        "upstream_lineage": None,
                    }
                )
            continue

        if section == "verification prompts":
            match = _CHECK_RE.match(line)
            if match:
                question_number += 1
                finding_text, _ = _split_inline_check(match.group(1))
                findings.append(
                    {
                        "finding_id": f"Q{question_number}",
                        "review_status": "verification_question",
                        "text": finding_text,
                        "upstream_lineage": None,
                    }
                )

    return findings


def _source_span_location(
    source_text: str,
    *,
    source_start_char: int,
    source_end_char: int,
) -> tuple[str | None, bool]:
    """Derive human-readable structural location for one exact source span.

    Only literal application-owned ``[Page N]`` regions and explicit
    ``[TABLE_START]`` / ``[TABLE_END]`` containers are used. Structural
    metadata establishes location only; it does not establish that the source
    supports any review finding.
    """
    page_matches = list(
        re.finditer(r"(?m)^\[Page\s+(\d+)\]\s*$", source_text)
    )
    literal_page: int | None = None

    for index, match in enumerate(page_matches):
        region_start = match.start()
        region_end = (
            page_matches[index + 1].start()
            if index + 1 < len(page_matches)
            else len(source_text)
        )

        if (
            region_start <= source_start_char
            and source_end_char <= region_end
        ):
            literal_page = int(match.group(1))
            break

    table_location: str | None = None
    inside_explicit_table = False
    stack: list[int] = []

    marker_pattern = re.compile(
        r"(?m)^\[TABLE_(START|END)\][^\n]*(?:\n|$)"
    )

    for match in marker_pattern.finditer(source_text):
        marker_type = match.group(1)

        if marker_type == "START":
            stack.append(match.start())
            continue

        if not stack:
            continue

        table_start = stack.pop()
        table_end = match.end()

        if not (
            table_start <= source_start_char
            and source_end_char <= table_end
        ):
            continue

        inside_explicit_table = True
        table_text = source_text[table_start:table_end]

        def metadata_field(field: str) -> str | None:
            found = re.search(
                rf"(?m)^{re.escape(field)}:\s*(.*?)\s*$",
                table_text,
            )
            if not found:
                return None
            value = found.group(1).strip()
            return value or None

        label = metadata_field("Label")
        table_page = metadata_field("Page")

        if label and table_page:
            table_location = f"{label}, p. {table_page}"
        elif label:
            table_location = label
        elif table_page:
            table_location = f"p. {table_page}"

        break

    if table_location:
        return table_location, inside_explicit_table

    if literal_page is not None:
        return f"p. {literal_page}", inside_explicit_table

    return None, inside_explicit_table


def build_verified_source_evidence(
    source_text: str,
    source_spans: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build evidence-card provenance from exact application-owned source spans.

    Each supplied span must already identify an exact occurrence in the
    supplied source snapshot. No relocation, fuzzy matching, semantic
    matching, whitespace repair, or evidence-relationship inference occurs
    here.

    Structural page/table metadata is used only to produce human-readable
    source locations. It does not establish that a span supports a finding.
    """
    if not isinstance(source_text, str):
        raise ValueError("source_text must be a string.")

    if not isinstance(source_spans, list) or not source_spans:
        raise ValueError("source_spans must be a non-empty list.")

    verified_texts: list[str] = []
    source_locations: list[str] = []
    table_evidence_used = False

    for span in source_spans:
        if not isinstance(span, dict):
            raise ValueError("Each source span must be a mapping.")

        required = {
            "source_start_char",
            "source_end_char",
            "text",
        }
        if set(span) != required:
            raise ValueError(
                "Each source span must contain exactly "
                "source_start_char, source_end_char, and text."
            )

        start = span["source_start_char"]
        end = span["source_end_char"]
        expected_text = span["text"]

        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
        ):
            raise ValueError("Source span offsets must be integers.")

        if not isinstance(expected_text, str) or not expected_text:
            raise ValueError("Source span text must be non-empty.")

        if start < 0 or end <= start or end > len(source_text):
            raise ValueError("Source span offsets are invalid.")

        if source_text[start:end] != expected_text:
            raise ValueError(
                "Source span does not match the supplied source snapshot."
            )

        location, inside_table = _source_span_location(
            source_text,
            source_start_char=start,
            source_end_char=end,
        )

        verified_texts.append(expected_text)
        table_evidence_used = table_evidence_used or inside_table

        if location and location not in source_locations:
            source_locations.append(location)

    if len(verified_texts) == 1:
        verified_source_evidence: str | list[str] = verified_texts[0]
    else:
        verified_source_evidence = verified_texts

    return {
        "source_locations": source_locations,
        "source_location": (
            "; ".join(source_locations)
            if source_locations
            else None
        ),
        "verified_source_evidence": verified_source_evidence,
        "source_passage_located": True,
        "table_evidence_used": table_evidence_used,
    }


_ALLOWED_EVIDENCE_RELATIONSHIPS = {
    "direct_manuscript_support",
    "direct_table_evidence",
    "multiple_source_support",
    "partial_support",
    "source_relationship_not_established",
    "conflicting_manuscript_evidence",
}


def _extract_finding_details(report_text: str) -> dict[str, dict[str, str | None]]:
    """Extract report-authored evidence/interpretation without verifying it.

    The returned Evidence/Why it matters/Reason text remains review content.
    This parser does not establish that any Evidence statement is supported by
    the manuscript.
    """
    details: dict[str, dict[str, str | None]] = {}
    section: str | None = None
    concern_number = 0
    question_number = 0
    current_id: str | None = None

    evidence_re = re.compile(r"^\s+Evidence:\s*(.*)$", re.IGNORECASE)
    why_re = re.compile(r"^\s+Why it matters:\s*(.*)$", re.IGNORECASE)
    reason_re = re.compile(r"^\s+Reason:\s*(.*)$", re.IGNORECASE)

    for line in report_text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            section = _normalise_heading(heading_match.group(1))
            current_id = None
            continue

        if section == "directly supported concerns":
            match = _CONCERN_RE.match(line)
            if match:
                concern_number += 1
                current_id = f"C{concern_number}"
                _, inline_evidence, inline_interpretation = (
                    _split_inline_concern(match.group(1))
                )
                details[current_id] = {
                    "reported_evidence": inline_evidence,
                    "interpretation": inline_interpretation,
                }
                continue

        if section == "verification prompts":
            match = _CHECK_RE.match(line)
            if match:
                question_number += 1
                current_id = f"Q{question_number}"
                _, inline_reason = _split_inline_check(match.group(1))
                details[current_id] = {
                    "reported_evidence": None,
                    "interpretation": inline_reason,
                }
                continue

        if current_id is None:
            continue

        evidence_match = evidence_re.match(line)
        if evidence_match:
            details[current_id]["reported_evidence"] = evidence_match.group(1)
            continue

        why_match = why_re.match(line)
        if why_match:
            details[current_id]["interpretation"] = why_match.group(1)
            continue

        reason_match = reason_re.match(line)
        if reason_match:
            details[current_id]["interpretation"] = reason_match.group(1)

    return details


def build_evidence_cards(
    report_text: str,
    *,
    verified_relationships: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic evidence-card data.

    Report-authored ``Evidence:`` text is retained as ``reported_evidence`` but
    is not promoted to verified manuscript evidence.

    A stronger evidence relationship can only be supplied through explicit
    application-owned ``verified_relationships`` state.

    This function performs no model inference and no source matching.
    """
    findings = extract_final_findings(report_text)
    details = _extract_finding_details(report_text)
    verified_relationships = verified_relationships or {}

    known_ids = {finding["finding_id"] for finding in findings}
    unknown_ids = set(verified_relationships) - known_ids
    if unknown_ids:
        raise ValueError(
            "Verification state supplied for unknown finding ID(s): "
            + ", ".join(sorted(unknown_ids))
        )

    cards: list[dict[str, Any]] = []

    for finding in findings:
        finding_id = finding["finding_id"]
        report_details = details.get(finding_id, {})
        verified = dict(verified_relationships.get(finding_id, {}))

        relationship = verified.get(
            "evidence_relationship",
            "source_relationship_not_established",
        )

        if relationship not in _ALLOWED_EVIDENCE_RELATIONSHIPS:
            raise ValueError(
                f"Invalid evidence relationship for {finding_id}: "
                f"{relationship!r}"
            )

        human_verification_required = verified.get(
            "human_verification_required",
            relationship
            in {
                "source_relationship_not_established",
                "partial_support",
                "conflicting_manuscript_evidence",
            },
        )

        structured_table = verified.get("structured_table")
        if structured_table is not None:
            if not isinstance(structured_table, dict):
                raise ValueError(
                    f"Structured table for {finding_id} must be a mapping."
                )

            columns = structured_table.get("columns")
            rows = structured_table.get("rows")

            if (
                not isinstance(columns, list)
                or not columns
                or not all(isinstance(column, str) for column in columns)
            ):
                raise ValueError(
                    f"Structured table for {finding_id} requires "
                    "non-empty string columns."
                )

            if not isinstance(rows, list):
                raise ValueError(
                    f"Structured table for {finding_id} requires rows."
                )

            expected_width = len(columns)
            for row in rows:
                if (
                    not isinstance(row, list)
                    or len(row) != expected_width
                    or not all(isinstance(cell, str) for cell in row)
                ):
                    raise ValueError(
                        f"Structured table row for {finding_id} must contain "
                        f"exactly {expected_width} string cells."
                    )

            structured_table = {
                "columns": list(columns),
                "rows": [list(row) for row in rows],
            }

        card = {
            "finding_id": finding_id,
            "review_status": finding["review_status"],
            "finding": finding["text"],
            "reported_evidence": report_details.get("reported_evidence"),
            "interpretation": report_details.get("interpretation"),
            "evidence_relationship": relationship,
            "source_location": verified.get("source_location"),
            "verified_source_evidence": verified.get(
                "verified_source_evidence"
            ),
            "evidence_type": verified.get("evidence_type"),
            "source_passage_located": verified.get("source_passage_located"),
            "exact_quotation_verified": verified.get(
                "exact_quotation_verified"
            ),
            "table_evidence_used": verified.get("table_evidence_used", False),
            "structured_table": structured_table,
            "human_verification_required": bool(
                human_verification_required
            ),
            "upstream_lineage": finding["upstream_lineage"],
        }

        cards.append(card)

    return cards


_RELATIONSHIP_LABELS = {
    "direct_manuscript_support": "Direct manuscript support",
    "direct_table_evidence": "Direct table evidence",
    "multiple_source_support": "Multiple-source support",
    "partial_support": "Partial support",
    "source_relationship_not_established":
        "Not established — human verification required",
    "conflicting_manuscript_evidence": "Conflicting manuscript evidence",
}

_EVIDENCE_TYPE_LABELS = {
    "quotation": "Quotation",
    "table": "Table",
    "numeric": "Numeric",
    "reasoned_inference": "Reasoned inference",
}


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _markdown_table_cell(value: str) -> str:
    """Escape Markdown table delimiters without changing source content."""
    return value.replace("|", "\\|").replace("\n", "<br>")


def _render_structured_table(table: dict[str, Any]) -> list[str]:
    """Render already-structured application-owned table evidence."""
    columns = table["columns"]
    rows = table["rows"]

    rendered = [
        "| " + " | ".join(_markdown_table_cell(cell) for cell in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]

    for row in rows:
        rendered.append(
            "| " + " | ".join(_markdown_table_cell(cell) for cell in row) + " |"
        )

    return rendered


def render_human_evidence_appendix(
    cards: list[dict[str, Any]],
) -> str:
    """Render deterministic human-facing evidence cards as Markdown.

    Rendering performs no inference, source matching, or evidence
    verification. It only presents state already contained in the cards.
    """
    lines = [
        "# Human Evidence Appendix",
        "",
        (
            "This appendix is designed to help a human reviewer verify the "
            "substantive concerns and verification questions in the review."
        ),
        "",
        (
            "Evidence reported in the review is not treated as verified "
            "manuscript evidence unless the application has established the "
            "source relationship."
        ),
        "",
    ]

    if not cards:
        lines.append(
            "No substantive concerns or verification questions were "
            "identified for evidence-card rendering."
        )
        return "\n".join(lines).rstrip() + "\n"

    for card in cards:
        finding_id = card["finding_id"]
        status = card["review_status"]

        if status == "concern":
            status_label = "Concern"
        elif status == "verification_question":
            status_label = "Verification question"
        else:
            status_label = str(status).replace("_", " ").capitalize()

        relationship = card["evidence_relationship"]
        relationship_label = _RELATIONSHIP_LABELS.get(
            relationship,
            str(relationship).replace("_", " ").capitalize(),
        )

        lines.extend(
            [
                f"## {finding_id} — {status_label}",
                "",
                f"**Finding:** {card['finding']}",
                "",
                f"**Source relationship:** {relationship_label}",
                "",
            ]
        )

        if card.get("source_location"):
            lines.extend(
                [
                    f"**Source:** {card['source_location']}",
                    "",
                ]
            )

        if card.get("reported_evidence"):
            lines.extend(
                [
                    (
                        "**Evidence reported in the review:** "
                        f"{card['reported_evidence']}"
                    ),
                    "",
                ]
            )

        verified_source_evidence = card.get("verified_source_evidence")
        if verified_source_evidence is not None:
            if isinstance(verified_source_evidence, list):
                lines.extend(
                    [
                        "**Verified manuscript evidence:**",
                        "",
                    ]
                )
                for passage in verified_source_evidence:
                    lines.append(f"- {passage}")
                lines.append("")
            else:
                lines.extend(
                    [
                        (
                            "**Verified manuscript evidence:** "
                            f"{verified_source_evidence}"
                        ),
                        "",
                    ]
                )

        structured_table = card.get("structured_table")
        if structured_table is not None:
            lines.extend(
                [
                    "**Verified table evidence:**",
                    "",
                    *_render_structured_table(structured_table),
                    "",
                ]
            )

        evidence_type = card.get("evidence_type")
        if evidence_type:
            evidence_type_label = _EVIDENCE_TYPE_LABELS.get(
                evidence_type,
                str(evidence_type).replace("_", " ").capitalize(),
            )
            lines.extend(
                [
                    f"**Evidence type:** {evidence_type_label}",
                    "",
                ]
            )

        if card.get("source_passage_located") is not None:
            lines.extend(
                [
                    (
                        "**Source passage located:** "
                        f"{_yes_no(bool(card['source_passage_located']))}"
                    ),
                    "",
                ]
            )

        if card.get("exact_quotation_verified") is not None:
            lines.extend(
                [
                    (
                        "**Exact quotation verified:** "
                        f"{_yes_no(bool(card['exact_quotation_verified']))}"
                    ),
                    "",
                ]
            )

        if card.get("table_evidence_used"):
            lines.extend(
                [
                    "**Table evidence used:** Yes",
                    "",
                ]
            )

        if card.get("interpretation"):
            lines.extend(
                [
                    (
                        "**Reviewer interpretation:** "
                        f"{card['interpretation']}"
                    ),
                    "",
                ]
            )

        if card.get("human_verification_required"):
            lines.extend(
                [
                    (
                        "**Human action:** Check this point against the "
                        "manuscript before using it."
                    ),
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"
