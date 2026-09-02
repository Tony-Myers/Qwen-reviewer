#!/usr/bin/env python3
"""
Study-design classification and expected-element checks.

Standalone by design. This module imports nothing from review_pipeline.py,
server.py or llm_backend.py, so it cannot move the pipeline fingerprint and
cannot alter any report. It exists to be built and measured while the
evaluation set is open; integration is a later, separate step.

See reports/DESIGN-EXPECTATIONS.md for the argument. In short:

  - MethodClass answers "what does the analysis do".
  - DesignClass answers "what kind of study is this".

They are orthogonal. A meta-analysis may pool with REML or with a Bayesian
hierarchical model; both are evidence syntheses, and the existing method
expectations remain correct for each.

The expected-element checks are absence checks, which fail in the opposite
direction from the pipeline's presence checks: a missed synonym produces a
false accusation rather than a missed catch. Every finding therefore carries
the terms that were searched for, so a reader can dismiss a wrong line in
seconds. Patterns are deliberately generous for the same reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Design classification
# ---------------------------------------------------------------------------

class DesignClass(Enum):
    EVIDENCE_SYNTHESIS = "evidence_synthesis"
    RANDOMISED_TRIAL = "randomised_trial"
    COHORT_LONGITUDINAL = "cohort_longitudinal"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    SURVEY = "survey"
    MEASUREMENT_VALIDATION = "measurement_validation"
    SIMULATION = "simulation"
    SECONDARY_ANALYSIS = "secondary_analysis"
    QUALITATIVE = "qualitative"
    UNCLASSIFIED = "unclassified"


# (signal name, pattern, strength)
#
# "strong" signals describe something only a study of that design does.
# "weak" signals are consistent with the design but appear in papers that
# merely cite or discuss one. A class fires only on at least one strong
# signal plus two distinct signals in total, which is the same conjunction
# discipline classify_method() uses for its early-routing rules.
_DESIGN_SIGNALS: Dict[DesignClass, List[Tuple[str, str, str]]] = {
    DesignClass.EVIDENCE_SYNTHESIS: [
        ("prisma", r"\bprisma\b", "strong"),
        ("search strategy", r"\bsearch (?:strategy|string|terms|syntax)\b", "strong"),
        ("we searched", r"\b(?:we|authors?|the (?:first|second) author)\s+searched\b", "strong"),
        ("records screened", r"\brecords?\s+(?:were\s+)?(?:identified|screened|retrieved|returned)\b", "strong"),
        ("studies were screened", r"\b(?:studies|articles|papers|abstracts|titles)\s+were\s+screened\b", "strong"),
        ("database search", r"\b(?:database|literature|electronic)\s+(?:search|searches)\b", "strong"),
        ("flow diagram", r"\bflow (?:diagram|chart)\b", "weak"),
        ("meta-analysis", r"\bmeta[- ]analys\w+\b", "weak"),
        ("systematic review", r"\bsystematic (?:review|search)\b", "weak"),
        ("scoping review", r"\bscoping review\b", "weak"),
        ("umbrella review", r"\bumbrella review\b", "weak"),
        ("eligibility", r"\beligib\w+ criteri\w+\b", "weak"),
        ("data extraction", r"\bdata (?:were |was )?extract(?:ed|ion)\b", "weak"),
        ("included studies", r"\bincluded (?:studies|articles|papers|trials)\b", "weak"),
        ("pooled estimate", r"\bpooled (?:estimate|effect|analysis|mean)\b", "weak"),
    ],
    DesignClass.RANDOMISED_TRIAL: [
        ("randomly allocated", r"\b(?:randomly|randomis\w+|randomiz\w+)\s+(?:allocat|assign)\w*\b", "strong"),
        ("allocation concealment", r"\ballocation concealment\b", "strong"),
        ("consort", r"\bconsort\b", "strong"),
        ("trial registration", r"\b(?:clinicaltrials\.gov|isrctn|anzctr|trial registration)\b", "strong"),
        ("control group", r"\b(?:control|placebo|sham|comparator)\s+group\b", "weak"),
        ("intervention arm", r"\b(?:intervention|treatment)\s+(?:arm|group)\b", "weak"),
        ("blinded", r"\b(?:single|double|triple)[- ]blind\w*\b", "weak"),
    ],
    DesignClass.COHORT_LONGITUDINAL: [
        ("prospective cohort", r"\b(?:prospective|retrospective)\s+cohort\b", "strong"),
        ("followed for", r"\b(?:followed|follow[- ]up)\s+(?:for|of|period)\b", "strong"),
        ("baseline and follow-up", r"\bbaseline\b[^.]{0,60}\bfollow[- ]up\b", "strong"),
        ("longitudinal", r"\blongitudinal\b", "weak"),
        ("repeated over seasons", r"\b(?:season|year|month)s?\s+of\s+(?:data|monitoring|observation)\b", "weak"),
    ],
    DesignClass.CASE_CONTROL: [
        ("cases and controls", r"\bcases?\s+(?:and|versus|vs\.?)\s+controls?\b", "strong"),
        ("case-control", r"\bcase[- ]control\b", "strong"),
        ("matched controls", r"\bmatched controls?\b", "weak"),
    ],
    DesignClass.CROSS_SECTIONAL: [
        ("cross-sectional", r"\bcross[- ]sectional\b", "strong"),
        ("single time point", r"\bsingle (?:time )?point\b|\bone occasion\b", "strong"),
        ("snapshot", r"\bat a single visit\b", "weak"),
    ],
    DesignClass.SURVEY: [
        ("questionnaire administered", r"\bquestionnaire\s+(?:was|were)\s+(?:administered|distributed|completed)\b", "strong"),
        ("response rate", r"\bresponse rate\b", "strong"),
        ("online survey", r"\b(?:online|web[- ]based|postal)\s+survey\b", "strong"),
        ("respondents", r"\brespondents?\b", "weak"),
        ("likert", r"\blikert\b", "weak"),
    ],
    DesignClass.MEASUREMENT_VALIDATION: [
        # ICC, CV and the word "reliability" appear in papers that merely
        # report the reliability of their measures, so they are weak. The
        # strong signals are the ones that describe the study's purpose.
        ("limits of agreement", r"\blimits of agreement\b|\bbland[- ]altman\b", "strong"),
        ("test-retest", r"\btest[- ]retest\b", "strong"),
        ("typical error", r"\btypical error\b", "strong"),
        ("validity of the measure", r"\b(?:validity|reliability|agreement) of the\b", "strong"),
        ("criterion validity", r"\b(?:criterion|construct|concurrent)\s+validity\b", "weak"),
        ("intraclass correlation", r"\bintraclass correlation\b|\bicc\b", "weak"),
        ("coefficient of variation", r"\bcoefficient of variation\b", "weak"),
        ("reliability", r"\breliabilit\w+\b", "weak"),
    ],
    DesignClass.SIMULATION: [
        # "Monte Carlo" and "simulated data" are demoted to weak because they
        # are the everyday vocabulary of MCMC estimation and posterior
        # predictive simulation. On the development corpus they classified a
        # Bayesian analysis of sleep deprivation as a simulation study. A real
        # simulation study names its data-generating process or its
        # replications, so those carry the class instead.
        ("data generating", r"\bdata[- ]generating (?:process|mechanism|model)\b", "strong"),
        ("replications", r"\b\d[\d,]*\s+(?:replications|replicates|simulated (?:datasets|samples))\b", "strong"),
        ("simulation study", r"\bsimulation study\b|\bsimulation experiment\b", "strong"),
        ("monte carlo", r"(?<!markov chain )(?<!hamiltonian )(?<!sequential )\bmonte carlo\b", "weak"),
        ("simulated datasets", r"\bsimulat\w+\s+(?:data|datasets?|samples?|studies)\b", "weak"),
    ],
    DesignClass.SECONDARY_ANALYSIS: [
        ("secondary analysis", r"\bsecondary analysis\b", "strong"),
        ("publicly available dataset", r"\bpublicly available (?:data|dataset)\b", "strong"),
        ("existing cohort data", r"\bdata (?:were|was) obtained from\b", "weak"),
    ],
    DesignClass.QUALITATIVE: [
        ("thematic analysis", r"\bthematic analysis\b|\bgrounded theory\b|\binterpretative phenomenolog\w+\b", "strong"),
        ("semi-structured interviews", r"\bsemi[- ]structured interviews?\b|\bfocus groups?\b", "strong"),
        ("saturation", r"\b(?:data|thematic) saturation\b", "weak"),
        ("transcripts", r"\btranscrib\w+\b|\btranscripts?\b", "weak"),
    ],
}

# Design classes that, when both fire, should resolve in this order.
# Evidence synthesis wins over the designs of the studies it includes, which
# is the whole contamination problem in one line.
_DESIGN_PRIORITY: List[DesignClass] = [
    DesignClass.EVIDENCE_SYNTHESIS,
    DesignClass.SIMULATION,
    DesignClass.RANDOMISED_TRIAL,
    DesignClass.QUALITATIVE,
    DesignClass.MEASUREMENT_VALIDATION,
    DesignClass.CASE_CONTROL,
    DesignClass.COHORT_LONGITUDINAL,
    DesignClass.SURVEY,
    DesignClass.SECONDARY_ANALYSIS,
    DesignClass.CROSS_SECTIONAL,
]

MIN_SIGNALS = 2


def strip_back_matter(text: str) -> str:
    """
    Drop references, bibliography and acknowledgements.

    Same split as classify_method(), for the same reason: a paper that cites a
    systematic review is not one, and the reference list is where most of those
    citations live.
    """
    return re.split(
        r"\b(?:references|bibliography|acknowledgments?|acknowledgements?)\b",
        text.lower(),
        maxsplit=1,
    )[0]


@dataclass
class DesignVerdict:
    design_class: DesignClass
    matched: List[str] = field(default_factory=list)
    runners_up: List[Tuple[DesignClass, List[str]]] = field(default_factory=list)

    def describe(self) -> str:
        if self.design_class is DesignClass.UNCLASSIFIED:
            return "design=unclassified"
        line = f"design={self.design_class.value} (signals: {', '.join(self.matched)})"
        if self.runners_up:
            others = "; ".join(
                f"{d.value} ({', '.join(s)})" for d, s in self.runners_up
            )
            line += f"\n  also matched: {others}"
        return line


def classify_design(full_text: str) -> DesignVerdict:
    """
    Rule-based study-design classification, independent of MethodClass.

    Requires at least one strong signal and MIN_SIGNALS distinct signals in
    total. Returns UNCLASSIFIED rather than guessing, because a wrong design
    class would attach a whole registry of irrelevant expected elements.
    """
    body = strip_back_matter(full_text)

    hits: Dict[DesignClass, List[str]] = {}
    for design, signals in _DESIGN_SIGNALS.items():
        names: List[str] = []
        strong = False
        for name, pattern, strength in signals:
            if re.search(pattern, body):
                names.append(name)
                if strength == "strong":
                    strong = True
        if strong and len(names) >= MIN_SIGNALS:
            hits[design] = names

    if not hits:
        return DesignVerdict(DesignClass.UNCLASSIFIED)

    ordered = [d for d in _DESIGN_PRIORITY if d in hits]
    primary = ordered[0]
    runners = [(d, hits[d]) for d in ordered[1:]]
    return DesignVerdict(primary, hits[primary], runners)


# ---------------------------------------------------------------------------
# Scoped method text (see section 10.3 of the design note)
# ---------------------------------------------------------------------------

_SYNTHESIS_ANALYSIS_CUES = re.compile(
    r"\b(?:we\s+(?:computed|calculated|estimated|fitted|conducted|performed|ran)"
    r"|analyses were (?:conducted|performed|undertaken|carried out)"
    r"|all analyses were"
    r"|statistical analys[ei]s (?:were|was)"
    r"|our analysis"
    r"|data were analysed|data were analyzed)\b"
)

_METHODS_END = re.compile(r"\n\s*(?:\d+\.?\s*)?(?:results|findings)\b", re.I)


def scoped_synthesis_text(full_text: str, window: int = 6000) -> Optional[str]:
    """
    Return the slice of text most likely to describe the review's OWN analysis.

    In an evidence synthesis the body describes the included studies' methods,
    so classifying the method from the full text attributes other people's
    analyses to this paper. This narrows to the first passage where the authors
    speak about what they did, up to the start of the results or `window`
    characters, whichever comes first.

    Returns None when no analysis cue is found, which is itself informative:
    the caller should then report that the review's own analysis could not be
    located rather than falling back to the full-text classification.
    """
    match = _SYNTHESIS_ANALYSIS_CUES.search(full_text.lower())
    if not match:
        return None
    start = max(0, match.start() - 400)
    tail = full_text[start:start + window]
    end = _METHODS_END.search(tail)
    return tail[:end.start()] if end else tail


# ---------------------------------------------------------------------------
# Expected elements
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    key: str
    kind: str            # "absent" | "restriction" | "present"
    label: str
    searched: str        # human-readable terms, printed in the report
    detail: str = ""

    def line(self) -> str:
        text = f"- {self.label}"
        if self.detail:
            text += f" {self.detail}"
        return f"{text}\n  Searched: {self.searched}."


_DATABASES = {
    "PubMed": r"\bpubmed\b",
    "MEDLINE": r"\bmedline\b",
    "Embase": r"\bembase\b",
    "Scopus": r"\bscopus\b",
    "Web of Science": r"\bweb of science\b",
    "SPORTDiscus": r"\bsportdiscus\b",
    "CINAHL": r"\bcinahl\b",
    "PsycINFO": r"\bpsyc[ ]?info\b",
    "Cochrane": r"\bcochrane\b",
    "Google Scholar": r"\bgoogle scholar\b",
    "ProQuest": r"\bproquest\b",
    "ScienceDirect": r"\bsciencedirect\b",
    "OpenAlex": r"\bopenalex\b",
    "Dimensions": r"\bdimensions\.ai\b",
    "SciELO": r"\bscielo\b",
    "ERIC": r"\beric\b",
    "LILACS": r"\blilacs\b",
}

# Platforms, not databases. Counted separately so that "searched via Ovid"
# is not mistaken for a second source.
_PLATFORMS = {
    "Ovid": r"\bovid\b",
    "EBSCOhost": r"\bebsco(?:host)?\b",
}

_SEARCH_CONTEXT = re.compile(
    r"\b(?:search\w*|database|databases|literature|records?|retriev\w+)\b"
)

_YEAR_RANGE = re.compile(
    r"\b((?:19|20)\d{2})\s*(?:to|through|until|and|[-‒–—−])\s*((?:19|20)\d{2})\b"
)

_EXCLUSION_SENTENCE = re.compile(
    r"\b(?:exclud\w+|exclusion|not eligible|ineligible|were removed|omitted)\b"
)

NARROW_WINDOW_YEARS = 10
MIN_DATABASES = 2


def _sentences(text: str) -> List[str]:
    return re.split(r"(?<=[.;:])\s+", text)


def _exclusion_sentences(text: str) -> List[str]:
    return [s for s in _sentences(text) if _EXCLUSION_SENTENCE.search(s)]


def _check_databases(body: str) -> Optional[Finding]:
    found = [name for name, pat in _DATABASES.items() if re.search(pat, body)]
    platforms = [name for name, pat in _PLATFORMS.items() if re.search(pat, body)]
    searched = "named bibliographic databases (" + ", ".join(sorted(_DATABASES)) + ")"

    if len(found) >= MIN_DATABASES:
        return Finding("databases", "present", f"Databases named: {', '.join(found)}.", searched)

    if found:
        detail = f"Only one named: {found[0]}."
        if platforms:
            detail += f" Platform(s) also named: {', '.join(platforms)} (a platform is not a second database)."
        return Finding(
            "databases", "restriction",
            "Search appears to cover a single bibliographic database.",
            searched, detail,
        )

    return Finding(
        "databases", "absent",
        "No named bibliographic database located.",
        searched,
        "The search sources could not be identified from the extracted text.",
    )


def _check_search_window(body: str) -> Optional[Finding]:
    best: Optional[Tuple[int, int, int]] = None   # (span, start_year, end_year)
    for m in _YEAR_RANGE.finditer(body):
        context = body[max(0, m.start() - 300):m.end() + 300]
        if not _SEARCH_CONTEXT.search(context):
            continue
        start_year, end_year = int(m.group(1)), int(m.group(2))
        span = end_year - start_year
        if span < 0:
            continue
        if best is None or span < best[0]:
            best = (span, start_year, end_year)

    searched = "a year range within 300 characters of search, database, literature or records"
    if best is None:
        return None

    span, start_year, end_year = best
    if span <= NARROW_WINDOW_YEARS:
        return Finding(
            "search_window", "restriction",
            f"Search window appears to span {span + 1} years ({start_year}-{end_year}).",
            searched,
            "A restricted window is a design choice; check that it is justified in the text.",
        )
    return Finding(
        "search_window", "present",
        f"Search window {start_year}-{end_year}.", searched,
    )


def _check_inclusion_asymmetry(body: str) -> Optional[Finding]:
    inclusion = re.search(
        r"\binclusion criteri\w+|\beligibilit\w+ criteri\w+|\bwere eligible if\b"
        r"|\bstudies were included if\b|\bincluded if they\b|\bto be included\b",
        body,
    )
    exclusion = re.search(r"\bexclusion criteri\w+|\bwere excluded if\b|\bstudies were excluded\b", body)
    searched = '"inclusion criteria", "eligibility criteria", "were eligible if", "studies were included if"'

    if inclusion:
        return Finding("inclusion_criteria", "present", "Inclusion or eligibility criteria stated.", searched)
    if exclusion:
        return Finding(
            "inclusion_criteria", "absent",
            "Exclusion criteria are stated but no inclusion or eligibility criteria were located.",
            searched,
            "A set defined only by what it excludes is hard to reproduce.",
        )
    return Finding(
        "inclusion_criteria", "absent",
        "No inclusion or eligibility criteria located.",
        searched,
    )


def _check_independent_screening(body: str) -> Optional[Finding]:
    searched = ('"two/both/independent reviewers", "second reviewer", "in duplicate", '
                '"dual screening", near screening, extraction or eligibility wording')
    pattern = re.compile(
        r"\b(?:two|2|three|3|both|independent(?:ly)?|dual|second)\b[^.]{0,80}"
        r"\b(?:review\w+|author\w+|research\w+|assessor\w+|rater\w+)\b"
        r"|\bin duplicate\b|\bdual screening\b"
    )
    for sentence in _sentences(body):
        if not re.search(r"\bscreen\w*|\bextract\w*|\bassess\w*|\beligib\w*|\bselect\w*", sentence):
            continue
        if pattern.search(sentence):
            return Finding("independent_screening", "present",
                           "Independent or duplicate screening described.", searched)
    return Finding(
        "independent_screening", "absent",
        "No independent or duplicate screening located.",
        searched,
        "Single-reviewer screening is usually declared and justified.",
    )


def _simple_absence(key: str, label: str, pattern: str, searched: str,
                    detail: str = "") -> "callable":
    compiled = re.compile(pattern)

    def check(body: str) -> Optional[Finding]:
        if compiled.search(body):
            return Finding(key, "present", f"{label} located.", searched)
        return Finding(key, "absent", f"No {label.lower()} located.", searched, detail)

    return check


_check_heterogeneity = _simple_absence(
    "heterogeneity",
    "Heterogeneity assessment",
    r"\bi\s*[²³2]\b|\bi[- ]squared\b|\btau\s*[²2]\b|τ"
    r"|\bbetween[- ]stud(?:y|ies) (?:variance|standard deviation|heterogeneit\w+)\b"
    r"|\bcochran'?s q\b|\bq[- ]statistic\b|\bheterogeneit\w+",
    'I2, I-squared, tau2, the Greek tau, "between-study variance", "between-study '
    'standard deviation", Cochran\'s Q, Q-statistic, "heterogeneity"',
    "A Bayesian synthesis reporting a posterior for between-study standard deviation satisfies this.",
)

_check_publication_bias = _simple_absence(
    "publication_bias",
    "Publication-bias or small-study assessment",
    r"\bfunnel plot\b|\begger'?s?\b|\bbegg'?s?\b|\btrim[- ]and[- ]fill\b|\bp[- ]curve\b"
    r"|\bpublication bias\b|\bselection model\b|\bfail[- ]safe n\b|\bsmall[- ]study effect",
    'funnel plot, Egger, Begg, trim-and-fill, p-curve, "publication bias", '
    '"selection model", "fail-safe N", "small-study effects"',
)

_check_risk_of_bias = _simple_absence(
    "risk_of_bias",
    "Risk-of-bias or quality appraisal",
    r"\brisk of bias\b|\brob ?2\b|\brobins[- ]?i\b|\bnewcastle[- ]ottawa\b"
    r"|\bdowns and black\b|\bpedro\b|\bamstar\b|\bcertainty of evidence\b"
    r"|\bgrade (?:approach|criteria|assessment)\b|\bmethodological quality\b"
    r"|\bquality (?:assessment|appraisal)\b|\bcritical appraisal\b",
    '"risk of bias", RoB 2, ROBINS-I, Newcastle-Ottawa, Downs and Black, PEDro, '
    'AMSTAR, GRADE, "methodological quality", "quality appraisal", "critical appraisal"',
)

_check_registration = _simple_absence(
    "registration",
    "Protocol registration",
    r"\bprospero\b|\bosf\.io\b|\bopen science framework\b|\bpre[- ]?registr\w+"
    r"|\bprotocol was registered\b|\bregistration number\b|\bregistered .{0,30}protocol\b",
    'PROSPERO, osf.io, "Open Science Framework", "preregistered", '
    '"protocol was registered", "registration number"',
)


def _restriction_in_exclusions(key: str, label: str, pattern: str, searched: str,
                               detail: str = "") -> "callable":
    compiled = re.compile(pattern)

    def check(body: str) -> Optional[Finding]:
        for sentence in _exclusion_sentences(body):
            m = compiled.search(sentence)
            if m:
                return Finding(key, "restriction", label, searched,
                               f'Matched "{m.group(0)}" in an exclusion sentence. {detail}'.strip())
        return None

    return check


_check_publisher_exclusion = _restriction_in_exclusions(
    "publisher_exclusion",
    "Studies appear to be excluded by publisher rather than by study characteristic.",
    r"\bmdpi\b|\bfrontiers\b|\bhindawi\b|\bbentham\b|\bscirp\b|\bpredator\w+",
    "publisher names (MDPI, Frontiers, Hindawi, Bentham, SCIRP) and "
    '"predatory", within sentences containing exclusion wording',
    "Publisher-level exclusion affects which studies could enter the sample.",
)

_check_design_exclusion = _restriction_in_exclusions(
    "design_exclusion",
    "A study design appears to be excluded a priori.",
    r"\bwithin[- ]subject\w*|\bcross[- ]?over\b|\brepeated[- ]measures?\b"
    r"|\bsingle[- ]group\b|\bpre[- ]post\b|\bcase (?:stud|report)\w*|\bqualitative\b",
    "within-subject, crossover, repeated-measures, single-group, pre-post, "
    "case study, qualitative, within sentences containing exclusion wording",
    "Excluding a design narrows what the sample can represent.",
)

_check_language_restriction = _restriction_in_exclusions(
    "language_restriction",
    "The search appears to be restricted by language.",
    r"\benglish\b",
    '"English", within sentences containing exclusion wording',
)

_check_grey_literature = _restriction_in_exclusions(
    "grey_literature",
    "Unpublished or grey literature appears to be excluded.",
    r"\bgrey literature\b|\bgray literature\b|\bunpublished\b|\bconference abstract\w*"
    r"|\bdissertation\w*|\btheses\b|\bthesis\b|\bpreprint\w*",
    '"grey literature", "unpublished", "conference abstract", "dissertation", '
    '"thesis", "preprint", within sentences containing exclusion wording',
)


_REGISTRY: Dict[DesignClass, List["callable"]] = {
    DesignClass.EVIDENCE_SYNTHESIS: [
        _check_databases,
        _check_search_window,
        _check_inclusion_asymmetry,
        _check_independent_screening,
        _check_heterogeneity,
        _check_publication_bias,
        _check_risk_of_bias,
        _check_registration,
        _check_publisher_exclusion,
        _check_design_exclusion,
        _check_language_restriction,
        _check_grey_literature,
    ],
}


def check_expected_elements(full_text: str, design: DesignClass) -> List[Finding]:
    """
    Run the element checks for a design class. Returns every finding,
    including "present" ones, so the runner can show what the checks saw.
    Only "absent" and "restriction" reach the report section.
    """
    checks = _REGISTRY.get(design, [])
    body = strip_back_matter(full_text)
    findings: List[Finding] = []
    for check in checks:
        finding = check(body)
        if finding is not None:
            findings.append(finding)
    return findings


def format_expected_elements_section(findings: List[Finding]) -> str:
    """
    Render the report section. Empty string when nothing fired, so a paper
    with no design registry adds nothing to its report.
    """
    absent = [f for f in findings if f.kind == "absent"]
    restrictions = [f for f in findings if f.kind == "restriction"]
    if not absent and not restrictions:
        return ""

    parts = ["# Expected reporting elements", ""]
    if absent:
        parts.append(
            "Not located in the extracted text. This is a keyword search, not a "
            "reading: a term the authors phrased differently will appear here "
            "wrongly. Verify before acting on any line."
        )
        parts.append("")
        parts.extend(f.line() for f in absent)
        parts.append("")
    if restrictions:
        parts.append("Restrictions stated in the text:")
        parts.append("")
        parts.extend(f.line() for f in restrictions)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Design expectations for the prompt
# ---------------------------------------------------------------------------

_DESIGN_EXPECTATIONS: Dict[DesignClass, str] = {
    DesignClass.EVIDENCE_SYNTHESIS: """Design-specific expectations (evidence synthesis):
