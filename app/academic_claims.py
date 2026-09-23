"""Claim-support structures for Academic Chat.

This module keeps source retrieval and substantive claim assessment separate
from bibliographic identity verification.

A failure to retrieve or locate evidence must not be interpreted as evidence
that an academic claim is false or unsupported.
"""

from dataclasses import asdict, dataclass
from io import BytesIO

import httpcore
import ipaddress
import re
import socket
import time
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from typing import Any
from urllib.parse import urljoin, urlparse


@dataclass
class ClaimEvidence:
    """An inspectable passage used when assessing a claim."""

    text: str
    locator: str
    source: str
    page_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimSupportResult:
    """Result for one academic reference-claim pair."""

    status: str
    source_status: str
    claim_status: str
    doi: str | None
    evidence: list[ClaimEvidence]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_status": self.source_status,
            "claim_status": self.claim_status,
            "doi": self.doi,
            "evidence": [
                item.to_dict()
                for item in self.evidence
            ],
            "reasons": self.reasons,
        }


class SourceRetrievalError(RuntimeError):
    """Expected failure while retrieving or extracting a scholarly source."""


@dataclass
class ClaimAssessmentResult:
    """An auditable assessment of located evidence against a claim."""

    status: str
    claim: str
    evidence: list[ClaimEvidence]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "claim": self.claim,
            "evidence": [item.to_dict() for item in self.evidence],
            "reasons": self.reasons,
        }


@dataclass
class ClaimPresentation:
    """Application-owned presentation of a validated semantic assessment."""

    status: str
    statement: str

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "statement": self.statement,
        }


_CLAIM_PRESENTATION_STATEMENTS = {
    "claim_supported": "The retrieved source supports this claim.",
    "claim_partially_supported": "The retrieved source partially supports this claim.",
    "claim_not_supported": "The retrieved evidence does not substantiate this claim.",
    "claim_contradicted": "The retrieved evidence appears inconsistent with this claim.",
}


def build_claim_presentation(
    assessment: ClaimAssessmentResult,
) -> ClaimPresentation:
    """Map validated assessment status to bounded presentation language."""
    if not isinstance(assessment, ClaimAssessmentResult):
        raise TypeError(
            "Claim presentation requires a ClaimAssessmentResult."
        )

    try:
        statement = _CLAIM_PRESENTATION_STATEMENTS[assessment.status]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported claim assessment status: {assessment.status}"
        ) from exc

    return ClaimPresentation(
        status=assessment.status,
        statement=statement,
    )


CLAIM_ASSESSMENT_STATUSES = (
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
    "claim_contradicted",
)


def claim_assessment_output_schema() -> dict[str, Any]:
    """Return the strict structured-output schema for claim assessment."""
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": list(CLAIM_ASSESSMENT_STATUSES),
            },
            "reason": {
                "type": "string",
                "minLength": 1,
            },
        },
        "required": ["status", "reason"],
        "additionalProperties": False,
    }


def build_claim_assessment_prompt(
    claim: str,
    evidence: list[ClaimEvidence],
) -> str:
    """Build an evidence-bounded prompt for semantic claim assessment."""
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("Claim assessment requires a substantive claim.")

    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, ClaimEvidence) for item in evidence)
    ):
        raise ValueError(
            "Claim assessment prompt requires located ClaimEvidence."
        )

    evidence_blocks = []
    for index, item in enumerate(evidence, start=1):
        page_number = (
            str(item.page_number)
            if item.page_number is not None
            else "not available"
        )
        evidence_blocks.append(
            "\n".join(
                [
                    f"EVIDENCE {index}",
                    f"source: {item.source}",
                    f"locator: {item.locator}",
                    f"page_number: {page_number}",
                    "text:",
                    item.text,
                ]
            )
        )

    return f"""Assess the claim using only the supplied evidence.

CLAIM
{claim}

LOCATED EVIDENCE
{chr(10).join(chr(10) + block for block in evidence_blocks)}

RULES
Use only the supplied evidence when judging the claim.
Do not use outside knowledge.
Do not fill gaps using prior knowledge, assumptions, or information that is
not stated in the supplied evidence.

Assess all material components of the claim when present, including direction,
numerical value, population or sample, outcome or construct, comparison,
intervention or exposure, and important qualifier or context.

Use exactly one of these statuses:

claim_supported
The supplied evidence supports all material components of the claim.

claim_partially_supported
The supplied evidence supports part of the claim, but at least one material
component is absent, narrower, qualified differently, or not established.

claim_not_supported
Relevant supplied evidence does not sufficiently substantiate the claim, but
does not clearly establish a materially inconsistent statement.

claim_contradicted
The supplied evidence clearly establishes a material statement or result that
is inconsistent with the claim.

Absence of support is not contradiction. A mismatch between the claim and
evidence is not necessarily contrary evidence. Evidence about a different
referent or context, such as a different population, intervention or exposure,
outcome, or comparison, does not by itself contradict the claim. If the
evidence concerns only a different referent and provides no evidence about the
referent stated in the claim, use claim_not_supported, not claim_contradicted.

Use claim_contradicted only when the supplied evidence provides clear contrary
evidence about the same relevant referent and context. An opposite direction
or incompatible numerical value can be contrary evidence when it concerns the
same relevant referent and context.

OUTPUT DISCIPLINE
Decide the status before writing the reason.
The reason must be one concise sentence of no more than 30 words.
The reason must be consistent with the selected status.
Do not show deliberation, self-correction, or reconsideration in the reason.

Return only the required judgement fields: status and reason.
The reason must explain the judgement from the supplied evidence.
Do not return the claim, evidence, page information, locator, source, or any
other provenance field.
"""


