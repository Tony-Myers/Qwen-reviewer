"""
Source-table identity and acquisition provenance for manuscript review.

This module sits between physical document extraction and quantitative
EvidenceValue objects.

It records that one source table may have multiple observations, such as a
text-layer extraction and a visual page transcription.  It deliberately does
not decide which observation is correct, whether two observations agree, or
what any reported quantity means methodologically.

The live review pipeline does not yet depend on this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence


class AcquisitionMethod(str, Enum):
    TEXT = "text"
    VISION = "vision"


class AcquisitionState(str, Enum):
    EXTRACTED = "extracted"
    VISION_TRANSCRIBED = "vision_transcribed"
    VISION_EMPTY = "vision_empty"
    VISION_FAILED = "vision_failed"
    VISION_REPORTED_NO_TABLE = "vision_reported_no_table"
    RENDER_FAILED = "render_failed"


@dataclass(frozen=True)
class TableObservation:
    """One acquisition of table evidence, not an independent source table."""

    acquisition_method: AcquisitionMethod
    content: str
    page: Optional[int]
    extraction_source: Optional[str] = None
    extraction_index: Optional[int] = None
    acquisition_state: AcquisitionState = AcquisitionState.EXTRACTED


@dataclass(frozen=True)
class StructuredTableColumn:
    """One explicitly identified column in a structured table observation."""

    index: int
    header: str


@dataclass(frozen=True)
class StructuredTableCell:
    """
    One observed cell.

    `value` remains the source transcription.  At this layer a string such as
    "10.08 (8.07, 12.71)" is not yet interpreted as an estimate plus interval.
    """

    column_index: int
    value: str


@dataclass(frozen=True)
class StructuredTableRow:
    """One row whose identity is supplied by the structured observation."""

    label: str
    cells: tuple[StructuredTableCell, ...]


@dataclass(frozen=True)
class StructuredTableSection:
    """An optional table section containing identified rows."""

    label: Optional[str]
    rows: tuple[StructuredTableRow, ...]


@dataclass(frozen=True)
class StructuredTableObservation:
    """
    Validated structural interpretation of one TableObservation.

    This records what an acquisition method reported about table structure.
    It does not establish that another observation represents the same cells,
    decide which observation is correct, or assign methodological meaning.
    """

    source_observation: TableObservation
    caption: Optional[str]
    columns: tuple[StructuredTableColumn, ...]
    sections: tuple[StructuredTableSection, ...]


@dataclass(frozen=True)
class ParsedQuantity:
    """
    Conservative syntactic decomposition of one observed cell value.

    This object records numeric syntax only.  It does not identify a
    statistical parameter, assign interval meaning, infer table roles,
    or establish methodological comparability.
    """

    raw_value: str
    central_value: float
    lower_value: Optional[float] = None
    upper_value: Optional[float] = None


@dataclass(frozen=True)
class NamedQuantity:
    """
    Numeric table evidence identified only by its observed structural labels.

    This object preserves literal table context and parsed numeric syntax.
    It does not assign semantic roles to section, row, or column labels and
    does not establish statistical meaning or comparability.
    """

    source_name: str
    page: Optional[int]
    table_evidence_id: Optional[str]
    caption: Optional[str]
    section_index: int
    section_label: Optional[str]
    row_index: int
    row_label: str
    row_label_header: Optional[str]
    quantity_label: str
    raw_value: str
    central_value: float
    lower_value: Optional[float]
    upper_value: Optional[float]
    acquisition_method: AcquisitionMethod
    extraction_source: Optional[str]


@dataclass(frozen=True)
class TableRecord:
    """
    Quantitative evidence observed together in one structured table row.

    A record preserves structural co-occurrence only.  It does not assert that
    the row is an analysis, model, intervention, outcome, or any other semantic
    type, and it does not establish comparability with another record.
    """

    source_name: str
    page: Optional[int]
    table_evidence_id: Optional[str]
    caption: Optional[str]
    section_index: int
    section_label: Optional[str]
    row_index: int
    row_label: str
    row_label_header: Optional[str]
    quantities: tuple[NamedQuantity, ...]


class TableRecordFamilyKind(str, Enum):
    """Purely structural forms of repeated table-record organisation."""

    PARALLEL_SCHEMA = "parallel_schema"
    REPEATED_ROW = "repeated_row"
    SCHEMA_EXTENSION = "schema_extension"


@dataclass(frozen=True)
class TableRecordFamily:
    """
    Observational family of table records sharing a repeated structural form.

    A family records organisation visible in the structured table only. It
    does not assert that members are analyses, models, sensitivity analyses,
    moderators, outcomes, statistically comparable, or methodologically valid.

    For PARALLEL_SCHEMA and REPEATED_ROW, `members` contains the complete
    structural group and `base_record` is None.

    For SCHEMA_EXTENSION, `base_record` is the record whose quantity-label
    schema is a proper subset of every record in `members`; `members` contains
    the extension records only. `added_quantity_labels` is the union of
    quantity labels added by those records after case/whitespace normalisation.
    """

    kind: TableRecordFamilyKind
    members: tuple[TableRecord, ...]
    base_record: Optional[TableRecord] = None
    added_quantity_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecordRelationshipEvidence:
    """
    Deterministic structural evidence relating two table records.

    This records only relationships established by source/table structure and
    literal quantity labels. It does not establish semantic identity, analysis
    identity, dataset identity, statistical comparability, or methodological
    meaning.

    `same_known_table` is True only when both records carry the same explicit
    table evidence identity. Sharing a source page with unresolved table
    identity is not promoted to evidence that the records belong to the same
    physical table.
    """

    left: TableRecord
    right: TableRecord

    same_source: bool
    same_page: bool
    same_known_table: bool
    same_section_label: bool
    same_row_label: bool

    shared_quantity_labels: tuple[str, ...]
    left_only_quantity_labels: tuple[str, ...]
    right_only_quantity_labels: tuple[str, ...]


@dataclass(frozen=True)
class RecordCorrespondence:
    """
    Deterministic evidence of repeated quantitative content across two records.

    Correspondence records exact agreement on multiple identically labelled
    quantities.  It is observational evidence only: it does not establish that
    the records are the same analysis, statistically equivalent, comparable,
    or methodologically valid.

    `shared_labels` contains every literally matched quantity label after only
    case/whitespace normalisation.  `exact_labels` and `different_labels`
    partition those shared labels by numeric agreement.
    """

    left: TableRecord
    right: TableRecord
    shared_labels: tuple[str, ...]
    exact_labels: tuple[str, ...]
    different_labels: tuple[str, ...]


@dataclass(frozen=True)
class TableCellEvidence:
    """
    One addressable cell from a structured table observation.

    This is structural evidence only.  `observed_value` remains a string:
    this layer does not parse numbers, identify statistical parameters,
    reconcile acquisition methods, or establish methodological meaning.

    `table_evidence_id` is optional because a page-level visual observation
    must not be assigned to a physical source table until that identity has
    been established separately.
    """

    source_name: str
    page: Optional[int]
    table_evidence_id: Optional[str]
    caption: Optional[str]
    section_index: int
    section_label: Optional[str]
    row_index: int
    row_label: str
    row_label_header: Optional[str]
    column_index: int
    column_header: str
    observed_value: str
    acquisition_method: AcquisitionMethod
    extraction_source: Optional[str]


class StructuredTableParseError(ValueError):
    """Structured table output failed conservative validation."""


@dataclass
class TableEvidence:
    """
    One identified source table.

    A label is strong identity evidence when present.  Page is retained as
    provenance and disambiguation, but page alone is not assumed to establish
    physical-table identity.
    """

    evidence_id: str
    source_name: str
    label: Optional[str]
    pages: list[int] = field(default_factory=list)
    text_observations: list[TableObservation] = field(default_factory=list)
    vision_observations: list[TableObservation] = field(default_factory=list)


@dataclass
class TablePageEvidence:
    """
    Evidence acquired at page level.

    Vision currently transcribes the whole rendered page.  A page observation
    therefore remains page-level until a separate operation establishes which
    source table or tables it represents.
    """

    source_name: str
    page: int
    table_evidence_ids: list[str] = field(default_factory=list)
    vision_observation: Optional[TableObservation] = None


def _normalise_label(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    return " ".join(label.casefold().split())


def _table_evidence_id(
    source_name: str,
    page: Optional[int],
    label: Optional[str],
    ordinal: int,
) -> str:
    """
    Stable application identity for the current evidence construction.

    Explicit labels are the strongest available table identity.  Page is
    retained to disambiguate repeated labels.  For unlabelled tables, ordinal
    prevents us from silently merging distinct tables merely because they
    occur on the same page.

    The extraction method's table_index is deliberately excluded: it is
    provenance of an observation, not identity of the physical source table.
    """
    normalised_label = _normalise_label(label) or "<unlabelled>"
    payload = (
        f"{source_name.casefold()}|"
        f"{page if page is not None else '<no-page>'}|"
        f"{normalised_label}|{ordinal}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"table-{digest}"


def table_evidence_from_selected(
    source_name: str,
    selected_tables: Iterable[dict],
) -> list[TableEvidence]:
    """
    Convert already-selected extractor dictionaries into source-table evidence.

    This does not redo extraction or deduplication.  It records the result of
    the existing selection stage with richer provenance than the serialised
    [TABLE_START] representation retains.
    """
    results: list[TableEvidence] = []
    identity_counts: dict[tuple[Optional[int], Optional[str]], int] = {}

    for table in selected_tables:
        page = table.get("page")
        label = table.get("label")
        normalised_label = _normalise_label(label)

        key = (page, normalised_label)
        ordinal = identity_counts.get(key, 0)
        identity_counts[key] = ordinal + 1

        rows = table.get("rows", [])
        content = "\n".join(
            "\t".join("" if cell is None else str(cell) for cell in row)
            for row in rows
        )

        observation = TableObservation(
            acquisition_method=AcquisitionMethod.TEXT,
            content=content,
            page=page,
            extraction_source=table.get("source"),
            extraction_index=table.get("table_index"),
            acquisition_state=AcquisitionState.EXTRACTED,
        )

        evidence = TableEvidence(
            evidence_id=_table_evidence_id(
                source_name,
                page,
                label,
                ordinal,
            ),
            source_name=source_name,
            label=label,
            pages=[page] if isinstance(page, int) else [],
            text_observations=[observation],
        )
        results.append(evidence)

    return results


def table_pages_from_evidence(
    source_name: str,
    tables: Iterable[TableEvidence],
) -> list[TablePageEvidence]:
    """
    Build page-level table identities without assuming one table per page.
    """
    by_page: dict[int, list[str]] = {}

    for table in tables:
        for page in table.pages:
            by_page.setdefault(page, []).append(table.evidence_id)

    return [
        TablePageEvidence(
            source_name=source_name,
            page=page,
            table_evidence_ids=list(ids),
        )
        for page, ids in sorted(by_page.items())
    ]


def attach_page_vision_observation(
    page_evidence: TablePageEvidence,
    content: str,
    state: AcquisitionState = AcquisitionState.VISION_TRANSCRIBED,
) -> None:
    """
    Attach a visual transcription to the page, not automatically to a table.
    """
    page_evidence.vision_observation = TableObservation(
        acquisition_method=AcquisitionMethod.VISION,
        content=content,
        page=page_evidence.page,
        extraction_source="vision",
        extraction_index=None,
        acquisition_state=state,
    )


def acquire_page_vision(
    pages: Iterable[TablePageEvidence],
    pdf_path,
    *,
    render_page,
    transcribe,
    prompt: str,
    dpi: int = 200,
) -> list[TablePageEvidence]:
    """
    Acquire one visual observation for every page containing selected tables.

    Acquisition is deliberately page-level.  The visual reader sees the
    rendered page, which may contain zero, one, or several physical tables.
    This function therefore does not attach the transcription to any
    individual TableEvidence object and does not attempt text/vision
    reconciliation.

    `render_page` and `transcribe` are injected dependencies so this evidence
    layer has no dependency on review_pipeline, llama-server, or a particular
    vision model.

    Acquisition failures are retained as explicit observations rather than
    silently removing the page from the evidence record.
    """
    results: list[TablePageEvidence] = []

    for page in pages:
        # Work on a new page object so diagnostic acquisition does not mutate
        # the caller's evidence representation.
        acquired = TablePageEvidence(
            source_name=page.source_name,
            page=page.page,
            table_evidence_ids=list(page.table_evidence_ids),
            vision_observation=page.vision_observation,
        )

        try:
            png = render_page(pdf_path, page.page, dpi)
        except Exception:  # acquisition must preserve evidence on backend failure
            png = b""

        if not png:
            acquired.vision_observation = TableObservation(
                acquisition_method=AcquisitionMethod.VISION,
                content="",
                page=page.page,
                extraction_source="vision",
                extraction_index=None,
                acquisition_state=AcquisitionState.RENDER_FAILED,
            )
            results.append(acquired)
            continue

        try:
            transcription = transcribe(png, prompt)
        except Exception:
            acquired.vision_observation = TableObservation(
                acquisition_method=AcquisitionMethod.VISION,
                content="",
                page=page.page,
                extraction_source="vision",
                extraction_index=None,
                acquisition_state=AcquisitionState.VISION_FAILED,
            )
            results.append(acquired)
            continue

        transcription = (transcription or "").strip()

        if not transcription:
            state = AcquisitionState.VISION_EMPTY
        elif _vision_reports_no_table(transcription):
            state = AcquisitionState.VISION_REPORTED_NO_TABLE
        else:
            state = AcquisitionState.VISION_TRANSCRIBED

        acquired.vision_observation = TableObservation(
            acquisition_method=AcquisitionMethod.VISION,
            content=transcription,
            page=page.page,
            extraction_source="vision",
            extraction_index=None,
            acquisition_state=state,
        )
        results.append(acquired)

    return results


def _vision_reports_no_table(text: str) -> bool:
    """
    Recognise the bounded no-table response used by the visual table reader.

    Keep this deliberately narrow: an uncertain or descriptive response is
    evidence to retain, not a reason to classify the page as table-free.
    """
    normalised = re.sub(r"\s+", " ", text).strip().casefold()
    return normalised.rstrip(".") == "no table on this page"


def parse_structured_table_observation(
    observation: TableObservation,
) -> StructuredTableObservation:
    """
    Parse and conservatively validate a structured table observation.

    The parser fails closed.  It does not repair malformed JSON, infer missing
    columns, renumber indices, merge duplicate cells, or fill absent values.

    Markdown JSON fences are accepted because they are transport decoration,
    not table evidence.  The original observation content is retained
    unchanged in `source_observation`.
    """
    raw = observation.content.strip()
    if not raw:
        raise StructuredTableParseError(
            "structured table observation is empty"
        )

    payload = _strip_json_code_fence(raw)

    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StructuredTableParseError(
            f"structured table observation is not valid JSON: {exc}"
        ) from exc

    if not isinstance(obj, dict):
        raise StructuredTableParseError(
            "structured table observation must be a JSON object"
        )

    caption = obj.get("caption")
    if caption is not None and not isinstance(caption, str):
        raise StructuredTableParseError(
            "caption must be a string or null"
        )

    raw_columns = obj.get("columns")
    raw_sections = obj.get("sections")

    if not isinstance(raw_columns, list) or not raw_columns:
        raise StructuredTableParseError(
            "columns must be a non-empty list"
        )
    if not isinstance(raw_sections, list):
        raise StructuredTableParseError(
            "sections must be a list"
        )

    columns: list[StructuredTableColumn] = []
    column_indices: set[int] = set()

    for position, raw_column in enumerate(raw_columns):
        if not isinstance(raw_column, dict):
            raise StructuredTableParseError(
                f"column {position} must be an object"
            )

        index = raw_column.get("index")
        header = raw_column.get("header")

        # bool is an int subclass in Python; it is not a valid column index.
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise StructuredTableParseError(
                f"column {position} has invalid index"
            )
        if index in column_indices:
            raise StructuredTableParseError(
                f"duplicate column index {index}"
            )
        if not isinstance(header, str):
            raise StructuredTableParseError(
                f"column {index} header must be a string"
            )

        column_indices.add(index)
        columns.append(
            StructuredTableColumn(
                index=index,
                header=header,
            )
        )

    sections: list[StructuredTableSection] = []

    for section_position, raw_section in enumerate(raw_sections):
        if not isinstance(raw_section, dict):
            raise StructuredTableParseError(
                f"section {section_position} must be an object"
            )

        section_label = raw_section.get("label")
        if section_label is not None and not isinstance(section_label, str):
            raise StructuredTableParseError(
                f"section {section_position} label must be a string or null"
            )

        raw_rows = raw_section.get("rows")
        if not isinstance(raw_rows, list):
            raise StructuredTableParseError(
                f"section {section_position} rows must be a list"
            )

        rows: list[StructuredTableRow] = []

        for row_position, raw_row in enumerate(raw_rows):
            if not isinstance(raw_row, dict):
                raise StructuredTableParseError(
                    f"section {section_position} row {row_position} "
                    "must be an object"
                )

            row_label = raw_row.get("label")
            if not isinstance(row_label, str):
                raise StructuredTableParseError(
                    f"section {section_position} row {row_position} "
                    "label must be a string"
                )

            raw_cells = raw_row.get("cells")
            if not isinstance(raw_cells, list):
                raise StructuredTableParseError(
                    f"section {section_position} row {row_position} "
                    "cells must be a list"
                )

            cells: list[StructuredTableCell] = []
            seen_cell_columns: set[int] = set()

            for cell_position, raw_cell in enumerate(raw_cells):
                if not isinstance(raw_cell, dict):
                    raise StructuredTableParseError(
                        f"section {section_position} row {row_position} "
                        f"cell {cell_position} must be an object"
                    )

                column_index = raw_cell.get("column_index")
                value = raw_cell.get("value")

                if (
                    isinstance(column_index, bool)
                    or not isinstance(column_index, int)
                    or column_index < 0
                ):
                    raise StructuredTableParseError(
                        f"section {section_position} row {row_position} "
                        f"cell {cell_position} has invalid column_index"
                    )
                if column_index not in column_indices:
                    raise StructuredTableParseError(
                        f"cell refers to unknown column index {column_index}"
                    )
                if column_index in seen_cell_columns:
                    raise StructuredTableParseError(
                        f"duplicate cell for column index {column_index} "
                        f"in section {section_position} row {row_position}"
                    )
                if not isinstance(value, str):
                    raise StructuredTableParseError(
                        f"cell value for column index {column_index} "
                        "must be a string"
                    )

                seen_cell_columns.add(column_index)
                cells.append(
                    StructuredTableCell(
                        column_index=column_index,
                        value=value,
                    )
                )

            rows.append(
                StructuredTableRow(
                    label=row_label,
                    cells=tuple(cells),
                )
            )

        sections.append(
            StructuredTableSection(
                label=section_label,
                rows=tuple(rows),
            )
        )

    return StructuredTableObservation(
        source_observation=observation,
        caption=caption,
        columns=tuple(columns),
        sections=tuple(sections),
    )


def _strip_json_code_fence(text: str) -> str:
    """
    Remove one complete Markdown JSON fence without modifying its contents.

    Anything other than a single enclosing ```json/``` fence is returned
    unchanged and must therefore pass normal JSON parsing on its own.
    """
    match = re.fullmatch(
        r"\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else text


def cell_evidence_from_structured_observation(
    source_name: str,
    structured: StructuredTableObservation,
    *,
    table_evidence_id: Optional[str] = None,
) -> list[TableCellEvidence]:
    """
    Flatten one validated structured observation into addressable cells.

    The operation is lossless with respect to the structural fields represented
    by StructuredTableObservation.  It does not infer missing cells, parse
    values, normalise labels, reconcile observations, or assign a source-table
    identity unless the caller explicitly supplies one.
    """
    headers = {
        column.index: column.header
        for column in structured.columns
    }
    observation = structured.source_observation
    results: list[TableCellEvidence] = []

    for section_index, section in enumerate(structured.sections):
        for row_index, row in enumerate(section.rows):
            label_matches = [
                cell.column_index
                for cell in row.cells
                if cell.value == row.label
            ]
            row_label_header = (
                headers[label_matches[0]]
                if len(label_matches) == 1
                else None
            )

            for cell in row.cells:
                results.append(
                    TableCellEvidence(
                        source_name=source_name,
                        page=observation.page,
                        table_evidence_id=table_evidence_id,
                        caption=structured.caption,
                        section_index=section_index,
                        section_label=section.label,
                        row_index=row_index,
                        row_label=row.label,
                        row_label_header=row_label_header,
                        column_index=cell.column_index,
                        column_header=headers[cell.column_index],
                        observed_value=cell.value,
                        acquisition_method=observation.acquisition_method,
                        extraction_source=observation.extraction_source,
                    )
                )

    return results


_SIMPLE_NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$"
)

_NUMBER_WITH_INTERVAL_RE = re.compile(
    r"^"
    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"\s*"
    r"\("
    r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"\s*,\s*"
    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"\s*\)"
    r"$"
)


def parse_quantity_syntax(value: str) -> Optional[ParsedQuantity]:
    """
    Parse only unambiguous numeric syntax from an observed table cell.

    Supported forms are deliberately narrow:

      245.273
      -10.28 (-31.49, -2.50)

    Descriptive text, missing-value markers, percentages, inequalities,
    plus/minus notation, malformed intervals, and mixed content are left
    unresolved rather than repaired or interpreted.
    """
    raw = value
    stripped = value.strip()

    interval_match = _NUMBER_WITH_INTERVAL_RE.fullmatch(stripped)
    if interval_match:
        central = float(interval_match.group(1))
        lower = float(interval_match.group(2))
        upper = float(interval_match.group(3))

        if not all(math.isfinite(x) for x in (central, lower, upper)):
            return None

        return ParsedQuantity(
            raw_value=raw,
            central_value=central,
            lower_value=lower,
            upper_value=upper,
        )

    if _SIMPLE_NUMBER_RE.fullmatch(stripped):
        central = float(stripped)
        if not math.isfinite(central):
            return None

        return ParsedQuantity(
            raw_value=raw,
            central_value=central,
        )

    return None


def named_quantity_from_cell(
    cell: TableCellEvidence,
) -> Optional[NamedQuantity]:
    """
    Convert a structurally identified cell into literal named quantity
    evidence when its numeric syntax is unambiguous.

    No semantic role assignment, label normalisation, statistical
    interpretation, or comparability judgement is performed.
    """
    parsed = parse_quantity_syntax(cell.observed_value)
    if parsed is None:
        return None

    return NamedQuantity(
        source_name=cell.source_name,
        page=cell.page,
        table_evidence_id=cell.table_evidence_id,
        caption=cell.caption,
        section_index=cell.section_index,
        section_label=cell.section_label,
        row_index=cell.row_index,
        row_label=cell.row_label,
        row_label_header=cell.row_label_header,
        quantity_label=cell.column_header,
        raw_value=parsed.raw_value,
        central_value=parsed.central_value,
        lower_value=parsed.lower_value,
        upper_value=parsed.upper_value,
        acquisition_method=cell.acquisition_method,
        extraction_source=cell.extraction_source,
    )


def table_record_from_quantities(
    quantities: Sequence[NamedQuantity],
) -> Optional[TableRecord]:
    """
    Group named quantities that demonstrably belong to one structural row.

    All quantities must carry the same source, page, table identity, caption,
    section label, row label, acquisition method, and extraction source.
    Mixed provenance is rejected rather than silently reconciled.
    """
    items = tuple(quantities)
    if not items:
        return None

    first = items[0]
    structural_identity = (
        first.source_name,
        first.page,
        first.table_evidence_id,
        first.caption,
        first.section_index,
        first.section_label,
        first.row_index,
        first.row_label,
        first.row_label_header,
        first.acquisition_method,
        first.extraction_source,
    )

    for item in items[1:]:
        candidate_identity = (
            item.source_name,
            item.page,
            item.table_evidence_id,
            item.caption,
            item.section_index,
            item.section_label,
            item.row_index,
            item.row_label,
            item.row_label_header,
            item.acquisition_method,
            item.extraction_source,
        )
        if candidate_identity != structural_identity:
            raise ValueError(
                "named quantities with different structural provenance "
                "cannot form one TableRecord"
            )

    return TableRecord(
        source_name=first.source_name,
        page=first.page,
        table_evidence_id=first.table_evidence_id,
        caption=first.caption,
        section_index=first.section_index,
        section_label=first.section_label,
        row_index=first.row_index,
        row_label=first.row_label,
        row_label_header=first.row_label_header,
        quantities=items,
    )


def _record_schema(record: TableRecord) -> frozenset[str]:
    """
    Return the minimally normalised literal quantity-label schema.

    Duplicate normalised labels are ambiguous and therefore rejected.
    """
    labels: set[str] = set()

    for quantity in record.quantities:
        key = _normalise_label(quantity.quantity_label)
        if key is None:
            raise ValueError("NamedQuantity has no usable quantity label")
        if key in labels:
            raise ValueError(
                "TableRecord contains duplicate normalised quantity labels"
            )
        labels.add(key)

    return frozenset(labels)


def _record_table_scope(
    record: TableRecord,
) -> tuple[str, Optional[int], Optional[str]]:
    """
    Return the structural table scope used for record-family discovery.

    Source identity prevents records from separate uploaded files with the
    same page number from being grouped. A known table identity also prevents
    distinct tables on the same source page from being grouped. When table
    identity is unresolved, records remain conservatively scoped to their
    source page.
    """
    return (
        record.source_name,
        record.page,
        record.table_evidence_id,
    )


def parallel_schema_families(
    records: Sequence[TableRecord],
) -> list[TableRecordFamily]:
    """
    Group records in the same table scope, section, and literal quantity schema.

    Only groups containing at least two records are returned. The grouping is
    structural only and does not establish semantic or methodological meaning.
    """
    groups: dict[
        tuple[
            tuple[str, Optional[int], Optional[str]],
            Optional[str],
            frozenset[str],
        ],
        list[TableRecord],
    ] = {}

    for record in records:
        key = (
            _record_table_scope(record),
            _normalise_label(record.section_label),
            _record_schema(record),
        )
        groups.setdefault(key, []).append(record)

    return [
        TableRecordFamily(
            kind=TableRecordFamilyKind.PARALLEL_SCHEMA,
            members=tuple(group),
        )
        for group in groups.values()
        if len(group) >= 2
    ]


def repeated_row_families(
    records: Sequence[TableRecord],
) -> list[TableRecordFamily]:
    """
    Group records in the same table scope with the same row label and literal quantity schema.

    Only groups spanning at least two distinct section labels are returned.
    """
    groups: dict[
        tuple[
            tuple[str, Optional[int], Optional[str]],
            Optional[str],
            frozenset[str],
        ],
        list[TableRecord],
    ] = {}

    for record in records:
        key = (
            _record_table_scope(record),
            _normalise_label(record.row_label),
            _record_schema(record),
        )
        groups.setdefault(key, []).append(record)

    results: list[TableRecordFamily] = []

    for group in groups.values():
        sections = {
            _normalise_label(record.section_label)
            for record in group
        }

        if len(group) >= 2 and len(sections) >= 2:
            results.append(
                TableRecordFamily(
                    kind=TableRecordFamilyKind.REPEATED_ROW,
                    members=tuple(group),
                )
            )

    return results


def schema_extension_families(
    records: Sequence[TableRecord],
) -> list[TableRecordFamily]:
    """
    Find within-section records whose schema is a proper subset of others.

    Each returned family has one structural base record and every other record
    in the same table scope and section whose schema properly extends that
    base schema.
    """
    groups: dict[
        tuple[
            tuple[str, Optional[int], Optional[str]],
            Optional[str],
        ],
        list[TableRecord],
    ] = {}

    for record in records:
        key = (
            _record_table_scope(record),
            _normalise_label(record.section_label),
        )
        groups.setdefault(key, []).append(record)

    results: list[TableRecordFamily] = []

    for group in groups.values():
        for base in group:
            base_schema = _record_schema(base)

            extensions = tuple(
                candidate
                for candidate in group
                if candidate is not base
                and base_schema < _record_schema(candidate)
            )

            if not extensions:
                continue

            added: set[str] = set()

            for candidate in extensions:
                added.update(
                    _record_schema(candidate) - base_schema
                )

            results.append(
                TableRecordFamily(
                    kind=TableRecordFamilyKind.SCHEMA_EXTENSION,
                    members=extensions,
                    base_record=base,
                    added_quantity_labels=tuple(sorted(added)),
                )
            )

    return results


def _record_quantity_map(
    record: TableRecord,
) -> dict[str, NamedQuantity]:
    """
    Index a record by minimally normalised literal quantity label.

    Duplicate normalised labels are ambiguous and therefore rejected rather
    than overwritten.
    """
    result: dict[str, NamedQuantity] = {}

    for quantity in record.quantities:
        key = _normalise_label(quantity.quantity_label)
        if key is None:
            raise ValueError("NamedQuantity has no usable quantity label")
        if key in result:
            raise ValueError(
                "TableRecord contains duplicate normalised quantity labels"
            )
        result[key] = quantity

    return result


def record_relationship_evidence(
    left: TableRecord,
    right: TableRecord,
) -> RecordRelationshipEvidence:
    """
    Materialise deterministic structural relationships between two records.

    Quantity labels receive only the module's existing case/whitespace
    normalisation. No semantic label equivalence is inferred.

    This operation deliberately does not infer outcomes, analyses, models,
    datasets, statistical comparability, or methodological meaning.
    """
    left_labels = _record_schema(left)
    right_labels = _record_schema(right)

    left_section = _normalise_label(left.section_label)
    right_section = _normalise_label(right.section_label)
    left_row = _normalise_label(left.row_label)
    right_row = _normalise_label(right.row_label)

    same_known_table = (
        left.table_evidence_id is not None
        and right.table_evidence_id is not None
        and left.table_evidence_id == right.table_evidence_id
        and left.source_name == right.source_name
    )

    return RecordRelationshipEvidence(
        left=left,
        right=right,
        same_source=left.source_name == right.source_name,
        same_page=(
            left.source_name == right.source_name
            and left.page is not None
            and right.page is not None
            and left.page == right.page
        ),
        same_known_table=same_known_table,
        same_section_label=(
            left_section is not None
            and right_section is not None
            and left_section == right_section
        ),
        same_row_label=(
            left_row is not None
            and right_row is not None
            and left_row == right_row
        ),
        shared_quantity_labels=tuple(sorted(left_labels & right_labels)),
        left_only_quantity_labels=tuple(sorted(left_labels - right_labels)),
        right_only_quantity_labels=tuple(sorted(right_labels - left_labels)),
    )


def _quantities_exactly_equal(
    left: NamedQuantity,
    right: NamedQuantity,
) -> bool:
    return (
        left.central_value == right.central_value
        and left.lower_value == right.lower_value
        and left.upper_value == right.upper_value
    )


def record_correspondence(
    left: TableRecord,
    right: TableRecord,
    *,
    minimum_exact_fields: int = 2,
) -> Optional[RecordCorrespondence]:
    """
    Detect conservative multi-field quantitative correspondence.

    Labels receive only the module's existing case/whitespace normalisation.
    No semantic label equivalence is inferred.  A single matching quantity is
    insufficient by default.

    The result records repeated content only; it makes no claim about analysis
    identity, statistical equivalence, comparability, or methodology.
    """
    if minimum_exact_fields < 2:
        raise ValueError("minimum_exact_fields must be at least 2")

    left_map = _record_quantity_map(left)
    right_map = _record_quantity_map(right)

    shared = tuple(sorted(set(left_map) & set(right_map)))
    exact = tuple(
        label
        for label in shared
        if _quantities_exactly_equal(left_map[label], right_map[label])
    )
    different = tuple(label for label in shared if label not in exact)

    if len(exact) < minimum_exact_fields:
        return None

    return RecordCorrespondence(
        left=left,
        right=right,
        shared_labels=shared,
        exact_labels=exact,
        different_labels=different,
    )
