"""Human-facing evidence appendix helpers.

Evidence cards begin with deterministic identity for substantive final findings.

This module does not perform model inference, source matching, evidence
assessment, or methodological interpretation. It extracts already-written
final concerns and verification questions and assigns identifiers in report
order. The identifiers are deterministic for a given report text; they are
not persistent identities across edits or reruns.

Upstream lineage is deliberately left unresolved unless it is established
elsewhere by application-owned state.

Report parsing specification
----------------------------
Only the "Directly supported concerns" and "Verification prompts" sections
are converted into cards (headings compared case-insensitively, any level).

* An item starts on a line of the form ``Concern: ...`` (concerns section) or
  ``Check: ...`` (verification section). The marker may be preceded by a
  ``-`` or ``*`` bullet and may be emphasised (``**Concern:**``,
  ``**Concern**:``, ``*Concern:*``). These are the forms the application's
  own report parsers in ``review_pipeline`` accept; unlike those parsers a
  colon is required, so prose such as "Concerns about ..." is not an item.
* Within an item, a line beginning with one of the labels ``Evidence``,
  ``Why it matters``, ``Reason``, ``Evidence match``, ``Severity`` or
  ``Confidence`` followed by a colon starts that field, with the same optional
  bullet and emphasis. A bullet-prefixed field on its own line (``* Evidence:
  ...``) therefore belongs to the item above it, as it does in the
  application's own concern grouping. ``Evidence match``, ``Severity`` and
  ``Confidence`` are recognised because the application writes or has written
  them into final reports; without recognising them they would be mistaken
  for continuation text of the preceding field. They are reproduced verbatim
  as additional report fields and never change the evidence relationship.
* Any other non-blank line inside an item continues the current field (the
  finding text until the first field). Continuation lines are joined to the
  field with single spaces, so wrapped text and qualifications are kept in
  order. After a blank line, only an indented line or a recognised field line
  continues the item; an unindented line, or an unindented bullet that is not
  a recognised marker or field, ends it.
* The older single-line layout ("Concern: X. Evidence: Y. Why it matters: Z"
  and "Check: X. Reason: Y") is still separated, after continuation lines
  have been joined.
* Text in the two sections that is not part of a recognised item is not
  discarded. ``extract_unparsed_report_content`` returns it verbatim so the
  rendered appendix can show it with an explicit parsing limitation.
* An item whose finding text is empty is kept, with a parsing limitation and
  its original report text.

None of this establishes that reported evidence is supported by the
manuscript. Report-authored fields remain review content.
"""

from __future__ import annotations

import re
from typing import Any


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")


def _marker_re(label: str) -> re.Pattern[str]:
    """Item/field marker with optional bullet and emphasis; colon required."""
    return re.compile(
        r"^\s*(?:[-*]\s+)?(?:\*{1,2})?\s*"
        + label
        + r"\s*(?:\*{1,2})?\s*:\s*(?:\*{1,2}(?=\s|$))?\s*(.*?)\s*$",
        re.IGNORECASE,
    )


_CONCERN_RE = _marker_re(r"(?:Concern)")
_CHECK_RE = _marker_re(r"(?:Check)")
_FIELD_RE = _marker_re(
    r"(Evidence\s+match|Evidence|Why\s+it\s+matters|Reason|Severity|Confidence)"
)
_INDENTED_RE = re.compile(r"^(?: {2,}|\t)")
_UNINDENTED_BULLET_RE = re.compile(r"^ ?[-*]\s")

_SECTIONS = {
    "directly supported concerns": ("concern", "C", _CONCERN_RE),
    "verification prompts": ("verification_question", "Q", _CHECK_RE),
}

_FIELD_KEYS = {
    "evidence": "evidence",
    "why it matters": "interpretation",
    "reason": "interpretation",
    "evidence match": "Evidence match",
    "severity": "Severity",
    "confidence": "Confidence",
}

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


def _join(parts: list[str]) -> str:
    return " ".join(part for part in parts if part)


