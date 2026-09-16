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

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


CROSSREF_API = "https://api.crossref.org"
USER_AGENT = (
    "QwenReviewer/academic-reference-tools "
    "(https://github.com/Tony-Myers/Qwen-reviewer)"
)


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


@dataclass
class VerificationResult:
    status: str
    candidate: ReferenceCandidate | None
    reasons: list[str]
    claim_verified: bool = False
    related_candidate: ReferenceCandidate | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
                return json.load(response)

        except HTTPError as exc:
            if exc.code != 429 or attempt == max_attempts - 1:
                raise RuntimeError(
                    f"Crossref request failed: {exc}"
                ) from exc

            retry_after = exc.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except (TypeError, ValueError):
                delay = 2 ** attempt

            time.sleep(min(delay, 10.0))

        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Crossref request failed: {exc}"
            ) from exc

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

    containers = item.get("container-title") or []
    venue = str(containers[0]).strip() if containers else ""

    doi = str(item.get("DOI") or "").strip().lower()

    similarity = (
        _title_similarity(query_title, title)
        if query_title and title
        else None
    )

    return ReferenceCandidate(
        title=title,
        authors=authors,
        year=_extract_year(item),
        venue=venue,
        doi=doi,
        work_type=work_type,
        title_similarity=similarity,
    )


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
            "DOI,title,author,published-print,published-online,"
            "published,issued,container-title,type"
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


def _author_matches(candidate: ReferenceCandidate, author: str) -> bool:
    wanted = _normalise_text(author)
    if not wanted:
        return False

    return any(
        wanted in _normalise_text(candidate_author)
        for candidate_author in candidate.authors
    )



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
        1
        if year is not None
        and candidate.year is not None
        and abs(year - candidate.year) <= 1
        else 0
    )

    publication_score = {
        "journal-article": 3,
        "book-chapter": 2,
        "book": 2,
        "proceedings-article": 2,
        "posted-content": 1,
    }.get(candidate.work_type, 0)

    return (
        similarity,
        author_score,
        year_score,
        publication_score,
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
                            if venue_similarity >= 0.90:
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
            similarity = _title_similarity(title, candidate.title)
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
            if venue_similarity >= 0.90:
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
                        if related_venue_similarity >= 0.90:
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

    candidates = search_crossref(title, author=None, rows=5)
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
            if venue_similarity >= 0.90
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
    acceptable_venue = venue_similarity is None or venue_similarity >= 0.90

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
