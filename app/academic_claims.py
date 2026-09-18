"""Claim-support structures for Academic Chat.

This module keeps source retrieval and substantive claim assessment separate
from bibliographic identity verification.

A failure to retrieve or locate evidence must not be interpreted as evidence
that an academic claim is false or unsupported.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ClaimEvidence:
    """An inspectable passage used when assessing a claim."""

    text: str
    locator: str
    source: str

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


@dataclass
class RetrievedSource:
    """Substantive scholarly text retrieved for a bibliographic identifier."""

    status: str
    doi: str | None
    source: str
    text: str | None
    locator: str | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