def assess_located_claim(
    claim: str,
    evidence: list[ClaimEvidence],
    assessor,
) -> ClaimAssessmentResult:
    """Assess located evidence through an injected semantic assessor."""
    prompt = build_claim_assessment_prompt(
        claim=claim,
        evidence=evidence,
    )
    schema = claim_assessment_output_schema()

    assessor_output = assessor(
        prompt=prompt,
        schema=schema,
    )

    return build_claim_assessment(
        claim=claim,
        evidence=evidence,
        assessor_output=assessor_output,
    )


def build_claim_assessment(
    claim: str,
    evidence: list[ClaimEvidence],
    assessor_output: Any,
) -> ClaimAssessmentResult:
    """Validate assessor judgement and attach application-owned provenance."""
    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, ClaimEvidence) for item in evidence)
    ):
        raise ValueError(
            "Semantic claim assessment requires located ClaimEvidence."
        )

    if not isinstance(assessor_output, dict):
        raise ValueError("Assessor output must be an object.")

    expected_fields = {"status", "reason"}
    if set(assessor_output) != expected_fields:
        raise ValueError(
            "Assessor output must contain exactly 'status' and 'reason'."
        )

    status = assessor_output["status"]
    reason = assessor_output["reason"]

    if (
        not isinstance(status, str)
        or status not in CLAIM_ASSESSMENT_STATUSES
    ):
        raise ValueError("Assessor output contains an invalid status.")

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Assessor reason must be non-empty text.")

    return ClaimAssessmentResult(
        status=status,
        claim=claim,
        evidence=evidence,
        reasons=[reason.strip()],
    )


@dataclass
class DownloadedSource:
    """Raw resource obtained from a discovered scholarly source location.

    A successful download does not imply that substantive scholarly text
    has been extracted or that any academic claim has been supported.
    """

    status: str
    requested_url: str
    final_url: str
    content_type: str | None
    content: bytes
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HTTPHopResponse:
    """One HTTP response before redirect handling or source interpretation."""

    status_code: int
    location: str | None
    content_type: str | None
    content: bytes


@dataclass
class ExtractedPage:
    """Text extracted from one physical page of a source document."""
    page_number: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievedSource:
    """Substantive scholarly text retrieved for a bibliographic identifier."""

    status: str
    doi: str | None
    source: str
    text: str | None
    locator: str | None
    reasons: list[str]
    pages: list[ExtractedPage] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "doi": self.doi,
            "source": self.source,
            "text": self.text,
            "locator": self.locator,
            "reasons": self.reasons,
        }


def _claim_terms(value: str) -> set[str]:
    """Return deterministic searchable terms for local claim location."""
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for",
        "from", "in", "is", "it", "of", "on", "or", "that", "the",
        "this", "to", "was", "were", "with",
    }
    tokens = re.findall(r"[A-Za-z0-9]+(?:\.[0-9]+)?", value.lower())
    return {
        token
        for token in tokens
        if token not in stop_words and (len(token) > 1 or token.isdigit())
    }


def _is_candidate_overlap(
    claim_terms: set[str],
    passage_terms: set[str],
) -> bool:
    """Return whether lexical overlap is sufficient for candidate location."""
    if not claim_terms:
        return False

    overlap = claim_terms & passage_terms

    if len(overlap) < 2:
        return False

    return len(overlap) / len(claim_terms) >= 0.25


def locate_claim_passages(
    retrieved: RetrievedSource,
    claim: str,
    max_passages: int = 3,
) -> list[ClaimEvidence]:
    """Locate candidate source passages by deterministic lexical overlap."""
    if (
        retrieved.status != "retrieved"
        or not retrieved.text
        or not retrieved.locator
        or max_passages <= 0
    ):
        return []

    claim_terms = _claim_terms(claim)
    if not claim_terms:
        return []

    passages = [
        passage.strip()
        for passage in re.split(r"\n\s*\n", retrieved.text)
        if passage.strip()
    ]

    ranked = []
    for index, passage in enumerate(passages):
        passage_terms = _claim_terms(passage)
        overlap = claim_terms & passage_terms
        if not _is_candidate_overlap(claim_terms, passage_terms):
            continue

        numeric_matches = sum(
            1
            for token in overlap
            if any(char.isdigit() for char in token)
        )
        score = (numeric_matches, len(overlap), -index)
        ranked.append((score, passage))

    ranked.sort(reverse=True)

    return [
        ClaimEvidence(
            text=passage,
            locator=retrieved.locator,
            source=retrieved.source,
        )
        for _, passage in ranked[:max_passages]
    ]


