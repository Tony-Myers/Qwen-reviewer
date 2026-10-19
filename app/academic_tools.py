"""
Academic reference verification tools.

This module is deliberately independent of the reviewer pipeline and the
language-model backend. It queries scholarly metadata services and returns
structured bibliographic evidence.

Important epistemic boundary:
    A verified reference establishes that a bibliographic record exists and
    that supplied metadata are compatible with it. It does NOT establish that
    the source supports a particular academic claim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
import json
import re
import time
import traceback
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, urlopen


CROSSREF_API = "https://api.crossref.org"
OPENALEX_API = "https://api.openalex.org"
USER_AGENT = (
    "QwenReviewer/academic-reference-tools "
    "(https://github.com/Tony-Myers/Qwen-reviewer)"
)


# Distinct from a completed search that did not verify a reference.
VERIFICATION_STATUS_UNAVAILABLE = "unavailable"


class BibliographicLookupError(RuntimeError):
    """An expected failure at the external metadata transport/response boundary."""

    def __init__(self, message: str, *, service: str, operation: str,
                 code: str, http_status: int | None = None):
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class BibliographicIssue:
    """Public issue metadata; never raw URLs, response bodies or tracebacks."""

    stage: str
    service: str
    outcome: str
    code: str
    http_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.http_status is None:
            result.pop("http_status")
        return result


def _lookup_operation(service: str, url: str) -> str:
    """Identify the existing transport operation without exposing its URL."""
    parsed = urlsplit(url)
    if service == "crossref":
        return "doi_lookup" if parsed.path.startswith("/works/") else "title_search"
    filters = parse_qs(parsed.query).get("filter", [""])[0]
    return "doi_lookup" if filters.startswith("doi:") else "title_search"


def _lookup_failure(service: str, url: str, exc: Exception) -> BibliographicLookupError:
    if isinstance(exc, HTTPError):
        code = "http_error"
    elif isinstance(exc, TimeoutError) or (
        isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError)
    ):
        code = "timeout"
    elif isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        code = "malformed_response"
    else:
        code = "network_error"
    name = "Crossref" if service == "crossref" else "OpenAlex"
    return BibliographicLookupError(
        f"{name} request failed: {exc}", service=service,
        operation=_lookup_operation(service, url), code=code,
        http_status=exc.code if isinstance(exc, HTTPError) else None,
    )


def _validate_bibliographic_response(data: Any, service: str, url: str) -> dict[str, Any]:
    """Validate external containers consumed by adapters, not application logic.

    Optional metadata remains optional. Empty result arrays are successful
    searches, whereas a missing/wrong envelope is not an empty search.
    """
    def require(condition: bool, field: str) -> None:
        if not condition:
            raise BibliographicLookupError(
                f"{service} response has invalid {field} structure.",
                service=service, operation=_lookup_operation(service, url),
                code="malformed_response",
            )

    def optional_container(obj, key, kind):
        value = obj.get(key)
        require(value is None or isinstance(value, kind), key)
        return value if value is not None else kind()

    require(isinstance(data, dict), "root")
    if service == "crossref":
        require(isinstance(data.get("message"), dict), "message")
        if _lookup_operation(service, url) == "doi_lookup":
            items = [data["message"]]
        else:
            require(isinstance(data["message"].get("items"), list), "message.items")
            items = data["message"]["items"]
        for item in items:
            require(isinstance(item, dict), "item")
            for key in ("title", "subtitle", "container-title"):
                values = optional_container(item, key, list)
                require(all(isinstance(v, str) for v in values), key)
            for author in optional_container(item, "author", list):
                require(isinstance(author, dict), "author")
            for key in ("published-print", "published-online", "published", "issued"):
                date = item.get(key, {})
                require(isinstance(date, dict), key)
                parts = optional_container(date, "date-parts", list)
                require(all(isinstance(part, list) for part in parts), "date-parts")
    else:
        require(isinstance(data.get("results"), list), "results")
        for item in data["results"]:
            require(isinstance(item, dict), "result")
            for authorship in optional_container(item, "authorships", list):
                require(isinstance(authorship, dict), "authorship")
                optional_container(authorship, "author", dict)
            location = optional_container(item, "primary_location", dict)
            optional_container(location, "source", dict)
    return data


@dataclass
class ReferenceCandidate:
    title: str
    authors: list[str]
    year: int | None
    venue: str
    doi: str
    work_type: str
    source: str = "crossref"
    title_similarity: float | None = None
    # Crossref splits many book titles into a main title and a subtitle, and
    # records a book's publisher and series separately from container-title.
    # venue keeps its existing meaning (the first container-title) for
    # display and cross-database corroboration; these fields let matching
    # read a record by its bibliographic type instead of as a journal article.
    subtitle: str = ""
    publisher: str = ""
    container_titles: list[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    status: str
    candidate: ReferenceCandidate | None
    reasons: list[str]
    claim_verified: bool = False
    related_candidate: ReferenceCandidate | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CorroborationResult:
    status: str
    crossref: ReferenceCandidate | None
    openalex: ReferenceCandidate | None
    same_doi: bool
    title_similarity: float | None
    author_agreement: bool | None
    venue_similarity: float | None
    year_difference: int | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AcademicReferenceResult:
    crossref_verification: VerificationResult
    doi_corroboration: CorroborationResult | None
    related_corroboration: CorroborationResult | None
    identity_conflict: bool
    reasons: list[str]
    corroboration_status: str = "complete"
    claim_verified: bool = False

    issues: list[BibliographicIssue] = field(default_factory=list)

    def bibliographic_notice(self) -> str | None:
        if self.crossref_verification.status == VERIFICATION_STATUS_UNAVAILABLE:
            return "Bibliographic verification could not be completed."
        if any(i.outcome == "skipped" and i.code == "unsafe_title_query"
               for i in self.issues):
            return ("Title corroboration not attempted. The title could not safely "
                    "be represented in the supported OpenAlex title query. "
                    "Independent bibliographic corroboration is incomplete.")
        if self.corroboration_status != "complete":
            return "Independent bibliographic corroboration could not be completed."
        return None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.issues:
            result["issues"] = [issue.to_dict() for issue in self.issues]
        else:
            result.pop("issues")
        notice = self.bibliographic_notice()
        if notice:
            result["bibliographic_notice"] = notice
        return result


def _get_json(
    url: str,
    timeout: float = 10.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """
    Retrieve JSON from Crossref with bounded handling of HTTP 429 responses.

    Retry-After is honoured when supplied. Otherwise a short exponential
    backoff is used. Other HTTP and network errors fail immediately.
    """
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    for attempt in range(max_attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                return _validate_bibliographic_response(
                    json.load(response), "crossref", url
                )

        except HTTPError as exc:
            if exc.code != 429 or attempt == max_attempts - 1:
                raise _lookup_failure("crossref", url, exc) from exc

            retry_after = exc.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except (TypeError, ValueError):
                delay = 2 ** attempt

            time.sleep(min(delay, 10.0))

        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise _lookup_failure("crossref", url, exc) from exc

    raise RuntimeError("Crossref request failed after retries.")


def _normalise_text(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        _normalise_text(a),
        _normalise_text(b),
    ).ratio()


# Crossref work types grouped by what an overloaded proposal "venue" can
# legitimately name. A journal-level item's venue is its container (journal).
# A whole book's venue may be its publisher or its series. A chapter's may be
# its containing book, that book's series, or the publisher.
BOOK_TYPES = frozenset({"book", "monograph", "edited-book", "reference-book"})
CHAPTER_TYPES = frozenset({"book-chapter", "book-part", "book-section"})

# Words that say what kind of organisation a publisher is rather than which
# one. Only publisher names are compared this way; venue matching in general
# is not loosened.
_PUBLISHER_GENERIC_TOKENS = frozenset({
    "and", "co", "company", "corporation", "gmbh", "group", "inc",
    "international", "limited", "llc", "ltd", "media", "press", "publisher",
    "publishers", "publishing", "sons", "university", "verlag",
})


def _full_titles(candidate: "ReferenceCandidate") -> list[str]:
    """The record's title alone and, when Crossref splits it, with subtitle."""
    titles = [candidate.title] if candidate.title else []
    if candidate.title and candidate.subtitle:
        titles.append(f"{candidate.title}: {candidate.subtitle}")
    return titles


