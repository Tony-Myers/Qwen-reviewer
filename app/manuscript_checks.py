#!/usr/bin/env python3
"""
Deterministic manuscript checks, built from faults found in the evaluation set.

Standalone by design: imports nothing from review_pipeline.py, server.py or
llm_backend.py, so it cannot move the pipeline fingerprint and cannot alter any
report. Standard library only.

Each check exists because a specific fault was missed or misreported. The
reference is the section of reports/EVALUATION.md that motivated it.

  estimate_outside_interval   9.3, 10.6   an estimate outside its own CI
  stated_criteria             10.8        thresholds a paper sets for itself
  percentage_sums             10.6        category percentages summing to 163%
  duplicated_sentences        9.3         the same statement twice in a row
  table_cross_references      9.2         a value attributed to the wrong table
  unsuitable_math_glyph       11.2        an operator the embedded font cannot render
  placeholder_warning         11.3        replaces the check that flagged review blinding
  numeric_fallback            9.2, 11.3   what to say when a quotation will not verify

Every generative check in this pipeline so far has produced a false positive on
some paper, so each function here returns findings with the evidence that
triggered them, and the runner reports firing rates rather than assuming they
are right.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class Finding:
    key: str
    label: str
    detail: str = ""
    page: Optional[int] = None

    def line(self) -> str:
        where = f" (page {self.page})" if self.page is not None else ""
        return f"[{self.key}]{where} {self.label} {self.detail}".rstrip()


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_MINUS = "−–—‒"
_NUM_RE = re.compile(
    r"[-+" + _MINUS + r"]?\d+(?:[.,]\d+)?(?:\s?[eE][-+" + _MINUS + r"]?\d+)?"
)


def _to_float(token: str) -> Optional[float]:
    t = token.strip()
    for ch in _MINUS:
        t = t.replace(ch, "-")
    t = t.replace(" ", "").replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _numbers(text: str) -> List[float]:
    out = []
    for m in _NUM_RE.finditer(text):
        v = _to_float(m.group(0))
        if v is not None:
            out.append(v)
    return out


# ---------------------------------------------------------------------------
# 1. An estimate outside its own confidence interval
# ---------------------------------------------------------------------------

# e003029 table 4a printed the Age-squared coefficient as -1.02E04 with an
# interval of -1.07E-04 to -9.83E-05: the minus in the exponent was lost.
# RJSP-2024-1475 reported "RMSEA was 0.86, with a 90% confidence interval of
# [0.06, 0.11]". Both are the same fault and neither was raised by a reviewer.

_INTERVAL_PROSE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9 ()²₂\-]{1,40}?)"
    r"\s*(?:was|were|is|are|=|of)\s*"
    r"(?P<est>[-+−]?\d+(?:\.\d+)?)"
    r"[^.\n]{0,60}?(?:CI|confidence interval|interval)[^0-9\-+−\[]{0,20}"
    r"[\[(]?\s*(?P<lo>[-+−]?\d+(?:\.\d+)?)\s*(?:,|to|–|-)\s*"
    r"(?P<hi>[-+−]?\d+(?:\.\d+)?)",
    re.I,
)

# A row-level "first number, last two numbers" rule was tried first and was
# unusable: 22, 13 and 15 findings on the three manuscripts, almost all false,
# because a label such as "(Agegroup=20.00)" or "Age2" contributes numbers of
# its own and a correlation matrix has no interval at all. The check is now
# gated on the table declaring a confidence interval, and locates the estimate
# relative to the interval rather than by position in the row.

_CI_HEADER = re.compile(r"95\s*%\s*CI|lower\s*bound|upper\s*bound|confidence interval", re.I)
# The separator must be unambiguous. An en dash with no spaces around it is a
# minus sign in these tables, not a range: "0.0002<tab>-0.07" was read as an
# interval of 0.0002 to 0.07 on a published paper, and the t-value before it
# became the estimate.
_CI_PAIR = re.compile(
    r"(?P<lo>[-+\u2212\u2013]?\d+(?:\.\d+)?)"
    r"(?:\s*,\s*|\s*;\s*|\s+to\s+|\s+[\u2013-]\s+)"
    r"(?P<hi>[-+\u2212\u2013]?\d+(?:\.\d+)?)"
)
_EXP_FIX = re.compile(r"([Ee])\s*([-+\u2212])\s*(\d)")
# A decimal or a signed number inside the label cell means a value has
# leaked into it -- "Ln(Mass) -0.05" -- and the next number along is then
# read as the estimate. A bare trailing digit is just a name: Age2, VO2.
_VALUE_IN_LABEL = re.compile(r"[-+\u2212\u2013]\s?\d|\d+\.\d")
MIN_ROW_CELLS = 4
OUTSIDE_SPANS = 5


def _pure_number(token: str) -> Optional[float]:
    """A token that is nothing but a number, so a label cannot masquerade."""
    token = _EXP_FIX.sub(r"\1\2\3", token.strip())
    if not re.fullmatch(r"[-+\u2212\u2013\u2014]?\d+(?:\.\d+)?(?:[eE][-+\u2212]?\d+)?", token):
        return None
    return _to_float(token)


def _row_estimate_and_interval(row: str, header_has_bounds: bool):
    """Return (estimate, lower, upper) for a table row, or None."""
    fixed = _EXP_FIX.sub(r"\1\2\3", row)
    tokens = [tok for tok in re.split(r"\s*\|\s*|\t+|\s{2,}|\s", fixed) if tok]

    pair = _CI_PAIR.search(fixed)
    if pair:
        lo, hi = _to_float(pair.group("lo")), _to_float(pair.group("hi"))
        before = fixed[:pair.start()]
        candidates = [v for v in (_pure_number(tok) for tok in before.split()) if v is not None]
        if lo is not None and hi is not None and candidates:
            return candidates[-1], lo, hi
        return None

    if not header_has_bounds:
        return None
    # The label must be digit-free. Where a text-layer row splits badly the
    # label absorbs the first value -- "Ln(Mass) -0.05" -- and the next number
    # along is then read as the estimate, which produced a false positive on a
    # published paper.
    lead = re.split(r"\s*\|\s*|\t+|\s{2,}", fixed.strip())
    if lead and _pure_number(lead[0]) is None and _VALUE_IN_LABEL.search(lead[0]):
        return None
    numbers = [(_pure_number(tok), tok) for tok in tokens]
    numbers = [v for v, _ in numbers if v is not None]
    if len(numbers) < 3:
        return None
    return numbers[0], numbers[-2], numbers[-1]


def estimate_outside_interval(text: str,
                              table_blocks: Sequence[str] = ()) -> List[Finding]:
    findings: List[Finding] = []
    seen = set()

    for m in _INTERVAL_PROSE.finditer(text):
        est, lo, hi = (_to_float(m.group("est")), _to_float(m.group("lo")),
                       _to_float(m.group("hi")))
        if None in (est, lo, hi) or lo >= hi or lo <= est <= hi:
            continue
        findings.append(Finding(
            "estimate_outside_interval",
            f"{m.group('name').strip()} is reported as {m.group('est')} with an "
            f"interval of {m.group('lo')} to {m.group('hi')}.",
            "The estimate lies outside its own interval.",
        ))

    for block in table_blocks:
        if not _CI_HEADER.search(block):
            continue
        page = _page_of(block)
        header_has_bounds = bool(re.search(r"lower\s*bound|upper\s*bound", block, re.I))
        for row in block.splitlines():
            cells = [c for c in re.split(r"\s*\|\s*|\t+|\s{2,}", row) if c.strip()]
            if len(cells) < MIN_ROW_CELLS and "|" not in row:
                continue
            parsed = _row_estimate_and_interval(row, header_has_bounds)
            if not parsed:
                continue
            est, lo, hi = parsed
            if lo >= hi or lo <= est <= hi:
                continue
            span = hi - lo
            if span <= 0 or abs(est - (lo + hi) / 2) < OUTSIDE_SPANS * span:
                continue
            label = cells[0][:40] if cells else row[:40]
            key = (page, label, round(est, 12), round(lo, 12), round(hi, 12))
            if key in seen:
                continue
            seen.add(key)
            findings.append(Finding(
                "estimate_outside_interval",
                f'Row "{label}" reports {_fmt(est)} against an interval of '
                f"{_fmt(lo)} to {_fmt(hi)}.",
                "The estimate lies far outside its own interval.",
                page,
            ))
    return findings


def _fmt(v: float) -> str:
    return f"{v:g}"


def _page_of(block: str) -> Optional[int]:
    m = re.search(r"Page:\s*(\d+)", block)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 2. Criteria a manuscript sets for itself
# ---------------------------------------------------------------------------

# RJSP-2024-1475 stated "CFI > 0.9, TLI > 0.95, RMSEA < 0.10 and SRMR < 0.08",
# reported TLI = 0.92, never reported SRMR at all, and called the fit good. The
# pipeline judged RMSEA against an external convention instead.

_CRITERION_CONTEXT = re.compile(
    r"criteri\w+|threshold|cut[- ]?off|considered (?:acceptable|adequate|good)"
    r"|deemed acceptable|acceptable if|regarded as",
    re.I,
)
_CRITERION_RE = re.compile(
    r"\b(?P<name>[A-Za-z][A-Za-z0-9\-]{1,12})\s*"
    r"(?P<op>>=|<=|>|<|≥|≤)\s*"
    r"(?P<value>\d+(?:\.\d+)?)"
)
_REPORTED_RE_TMPL = (
    r"\b{name}\b[^.\n]{{0,40}}?(?:=|of|was|were|is|are|:)\s*"
    r"(?P<value>\d+(?:\.\d+)?)"
)


def _satisfies(value: float, op: str, threshold: float) -> bool:
    if op in (">", ):
        return value > threshold
    if op in (">=", "≥"):
        return value >= threshold
    if op in ("<", ):
        return value < threshold
    return value <= threshold


def stated_criteria(text: str) -> List[Finding]:
    findings: List[Finding] = []
    seen: Dict[str, Tuple[str, float]] = {}

    # "... approximated the following criteria: CFI > 0.9, TLI > 0.95 ..." splits
    # at the colon, leaving the thresholds in a sentence with no context word,
    # so each context sentence is searched together with the one after it.
    sentences = _sentences(text)
    for first, second in zip(sentences, list(sentences[1:]) + [""]):
        if not _CRITERION_CONTEXT.search(first):
            continue
        sentence = first + " " + second
        for m in _CRITERION_RE.finditer(sentence):
            name = m.group("name")
            # An index name, not any word that happens to precede a threshold.
            # "score < 5" fired on the corpus; CFI, TLI, RMSEA and SRMR are the
            # shape this is for.
            if not (2 <= len(name) <= 8 and name.upper() == name and name.isalpha()):
                continue
            threshold = _to_float(m.group("value"))
            if threshold is None:
                continue
            seen.setdefault(name, (m.group("op"), threshold))

    for name, (op, threshold) in seen.items():
        pattern = re.compile(_REPORTED_RE_TMPL.format(name=re.escape(name)), re.I)
        values = []
        for m in pattern.finditer(text):
            v = _to_float(m.group("value"))
            if v is not None and v != threshold:
                values.append(v)
        if not values:
            findings.append(Finding(
                "criterion_not_reported",
                f"{name} is named as a criterion ({name} {op} {threshold:g}) "
                f"but no value for it was located.",
                "An index declared and never reported.",
            ))
            continue
        failing = [v for v in values if not _satisfies(v, op, threshold)]
        if failing and len(failing) == len(values):
            findings.append(Finding(
                "criterion_not_met",
                f"{name} is reported as {', '.join(_fmt(v) for v in sorted(set(failing)))} "
                f"against the manuscript's own criterion of {name} {op} {threshold:g}.",
                "Judge against the stated criterion, not a convention.",
            ))
    return findings


# ---------------------------------------------------------------------------
# 3. Category percentages that do not sum
# ---------------------------------------------------------------------------

# RJSP-2024-1475: "acute myocardial infraction (60%), coronary artery bypass
# grafting (14%), percutaneous cardiac intervention (66%), valvular replacement
# (10%), or other CVD reasons (13%)" -- 163%, against a table giving 59, 14, 14,
# 7.9 and 5.6.

_PCT_RE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*%\s*\)")
PCT_TOLERANCE = 8.0
# A share of 90% or more leaves no room for two further categories, so a list
# containing one is not an exhaustive breakdown. On the corpus this rule
# removed the only false positive: three posterior probabilities of 100%, 100%
# and 99.95% read as category shares summing to 300%.
MAX_PLAUSIBLE_SHARE = 90.0


def percentage_sums(text: str) -> List[Finding]:
    findings: List[Finding] = []
    for sentence in _sentences(text):
        # Only exhaustive lists: the final item introduced by "or"/"and other".
        if not re.search(r",\s*(?:or|and)\s+(?:other|another|the\s+\w+)?", sentence, re.I):
            continue
        values = [float(v) for v in _PCT_RE.findall(sentence)]
        if len(values) < 3:
            continue
        if max(values) >= MAX_PLAUSIBLE_SHARE:
            continue
        total = sum(values)
        if abs(total - 100.0) <= PCT_TOLERANCE:
            continue
        findings.append(Finding(
            "percentage_sum",
            f"A list of {len(values)} category percentages sums to {total:g}%.",
            f"Values: {', '.join(f'{v:g}%' for v in values)}. "
            f"In: \"{' '.join(sentence.split())[:170]}\"",
        ))
    return findings


# ---------------------------------------------------------------------------
# 4. The same statement twice
# ---------------------------------------------------------------------------

# e003029 methods: "To assess potential multicollinearity among predictors,
# variance inflation factors (VIFs) were calculated. To assess the potential for
# multicollinearity among the predictor variables in the ANCOVA models, VIFs
# were calculated."

# Measured on the sixteen-paper corpus, a min-overlap rule at 0.7 fired 95
# times across 14 papers, almost all on parallel figure descriptions ("Figure 2A
# illustrates concentric knee extensors ...", "Figure 2B illustrates concentric
# knee flexors ..."). Those score HIGHER than the case the check was built for,
# so lexical overlap cannot separate a paraphrase repeated from two different
# statements phrased alike. The check is narrowed to near-verbatim repetition,
# which is still a real editing artefact, and the paraphrase case (e003029,
# section 9.3 of the evaluation record) is knowingly given up.
DUPLICATE_JACCARD = 0.9
MAX_LENGTH_RATIO = 1.15
MIN_DUPLICATE_TOKENS = 8

_STOP = {"the", "a", "an", "of", "for", "to", "in", "and", "or", "was", "were",
         "is", "are", "be", "been", "with", "that", "this", "these", "those",
         "as", "by", "on", "at", "from", "it", "we", "our", "their"}


def _content(sentence: str) -> set:
    words = re.findall(r"[a-z][a-z\-]+", sentence.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def duplicated_sentences(text: str) -> List[Finding]:
    """
    NOT RECOMMENDED FOR INTEGRATION. Kept because the measurement is the
    result: after narrowing to near-verbatim repetition this fired 8 times
    across 5 of 16 corpus papers and every finding was false. The true case it
    was built for -- the same statement made twice in different words -- scores
    lower on every lexical measure than the parallel figure and reference
    sentences that dominate the false positives.
    """
    findings: List[Finding] = []
    sentences = [s for s in _sentences(text) if len(s.split()) >= MIN_DUPLICATE_TOKENS]
    for first, second in zip(sentences, sentences[1:]):
        a, b = _content(first), _content(second)
        if not a or not b:
            continue
        lengths = sorted((len(a), len(b)))
        if lengths[1] / lengths[0] > MAX_LENGTH_RATIO:
            continue
        if len(a | b) == 0 or len(a & b) / len(a | b) < DUPLICATE_JACCARD:
            continue
        if " ".join(first.split()) == " ".join(second.split()):
            note = "The sentence is repeated verbatim."
        else:
            note = "Two consecutive sentences are all but identical."
        findings.append(Finding(
            "duplicated_sentence", note,
            f"\"{' '.join(first.split())[:110]}\" / \"{' '.join(second.split())[:110]}\"",
        ))
    return findings


# ---------------------------------------------------------------------------
# 5. Values attributed to the wrong table
# ---------------------------------------------------------------------------

# e003029 discussion attributed table 4a's exponent, R-squared and AIC to table
# 3a, table 4b's to table 3b, and table 3b's AIC to table 3a -- three mislabels
# in one passage, one of which the pipeline caught.

_TABLE_MENTION = re.compile(r"\btables?\s+(\d+\s?[a-d]?)\b", re.I)
_NEAR_VALUE = re.compile(r"[-+−]?\d+(?:\.\d+)?")
CROSS_REF_WINDOW = 150
_COMPARISON = re.compile(
    r"\bversus\b|\bvs\.?\b|\bcompared (?:with|to)\b|\bthan (?:that|those)\b"
    r"|\brather than\b|\bwhereas\b", re.I)


def _table_index(table_blocks: Sequence[str]) -> Dict[str, str]:
    """Map a table label, including sub-labels such as 4a, to its text."""
    index: Dict[str, str] = {}
    for block in table_blocks:
        current = None
        label = re.search(r"Label:\s*Table\s*([0-9]+\s?[a-d]?)", block, re.I)
        if label:
            current = re.sub(r"\s+", "", label.group(1)).lower()
            index.setdefault(current, "")
        for line in block.splitlines():
            # Sub-table rows carry trailing tabs or empty pipe cells, so the
            # label match must tolerate them: "Table 4a |  |  |  |" and
            # "Table 4a\t\t\t" are both the start of table 4a.
            sub = re.match(r"\s*\|?\s*Table\s*([0-9]+\s?[a-d]?)\s*[|\s]*$", line, re.I)
            if sub:
                current = re.sub(r"\s+", "", sub.group(1)).lower()
                index.setdefault(current, "")
                continue
            if current:
                index[current] += line + "\n"
    return index


def table_cross_references(text: str,
                           table_blocks: Sequence[str]) -> List[Finding]:
    index = _table_index(table_blocks)
    if not index:
        return []
    findings: List[Finding] = []
    for m in _TABLE_MENTION.finditer(text):
        label = re.sub(r"\s+", "", m.group(1)).lower()
        if label not in index:
            continue
        window = text[m.end():m.end() + CROSS_REF_WINDOW]
        # Not window.split("."): every decimal point is a full stop, and that
        # truncated "b=0.643" to "b=0" and silenced the check entirely. A
        # sentence ends with a period followed by space after a word character.
        window = re.split(r"(?<=[A-Za-z%)])\.\s", window)[0]
        # Stop at the next table mention. "The explained variance in table 4b
        # was greater than that reported in table 4a, R2=0.733 ... versus
        # R2=0.727" otherwise attributes 4a's values to 4b and vice versa,
        # which produced two false positives on e003029.
        following = _TABLE_MENTION.search(window)
        if following:
            window = window[:following.start()]
        # A comparison clause introduces the OTHER table's values even before
        # that table is named: "in table 4a, R2=0.733 or 73.3% versus R2=0.727"
        # attributes 4b's figure to 4a. Stop at the comparison.
        comparison = _COMPARISON.search(window)
        if comparison:
            window = window[:comparison.start()]

        misplaced: List[Tuple[str, List[str]]] = []
        for value in _NEAR_VALUE.findall(window):
            v = _to_float(value)
            # Four printed characters, so "0.1", "0.5" and "840" are out.
            # Running against the pipeline's own table extraction rather than
            # an evidence appendix, a three-character rule matched quantiles
            # discussed in prose and a duration inside a table caption, on two
            # published papers. Values worth checking a cross-reference for --
            # coefficients, R-squared, AIC -- all carry more precision.
            if v is None or abs(v) < 0.001 or len(value.strip("-\u2212")) < 4:
                continue
            if _contains_value(index[label], v):
                continue
            elsewhere = sorted(lab for lab, body in index.items()
                               if lab != label and _contains_value(body, v))
            if elsewhere:
                misplaced.append((value, elsewhere))
        if not misplaced:
            continue

        targets = sorted({lab for _, labs in misplaced for lab in labs})
        values = ", ".join(v for v, _ in misplaced)
        findings.append(Finding(
            "table_cross_reference",
            f"The text attributes {len(misplaced)} value(s) to table {label} "
            f"that appear in table {', '.join(targets)} and not in table {label}.",
            f"Values: {values}. In: "
            f"\"{' '.join(text[max(0, m.start() - 40):m.end() + 110].split())}\"",
        ))
    return findings


def _contains_value(body: str, value: float) -> bool:
    for token in _NUM_RE.finditer(body):
        v = _to_float(token.group(0))
        if v is not None and abs(v - value) < 1e-9:
            return True
    return False


# ---------------------------------------------------------------------------
# 6. An operator the font cannot render
# ---------------------------------------------------------------------------

# RJSP-2021-1229 used U+2027 HYPHENATION POINT as a multiplication sign 24
# times. The text layer is intact, so no text check finds this, but the
# embedded font has no glyph and the reader sees an empty box. A reviewer
# raised it; the pipeline could not.

# Only characters that are never a multiplication sign in any typesetting
# convention. U+2219 BULLET OPERATOR and U+2217 ASTERISK OPERATOR are proper
# math operators and were removed; U+02D9 DOT ABOVE was removed after firing
# on published papers that render correctly.
_WRONG_OPERATORS = {
    "\u2027": "HYPHENATION POINT",
    "\u0387": "GREEK ANO TELEIA",
}
_SANE_OPERATORS = "·⋅×*"
# One stray occurrence is a typo, not a systematic choice of operator; the
# corpus produced a single U+0387 in a paper that renders correctly.
MIN_GLYPH_HITS = 3


def unsuitable_math_glyph(text: str) -> List[Finding]:
    findings: List[Finding] = []
    for ch, name in _WRONG_OPERATORS.items():
        hits = [m for m in re.finditer(
            r"(?<=[0-9A-Za-z\)\s])" + re.escape(ch) + r"(?=[0-9A-Za-z\(\s√])", text)]
        if len(hits) < MIN_GLYPH_HITS:
            continue
        alternatives = {c: text.count(c) for c in _SANE_OPERATORS if text.count(c)}
        detail = (f"U+{ord(ch):04X} {name}, {len(hits)} time(s)")
        if alternatives:
            detail += (". The document also uses "
                       + ", ".join(f"U+{ord(c):04X} x{n}" for c, n in alternatives.items())
                       + " for the same purpose")
        findings.append(Finding(
            "unsuitable_math_glyph",
            "A character not intended as a mathematical operator is used as one.",
            detail + ". Fonts often lack a glyph for it, so it may render as an "
            "empty box in the submitted file even though the text layer is "
            "intact. Confirm by looking at a rendered page.",
        ))
    return findings


# ---------------------------------------------------------------------------
# 7. Placeholders, with the review blinding excluded
# ---------------------------------------------------------------------------

# Replaces submission_integrity_warning(). Its `\bXXX\b` matched a blinded grant
# number and a redacted contact address on RJSP-2021-1229, and it instructed the
# reviewer to raise the anonymisation as an editorial concern.

_AUTHORING_ARTEFACT = re.compile(
    r"Error!\s*(?:Reference source not found|Bookmark not defined|"
    r"No text of specified style|Unknown switch argument)"
    r"|\?\?\?\s*(?:ref|cite)|\\ref\{|\\cite\{|\[CITATION\]|\bTODO\b|\bTBD\b"
    r"|\blorem ipsum\b",
    re.I,
)
_X_PLACEHOLDER = re.compile(r"\b[Xx]{3}\b")
_BLINDING_CONTEXT = re.compile(
    r"fund|grant|ethic|approv|institution|contact|e-?mail|@|correspond"
    r"|cite this|this spreadsheet|acknowledg|conflict|affiliat|anonymi[sz]"
    r"|blinded|registration|clinicaltrials|doi",
    re.I,
)


def placeholder_warning(text: str) -> List[Finding]:
    findings: List[Finding] = []

    artefacts = [m.group(0).strip() for m in _AUTHORING_ARTEFACT.finditer(text)]
    if artefacts:
        counts: Dict[str, int] = {}
        for hit in artefacts:
            key = re.sub(r"\s+", " ", hit)
            counts[key] = counts.get(key, 0) + 1
        shown = "; ".join(f'"{k}" x{v}' if v > 1 else f'"{k}"'
                          for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:4])
        # A bare total misleads when the artefacts cluster: one submission held
        # 21, of which 13 sat on a single appendix-listing page, and a reader
        # working through the body could find only 7.
        pages: Dict[str, int] = {}
        current = "?"
        for line in text.splitlines():
            page = re.match(r"\s*\[Page (\d+)\]", line)
            if page:
                current = page.group(1)
            found = len(_AUTHORING_ARTEFACT.findall(line))
            if found:
                pages[current] = pages.get(current, 0) + found
        where = ""
        if pages and "?" not in pages:
            where = (" - " + ", ".join(f"page {k}: {v}" for k, v in
                                       sorted(pages.items(), key=lambda kv: int(kv[0]))))
        findings.append(Finding(
            "authoring_artefact",
            f"The document contains {len(artefacts)} unresolved reference(s) or "
            f"placeholder(s) ({shown}){where}.",
            "These are artefacts of the authoring tool, not of this extraction: "
            "the submitted file itself does not resolve them, so the reader "
            "cannot tell which table or figure is meant.",
        ))

    # X-placeholders are reported only outside the slots a journal asks authors
    # to redact, and never as an instruction.
    stray: List[str] = []
    for sentence in _sentences(text):
        if not _X_PLACEHOLDER.search(sentence):
            continue
        if _BLINDING_CONTEXT.search(sentence):
            continue
        if re.search(r"[Xx]{4,}", sentence):      # a long run is redaction
            continue
        stray.append(" ".join(sentence.split())[:120])
    if stray:
        findings.append(Finding(
            "x_placeholder",
            f"{len(stray)} X-placeholder(s) appear outside the sections a "
            "blinded submission normally redacts.",
            "Examples: " + " | ".join(stray[:3])
            + ". Redactions in funding, ethics, contact and self-citation "
              "slots are the review blinding and are not reported.",
        ))
    return findings


# ---------------------------------------------------------------------------
# 8. What to say when a quotation will not verify
# ---------------------------------------------------------------------------

# On three consecutive papers the citation check demoted a concern whose numbers
# were all present in the manuscript, because the model had joined a row label
# to a value from another cell.

def numeric_fallback(quotation: str, source_text: str) -> Optional[str]:
    """
    Return a sentence describing which numbers in a failed quotation are
    present in the source, or None when the quotation carries no numbers.
    """
    tokens = [m.group(0) for m in _NUM_RE.finditer(quotation)]
    if not tokens:
        return None
    values = [v for v in (_to_float(t) for t in tokens) if v is not None]
    if not values:
        return None
    present, missing = [], []
    for token, value in zip(tokens, values):
        (present if _contains_value(source_text, value) else missing).append(token)
    if not missing:
        return ("the quotation could not be located, but every value it cites "
                f"({', '.join(present)}) is present in the manuscript; the "
                "wording, not the evidence, is the problem")
    if present:
        return (f"the quotation could not be located; {', '.join(present)} "
                f"appear in the manuscript, {', '.join(missing)} do not")
    return ("the quotation could not be located, and none of the values it "
            "cites appear in the manuscript")


# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+")


def _sentences(text: str) -> List[str]:
    return [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def run_all(text: str, table_blocks: Sequence[str] = ()) -> List[Finding]:
    findings: List[Finding] = []
    findings += estimate_outside_interval(text, table_blocks)
    findings += stated_criteria(text)
    findings += percentage_sums(text)
    # duplicated_sentences() is deliberately NOT run. See its docstring: on the
    # sixteen-paper corpus it produced 8 findings across 5 papers after
    # tightening, every one of them false (parallel prose, reference entries,
    # table rows, repeated author-contribution statements), and zero true
    # positives, because the case it was built for is not separable from
    # parallel prose by lexical overlap.
    findings += table_cross_references(text, table_blocks)
    findings += unsuitable_math_glyph(text)
    # placeholder_warning() is NOT run here. review_pipeline calls it through
    # submission_integrity_warning(), and running it in both places printed the
    # same 23 unresolved references twice in one report.
    return findings