def locate_claim_passages_in_pages(
    pages: list[ExtractedPage],
    claim: str,
    locator: str,
    source: str,
    max_passages: int = 3,
) -> list[ClaimEvidence]:
    """Locate candidate passages while preserving physical page provenance."""
    if not locator or max_passages <= 0:
        return []

    claim_terms = _claim_terms(claim)
    if not claim_terms:
        return []

    ranked = []

    for page_index, page in enumerate(pages):
        if not page.text:
            continue

        passages = [
            passage.strip()
            for passage in re.split(r"\n\s*\n", page.text)
            if passage.strip()
        ]

        for passage_index, passage in enumerate(passages):
            passage_terms = _claim_terms(passage)
            overlap = claim_terms & passage_terms
            if not _is_candidate_overlap(claim_terms, passage_terms):
                continue

            numeric_matches = sum(
                1
                for token in overlap
                if any(char.isdigit() for char in token)
            )

            score = (
                numeric_matches,
                len(overlap),
                -page_index,
                -passage_index,
            )

            ranked.append(
                (
                    score,
                    page.page_number,
                    passage,
                )
            )

    ranked.sort(reverse=True)

    return [
        ClaimEvidence(
            text=passage,
            locator=locator,
            source=source,
            page_number=page_number,
        )
        for _, page_number, passage in ranked[:max_passages]
    ]


def locate_pdf_claim_passages(
    content: bytes,
    claim: str,
    locator: str,
    source: str,
    max_passages: int = 3,
    reader_factory=PdfReader,
) -> list[ClaimEvidence]:
    """Extract PDF pages and locate candidate passages with page provenance."""
    pages = extract_pdf_pages(
        content,
        reader_factory=reader_factory,
    )

    return locate_claim_passages_in_pages(
        pages,
        claim,
        locator=locator,
        source=source,
        max_passages=max_passages,
    )


def locate_pdf_claim_from_location(
    location: "SourceLocation",
    claim: str,
    downloader,
    max_passages: int = 3,
    reader_factory=PdfReader,
) -> list[ClaimEvidence]:
    """Download a located PDF and preserve provenance through claim location."""
    if not location.pdf_url:
        raise SourceRetrievalError(
            "No PDF URL is available for page-aware claim location."
        )

    downloaded = downloader(location.pdf_url)

    if downloaded.status != "downloaded":
        raise SourceRetrievalError(
            "PDF source was not successfully downloaded."
        )

    return locate_pdf_claim_passages(
        downloaded.content,
        claim,
        locator=downloaded.final_url,
        source=location.source,
        max_passages=max_passages,
        reader_factory=reader_factory,
    )


def prepare_pdf_claim_support(
    location: "SourceLocation",
    claim: str,
    downloader,
    max_passages: int = 3,
    reader_factory=PdfReader,
) -> ClaimSupportResult:
    """Compose PDF retrieval, page-aware location, and claim-support state."""
    try:
        evidence = locate_pdf_claim_from_location(
            location,
            claim,
            downloader=downloader,
            max_passages=max_passages,
            reader_factory=reader_factory,
        )
    except SourceRetrievalError as exc:
        return ClaimSupportResult(
            status="source_not_retrieved",
            source_status="not_retrieved",
            claim_status="not_assessed",
            doi=location.doi,
            evidence=[],
            reasons=[str(exc)],
        )

    return prepare_page_aware_claim_support(
        doi=location.doi,
        evidence=evidence,
        search_attempted=bool(_claim_terms(claim)),
    )


def prepare_page_aware_claim_support(
    doi: str | None,
    evidence: list[ClaimEvidence],
    search_attempted: bool,
) -> ClaimSupportResult:
    """Map page-aware claim location into claim-support state semantics."""
    if evidence:
        return ClaimSupportResult(
            status="claim_located",
            source_status="retrieved",
            claim_status="located",
            doi=doi,
            evidence=evidence,
            reasons=["Candidate claim passage located in retrieved source."],
        )

    if search_attempted:
        return ClaimSupportResult(
            status="claim_not_located",
            source_status="retrieved",
            claim_status="not_located",
            doi=doi,
            evidence=[],
            reasons=[
                "Retrieved source was searched but no candidate claim passage was located."
            ],
        )

    return ClaimSupportResult(
        status="claim_not_assessed",
        source_status="retrieved",
        claim_status="not_assessed",
        doi=doi,
        evidence=[],
        reasons=[
            "Source was retrieved but claim location was not meaningfully attempted."
        ],
    )


