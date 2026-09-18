"""Claim-support structures for Academic Chat.

This module keeps source retrieval and substantive claim assessment separate
from bibliographic identity verification.

A failure to retrieve or locate evidence must not be interpreted as evidence
that an academic claim is false or unsupported.
"""

from dataclasses import asdict, dataclass
import ipaddress
from typing import Any
from urllib.parse import urlparse


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


class SourceRetrievalError(RuntimeError):
    """Expected failure while retrieving or extracting a scholarly source."""


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



def _validate_http_url(url: str, resolver=None) -> None:
    """Reject URLs that are not eligible public HTTP(S) source locations."""
    parsed = urlparse(url)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise SourceRetrievalError("Source URL is not an eligible HTTP(S) URL.")

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

        if resolver is not None:
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
    else:
        if not address.is_global:
            raise SourceRetrievalError(
                "Source URL targets a non-public network destination."
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