def _candidate_title_similarity(
    query_title: str,
    candidate: "ReferenceCandidate",
) -> float:
    """Best title similarity over the main title and main title + subtitle.

    The similarity threshold is unchanged: a proposal must still closely match
    one complete form of the record's title.
    """
    return max(
        (_title_similarity(query_title, title) for title in _full_titles(candidate)),
        default=0.0,
    )


def _publisher_core_tokens(name: str) -> set[str]:
    return {
        token
        for token in _normalise_text(name).split()
        if token not in _PUBLISHER_GENERIC_TOKENS
    }


def _publisher_matches(supplied: str, publisher: str) -> bool:
    """Whether two publisher names name the same publisher.

    "John Wiley & Sons" and "Wiley", or "Springer New York" and "Springer",
    differ only by forenames, places and corporate words. Names match when
    the distinctive words of one are all among those of the other. Generic
    words ("University", "Press", "Publishing") never count on their own, so
    "Oxford University Press" does not match "Cambridge University Press".

    A university press matches only another university press: without that,
    "Cambridge University Press" reduces to "cambridge" and would match
    "Cambridge Scholars Publishing".
    """
    if not supplied or not publisher:
        return False
    if _title_similarity(supplied, publisher) >= 0.90:
        return True
    if (
        ("university" in _normalise_text(supplied).split())
        != ("university" in _normalise_text(publisher).split())
    ):
        return False
    a = _publisher_core_tokens(supplied)
    b = _publisher_core_tokens(publisher)
    if not a or not b:
        return False
    return a <= b or b <= a