def prepare_claim_support(
    retrieved: RetrievedSource,
    claim: str,
    max_passages: int = 3,
) -> ClaimSupportResult:
    """Prepare a claim for later support assessment without judging support."""
    if retrieved.status != "retrieved" or not retrieved.text:
        return ClaimSupportResult(
            status="source_not_retrieved",
            source_status=retrieved.status,
            claim_status="not_assessed",
            doi=_normalise_doi(retrieved.doi),
            evidence=[],
            reasons=[
                "Substantive source text was not available for claim location."
            ],
        )

    if (
        not retrieved.locator
        or max_passages <= 0
        or not _claim_terms(claim)
    ):
        return ClaimSupportResult(
            status="claim_not_assessed",
            source_status="retrieved",
            claim_status="not_assessed",
            doi=_normalise_doi(retrieved.doi),
            evidence=[],
            reasons=[
                "Claim passage location could not be meaningfully attempted."
            ],
        )

    if retrieved.pages is not None:
        evidence = locate_claim_passages_in_pages(
            retrieved.pages,
            claim,
            locator=retrieved.locator,
            source=retrieved.source,
            max_passages=max_passages,
        )
    else:
        evidence = locate_claim_passages(
            retrieved,
            claim,
            max_passages=max_passages,
        )

    if not evidence:
        return ClaimSupportResult(
            status="claim_not_located",
            source_status="retrieved",
            claim_status="not_located",
            doi=_normalise_doi(retrieved.doi),
            evidence=[],
            reasons=[
                "Source text was retrieved but no candidate claim passage was located."
            ],
        )

    return ClaimSupportResult(
        status="claim_located",
        source_status="retrieved",
        claim_status="located",
        doi=_normalise_doi(retrieved.doi),
        evidence=evidence,
        reasons=[
            "Candidate claim evidence was located but support has not been assessed."
        ],
    )


def extract_pdf_pages(
    content: bytes,
    reader_factory=PdfReader,
) -> list[ExtractedPage]:
    """Extract text while preserving one-based physical PDF page identity."""
    try:
        reader = reader_factory(BytesIO(content))
        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            text = page_text.strip() if isinstance(page_text, str) else ""
            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=text,
                )
            )

        return pages

    except PyPdfError as exc:
        raise SourceRetrievalError(
            "PDF page text extraction failed."
        ) from exc


def extract_pdf_text(
    content: bytes,
    reader_factory=PdfReader,
) -> str:
    """Extract available text from PDF bytes in document page order."""
    try:
        reader = reader_factory(BytesIO(content))
        pages = []

        for page in reader.pages:
            page_text = page.extract_text()
            if isinstance(page_text, str) and page_text.strip():
                pages.append(page_text.strip())

        return "\n\n".join(pages)

    except PyPdfError as exc:
        raise SourceRetrievalError(
            "PDF text extraction failed."
        ) from exc


def extract_downloaded_source(
    downloaded: DownloadedSource,
    doi: str | None,
    source: str,
    extractor,
) -> RetrievedSource:
    """Extract substantive text from already-downloaded source bytes.

    The extractor receives only the downloaded bytes. A successful HTTP
    download does not itself imply successful substantive retrieval.
    """
    try:
        text = extractor(downloaded.content)
    except SourceRetrievalError:
        return RetrievedSource(
            status="not_retrieved",
            doi=_normalise_doi(doi),
            source=source,
            text=None,
            locator=None,
            reasons=["Source text extraction failed."],
        )

    if not isinstance(text, str) or not text.strip():
        return RetrievedSource(
            status="not_retrieved",
            doi=_normalise_doi(doi),
            source=source,
            text=None,
            locator=None,
            reasons=["Extracted source content was empty."],
        )

    return RetrievedSource(
        status="retrieved",
        doi=_normalise_doi(doi),
        source=source,
        text=text,
        locator=downloaded.final_url,
        reasons=["Substantive source text was extracted from downloaded content."],
    )


def retrieve_source(doi: str, retriever) -> RetrievedSource:
    """Retrieve scholarly source text using a bibliographic identifier only.

    The retriever deliberately receives only the DOI. Academic questions,
    claims, manuscripts, reviewer notes, and other substantive user content
    do not cross this boundary.
    """
    return retriever(doi)


@dataclass
class SourceLocation:
    """A discovered location from which scholarly content may be retrieved."""

    status: str
    doi: str | None
    source: str
    landing_page_url: str | None
    pdf_url: str | None
    is_oa: bool | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_doi(doi: str | None) -> str | None:
    """Normalise a DOI without resolving or retrieving it."""
    if not doi:
        return None

    cleaned = doi.strip()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    return cleaned.lower() or None


