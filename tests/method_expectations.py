#!/usr/bin/env python3
"""
Expected reporting elements for the ANALYSIS FRAMEWORK.

Section 18 of reports/EVALUATION.md. The design axis carries a deterministic
registry of expected elements; the method axis carries its expectations only
through the prompt, where the quotation rule suppresses them, because an
absence has no quotation. This can suppress legitimate reporting checks:
for example, a Bayesian analysis may omit prior specification or convergence
diagnostics even though those elements cannot themselves be supported by a
quotation demonstrating their absence.

This module is standalone and lives in tests/, outside the pipeline
fingerprint (constraint 18.3.4). It is imported by nothing in app/. It reads
`design_expectations` for the two text helpers 18.3.1 requires and for the
`Finding` shape, and it does not modify them.

    python3 tests/run_method_expectations.py

Design decisions taken here, each with its evidence:

1.  THE REGISTRY DOES NOT KEY ON MethodClass.

    18.2 proposes keying on MethodClass. The diagnosis found two reasons not
    to. First, ordinary-English uses of "prior" can occur near descriptions of
    hierarchical Bayesian methods without constituting prior specification.
    A whole-document classifier can therefore acquire a Bayesian method label
    from discussion vocabulary rather than the analysis actually performed.
    Separately,
    `BAYESIAN_MODEL` carries an exclusion on `\\bdic\\b`, added to keep MLwiN
    cross-classified MCMC out of the Bayesian family; DIC is a routine fit
    statistic in Bayesian network meta-analysis, so that exclusion fires on
    exactly the papers this registry exists for.

    Instead the registry opens on `bayesian_gate()`: deterministic evidence
    that the paper reports Bayesian OUTPUT, which is what makes priors and
    convergence owed in the first place. Two or more distinct strong signals
    (constraint 18.3.3), and at least one signal that an analysis was run rather
    than described -- see design decision 5. MethodClass is still
    reported alongside, and a disagreement between the two is printed rather
    than resolved.

2.  BARE WORDS ARE NOT ELEMENTS.

    A bare statement that a model converged does not establish that a
    convergence diagnostic was reported. The convergence element therefore
    requires a NAMED diagnostic. This is fault 3
    of section 12.1 of the design note repeating: the bare word "heterogeneity"
    once turned a correct finding into silence.

3.  "WARM-UP" IS NOT A SAMPLER TERM IN THIS CORPUS.

    18.2's candidate list names "burn-in or warm-up". In sport and exercise
    manuscripts, "warm-up" commonly describes exercise rather than a sampler.
    Taken literally, that vocabulary could record sampler settings as present
    when none were reported. Warm-up therefore counts only when it is adjacent
    to a number and to sampler vocabulary.

5.  DESCRIBING A METHOD IS NOT USING IT.

    A methodological paper discussing Bayesian approaches can contain several
    strong Bayesian signals without fitting a Bayesian model itself. The gate
    therefore also requires one signal that an analysis was run: named software, a numeric credible
    interval, sampler settings, a convergence diagnostic, a numeric Bayes factor
    or posterior summary, or a statement that a model was fitted. Full reasoning
    is above `_DOING_SIGNALS`.

4.  ABSENCE IS SEARCHED OVER THE SUPPLEMENT AS WELL AS THE BODY.

    A reference list can precede substantial supplementary material. Priors,
    convergence diagnostics and other analysis details may be reported there.
    An absence check that discards the supplement therefore fails in the
    accusing direction, so `analysis_text()` re-attaches supplementary material
    and drops only the reference list. Both scopes are computed so the runner
    can show they agree.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import design_expectations as de   # noqa: E402  (read-only; nothing is written back)

Finding = de.Finding

# Two STRONG signals, not two signals of any strength. Constraint 18.3.3
# requires strong signals where a single phrase would otherwise carry the
# decision, and one strong plus one weak lets "a Bayesian approach has been
# suggested elsewhere" open the gate on a frequentist paper. Nothing in the
# corpus is lost by the stricter rule: the narrowest true opening is the Muay
# Thai paper, on MLwiN and MCMC, which is two strong.
MIN_STRONG_SIGNALS = 2


# ---------------------------------------------------------------------------
# Text scopes
# ---------------------------------------------------------------------------

# A supplement heading standing on its own line, or the first supplementary
# display item. Both are looked for only in the material AFTER the reference
# list, so an in-text mention of "supplementary material" cannot trigger it.
_SUPPLEMENT_HEADING = re.compile(
    r"^[ \t]*(?:\d+[.)]?[ \t]+)?"
    r"(?:supplement\w*(?:[ \t]+\w+)?"
    r"|appendi(?:x|ces)"
    r"|supporting[ \t]+information"
    r"|online[ \t]+(?:supplement\w*|appendix))"
    r"\b.*$",
    re.M,
)
_SUPPLEMENT_ITEM = re.compile(r"\b(?:table|fig(?:ure)?\.?)[ \t]*s\s*\d+\b")


def analysis_text(full_text: str, include_supplement: bool = True) -> str:
    """
    The text an absence check may search.

    `strip_back_matter` is used as constraint 18.3.1 requires, and returns a
    prefix of the normalised, lowercased document. When the material it
    discarded contains a supplement, that supplement is re-attached and only
    the reference list is dropped.
    """
    body = de.strip_back_matter(full_text)
    if not include_supplement:
        return body

    lowered = de.normalise_extraction(full_text)
    if len(body) >= len(lowered):
        return body

    tail = lowered[len(body):]
    heading = _SUPPLEMENT_HEADING.search(tail)
    item = _SUPPLEMENT_ITEM.search(tail)
    starts = [m.start() for m in (heading, item) if m is not None]
    if not starts:
        return body
    return body + "\n" + tail[min(starts):]


# The Methods heading standing alone on its line. A structured abstract writes
# "Methods:" inline, followed by prose on the same line, so requiring the line
# to end after the heading is what keeps the abstract out. This is the fault
# the diagnosis exposed: the first analysis cue can occur inside a structured
# abstract, after which _METHODS_END may cut the window at the abstract's own
# Results heading rather than reaching the manuscript Methods section.
_METHODS_HEADING = re.compile(
    r"^[ \t]*(?:\d+(?:\.\d+)*[.)]?[ \t]*)?"
    r"(?:materials?[ \t]+and[ \t]+methods?"
    r"|methods?(?:[ \t]+and[ \t]+materials?)?"
    r"|methodology"
    r"|statistical[ \t]+analys[ei]s)"
    r"[ \t]*:?[ \t]*$",
    re.M | re.I,
)
_SECTION_AFTER_METHODS = re.compile(
    r"^[ \t]*(?:\d+(?:\.\d+)*[.)]?[ \t]*)?"
    r"(?:results?|findings|discussion|conclusions?)"
    r"[ \t]*:?[ \t]*$",
    re.M | re.I,
)

# A heading in the first 3% of a document is a contents entry or a running
# head, not the section itself.
METHODS_MIN_POSITION = 0.03


@dataclass
class MethodsScope:
    text: Optional[str]
    reason: str
    start: Optional[int] = None
    end: Optional[int] = None


def methods_scope(full_text: str) -> MethodsScope:
    """
    The review's own methods, located by section heading rather than by cue.

    Prototype of the replacement for `scoped_synthesis_text()`, kept here
    because app/design_expectations.py is inside the fingerprint. The two
    recorded failure modes of the cue-first approach are both addressed:
    an analysis cue may be absent, or the first cue may occur in a structured
    abstract rather than the Methods section. A standalone section heading is
    therefore used as the stronger structural signal.
    """
    floor = int(len(full_text) * METHODS_MIN_POSITION)
    heading = None
    for match in _METHODS_HEADING.finditer(full_text):
        if match.start() >= floor:
            heading = match
            break
    if heading is None:
        return MethodsScope(None, "no stand-alone methods heading after the "
                                  f"first {METHODS_MIN_POSITION:.0%} of the document")

    start = heading.end()
    rest = full_text[start:]
    closer = _SECTION_AFTER_METHODS.search(rest)
    end = start + closer.start() if closer else len(full_text)
    return MethodsScope(full_text[start:end],
                        f"heading {heading.group(0).strip()!r}",
                        start, end)


# ---------------------------------------------------------------------------
# The gate: does this paper owe Bayesian reporting at all?
# ---------------------------------------------------------------------------

# (name, pattern, strength). Patterns run against normalised lowercased text.
_BAYESIAN_SIGNALS: List[Tuple[str, str, str]] = [
    ("credible interval",
     r"\bcredible\s+interval\w*|\b\d{2}%\s*cr[il]s?\b|\bcredible\s+region",
     "strong"),
    ("posterior summary",
     r"\bposterior\s+(?:distribution|mean|median|mode|probabilit|estimate|"
     r"sample|draw|predictive|sd\b|standard\s+deviation|summar|interval)",
     "strong"),
    ("bayesian analysis named",
     r"\bbayesian\s+(?:model|models|analys[ei]s|framework|approach|estimation|"
     r"inference|regression|meta[- ]analys[ei]s|network|hierarch|multilevel|"
     r"method|statistic)",
     "strong"),
    ("prior specification", "", "strong"),          # filled in below
    ("bayes factor", r"\bbayes\s*factors?\b", "strong"),
    # ROPE is guarded: "rope skipping" appears in a reference title in the
    # Muay Thai paper.
    ("HDI or ROPE",
     r"\bhdi\b|\bhighest\s+(?:posterior\s+)?density\s+interval"
     r"|\bregion\s+of\s+practical\s+equivalence"
     r"|\brope\s*(?:\[|\(|=|:|analys|interval|test|bound)",
     "strong"),
    ("named Bayesian software", "", "strong"),      # filled in below
    ("MCMC", r"\bmcmc\b|\bmarkov\s+chain\s+monte\s+carlo\b", "strong"),
    ("information criterion",
     r"\bdic\b|\bwaic\b|\bloo(?:ic)?\b|\bdeviance\s+information\s+criterion",
     "weak"),
    ("the word Bayesian", r"\bbayesian\b", "weak"),
    ("the word posterior", r"\bposterior\b", "weak"),
]

# ---------------------------------------------------------------------------
# Element patterns
# ---------------------------------------------------------------------------

# Priors. Ordinary English "prior" is the central ambiguity: phrases such as
# "prior research", "prior information", "prior to modelling" and "prior
# approaches" need not specify a statistical prior. The pattern therefore never
# matches the bare word; it requires the statistical sense. Being generous here is the
# safe direction, because a generous PRESENCE pattern suppresses a finding
# rather than inventing one.
# The ordinary-English collocations of "prior". Everything else is treated as
# the statistical sense. Listing the everyday uses rather than the statistical
# ones is the safe direction: an unlisted everyday phrase produces a false
# PRESENT, which suppresses a finding, whereas an unlisted statistical phrase
# would produce a false ABSENCE, which accuses. Myers et al. 2020 is why this
# exists: "a jeffrey's prior on sigma and a zellner-siow cauchy prior on model
# coefficients" was reported as an absence by a pattern that listed families.
_PRIOR_ORDINARY = (
    r"to|research|work|study|studies|literature|evidence|finding|findings|"
    r"knowledge|information|experience|approach|approaches|art|notice|consent|"
    r"history|report|reports|data|investigation|investigations|publication|"
    r"publications|paper|papers|author|authors|season|seasons|year|years|"
    r"week|weeks|day|days|month|months|hour|hours|minute|minutes|"
    r"training|injury|injuries|exposure|testing|test|tests|visit|visits|"
    r"session|sessions|attendance|participation|involvement|competition|"
    r"screening|surgery|illness|infection|diagnosis|treatment|medication|"
    r"use|uses|usage|contact|engagement|employment|service|services|"
    r"education|qualification|qualifications|performance|results|record|records|"
    r"convictions|agreement|arrangement|permission|approval|"
    r"night|nights|episode|episodes|attempt|attempts|"
    r"experiences|selection|version|versions|feature|features|"
    r"appointment|appointments|arrangement|arrangements|assessment|assessments"
)

# The plural is not excluded by the same list. "Different priors to examine the
# influence of measurement error" is a prior sensitivity analysis, not the
# preposition, and the singular list read it as one. Ordinary English has
# essentially no plural use of "priors" in this corpus.
_PRIORS_ORDINARY = r"research|studies|work|literature"

_PRIOR_PATTERN = (
    rf"\bprior\b(?!\s+(?:{_PRIOR_ORDINARY})\b)"
    rf"|\bpriors\b(?!\s+(?:{_PRIORS_ORDINARY})\b)"
    r"|\bprior\s+(?:distribution|specification|densit|belief|variance|scale|"
    r"mean|choice|selection|sensitivit|predictive|elicitation|probabilit)"
    r"|\bprior\s+(?:was|were|is|are)\s+(?:set|specified|chosen|assigned|placed|"
    r"used|defined|given|assumed|selected)"
    r"|\b(?:non[- ]?informative|uninformative|weakly[- ]?informative|informative|"
    r"vague|flat|diffuse|default|conjugate|regularis\w+|regulariz\w+|shrinkage|"
    r"horseshoe|jeffreys|reference)\s+prior"
    r"|\bhyper[- ]?prior"
    r"|\bhalf[- ]?cauchy\b|\binverse[- ]?gamma\b|\blkj\b"
    r"|\bset_prior\b|\bprior\s*=|\bd(?:norm|unif|gamma|beta)\s*\("
    r"|\bnormal\s*\(\s*0\s*,|\bstudent_t\s*\(|\bcauchy\s*\(\s*0\s*,"
)
_PRIOR_SEARCHED = (
    '"priors", and "prior" in any use except its ordinary-English collocations '
    '(prior to, prior research, prior use, prior experience and the like); '
    '"prior distribution", "prior specification", "prior sensitivity", '
    'a prior paired with a setting verb, the named prior families '
    '(non-informative, weakly informative, vague, flat, diffuse, conjugate, '
    'horseshoe, Jeffreys), hyperprior, half-Cauchy, inverse-gamma, LKJ, and the '
    'BUGS/Stan/brms declaration forms (dnorm(, dunif(, set_prior, prior =, '
    'normal(0,, student_t(). The bare word "prior" does not count, because in '
    'ordinary English it means "earlier"'
)

# Convergence. A named diagnostic or nothing. See design decision 2 above.
_CONVERGENCE_PATTERN = (
    # R-hat reaches the text layer in at least three encodings across this
    # corpus: "r-hat" (Eustace et al. 2025), "r̂" as r plus a combining
    # circumflex (Myers et al. 2020), and "r ̂" with a space between them
    # (Cullen et al., sleep deprivation). Matching only the spelled form
    # reported two of the three as missing convergence diagnostics.
    r"\br[\s\-]?hat\b|\brhat\b|r\s*[\u0302\u02c6\^]|\\hat\s*\{\s*r\s*\}"
    r"|\bpotential\s+scale[\s\-]reduction|\bpsrf\b"
    r"|\bgelman[\s\-]?rubin|\bbrooks[\s\-]?gelman"
    # Bare "ESS" is deliberately excluded: PDF extraction splits words, and
    # "str ess" and "ass ess" both occur in this corpus.
    r"|\beffective\s+sample\s+size|\bn[_\s]?eff\b"
    r"|\bbulk[\s\-]ess\b|\btail[\s\-]ess\b"
    r"|\btrace[\s\-]?plots?\b|\btraceplots?\b"
    r"|\bdivergent\s+transition"
    r"|\bgeweke\b|\bheidelberger\b|\braftery[\s\-]lewis\b"
    r"|\bautocorrelation\s+(?:plot|function)\b"
    r"|\bmcse\b|\bmonte\s+carlo\s+standard\s+error"
    r"|\bconvergence\s+(?:diagnostic|statistic|criteri)"
)
_CONVERGENCE_SEARCHED = (
    'R-hat in its spelled and circumflex forms, potential scale reduction, '
    'PSRF, Gelman-Rubin, Brooks-Gelman, '
    'effective sample size, n_eff, bulk-ESS, tail-ESS, trace plot, '
    'divergent transitions, Geweke, Heidelberger, Raftery-Lewis, autocorrelation '
    'plot, MCSE, and "convergence" paired with diagnostic, statistic or '
    'criterion. The bare word "convergence" does not count, because it is a '
    'claim rather than a diagnostic'
)

# Sampler settings. Every alternative requires a number, and "warm-up" requires
# sampler vocabulary beside it. See design decision 3 above.
_SAMPLER_PATTERN = (
    # "samples" must not be "sample size". Marginal line-number artefacts can
    # also become attached to that phrase. These are false PRESENTS, which can
    # suppress a true absence of sampler settings.
    r"\b\d[\d,]*\s+(?:mcmc\s+|posterior\s+)?(?:iterations?|samples?(?!\s+size)|draws?)\b"
    r"|\biterations?\s*[:=]\s*\d"
    r"|\b(?:two|three|four|five|six|eight|ten|\d+)\s+"
    r"(?:parallel\s+|independent\s+|markov\s+|mcmc\s+)?chains?\b"
    r"|\bchains?\s*[:=]\s*\d"
    r"|\bburn[\s\-]?in\s+(?:period\s+|phase\s+)?(?:of\s+)?\d"
    r"|\b\d[\d,]*\s+burn[\s\-]?in\b"
    r"|\bwarm[\s\-]?up\s+(?:of\s+)?\d[\d,]*\s*(?:iterations?|samples?|draws?)\b"
    r"|\b\d[\d,]*\s+warm[\s\-]?up\s+(?:iterations?|samples?|draws?)\b"
    r"|\bthin(?:ning)?\s+(?:interval\s+)?(?:of\s+|every\s+)?\d|\bthinned\s+(?:by\s+)?(?:every\s+)?\d"
    r"|\badapt(?:ation|ive)\s+(?:phase|period)\s+of\s+\d"
)
_SAMPLER_SEARCHED = (
    'a number beside iterations, draws, chains, or samples where the word is not '
    '"sample size"; "burn-in" or '
    '"thinning" followed by a number; an adaptation phase of a stated length. '
    'Bare "warm-up" is deliberately excluded, because in a sport science corpus '
    'it means the exercise warm-up'
)

_SOFTWARE_PATTERN = (
    # "stan" is guarded because extraction splits "gold standard" into
    # "gold stan - dard" in Eustace et al. 2025, which the bare word matched.
    r"\b(?:rstan|cmdstanr?|pystan)\b|\bstan\b(?!\s*-\s*dard)"
    r"|\bbrms\b|\brstanarm\b|\bblavaan\b"
    r"|\bjags\b|\brjags\b|\brunjags\b|\br2jags\b"
    r"|\b(?:win|open)?bugs\b"
    r"|\bnimble\b|\bpymc\d?\b|\bmcmcglmm\b|\bmcmcpack\b"
    r"|\bmbnmadose\b|\bgemtc\b|\bbayesmeta\b|\bmetabma\b|\bmulti[- ]?nma\b"
    r"|\bbayesplot\b|\barviz\b|\bgreta\b|\bturing\b"
    r"|\br[\s\-]?inla\b|\binla\b|\bmlwin\b|\bbayesfactor\b"
)
_SOFTWARE_SEARCHED = (
    'Stan, RStan, CmdStan, PyStan, brms, rstanarm, blavaan, JAGS, rjags, '
    'runjags, BUGS, WinBUGS, OpenBUGS, NIMBLE, PyMC, MCMCglmm, MCMCpack, '
    'MBNMAdose, gemtc, bayesmeta, metaBMA, multinma, bayesplot, ArviZ, greta, '
    'Turing, INLA, MLwiN, BayesFactor'
)

for _i, (_name, _pat, _strength) in enumerate(_BAYESIAN_SIGNALS):
    if _name == "prior specification":
        _BAYESIAN_SIGNALS[_i] = (_name, _PRIOR_PATTERN, _strength)
    elif _name == "named Bayesian software":
        _BAYESIAN_SIGNALS[_i] = (_name, _SOFTWARE_PATTERN, _strength)


# ---------------------------------------------------------------------------
# Evidence of doing, as distinct from describing
# ---------------------------------------------------------------------------

# A paper discussing Bayesian methods can contain several strong Bayesian
# signals while fitting no model itself. In that case, absence findings about
# priors or software would be irrelevant because the paper has no Bayesian
# analysis for which those elements are owed.
#
# This is the contamination argument of section 10.2 of the design note in its
# general form: it applies to evidence syntheses describing included studies'
# methods and to methodological papers discussing methods they do not use.
#
# The gate therefore also requires one signal that an analysis was RUN, not
# merely discussed. The narrowest true case is the body-size paper, which names
# no software, reports no diagnostic and gives no numeric interval, but does say
# that "a series of bayesian models were also fitted"; without the last of these
# signals the gate would close on it and three true findings would be lost.

_NUM = r"[-+]?\d+(?:[.,]\d+)?"

_DOING_SIGNALS: List[Tuple[str, str]] = [
    ("named software", _SOFTWARE_PATTERN),
    ("a numeric credible interval",
     rf"(?:credible\s+interval|\b\d{{2}}%\s*cr[il]s?\b|\bhdi\b"
     rf"|highest\s+(?:posterior\s+)?density\s+interval)"
     rf"[^.\n]{{0,90}}?{_NUM}\s*(?:to|,|;|:|–|—|-|−)\s*{_NUM}"),
    ("sampler settings", _SAMPLER_PATTERN),
    ("a convergence diagnostic", _CONVERGENCE_PATTERN),
    ("a numeric Bayes factor",
     rf"bayes\s*factors?[^.\n]{{0,40}}?{_NUM}|\bbf\s*_?[01]{{1,2}}\s*[=:]\s*{_NUM}"),
    ("a numeric posterior summary",
     rf"posterior\s+(?:mean|median|mode|probabilit\w+|estimate|sd"
     rf"|standard\s+deviation)[^.\n]{{0,60}}?{_NUM}"),
    ("a statement that a model was fitted",
     r"\bbayes\w*\b[^.\n]{0,70}\b(?:model|models|analys[ei]s|regression|"
     r"framework|approach)\b[^.\n]{0,70}\b(?:was|were)\s+(?:also\s+|then\s+|"
     r"subsequently\s+)?(?:fitted|fit|estimated|implemented|run|conducted|"
     r"performed|applied|specified|constructed)\b"
     r"|\b(?:we|the\s+authors)\s+(?:also\s+)?(?:fitted|fit|estimated|"
     r"implemented|ran|conducted|performed|applied|specified)\b[^.\n]{0,70}\bbayes\w*"
     r"|\b(?:was|were)\s+(?:also\s+)?(?:fitted|fit|estimated|implemented|run)\b"
     r"[^.\n]{0,50}\busing\s+(?:a\s+|the\s+)?bayes\w*"),
]


@dataclass
class GateVerdict:
    fired: bool
    strong: List[str] = field(default_factory=list)
    weak: List[str] = field(default_factory=list)
    doing: List[str] = field(default_factory=list)
    scope: str = ""

    def describe(self) -> str:
        if not self.fired:
            found = self.strong + self.weak
            reason = ""
            if len(self.strong) >= MIN_STRONG_SIGNALS and not self.doing:
                reason = ("; the paper describes Bayesian methods but nothing "
                          "shows an analysis was run")
            return ("bayesian gate: closed"
                    + (f" (only: {', '.join(found)}{reason})" if found
                       else " (no signal)"))
        line = f"bayesian gate: open on {len(self.strong) + len(self.weak)} signals"
        line += f" [strong: {', '.join(self.strong)}]"
        if self.weak:
            line += f" [weak: {', '.join(self.weak)}]"
        line += f" [ran: {', '.join(self.doing)}]"
        if self.scope:
            line += f" (scope: {self.scope})"
        return line


def bayesian_gate(text: str, scope: str = "") -> GateVerdict:
    """
    Fire only on evidence that the paper reports Bayesian output.

    Two or more distinct STRONG signals, per constraint 18.3.3, AND at least one
    signal that an analysis was actually run rather than discussed. This is what
    makes priors and convergence owed; unlike MethodClass it cannot be carried
    by the ordinary-English word "prior", and unlike the first version of this
    gate it does not open on a paper arguing about Bayesian methods.
    """
    lowered = de.normalise_extraction(text)
    strong: List[str] = []
    weak: List[str] = []
    for name, pattern, strength in _BAYESIAN_SIGNALS:
        if re.search(pattern, lowered):
            (strong if strength == "strong" else weak).append(name)
    doing = [name for name, pattern in _DOING_SIGNALS if re.search(pattern, lowered)]
    fired = len(strong) >= MIN_STRONG_SIGNALS and bool(doing)
    return GateVerdict(fired, strong, weak, doing, scope)


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------

def _absence(key: str, label: str, pattern: str, searched: str,
             detail: str = "") -> Callable[[str], Finding]:
    compiled = re.compile(pattern)

    def check(body: str) -> Finding:
        if compiled.search(body):
            return Finding(key, "present", f"{label} located.", searched)
        return Finding(key, "absent", f"No {label.lower()} located.", searched, detail)

    return check


_check_priors = _absence(
    "priors", "Prior distributions",
    _PRIOR_PATTERN, _PRIOR_SEARCHED,
    "A Bayesian analysis owes a statement of the priors placed on its parameters.",
)

_check_convergence = _absence(
    "convergence", "Convergence diagnostics",
    _CONVERGENCE_PATTERN, _CONVERGENCE_SEARCHED,
    "A claim that the chains converged is not a diagnostic.",
)

_check_sampler = _absence(
    "sampler", "Sampler settings",
    _SAMPLER_PATTERN, _SAMPLER_SEARCHED,
    "Chains, iterations, burn-in or thinning, with the numbers used.",
)

_check_software = _absence(
    "software", "Named Bayesian software or sampler",
    _SOFTWARE_PATTERN, _SOFTWARE_SEARCHED,
)

BAYESIAN_ELEMENTS: List[Callable[[str], Finding]] = [
    _check_priors,
    _check_convergence,
    _check_sampler,
    _check_software,
]


@dataclass
class MethodVerdict:
    gate: GateVerdict
    findings: List[Finding] = field(default_factory=list)
    scope_note: str = ""

    @property
    def absent(self) -> List[Finding]:
        return [f for f in self.findings if f.kind == "absent"]

    @property
    def present(self) -> List[Finding]:
        return [f for f in self.findings if f.kind == "present"]


def check_method_elements(full_text: str,
                          is_evidence_synthesis: bool = False,
                          include_supplement: bool = True) -> MethodVerdict:
    """
    Run the analysis-framework registry.

    The GATE is evaluated on the review's own methods when the document is an
    evidence synthesis, because the body of a review describes the included
    studies' analyses and the gate is a question of attribution. The ELEMENTS
    are searched over the whole analysis text including the supplement,
    because a diagnostic may be reported anywhere and an absence check must
    not accuse on the strength of 30% of a document.
    """
    body = analysis_text(full_text, include_supplement=include_supplement)

    if is_evidence_synthesis:
        scope = methods_scope(full_text)
        if scope.text is None:
            return MethodVerdict(
                GateVerdict(False, scope=scope.reason),
                [],
                "evidence synthesis: the review's own methods could not be "
                f"located ({scope.reason}); no framework expectations applied",
            )
        gate = bayesian_gate(scope.text, scope=f"methods section, {scope.reason}")
        note = ("evidence synthesis: the gate was evaluated on the review's own "
                "methods, the elements over the whole document")
    else:
        gate = bayesian_gate(body, scope="body and supplement")
        note = ""

    if not gate.fired:
        return MethodVerdict(gate, [], note)

    return MethodVerdict(gate, [check(body) for check in BAYESIAN_ELEMENTS], note)


def format_method_elements_section(verdict: MethodVerdict) -> str:
    """
    Render the report section. Empty when nothing is absent, so a paper that
    reports everything adds nothing.

    Every line carries the terms that were searched, per constraint 18.3.2.
    This is not a set of concerns: it does not enter the items table, does not
    consume the concern budget, and is not labelled Verified or Inferred.
    """
    absent = verdict.absent
    if not absent:
        return ""
    parts = [
        "# Expected reporting elements (analysis framework)",
        "",
        "This analysis is Bayesian on "
        f"{len(verdict.gate.strong) + len(verdict.gate.weak)} deterministic "
        f"signals ({', '.join(verdict.gate.strong + verdict.gate.weak)}). The "
        "following elements were not located in the extracted text. This is a "
        "keyword search, not a reading: a term the authors phrased differently "
        "will appear here wrongly. Verify before acting on any line.",
        "",
    ]
    parts.extend(f.line() for f in absent)
    return "\n".join(parts).rstrip() + "\n"