def _candidate_venue_matches(
    supplied: str,
    candidate: "ReferenceCandidate",
) -> bool:
    """Interpret the proposal's venue according to the record's type.

    Journal-level and other records: compared with the journal/container
    title exactly as before. Books: the publisher or a series/container
    title. Chapters: the containing book, its series, or the publisher.
    Only fields Crossref supplies are compared.
    """
    containers = list(candidate.container_titles) or (
        [candidate.venue] if candidate.venue else []
    )
    work_type = candidate.work_type

    if work_type in BOOK_TYPES or work_type in CHAPTER_TYPES:
        if any(_venue_matches(supplied, container) for container in containers):
            return True
        return _publisher_matches(supplied, candidate.publisher)

    return _venue_matches(supplied, candidate.venue)


def _extract_year(item: dict[str, Any]) -> int | None:
    for field in ("published-print", "published-online", "published", "issued"):
        parts = item.get(field, {}).get("date-parts", [])
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def _extract_candidate(
    item: dict[str, Any],
    *,
    query_title: str | None = None,
) -> ReferenceCandidate:
    titles = item.get("title") or []
    title = str(titles[0]).strip() if titles else ""

    authors = []
    for author in item.get("author") or []:
        given = str(author.get("given") or "").strip()
        family = str(author.get("family") or "").strip()
        name = " ".join(part for part in (given, family) if part)
        if name:
            authors.append(name)

    work_type = str(item.get("type") or "").strip()

    containers = [
        str(value).strip()
        for value in (item.get("container-title") or [])
        if str(value).strip()
    ]
    venue = containers[0] if containers else ""

    subtitles = item.get("subtitle") or []
    subtitle = str(subtitles[0]).strip() if subtitles else ""
    publisher = str(item.get("publisher") or "").strip()

    doi = str(item.get("DOI") or "").strip().lower()

    candidate = ReferenceCandidate(
        title=title,
        authors=authors,
        year=_extract_year(item),
        venue=venue,
        doi=doi,
        work_type=work_type,
        subtitle=subtitle,
        publisher=publisher,
        container_titles=containers,
    )

    if query_title and title:
        candidate.title_similarity = _candidate_title_similarity(
            query_title, candidate
        )

    return candidate


class OpenAlexUnavailableError(BibliographicLookupError):
    """OpenAlex remained unavailable after bounded transient retries."""

    def __init__(self, message: str, *, operation: str = "lookup",
                 http_status: int | None = None):
        super().__init__(message, service="openalex", operation=operation,
                         code="http_error", http_status=http_status)