def discover_openalex_source(doi: str, work_getter) -> SourceLocation:
    """Discover an accessible scholarly source location using DOI only.

    This function performs discovery, not substantive source retrieval.
    The injected work_getter receives only the DOI.
    """
    item = work_getter(doi)

    if not item:
        return SourceLocation(
            status="location_not_found",
            doi=_normalise_doi(doi),
            source="openalex",
            landing_page_url=None,
            pdf_url=None,
            is_oa=None,
            reasons=["OpenAlex returned no work for the supplied DOI."],
        )

    location = item.get("best_oa_location") or {}

    landing_page_url = location.get("landing_page_url")
    pdf_url = location.get("pdf_url")
    is_oa = location.get("is_oa")

    status = (
        "location_found"
        if landing_page_url or pdf_url
        else "location_not_found"
    )

    reasons = [
        "OpenAlex supplied an accessible source location."
        if status == "location_found"
        else "OpenAlex supplied no accessible source location."
    ]

    return SourceLocation(
        status=status,
        doi=_normalise_doi(item.get("doi") or doi),
        source="openalex",
        landing_page_url=landing_page_url,
        pdf_url=pdf_url,
        is_oa=is_oa,
        reasons=reasons,
    )


def retrieve_pdf_source_from_location(
    location: SourceLocation,
    downloader=None,
    extractor=None,
    reader_factory=PdfReader,
) -> RetrievedSource:
    """Download and extract a discovered PDF source location."""
    if downloader is None:
        downloader = download_validated_http_source

    if not location.pdf_url:
        return RetrievedSource(
            status="not_retrieved",
            doi=_normalise_doi(location.doi),
            source=location.source,
            text=None,
            locator=None,
            reasons=["No PDF source URL was available for retrieval."],
        )

    try:
        downloaded = downloader(location.pdf_url)
    except SourceRetrievalError:
        return RetrievedSource(
            status="not_retrieved",
            doi=_normalise_doi(location.doi),
            source=location.source,
            text=None,
            locator=None,
            reasons=["PDF source download failed."],
        )

    if extractor is not None:
        return extract_downloaded_source(
            downloaded,
            doi=location.doi,
            source=location.source,
            extractor=extractor,
        )

    try:
        pages = extract_pdf_pages(
            downloaded.content,
            reader_factory=reader_factory,
        )
    except SourceRetrievalError:
        return RetrievedSource(
            status="not_retrieved",
            doi=_normalise_doi(location.doi),
            source=location.source,
            text=None,
            locator=None,
            reasons=["Source text extraction failed."],
        )

    text = "\n\n".join(
        page.text
        for page in pages
        if page.text
    )

    if not text.strip():
        return RetrievedSource(
            status="not_retrieved",
            doi=_normalise_doi(location.doi),
            source=location.source,
            text=None,
            locator=None,
            reasons=["Extracted source content was empty."],
        )

    return RetrievedSource(
        status="retrieved",
        doi=_normalise_doi(location.doi),
        source=location.source,
        text=text,
        locator=downloaded.final_url,
        reasons=[
            "Substantive source text was extracted from downloaded content."
        ],
        pages=pages,
    )


def retrieve_source_from_location(
    location: SourceLocation,
    fetcher,
) -> RetrievedSource:
    """Retrieve substantive source text from a discovered location.

    The fetcher receives only the discovered source URL. Academic questions,
    claims, manuscripts, reviewer notes, and other substantive user content
    do not cross this boundary.
    """
    if location.landing_page_url:
        url = location.landing_page_url
        locator = "landing_page"
    elif location.pdf_url:
        url = location.pdf_url
        locator = "pdf"
    else:
        return RetrievedSource(
            status="not_retrieved",
            doi=location.doi,
            source=location.source,
            text=None,
            locator=None,
            reasons=["No retrievable source URL was available."],
        )

    try:
        text = fetcher(url)
    except SourceRetrievalError:
        return RetrievedSource(
            status="not_retrieved",
            doi=location.doi,
            source=location.source,
            text=None,
            locator=None,
            reasons=["Source retrieval failed."],
        )

    if not isinstance(text, str) or not text.strip():
        return RetrievedSource(
            status="not_retrieved",
            doi=location.doi,
            source=location.source,
            text=None,
            locator=None,
            reasons=["Fetched source content was empty."],
        )

    return RetrievedSource(
        status="retrieved",
        doi=location.doi,
        source=location.source,
        text=text,
        locator=locator,
        reasons=["Substantive source text was retrieved."],
    )



@dataclass
class ValidatedHTTPDestination:
    """Canonical hostname and network addresses approved for one HTTP hop."""

    hostname: str
    addresses: list[str]