- This paper is a review or synthesis of other studies. Statistical methods named in the text may belong to the included studies rather than to this review. Before raising a concern about a method, establish from the text whose analysis it is. Do not request diagnostics from the review for a model the review did not fit.
- The review's own analysis is the object of scrutiny: how studies were found, selected, appraised and combined.
- Appropriate focus: search sources and dates, eligibility criteria, screening procedure, data extraction, appraisal of the included studies, and how results were combined or summarised.
- Where the review pools estimates, the pooling model itself carries the usual method expectations for its framework, whether frequentist or Bayesian. Apply those in addition to these, not instead of them.
- Do not treat the sample size of the review as the number of participants in the included studies unless the text does.
""",
}


def get_design_expectations(design: DesignClass) -> str:
    """Return the design expectations block, or an empty string when none."""
    return _DESIGN_EXPECTATIONS.get(design, "")


# ---------------------------------------------------------------------------
# Self-report strength guard (part C of the design note)
# ---------------------------------------------------------------------------

_SELF_REPORT_TERMS = re.compile(
    r"\bdata (?:are |is |were )?availab\w+|\bcode (?:is |are |was )?availab\w+"
    r"|\bavailability statement\b|\bosf\.io\b|\bopen science framework\b|\bgithub\b"
    r"|\brepositor\w+|\bpre[- ]?registr\w+|\bprisma\b|\bconsort\b|\bstrobe\b"
    r"|\breporting guideline\w*|\bethics approval\b|\bopenly available\b"
    r"|\bshared publicly\b|\bupon request\b",
    re.I,
)

_STRENGTH_BULLET = re.compile(r"^\s*[-*]?\s*\**\s*Strength:", re.I)

SELF_REPORT_NOTE = (
    "  Note: stated by the authors, not verified. This pipeline cannot open "
    "links or check repositories or registries. Confirm the resource resolves "
    "before crediting it."
)


def _strengths_span(report_text: str) -> Optional[Tuple[int, int]]:
    lines = report_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^#{1,3}\s*Major strengths\s*$", line.strip(), re.I):
            start = i + 1
            continue
        if start is not None and re.match(r"^#{1,3}\s+", line):
            return start, i
    if start is not None:
        return start, len(lines)
    return None


def self_report_strengths(report_text: str) -> List[Tuple[int, str, str]]:
    """
    Find strength bullets that rest on a claim the manuscript makes about its
    own transparency. Returns (line index, bullet text, matched term).

    Section 4.4 of EVALUATION.md: a report credited "Data and code availability
    supporting reproducibility" as a strength on a manuscript whose code link a
    reviewer could not access. Stated availability is not verified availability.
    """
    span = _strengths_span(report_text)
    if span is None:
        return []

    lines = report_text.splitlines()
    start, end = span
    flagged: List[Tuple[int, str, str]] = []
    current_start: Optional[int] = None
    buffer: List[str] = []

    def flush():
        if current_start is None:
            return
        text = "\n".join(buffer)
        m = _SELF_REPORT_TERMS.search(text)
        if m:
            flagged.append((current_start, text, m.group(0)))

    for i in range(start, end):
        line = lines[i]
        if _STRENGTH_BULLET.match(line):
            flush()
            current_start = i
            buffer = [line]
        elif current_start is not None:
            if line.strip() == "":
                flush()
                current_start = None
                buffer = []
            else:
                buffer.append(line)
    flush()
    return flagged


def annotate_self_report_strengths(report_text: str) -> str:
    """
    Append the stated-not-verified note to every self-report strength bullet.

    The safer alternative is demotion out of Major strengths entirely; that is
    a decision for integration, and this function is the milder half so both
    can be compared on the same reports.
    """
    flagged = self_report_strengths(report_text)
    if not flagged:
        return report_text

    lines = report_text.splitlines()
    insert_after: Dict[int, None] = {}
    for start, text, _ in flagged:
        insert_after[start + len(text.splitlines()) - 1] = None

    out: List[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i in insert_after:
            out.append(SELF_REPORT_NOTE)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

@dataclass
class DocumentVerdict:
    design: DesignVerdict
    findings: List[Finding]
    scoped_method_text: Optional[str]

    @property
    def section(self) -> str:
        return format_expected_elements_section(self.findings)


def check_document(full_text: str) -> DocumentVerdict:
    verdict = classify_design(full_text)
    findings = check_expected_elements(full_text, verdict.design_class)
    scoped = (scoped_synthesis_text(full_text)
              if verdict.design_class is DesignClass.EVIDENCE_SYNTHESIS else None)
    return DocumentVerdict(verdict, findings, scoped)