def _parse_report(report_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Group the two finding sections into items and unattributed blocks.

    Returns ``(items, unparsed)``. Each item carries its finding type, raw
    report lines, finding parts and fields in report order. Each unparsed
    block carries the heading it appeared under and its verbatim lines.
    """
    items: list[dict[str, Any]] = []
    unparsed: list[dict[str, Any]] = []
    section: str | None = None
    heading_text = ""
    current: dict[str, Any] | None = None
    loose: dict[str, Any] | None = None
    blank_since_last = False

    def close_item() -> None:
        nonlocal current
        if current is not None:
            while current["raw"] and not current["raw"][-1].strip():
                current["raw"].pop()
            items.append(current)
        current = None

    def close_loose() -> None:
        nonlocal loose
        if loose is not None:
            while loose["lines"] and not loose["lines"][-1].strip():
                loose["lines"].pop()
            if loose["lines"]:
                unparsed.append(loose)
        loose = None

    for line in (report_text or "").splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            close_item()
            close_loose()
            heading_text = heading_match.group(1).strip()
            section = _normalise_heading(heading_text)
            blank_since_last = False
            continue

        if section not in _SECTIONS:
            continue

        review_status, _, marker_re = _SECTIONS[section]
        marker = marker_re.match(line)
        if marker:
            close_item()
            close_loose()
            current = {
                "review_status": review_status,
                "raw": [line],
                "finding_parts": [marker.group(1)],
                "fields": [],
            }
            blank_since_last = False
            continue

        if not line.strip():
            if current is not None:
                current["raw"].append(line)
            elif loose is not None:
                loose["lines"].append(line)
            blank_since_last = True
            continue

        field = _FIELD_RE.match(line) if current is not None else None
        if field:
            label = _normalise_heading(field.group(1))
            current["fields"].append([_FIELD_KEYS[label], [field.group(2)]])
            current["raw"].append(line)
            blank_since_last = False
            continue

        indented = bool(_INDENTED_RE.match(line))
        continues = (
            current is not None
            and (indented or not blank_since_last)
            and (indented or not _UNINDENTED_BULLET_RE.match(line))
        )
        if continues:
            text = line.strip()
            if current["fields"]:
                current["fields"][-1][1].append(text)
            else:
                current["finding_parts"].append(text)
            current["raw"].append(line)
            blank_since_last = False
            continue

        close_item()
        if loose is None:
            loose = {"heading": heading_text, "section": section, "lines": []}
        loose["lines"].append(line)
        blank_since_last = False

    close_item()
    close_loose()
    return items, unparsed


def _item_content(item: dict[str, Any]) -> dict[str, Any]:
    """Finding text, report fields and parsing limitations for one item."""
    finding = _join(item["finding_parts"])
    evidence: list[str] = []
    interpretation: list[str] = []
    other_fields: list[dict[str, str]] = []
    limitations: list[str] = []

    if item["review_status"] == "concern":
        finding, inline_evidence, inline_interpretation = _split_inline_concern(finding)
        if inline_evidence is not None:
            evidence.append(inline_evidence)
        if inline_interpretation is not None:
            interpretation.append(inline_interpretation)
    else:
        finding, inline_reason = _split_inline_check(finding)
        if inline_reason is not None:
            interpretation.append(inline_reason)

    for key, parts in item["fields"]:
        value = _join(parts)
        if key == "evidence":
            evidence.append(value)
        elif key == "interpretation":
            interpretation.append(value)
        else:
            other_fields.append({"label": key, "text": value})

    evidence = [value for value in evidence if value]
    interpretation = [value for value in interpretation if value]

    if not finding:
        limitations.append(
            "The item marker carried no finding text, so the finding could "
            "not be separated from the rest of the item."
        )

    return {
        "text": finding,
        "reported_evidence": _join(evidence) or None,
        "interpretation": _join(interpretation) or None,
        "other_report_fields": other_fields,
        "parse_limitations": limitations,
        "report_block": "\n".join(item["raw"]),
    }


def extract_final_findings(report_text: str) -> list[dict[str, Any]]:
    """Extract final concerns/questions and assign deterministic IDs.

    IDs are assigned independently by finding type:

    - concerns: C1, C2, ...
    - verification questions: Q1, Q2, ...

    Finding text is preserved apart from removing the existing Markdown
    bullet, emphasis and ``Concern:`` / ``Check:`` marker, and joining wrapped
    continuation lines with single spaces (see the module docstring).

    This function does not infer candidate lineage. ``upstream_lineage`` is
    therefore ``None`` unless a later, separately validated application layer
    establishes that relationship.
    """
    if not report_text:
        return []

    items, _ = _parse_report(report_text)
    findings: list[dict[str, Any]] = []
    counters = {"concern": 0, "verification_question": 0}
    prefixes = {"concern": "C", "verification_question": "Q"}

    for item in items:
        status = item["review_status"]
        counters[status] += 1
        findings.append(
            {
                "finding_id": f"{prefixes[status]}{counters[status]}",
                "review_status": status,
                "text": _item_content(item)["text"],
                "upstream_lineage": None,
            }
        )

    return findings


def extract_unparsed_report_content(report_text: str) -> list[dict[str, str]]:
    """Return finding-section text that was not converted into a card.

    Each entry gives the section heading as written and the verbatim text.
    Nothing here is assigned an identifier or interpreted.
    """
    _, unparsed = _parse_report(report_text or "")
    return [
        {"heading": block["heading"], "text": "\n".join(block["lines"])}
        for block in unparsed
    ]


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


def _extract_finding_details(report_text: str) -> dict[str, dict[str, Any]]:
    """Extract report-authored evidence/interpretation without verifying it.

    The returned Evidence/Why it matters/Reason text remains review content.
    This parser does not establish that any Evidence statement is supported by
    the manuscript.
    """
    details: dict[str, dict[str, Any]] = {}
    items, _ = _parse_report(report_text or "")
    counters = {"concern": 0, "verification_question": 0}
    prefixes = {"concern": "C", "verification_question": "Q"}

    for item in items:
        status = item["review_status"]
        counters[status] += 1
        content = _item_content(item)
        details[f"{prefixes[status]}{counters[status]}"] = {
            "reported_evidence": content["reported_evidence"],
            "interpretation": content["interpretation"],
            "other_report_fields": content["other_report_fields"],
            "parse_limitations": content["parse_limitations"],
            "report_block": content["report_block"],
        }

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
            "other_report_fields": list(
                report_details.get("other_report_fields") or []
            ),
            "parse_limitations": list(
                report_details.get("parse_limitations") or []
            ),
            "report_block": report_details.get("report_block"),
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


def _fenced_text(text: str) -> list[str]:
    """Verbatim text in a fence longer than any backtick run inside it."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence + "text", text, fence]


def _render_unparsed_content(unparsed_content: list[dict[str, str]]) -> list[str]:
    lines = [
        "## Report content not converted into cards",
        "",
        (
            "**Parsing limitation:** The following text appears in the "
            "review's concern or verification sections but is not in a "
            "recognised Concern: or Check: item, so no card or identifier was "
            "assigned. It is reproduced verbatim from the review and has not "
            "been checked against the manuscript."
        ),
        "",
    ]
    for block in unparsed_content:
        lines.extend(
            [
                f"### Under \"{block.get('heading') or 'unknown section'}\"",
                "",
                *_fenced_text(block.get("text") or ""),
                "",
            ]
        )
    return lines


def render_human_evidence_appendix(
    cards: list[dict[str, Any]],
    *,
    unparsed_content: list[dict[str, str]] | None = None,
) -> str:
    """Render deterministic human-facing evidence cards as Markdown.

    Rendering performs no inference, source matching, or evidence
    verification. It only presents state already contained in the cards.
    ``unparsed_content`` (from ``extract_unparsed_report_content``) is
    reproduced verbatim under an explicit parsing limitation.
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
        (
            "Identifiers (C1, Q1, ...) follow the order of this review only; "
            "they are not stable across edits or reruns. What the application "
            "extracted from the uploaded files is recorded separately in the "
            "extraction evidence appendix."
        ),
        "",
    ]

    if not cards:
        lines.append(
            "No substantive concerns or verification questions were "
            "identified for evidence-card rendering."
        )
        if unparsed_content:
            lines.append("")
            lines.extend(_render_unparsed_content(unparsed_content))
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

        other_fields = card.get("other_report_fields") or []
        if other_fields:
            lines.extend(
                [
                    (
                        "**Other fields written in the review** (reproduced "
                        "as written; they do not establish the source "
                        "relationship):"
                    ),
                    "",
                ]
            )
            for field in other_fields:
                lines.append(f"- {field['label']} — {field['text']}")
            lines.append("")

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

        limitations = card.get("parse_limitations") or []
        if limitations:
            lines.extend(
                [
                    "**Parsing limitation:** " + " ".join(limitations),
                    "",
                    "Original text of this item in the review:",
                    "",
                    *_fenced_text(card.get("report_block") or ""),
                    "",
                ]
            )

    if unparsed_content:
        lines.extend(_render_unparsed_content(unparsed_content))

    return "\n".join(lines).rstrip() + "\n"