def resolve_validated_http_destination(
    url: str,
    resolver=None,
) -> ValidatedHTTPDestination:
    """Validate an HTTP(S) URL and retain its approved network destination."""
    parsed = urlparse(url)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise SourceRetrievalError("Source URL is not an eligible HTTP(S) URL.")

    if parsed.username is not None or parsed.password is not None:
        raise SourceRetrievalError(
            "Source URL must not contain embedded credentials."
        )

    try:
        parsed.port
    except ValueError as exc:
        raise SourceRetrievalError(
            "Source URL contains an invalid port."
        ) from exc

    hostname = parsed.hostname

    if not hostname:
        raise SourceRetrievalError("Source URL has no eligible hostname.")

    hostname = hostname.rstrip(".").lower()

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise SourceRetrievalError("Source URL targets a local network destination.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        # Numeric-looking non-canonical hosts such as 127.1 may be interpreted
        # as IP addresses by lower networking layers. Reject them rather than
        # allowing them to fall through as ordinary DNS hostnames.
        if all(character in "0123456789." for character in hostname):
            raise SourceRetrievalError(
                "Source URL contains a non-canonical numeric network destination."
            )

        if resolver is None:
            return ValidatedHTTPDestination(
                hostname=hostname,
                addresses=[],
            )

        try:
            resolved_addresses = resolver(hostname)
        except SourceRetrievalError:
            raise
        except Exception as exc:
            raise SourceRetrievalError(
                "Source hostname could not be resolved safely."
            ) from exc

        if not resolved_addresses:
            raise SourceRetrievalError(
                "Source hostname did not resolve to an eligible address."
            )

        validated_addresses = []

        for resolved in resolved_addresses:
            try:
                resolved_address = ipaddress.ip_address(resolved)
            except ValueError as exc:
                raise SourceRetrievalError(
                    "Source hostname resolved to an invalid network address."
                ) from exc

            if not resolved_address.is_global:
                raise SourceRetrievalError(
                    "Source hostname resolves to a non-public network destination."
                )

            validated_addresses.append(str(resolved_address))

        return ValidatedHTTPDestination(
            hostname=hostname,
            addresses=validated_addresses,
        )

    if not address.is_global:
        raise SourceRetrievalError(
            "Source URL targets a non-public network destination."
        )

    return ValidatedHTTPDestination(
        hostname=hostname,
        addresses=[str(address)],
    )


def _validate_http_url(url: str, resolver=None) -> None:
    """Compatibility wrapper for callers that need validation only."""
    resolve_validated_http_destination(
        url,
        resolver=resolver,
    )

def safe_http_fetch(url: str, http_get, resolver=None) -> DownloadedSource:
    """Validate source URLs around delegation to an HTTP client.

    Both requested and final URLs must be eligible HTTP(S) locations. When a
    resolver is supplied, hostname resolutions must contain only public IP
    addresses before HTTP delegation.
    """
    _validate_http_url(url, resolver=resolver)

    downloaded = http_get(url)

    if not isinstance(downloaded, DownloadedSource):
        raise TypeError("HTTP client must return DownloadedSource.")

    _validate_http_url(downloaded.final_url, resolver=resolver)

    return downloaded


def fetch_validated_http_source(
    url: str,
    hostname: str,
    validated_addresses: list[str],
    connection_adapter,
) -> DownloadedSource:
    """Delegate HTTP transfer using an explicitly validated destination.

    This boundary independently requires every supplied destination address
    to be a canonical public IP address before invoking the connection
    adapter. It does not itself perform DNS resolution or network access.
    """
    if not validated_addresses:
        raise SourceRetrievalError(
            "Validated HTTP connection requires at least one network address."
        )

    for supplied_address in validated_addresses:
        try:
            address = ipaddress.ip_address(supplied_address)
        except ValueError as exc:
            raise SourceRetrievalError(
                "Validated HTTP connection received an invalid network address."
            ) from exc

        if not address.is_global:
            raise SourceRetrievalError(
                "Validated HTTP connection received a non-public network address."
            )

    downloaded = connection_adapter(
        url,
        hostname,
        validated_addresses,
    )

    if not isinstance(downloaded, DownloadedSource):
        raise TypeError("Connection adapter must return DownloadedSource.")

    return downloaded


class DeadlineNetworkStream(httpcore.NetworkStream):
    """Cap each blocking network operation by one absolute deadline."""

    def __init__(self, stream, deadline: float, monotonic=time.monotonic):
        self._stream = stream
        self._deadline = deadline
        self._monotonic = monotonic

    def _remaining_timeout(self, timeout: float | None) -> float:
        remaining = self._deadline - self._monotonic()

        if remaining <= 0:
            raise httpcore.TimeoutException(
                "HTTP source retrieval exceeded its time limit."
            )

        if timeout is None:
            return remaining

        return min(timeout, remaining)

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._stream.read(
            max_bytes,
            timeout=self._remaining_timeout(timeout),
        )

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._stream.write(
            buffer,
            timeout=self._remaining_timeout(timeout),
        )

    def close(self) -> None:
        self._stream.close()

    def start_tls(
        self,
        ssl_context,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ):
        stream = self._stream.start_tls(
            ssl_context=ssl_context,
            server_hostname=server_hostname,
            timeout=self._remaining_timeout(timeout),
        )

        return DeadlineNetworkStream(
            stream,
            deadline=self._deadline,
            monotonic=self._monotonic,
        )

    def get_extra_info(self, info: str):
        return self._stream.get_extra_info(info)


class ValidatedAddressSyncBackend(httpcore.SyncBackend):
    """Connect only to network addresses validated before backend creation.

    DNS resolution is deliberately outside this backend. The HTTP connection
    retains the original origin hostname for HTTP/TLS semantics, while TCP is
    delegated only to a supplied canonical public IP address.
    """

    def __init__(
        self,
        validated_addresses: list[str],
        deadline: float | None = None,
        monotonic=time.monotonic,
    ):
        super().__init__()

        self._deadline = deadline
        self._monotonic = monotonic

        if not validated_addresses:
            raise SourceRetrievalError(
                "Validated-address backend requires at least one network address."
            )

        addresses = []

        for supplied_address in validated_addresses:
            try:
                address = ipaddress.ip_address(supplied_address)
            except ValueError as exc:
                raise SourceRetrievalError(
                    "Validated-address backend received an invalid network address."
                ) from exc

            if not address.is_global:
                raise SourceRetrievalError(
                    "Validated-address backend received a non-public network address."
                )

            addresses.append(str(address))

        self._validated_addresses = addresses

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        if self._deadline is not None:
            remaining = self._deadline - self._monotonic()

            if remaining <= 0:
                raise httpcore.ConnectTimeout(
                    "HTTP source retrieval exceeded its time limit."
                )

            if timeout is None:
                timeout = remaining
            else:
                timeout = min(timeout, remaining)

        stream = super().connect_tcp(
            host=self._validated_addresses[0],
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

        if self._deadline is None:
            return stream

        return DeadlineNetworkStream(
            stream,
            deadline=self._deadline,
            monotonic=self._monotonic,
        )


class PinnedSyncBackend(httpcore.SyncBackend):
    """Pin HTTP TCP connections to a validated public IP address.

    The HTTP origin hostname is resolved and validated here, but the parent
    httpcore backend receives a numeric IP address as the TCP destination.
    This prevents an independent hostname resolution at connection time while
    leaving httpcore responsible for socket handling and TLS streams.
    """

    def __init__(self, resolver):
        super().__init__()
        self._resolver = resolver

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        resolved_addresses = self._resolver(host)

        if not resolved_addresses:
            raise SourceRetrievalError(
                "Source hostname did not resolve to an eligible address."
            )

        validated_addresses = []

        for supplied_address in resolved_addresses:
            try:
                address = ipaddress.ip_address(supplied_address)
            except ValueError as exc:
                raise SourceRetrievalError(
                    "Source hostname resolved to an invalid network address."
                ) from exc

            if not address.is_global:
                raise SourceRetrievalError(
                    "Source hostname resolves to a non-public network destination."
                )

            validated_addresses.append(str(address))

        return super().connect_tcp(
            host=validated_addresses[0],
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

def fetch_with_validated_redirects(
    url: str,
    requester,
    max_redirects: int = 5,
    resolver=None,
):
    """Follow redirects only after validating each destination URL."""
    current_url = url
    redirects_followed = 0

    while True:
        _validate_http_url(current_url, resolver=resolver)
        response = requester(current_url)

        status_code = response["status_code"]

        if status_code not in {301, 302, 303, 307, 308}:
            return response

        location = response.get("location")

        if not location:
            raise SourceRetrievalError(
                "Redirect response did not provide a destination."
            )

        if redirects_followed >= max_redirects:
            raise SourceRetrievalError(
                "Source retrieval exceeded the redirect limit."
            )

        next_url = urljoin(current_url, location)

        current_url = next_url
        redirects_followed += 1


def request_validated_http_hop(
    url: str,
    destination: ValidatedHTTPDestination,
    connection_factory=httpcore.HTTPConnection,
    max_bytes: int = 20 * 1024 * 1024,
    deadline: float | None = None,
    monotonic=time.monotonic,
) -> HTTPHopResponse:
    """Issue one HTTP GET using only the already-validated destination."""
    if max_bytes < 0:
        raise ValueError("max_bytes must not be negative.")

    if deadline is not None:
        remaining = deadline - monotonic()

        if remaining <= 0:
            raise SourceRetrievalError(
                "HTTP source retrieval exceeded its time limit."
            )
    else:
        remaining = None

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()

    if scheme not in {"http", "https"}:
        raise SourceRetrievalError(
            "Validated HTTP hop requires an HTTP(S) URL."
        )

    request_hostname = (parsed.hostname or "").lower().rstrip(".")
    destination_hostname = destination.hostname.lower().rstrip(".")

    if not request_hostname or request_hostname != destination_hostname:
        raise SourceRetrievalError(
            "HTTP request hostname does not match validated destination."
        )

    if not destination.addresses:
        raise SourceRetrievalError(
            "Validated HTTP hop requires approved network addresses."
        )

    default_port = 443 if scheme == "https" else 80
    port = parsed.port or default_port

    origin = httpcore.Origin(
        scheme=scheme.encode("ascii"),
        host=destination.hostname.encode("idna"),
        port=port,
    )

    backend = ValidatedAddressSyncBackend(
        validated_addresses=destination.addresses,
        deadline=deadline,
        monotonic=monotonic,
    )

    connection = connection_factory(
        origin=origin,
        network_backend=backend,
        http1=True,
        http2=False,
    )

    host = parsed.hostname or ""

    if ":" in host:
        host = f"[{host}]"

    authority = host

    if port != default_port:
        authority = f"{authority}:{port}"

    request_extensions = {}

    if remaining is not None:
        request_extensions["timeout"] = {
            "connect": remaining,
            "read": remaining,
            "write": remaining,
            "pool": remaining,
        }

    request = httpcore.Request(
        method="GET",
        url=url,
        headers=[(b"Host", authority.encode("ascii"))],
        extensions=request_extensions,
    )

    response = None

    try:
        response = connection.handle_request(request)

        location = None
        content_type = None

        for name, value in response.headers:
            header_name = name.lower()

            if header_name == b"location":
                location = value.decode("latin-1")
            elif header_name == b"content-type":
                content_type = value.decode("latin-1")

        chunks = []
        total_bytes = 0

        for chunk in response.iter_stream():
            if deadline is not None and monotonic() >= deadline:
                raise SourceRetrievalError(
                    "HTTP source retrieval exceeded its time limit."
                )

            total_bytes += len(chunk)

            if total_bytes > max_bytes:
                raise SourceRetrievalError(
                    "HTTP response exceeded the maximum permitted body size."
                )

            chunks.append(chunk)

        content = b"".join(chunks)

        return HTTPHopResponse(
            status_code=response.status,
            location=location,
            content_type=content_type,
            content=content,
        )
    except (
        httpcore.ConnectionNotAvailable,
        httpcore.ProxyError,
        httpcore.NetworkError,
        httpcore.TimeoutException,
        httpcore.ProtocolError,
        httpcore.UnsupportedProtocol,
    ) as exc:
        raise SourceRetrievalError(
            "HTTP source retrieval failed during transport."
        ) from exc
    finally:
        if response is not None:
            response.close()
        connection.close()


def _fetch_with_validated_destinations_and_final_url(
    url: str,
    requester,
    max_redirects: int = 5,
    resolver=None,
    deadline: float | None = None,
    monotonic=time.monotonic,
):
    """Follow validated redirects and retain the final requested URL."""
    current_url = url
    redirects_followed = 0

    while True:
        if deadline is not None and monotonic() >= deadline:
            raise SourceRetrievalError(
                "HTTP source retrieval exceeded its time limit."
            )

        destination = resolve_validated_http_destination(
            current_url,
            resolver=resolver,
        )
        response = requester(
            current_url,
            destination,
        )

        status_code = response.status_code

        if status_code not in {301, 302, 303, 307, 308}:
            return response, current_url

        location = response.location

        if not location:
            raise SourceRetrievalError(
                "Redirect response did not provide a destination."
            )

        if redirects_followed >= max_redirects:
            raise SourceRetrievalError(
                "Source retrieval exceeded the redirect limit."
            )

        current_url = urljoin(current_url, location)
        redirects_followed += 1


def fetch_with_validated_destinations(
    url: str,
    requester,
    max_redirects: int = 5,
    resolver=None,
):
    """Follow redirects using the exact destination validated for each hop."""
    response, _ = _fetch_with_validated_destinations_and_final_url(
        url,
        requester=requester,
        max_redirects=max_redirects,
        resolver=resolver,
    )
    return response


def resolve_system_http_hostname(hostname: str) -> list[str]:
    """Resolve a hostname using system DNS for subsequent address validation."""
    records = socket.getaddrinfo(
        hostname,
        0,
        type=socket.SOCK_STREAM,
    )

    addresses = []

    for _family, _socktype, _proto, _canonname, sockaddr in records:
        address = sockaddr[0]

        if address not in addresses:
            addresses.append(address)

    return addresses


def download_validated_http_source(
    url: str,
    requester=request_validated_http_hop,
    max_redirects: int = 5,
    resolver=None,
    timeout: float = 30.0,
    monotonic=time.monotonic,
) -> DownloadedSource:
    """Download a source through the validated HTTP retrieval path."""
    if timeout <= 0:
        raise ValueError("timeout must be positive.")

    if resolver is None:
        resolver = resolve_system_http_hostname

    deadline = monotonic() + timeout

    if requester is request_validated_http_hop:
        def bounded_requester(current_url, destination):
            return requester(
                current_url,
                destination,
                deadline=deadline,
                monotonic=monotonic,
            )
    else:
        bounded_requester = requester

    response, final_url = _fetch_with_validated_destinations_and_final_url(
        url,
        requester=bounded_requester,
        max_redirects=max_redirects,
        resolver=resolver,
        deadline=deadline,
        monotonic=monotonic,
    )

    if not 200 <= response.status_code < 300:
        raise SourceRetrievalError(
            f"Source download returned HTTP status {response.status_code}."
        )

    return DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url=final_url,
        content_type=response.content_type,
        content=response.content,
        reasons=["Source bytes were downloaded through validated HTTP retrieval."],
    )