def _get_openalex_json(
    url: str,
    timeout: float = 10.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Retrieve OpenAlex JSON with bounded retries for transient HTTP errors."""
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    for attempt in range(max_attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                return _validate_bibliographic_response(
                    json.load(response), "openalex", url
                )

        except HTTPError as exc:
            if exc.code not in {429, 503}:
                raise _lookup_failure("openalex", url, exc) from exc

            if attempt == max_attempts - 1:
                raise OpenAlexUnavailableError(
                    f"OpenAlex request failed after transient retries: {exc}",
                    operation=_lookup_operation("openalex", url),
                    http_status=exc.code,
                ) from exc

            retry_after = (
                exc.headers.get("Retry-After")
                if exc.headers is not None
                else None
            )
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except (TypeError, ValueError):
                delay = 2 ** attempt

            time.sleep(min(delay, 10.0))

        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise _lookup_failure("openalex", url, exc) from exc

    raise RuntimeError("OpenAlex request failed after retries.")


def _extract_openalex_candidate(
    item: dict[str, Any],
    *,
    query_title: str | None = None,
) -> ReferenceCandidate:
    """Convert an OpenAlex work into the common candidate structure."""
    title = str(
        item.get("title")
        or item.get("display_name")
        or ""
    ).strip()

    authors = []
    for authorship in item.get("authorships") or []:
        author = authorship.get("author") or {}
        name = str(author.get("display_name") or "").strip()
        if name:
            authors.append(name)

    try:
        year = (
            int(item["publication_year"])
            if item.get("publication_year") is not None
            else None
        )
    except (TypeError, ValueError):
        year = None

    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    venue = str(source.get("display_name") or "").strip()

    doi = str(item.get("doi") or "").strip()
    doi = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        doi,
        flags=re.I,
    ).lower()

    work_type = str(item.get("type") or "").strip()

    similarity = (
        _title_similarity(query_title, title)
        if query_title and title
        else None
    )

    return ReferenceCandidate(
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        work_type=work_type,
        source="openalex",
        title_similarity=similarity,
    )


# Conservative application limit on the complete ASCII-encoded request URL.
OPENALEX_TITLE_URL_MAX_BYTES = 2048


class UnsafeOpenAlexTitleQuery(ValueError):
    """Local preflight skip; not a lookup failure or an empty search result."""


def _openalex_title_url(title: str, rows: int) -> str:
    return f"{OPENALEX_API}/works?" + urlencode({
        "filter": f"title.search:{title}",
        "per-page": rows,
    })


def is_safe_openalex_title(title: str, *, rows: int = 5) -> bool:
    """Allow only ASCII alphanumerics/spaces, without standalone operators.

    Preserve internal text exactly. Only the existing surrounding trim is
    permitted. The 2048-byte bound includes the URL and bounded page size.
    """
    cleaned = title.strip()
    if not re.fullmatch(r"[A-Za-z0-9 ]+", cleaned):
        return False
    if any(word.upper() in {"AND", "OR", "NOT"} for word in cleaned.split(" ")):
        return False
    rows = max(1, min(int(rows), 25))
    return len(_openalex_title_url(cleaned, rows).encode("ascii")) <= OPENALEX_TITLE_URL_MAX_BYTES


def search_openalex(
    title: str,
    *,
    rows: int = 5,
) -> list[ReferenceCandidate]:
    """Search OpenAlex for works by bibliographic title."""
    cleaned_title = title.strip()
    rows = max(1, min(int(rows), 25))
    if not is_safe_openalex_title(cleaned_title, rows=rows):
        raise UnsafeOpenAlexTitleQuery(
            "OpenAlex title corroboration was skipped because the title "
            "cannot safely be represented by the supported title query."
        )

    url = _openalex_title_url(cleaned_title, rows)

    data = _get_openalex_json(url)
    results = data.get("results") or []

    return [
        _extract_openalex_candidate(
            item,
            query_title=cleaned_title,
        )
        for item in results
    ]


def get_openalex_work_by_doi(
    doi: str,
) -> dict[str, Any] | None:
    """Return the raw OpenAlex work for an exact DOI."""
    cleaned = doi.strip()
    cleaned = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"^doi:\s*", "", cleaned, flags=re.I)

    if not cleaned:
        return None

    params = urlencode({
        "filter": f"doi:https://doi.org/{cleaned}",
        "per-page": 1,
    })
    url = f"{OPENALEX_API}/works?{params}"

    try:
        data = _get_openalex_json(url)
    except RuntimeError as exc:
        if "HTTP Error 404" in str(exc):
            return None
        raise

    results = data.get("results") or []
    if not results:
        return None

    return results[0]


def resolve_openalex_doi(
    doi: str,
) -> ReferenceCandidate | None:
    """Resolve an exact DOI through OpenAlex."""
    item = get_openalex_work_by_doi(doi)

    if item is None:
        return None

    return _extract_openalex_candidate(item)


def resolve_doi(doi: str) -> ReferenceCandidate | None:
    """Resolve an exact DOI through Crossref."""
    cleaned = doi.strip()
    cleaned = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^doi:\s*", "", cleaned, flags=re.I)

    if not cleaned:
        return None

    url = f"{CROSSREF_API}/works/{quote(cleaned, safe='')}"
    try:
        payload = _get_json(url)
    except RuntimeError as exc:
        # A missing DOI is an ordinary verification result, not an application
        # failure. Other network failures remain visible to the caller.
        if "HTTP Error 404" in str(exc):
            return None
        raise

    item = payload.get("message")
    if not isinstance(item, dict):
        return None

    return _extract_candidate(item)


def search_crossref(
    title: str,
    *,
    author: str | None = None,
    rows: int = 3,
) -> list[ReferenceCandidate]:
    """
    Search Crossref for likely bibliographic matches.

    When an author-constrained search returns no candidates, retry using the
    title alone. This allows the verifier to detect a misspelled or incorrect
    author rather than incorrectly concluding that no matching work exists.
    """
    params = {
        "query.title": title,
        "rows": max(1, min(rows, 10)),
        "select": (
            "DOI,title,subtitle,author,published-print,published-online,"
            "published,issued,container-title,publisher,type"
        ),
    }

    if author:
        params["query.author"] = author

    url = f"{CROSSREF_API}/works?{urlencode(params)}"
    payload = _get_json(url)
    items = payload.get("message", {}).get("items", [])

    if not isinstance(items, list):
        items = []

    if not items and author:
        params.pop("query.author", None)
        url = f"{CROSSREF_API}/works?{urlencode(params)}"
        payload = _get_json(url)
        items = payload.get("message", {}).get("items", [])

        if not isinstance(items, list):
            items = []

    return [
        _extract_candidate(item, query_title=title)
        for item in items
        if isinstance(item, dict)
    ]



def _crossref_candidates(
    title: str,
    *,
    author: str | None = None,
    rows: int = 5,
) -> list[ReferenceCandidate]:
    """
    Combine title-only and author-constrained Crossref discovery.

    Title-only discovery remains necessary when supplied author metadata is
    wrong. When author metadata is available, an additional constrained search
    can recover the intended work when exact-title reviews or related records
    crowd it out of the title-only result set.

    Candidates with the same DOI are deduplicated. DOI-less candidates are
    retained because identical titles alone do not establish identity.
    """
    candidates = list(
        search_crossref(
            title,
            author=None,
            rows=rows,
        )
    )

    if author:
        candidates.extend(
            search_crossref(
                title,
                author=author,
                rows=rows,
            )
        )

    deduplicated = []
    seen_dois = set()

    for candidate in candidates:
        doi = candidate.doi.strip().lower() if candidate.doi else None

        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)

        deduplicated.append(candidate)

    return deduplicated


def _author_matches(candidate: ReferenceCandidate, author: str) -> bool:
    """
    Match supplied bibliographic author text against candidate authors.

    Candidate authors are individual names, while supplied metadata may be a
    citation-style string containing several authors. Use the final meaningful
    token of each candidate name as conservative surname evidence rather than
    accepting arbitrary token overlap.
    """
    wanted = _normalise_text(author)
    if not wanted:
        return False

    wanted_tokens = set(wanted.split())

    for candidate_author in candidate.authors:
        candidate_name = _normalise_text(candidate_author)
        if not candidate_name:
            continue

        if candidate_name in wanted or wanted in candidate_name:
            return True

        candidate_tokens = candidate_name.split()
        surname = candidate_tokens[-1]

        if len(surname) > 1 and surname in wanted_tokens:
            return True

    return False


def _venue_matches(supplied: str, candidate: str) -> bool:
    """
    Return whether supplied and candidate venue metadata are compatible.

    Exact/near-exact similarity remains the primary rule. A shorter venue or
    publisher form is also accepted when all of its meaningful normalised
    tokens occur as complete tokens in the longer form.
    """
    if _title_similarity(supplied, candidate) >= 0.90:
        return True

    supplied_tokens = [
        token
        for token in _normalise_text(supplied).split()
        if len(token) >= 3
    ]
    candidate_tokens = set(_normalise_text(candidate).split())

    if not supplied_tokens:
        return False

    return all(token in candidate_tokens for token in supplied_tokens)


def _candidate_rank(
    candidate: ReferenceCandidate,
    *,
    author: str | None,
    year: int | None,
) -> tuple[float, int, int, int]:
    """
    Rank bibliographic candidates.

    Title agreement remains primary. When candidates have essentially the
    same bibliographic identity, prefer a formally published journal version
    over posted content such as a preprint.
    """
    similarity = candidate.title_similarity or 0.0

    author_score = (
        1 if author and _author_matches(candidate, author)
        else 0
    )

    year_score = (
        2
        if year is not None
        and candidate.year is not None
        and year == candidate.year
        else (
            1
            if year is not None
            and candidate.year is not None
            and abs(year - candidate.year) == 1
            else 0
        )
    )

    # Crossref types formally published works of all book-level kinds as
    # book, monograph, edited-book or reference-book; scoring only "book"
    # left real monographs below an unknown type.
    publication_score = (
        2
        if candidate.work_type in BOOK_TYPES or candidate.work_type in CHAPTER_TYPES
        else {
            "journal-article": 3,
            "proceedings-article": 2,
            "posted-content": 1,
        }.get(candidate.work_type, 0)
    )

    return (
        similarity,
        author_score,
        year_score,
        publication_score,
    )


def _normalised_author_set(
    candidate: ReferenceCandidate,
) -> set[str]:
    """Return normalised complete author names for cross-source comparison."""
    return {
        _normalise_text(author)
        for author in candidate.authors
        if _normalise_text(author)
    }


def corroborate_candidates(
    crossref: ReferenceCandidate | None,
    openalex: ReferenceCandidate | None,
) -> CorroborationResult:
    """
    Compare bibliographic records returned by Crossref and OpenAlex.

    This assesses cross-database bibliographic corroboration only. It does
    not establish that the source supports any substantive academic claim.
    """
    if crossref is None and openalex is None:
        return CorroborationResult(
            status="no_source",
            crossref=None,
            openalex=None,
            same_doi=False,
            title_similarity=None,
            author_agreement=None,
            venue_similarity=None,
            year_difference=None,
            reasons=[
                "No bibliographic record was available from either database."
            ],
        )

    if crossref is None or openalex is None:
        available = crossref if crossref is not None else openalex

        return CorroborationResult(
            status="single_source",
            crossref=crossref,
            openalex=openalex,
            same_doi=False,
            title_similarity=None,
            author_agreement=None,
            venue_similarity=None,
            year_difference=None,
            reasons=[
                f"A bibliographic record was available from {available.source}, "
                "but could not be compared across both databases."
            ],
        )

    crossref_doi = crossref.doi.strip().lower()
    openalex_doi = openalex.doi.strip().lower()

    same_doi = bool(
        crossref_doi
        and openalex_doi
        and crossref_doi == openalex_doi
    )

    title_similarity = (
        max(
            _title_similarity(title, openalex.title)
            for title in _full_titles(crossref)
        )
        if crossref.title and openalex.title
        else None
    )

    crossref_authors = _normalised_author_set(crossref)
    openalex_authors = _normalised_author_set(openalex)

    author_agreement = (
        crossref_authors == openalex_authors
        if crossref_authors and openalex_authors
        else None
    )

    venue_similarity = (
        _title_similarity(crossref.venue, openalex.venue)
        if crossref.venue and openalex.venue
        else None
    )

    year_difference = (
        abs(crossref.year - openalex.year)
        if crossref.year is not None and openalex.year is not None
        else None
    )

    reasons = []

    if same_doi:
        reasons.append(
            "Crossref and OpenAlex identify the same work by DOI."
        )
    else:
        reasons.append(
            "Crossref and OpenAlex do not identify the same DOI."
        )

    if title_similarity is not None:
        reasons.append(
            "Cross-source title similarity is "
            f"{title_similarity:.3f}."
        )

    if author_agreement is True:
        reasons.append(
            "Crossref and OpenAlex report the same normalised author set."
        )
    elif author_agreement is False:
        reasons.append(
            "Crossref and OpenAlex report different author sets."
        )

    if venue_similarity is not None:
        reasons.append(
            "Cross-source venue similarity is "
            f"{venue_similarity:.3f}."
        )

    if year_difference is not None:
        if year_difference == 0:
            reasons.append(
                "Crossref and OpenAlex report the same publication year."
            )
        else:
            unit = "year" if year_difference == 1 else "years"
            reasons.append(
                "Crossref and OpenAlex publication years differ by "
                f"{year_difference} {unit} "
                f"({crossref.year} vs {openalex.year})."
            )

    strong_title = (
        title_similarity is not None
        and title_similarity >= 0.90
    )
    compatible_year = (
        year_difference is None
        or year_difference <= 1
    )
    compatible_authors = author_agreement is not False
    compatible_venue = (
        venue_similarity is None
        or venue_similarity >= 0.90
    )

    if (
        same_doi
        and strong_title
        and compatible_authors
        and compatible_venue
        and compatible_year
    ):
        status = "corroborated"
    else:
        status = "cross_source_conflict"

    return CorroborationResult(
        status=status,
        crossref=crossref,
        openalex=openalex,
        same_doi=same_doi,
        title_similarity=title_similarity,
        author_agreement=author_agreement,
        venue_similarity=venue_similarity,
        year_difference=year_difference,
        reasons=reasons,
    )


def verify_reference(
    *,
    title: str | None = None,
    author: str | None = None,
    year: int | None = None,
    venue: str | None = None,
    doi: str | None = None,
) -> VerificationResult:
    """
    Verify bibliographic identity using Crossref.

    This function deliberately does not verify whether a source supports a
    claim. `claim_verified` therefore remains False.
    """
    if doi:
        candidate = resolve_doi(doi)
        if candidate is None:
            reasons = ["The supplied DOI was not found in Crossref."]
            related_candidate = None

            if title:
                recovery_candidates = search_crossref(
                    title,
                    author=None,
                    rows=5,
                )

                if recovery_candidates:
                    best_related = max(
                        recovery_candidates,
                        key=lambda item: _candidate_rank(
                            item,
                            author=author,
                            year=year,
                        ),
                    )

                    similarity = best_related.title_similarity or 0.0

                    if similarity >= 0.80:
                        related_candidate = best_related
                        reasons.append(
                            "A related Crossref record was found by "
                            "bibliographic search."
                        )
                        reasons.append(
                            f"Related-record title similarity: "
                            f"{similarity:.3f}."
                        )

                        if author:
                            if _author_matches(best_related, author):
                                reasons.append(
                                    "The supplied author matches the "
                                    "related Crossref record."
                                )
                            else:
                                reasons.append(
                                    "The supplied author does not match the "
                                    "related Crossref record."
                                )

                        if venue:
                            venue_similarity = _title_similarity(
                                venue,
                                best_related.venue,
                            )
                            if _candidate_venue_matches(
                                venue,
                                best_related,
                            ):
                                reasons.append(
                                    "The supplied venue closely matches the "
                                    "related Crossref record."
                                )
                            else:
                                reasons.append(
                                    "The supplied venue does not closely "
                                    "match the related Crossref record "
                                    f"(similarity {venue_similarity:.3f})."
                                )

                        if year is not None and best_related.year is not None:
                            year_difference = abs(
                                year - best_related.year
                            )
                            if year_difference == 0:
                                reasons.append(
                                    "The supplied year matches the related "
                                    "Crossref record."
                                )
                            else:
                                reasons.append(
                                    "The supplied year differs from the "
                                    "related Crossref record by "
                                    f"{year_difference} year(s)."
                                )

            return VerificationResult(
                status="not_verified",
                candidate=None,
                reasons=reasons,
                related_candidate=related_candidate,
            )

        reasons = ["The supplied DOI resolves in Crossref."]
        conflicts = []
        uncertainties = []

        if title:
            similarity = _candidate_title_similarity(title, candidate)
            candidate.title_similarity = similarity
            if similarity >= 0.90:
                reasons.append(
                    "The supplied title closely matches the Crossref title."
                )
            elif similarity >= 0.80:
                uncertainties.append(
                    "The supplied title is similar to, but does not closely "
                    "match, the DOI record "
                    f"(similarity {similarity:.3f})."
                )
            else:
                conflicts.append(
                    "The supplied title does not closely match the DOI record "
                    f"(similarity {similarity:.3f})."
                )

        if author:
            if _author_matches(candidate, author):
                reasons.append("The supplied author matches the Crossref record.")
            else:
                conflicts.append("The supplied author was not matched in the DOI record.")

        if venue:
            venue_similarity = _title_similarity(venue, candidate.venue)
            if _candidate_venue_matches(venue, candidate):
                reasons.append("The supplied venue closely matches the Crossref record.")
            else:
                conflicts.append(
                    "The supplied venue does not closely match the DOI record "
                    f"(similarity {venue_similarity:.3f})."
                )

        if year is not None and candidate.year is not None:
            if year == candidate.year:
                reasons.append("The supplied year matches the Crossref record.")
            elif abs(year - candidate.year) == 1:
                reasons.append(
                    "The supplied year differs by one year from the Crossref record."
                )
            else:
                conflicts.append("The supplied year conflicts with the DOI record.")

        related_candidate = None

        if conflicts and title:
            recovery_candidates = search_crossref(
                title,
                author=None,
                rows=5,
            )

            alternative_candidates = [
                item
                for item in recovery_candidates
                if item.doi.lower() != candidate.doi.lower()
            ]

            if alternative_candidates:
                best_related = max(
                    alternative_candidates,
                    key=lambda item: _candidate_rank(
                        item,
                        author=author,
                        year=year,
                    ),
                )

                related_similarity = (
                    best_related.title_similarity or 0.0
                )

                if related_similarity >= 0.80:
                    related_candidate = best_related
                    reasons.append(
                        "A different related Crossref record was found "
                        "by bibliographic search."
                    )
                    reasons.append(
                        "Related-record title similarity: "
                        f"{related_similarity:.3f}."
                    )

                    if author:
                        if _author_matches(best_related, author):
                            reasons.append(
                                "The supplied author matches the related "
                                "Crossref record."
                            )
                        else:
                            reasons.append(
                                "The supplied author does not match the "
                                "related Crossref record."
                            )

                    if venue:
                        related_venue_similarity = _title_similarity(
                            venue,
                            best_related.venue,
                        )
                        if _candidate_venue_matches(
                            venue,
                            best_related,
                        ):
                            reasons.append(
                                "The supplied venue closely matches the "
                                "related Crossref record."
                            )
                        else:
                            reasons.append(
                                "The supplied venue does not closely match "
                                "the related Crossref record "
                                f"(similarity "
                                f"{related_venue_similarity:.3f})."
                            )

                    if (
                        year is not None
                        and best_related.year is not None
                    ):
                        related_year_difference = abs(
                            year - best_related.year
                        )
                        if related_year_difference == 0:
                            reasons.append(
                                "The supplied year matches the related "
                                "Crossref record."
                            )
                        else:
                            reasons.append(
                                "The supplied year differs from the related "
                                "Crossref record by "
                                f"{related_year_difference} year(s)."
                            )

        if conflicts:
            status = "metadata_conflict"
        elif uncertainties:
            status = "probable"
        else:
            status = "verified"

        return VerificationResult(
            status=status,
            candidate=candidate,
            reasons=reasons + uncertainties + conflicts,
            related_candidate=related_candidate,
        )

    if not title:
        return VerificationResult(
            status="not_verified",
            candidate=None,
            reasons=["A title or DOI is required for verification."],
        )

    candidates = _crossref_candidates(
        title,
        author=author,
        rows=5,
    )
    if not candidates:
        return VerificationResult(
            status="not_verified",
            candidate=None,
            reasons=["No Crossref candidates were returned."],
        )

    candidate = max(
        candidates,
        key=lambda item: _candidate_rank(
            item,
            author=author,
            year=year,
        ),
    )

    similarity = candidate.title_similarity or 0.0
    author_ok = _author_matches(candidate, author) if author else None
    venue_similarity = (
        _title_similarity(venue, candidate.venue)
        if venue
        else None
    )
    venue_ok = (
        _candidate_venue_matches(venue, candidate)
        if venue
        else None
    )
    year_difference = (
        abs(year - candidate.year)
        if year is not None and candidate.year is not None
        else None
    )

    reasons = [f"Best Crossref title similarity: {similarity:.3f}."]

    if author is not None:
        reasons.append(
            "The supplied author matches the best Crossref result."
            if author_ok
            else "The supplied author was not matched in the best Crossref result."
        )

    if venue_similarity is not None:
        reasons.append(
            "The supplied venue closely matches the best Crossref result."
            if venue_ok
            else (
                "The supplied venue does not closely match the best Crossref "
                f"result (similarity {venue_similarity:.3f})."
            )
        )

    if year_difference is not None:
        reasons.append(
            "The supplied year matches the best Crossref result."
            if year_difference == 0
            else (
                "The supplied year differs from the best Crossref result by "
                f"{year_difference} year(s)."
            )
        )

    strong_title = similarity >= 0.90
    acceptable_year = year_difference is None or year_difference <= 1
    acceptable_author = author_ok is not False
    acceptable_venue = venue_ok is None or venue_ok

    if (
        strong_title
        and acceptable_author
        and acceptable_year
        and acceptable_venue
    ):
        status = "verified"
        verified_candidate = candidate
        related_candidate = None

    elif (
        similarity >= 0.80
        and acceptable_author
        and acceptable_year
        and acceptable_venue
    ):
        status = "probable"
        verified_candidate = candidate
        related_candidate = None

    else:
        status = "not_verified"
        verified_candidate = None
        related_candidate = (
            candidate
            if similarity >= 0.80
            else None
        )

    return VerificationResult(
        status=status,
        candidate=verified_candidate,
        reasons=reasons,
        related_candidate=related_candidate,
    )


def verify_academic_reference(
    *,
    title: str | None = None,
    author: str | None = None,
    year: int | None = None,
    venue: str | None = None,
    doi: str | None = None,
) -> AcademicReferenceResult:
    """
    Verify a reference with Crossref and add OpenAlex corroboration.

    Bibliographic corroboration does not establish claim support.
    """
    verification = None
    doi_corroboration = None
    related_corroboration = None
    reasons = []

    def unavailable(exc: BibliographicLookupError, stage: str) -> AcademicReferenceResult:
        # Diagnostics are server-side only and must not defeat containment.
        try:
            traceback.print_exc()
        except Exception:
            pass
        retained = verification if verification is not None else VerificationResult(
            status=VERIFICATION_STATUS_UNAVAILABLE, candidate=None,
            reasons=["Bibliographic verification could not be completed."],
        )
        return AcademicReferenceResult(
            crossref_verification=retained,
            doi_corroboration=doi_corroboration,
            related_corroboration=related_corroboration,
            identity_conflict=False,
            reasons=reasons + ["Required bibliographic checking could not be completed."],
            corroboration_status="unavailable",
            issues=[BibliographicIssue(stage=stage, service=exc.service,
                outcome="unavailable", code=exc.code, http_status=exc.http_status)],
        )

    try:
        verification = verify_reference(
            title=title, author=author, year=year, venue=venue, doi=doi,
        )
    except BibliographicLookupError as exc:
        return unavailable(exc, "reference_verification")

    if doi:
        try:
            crossref_doi = resolve_doi(doi)
            openalex_doi = resolve_openalex_doi(doi)
        except BibliographicLookupError as exc:
            return unavailable(exc, "doi_corroboration")

        doi_corroboration = corroborate_candidates(
            crossref_doi,
            openalex_doi,
        )

        reasons.append(
            "The supplied DOI was checked in both Crossref "
            "and OpenAlex."
        )

    if title:
        try:
            crossref_results = _crossref_candidates(title, author=author, rows=5)
            openalex_results = search_openalex(title, rows=5)
        except UnsafeOpenAlexTitleQuery as exc:
            reasons.append(str(exc))
            return AcademicReferenceResult(
                crossref_verification=verification,
                doi_corroboration=doi_corroboration,
                related_corroboration=None,
                identity_conflict=False,
                reasons=reasons,
                corroboration_status="unavailable",
                issues=[BibliographicIssue(
                    stage="title_corroboration", service="openalex",
                    outcome="skipped", code="unsafe_title_query",
                )],
            )
        except BibliographicLookupError as exc:
            return unavailable(exc, "title_corroboration")

        best_crossref = (
            max(
                crossref_results,
                key=lambda candidate: _candidate_rank(
                    candidate,
                    author=author,
                    year=year,
                ),
            )
            if crossref_results
            else None
        )

        best_openalex = (
            max(
                openalex_results,
                key=lambda candidate: _candidate_rank(
                    candidate,
                    author=author,
                    year=year,
                ),
            )
            if openalex_results
            else None
        )

        related_corroboration = corroborate_candidates(
            best_crossref,
            best_openalex,
        )

        reasons.append(
            "The supplied title was searched in both Crossref "
            "and OpenAlex."
        )

    identity_conflict = False

    if (
        doi_corroboration is not None
        and related_corroboration is not None
        and doi_corroboration.status == "corroborated"
        and related_corroboration.status == "corroborated"
        and doi_corroboration.crossref is not None
        and related_corroboration.crossref is not None
    ):
        doi_identity = doi_corroboration.crossref.doi.strip().lower()
        title_identity = (
            related_corroboration.crossref.doi.strip().lower()
        )

        if (
            doi_identity
            and title_identity
            and doi_identity != title_identity
        ):
            identity_conflict = True
            reasons.append(
                "The supplied DOI and supplied title identify different "
                "publications across the corroborated database records."
            )

    if not identity_conflict:
        reasons.append(
            "No cross-database DOI-versus-title identity conflict was "
            "established."
        )

    return AcademicReferenceResult(
        crossref_verification=verification,
        doi_corroboration=doi_corroboration,
        related_corroboration=related_corroboration,
        identity_conflict=identity_conflict,
        reasons=reasons,
    )

