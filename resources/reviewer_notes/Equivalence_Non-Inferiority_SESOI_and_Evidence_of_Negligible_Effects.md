# Equivalence, Non-Inferiority, SESOI and Evidence of Negligible Effects

## Purpose

Researchers often need to distinguish between evidence that an effect
exists and evidence that any effect is small enough to be
scientifically, practically or clinically negligible. Ordinary
non-significance does not establish the latter.

This note provides guidance for evaluating claims involving smallest
effect sizes of interest (SESOIs), smallest worthwhile effects (SWEs),
equivalence testing, the two one-sided tests (TOST) procedure,
non-inferiority, minimum-effect questions, and Bayesian approaches to
evaluating negligible effects.

The central reviewing principle is:

> **The statistical procedure should match the scientific question, and
> the threshold defining what matters should be substantively
> justified.**

A reviewer should distinguish the size of effect that would matter, the
amount of ordinary or measurement variation, the precision with which
the effect has been estimated, and the inferential question actually
tested.

------------------------------------------------------------------------

## A. Smallest Effect Size of Interest and Smallest Worthwhile Effect

### What is a SESOI?

A **Smallest Effect Size of Interest (SESOI)** is a threshold
representing an effect sufficiently large to matter for the scientific,
practical, clinical or other substantive purpose under consideration.

In sport and exercise science, closely related terminology such as
**smallest worthwhile effect (SWE)** is also common. The terms are often
used for similar purposes, but reviewers should not automatically assume
that differently named thresholds have been defined identically. Authors
should make clear what their threshold represents and how it was
derived.

A SESOI or SWE can be expressed on a raw or standardised scale and need
not be symmetric around zero. The appropriate scale and direction depend
on the substantive question.

### How should a SESOI or SWE be justified?

A threshold should answer a meaningful substantive question rather than
merely provide a convenient statistical cut-off.

Possible justifications can include:

-   theory or prior substantive knowledge;
-   clinical, performance or practical consequences;
-   stakeholder or expert judgement;
-   anchor-based approaches;
-   cost-benefit or decision considerations;
-   prior empirical work;
-   natural constraints of the outcome;
-   justified combinations of these considerations.

Generic conventional benchmarks such as describing a standardised effect
as "small" are not, by themselves, strong justification for a SESOI or
SWE. A conventional benchmark becomes substantively meaningful only when
there is a defensible reason why that magnitude matters in the context
being studied.

Where possible, the threshold should be specified independently of the
observed result. Choosing or changing a threshold after seeing the data
risks allowing the result to determine the scientific question.

### How do natural variation and measurement error relate to the SESOI or SWE?

A SESOI or SWE should not automatically be equated with measurement
error, typical error, reliability statistics, or natural biological or
within-person variation. These quantities answer different questions.

The SESOI or SWE concerns:

> **How large would an effect need to be to matter?**

Measurement error concerns:

> **How much observed variation may arise from the measurement
> process?**

Natural or within-person variation concerns:

> **How much might the underlying outcome fluctuate in the absence of
> the intervention or effect of interest?**

Natural variation is itself context-dependent. Its magnitude can depend
on the outcome, population, measurement procedure, timescale, training
status, environmental conditions and the sources of within-person or
between-occasion variability being considered.

Measurement error and natural variation can nevertheless be relevant
when choosing and interpreting a SESOI or SWE. In some applied settings,
particularly sport and exercise science, ordinary variation in
performance or measurement may reasonably inform judgements about what
change would be useful or interpretable.

However:

> **Natural variation should not itself define what is worthwhile.**

A threshold can exceed estimated natural variation or measurement error
and still represent an effect too small to matter. Conversely, a
substantively important effect can be difficult to distinguish from
natural variation or measurement error with the available measurement,
sample and design.

Reviewers should therefore distinguish three questions:

1.  **Is the effect large enough to matter?** --- substantive importance
    and the SESOI/SWE.
2.  **Is the effect distinguishable from ordinary fluctuation and
    measurement error?** --- variability and measurement properties.
3.  **Does the study provide sufficiently precise evidence to support
    the intended inference?** --- inferential precision.

Satisfying one of these conditions does not automatically satisfy the
others.

------------------------------------------------------------------------

## B. Equivalence Testing and TOST

### What question does equivalence testing answer?

Equivalence testing asks whether effects at or beyond prespecified
bounds representing meaningful effects can be rejected.

For a parameter (`\theta`{=tex}), with lower and upper equivalence
bounds (`\Delta`{=tex}\_L) and (`\Delta`{=tex}\_U), the equivalence
region is:

\[ `\Delta`{=tex}\_L \< `\theta `{=tex}\< `\Delta`{=tex}\_U \]

The bounds should represent effects outside the range that would be
considered negligible for the stated purpose. They are commonly derived
from a SESOI.

Equivalence testing therefore does **not** ask whether the effect is
exactly zero. It asks whether effects regarded as meaningfully large can
be excluded with the specified frequentist error control.

### How does TOST work?

The **two one-sided tests (TOST)** procedure tests two composite null
hypotheses:

\[ H\_{01}: `\theta `{=tex}`\leq `{=tex}`\Delta`{=tex}\_L \]

and

\[ H\_{02}: `\theta `{=tex}`\geq `{=tex}`\Delta`{=tex}\_U \]

against the alternative:

\[ `\Delta`{=tex}\_L \< `\theta `{=tex}\< `\Delta`{=tex}\_U \]

Both one-sided null hypotheses must be rejected to conclude statistical
equivalence at the chosen alpha level.

A successful TOST therefore provides frequentist evidence against
effects at or beyond both equivalence bounds, under the model
assumptions and specified error rate.

It does **not** establish that the true effect is exactly zero.

### Confidence-interval formulation

For the usual TOST procedure conducted with each one-sided test at level
(`\alpha`{=tex}), the equivalent confidence-interval criterion is that
the entire:

\[ 100(1-2`\alpha`{=tex})% \]

confidence interval lies within the equivalence bounds.

Thus, when each one-sided test uses (`\alpha`{=tex}=.05), the
corresponding interval is a **90% confidence interval**, not a 95%
confidence interval.

If the complete 90% confidence interval lies within the equivalence
bounds, this corresponds to rejecting both one-sided null hypotheses at
(`\alpha`{=tex}=.05).

A reviewer should therefore be cautious about claims that a 95%
confidence interval must fall inside the bounds for a conventional
(`\alpha`{=tex}=.05) TOST. That criterion is more stringent than the
standard TOST criterion.

### What does a successful TOST establish?

A successful TOST supports the conclusion that effects at or beyond the
specified equivalence bounds can be rejected at the chosen frequentist
error rate.

The substantive interpretation depends critically on the bounds. Narrow,
well-justified bounds may support a strong claim that any remaining
plausible effect is too small to matter for the stated purpose. Very
wide or poorly justified bounds can make a formally correct equivalence
result substantively uninformative.

Equivalence is therefore always **relative to the specified bounds and
their justification**.

### What does a failed TOST establish?

Failure to reject one or both equivalence null hypotheses means that
equivalence has **not been established**.

It does not demonstrate that a meaningful effect exists.

An imprecise study can therefore produce a result that is neither
statistically different from zero nor statistically equivalent. This is
an inconclusive result rather than evidence for either a meaningful
effect or negligible effect.

### Evidence for equivalence versus strength of evidence

It is important to distinguish two statements:

> **TOST can provide evidence supporting equivalence relative to
> prespecified bounds.**

and:

> **The TOST decision is not a posterior probability that the effect is
> equivalent, nor is the reject/fail-to-reject decision itself a general
> continuous scale of evidential strength.**

These statements are compatible.

TOST is designed to test whether effects at or beyond the equivalence
bounds can be rejected while controlling a frequentist error rate. The
component test statistics, p-values, estimates and confidence intervals
contain information that can vary continuously, but they should not be
interpreted as posterior probabilities of equivalence or as a generic
probability that the negligible-effect hypothesis is true.

A reviewer should therefore reject both extremes:

-   claiming that TOST **cannot provide evidence of absence or
    equivalence** is too strong; and
-   interpreting a successful TOST as the **probability that equivalence
    is true** is incorrect.

### Why ordinary non-significance is not enough

A non-significant conventional test against zero means that the null
hypothesis has not been rejected at the chosen threshold.

It does not establish that the effect is negligible.

A wide confidence interval can include both zero and effects large
enough to be scientifically important. Equivalence testing addresses a
different question by directly testing effects against substantively
defined bounds.

------------------------------------------------------------------------

## C. Equivalence, Non-Inferiority and Minimum-Effect Questions

### Equivalence

Equivalence testing is generally two-sided with respect to a region of
negligible effects. The aim is to exclude effects at or beyond both
equivalence bounds.

### Non-inferiority

A **non-inferiority** question is directional. It asks whether an effect
is not worse than a comparator by more than a prespecified
non-inferiority margin, where "worse" must be defined according to the
direction and scale of the outcome.

The margin requires substantive justification just as equivalence bounds
do.

Non-inferiority should not be treated as interchangeable with
equivalence. Demonstrating that a new treatment is not unacceptably
worse than a comparator does not, by itself, establish two-sided
equivalence.

### Minimum-effect questions

A minimum-effect test asks a different question again: whether an effect
is sufficiently large to exceed a prespecified threshold of substantive
importance.

This can be useful when the scientific claim is not merely that an
effect differs from zero but that it is at least large enough to matter.

Equivalence and minimum-effect tests therefore reverse the inferential
focus:

-   equivalence asks whether meaningfully large effects can be rejected;
-   a minimum-effect test asks whether effects too small to matter can
    be rejected.

Reviewers should identify the scientific question before deciding which
inferential procedure is appropriate.

### Alpha levels

The alpha level determines the frequentist decision threshold and
associated long-run error control. It should not be treated as a law of
nature.

Where an alpha level is used, its role should be clear and, where
appropriate, justified in relation to the inferential and decision
context.

Changing alpha after seeing the result undermines the intended
error-control interpretation.

------------------------------------------------------------------------

## D. Bayesian Approaches to Evaluating Negligible Effects

There is no single procedure that should be described as **the Bayesian
equivalent of TOST**.

Bayesian approaches can address questions about negligible effects in
several different ways, including:

-   estimating a posterior distribution and examining its location and
    uncertainty;
-   calculating the posterior probability that a parameter lies within a
    substantively negligible region;
-   using a region of practical equivalence (ROPE) as part of an
    estimation or decision procedure;
-   comparing interval or point hypotheses using Bayes factors;
-   applying an explicit Bayesian decision model with specified
    consequences or losses.

These approaches answer related but not identical questions.

### Posterior estimation

A Bayesian analysis produces a posterior distribution conditional on the
model, data and prior specification.

The posterior can be used to examine which parameter values remain
plausible under that model. A researcher may, for example, report the
posterior probability that an effect lies inside a substantively defined
negligible-effect region.

Such a probability is a direct posterior probability statement under the
specified model and prior. It should not be interpreted as model-free
evidence.

### ROPE

A **region of practical equivalence (ROPE)** defines a range of
parameter values regarded as practically negligible for a stated
purpose.

The substantive logic is therefore related to a SESOI or equivalence
region: the region itself requires justification.

Different Bayesian procedures use ROPEs differently. For example, some
procedures compare a posterior interval with the ROPE, whereas others
examine the posterior probability contained within the region.

A ROPE should therefore not simply be described as "Bayesian TOST". The
inferential quantities and decision rules differ.

### Posterior probability of a negligible region

A researcher may calculate:

\[ P(`\Delta`{=tex}\_L \< `\theta `{=tex}\< `\Delta`{=tex}\_U
`\mid `{=tex}`\text{data, model, prior}`{=tex}) \]

This directly quantifies the posterior probability assigned to the
specified negligible-effect region under the model and prior.

It answers a different inferential question from TOST. TOST controls
frequentist error rates when testing equivalence bounds;
posterior-region probability describes how posterior probability is
distributed relative to a specified region.

### Priors matter

Bayesian conclusions depend on the prior as well as the likelihood and
model.

Reviewers should therefore examine whether the prior is appropriate for
the scientific question and whether conclusions are sensitive to
reasonable alternative prior specifications when this could materially
affect interpretation.

### Bayes factors and interval hypotheses

Bayes factors can compare specified hypotheses or models, including
interval-null or interval-equivalence hypotheses when these are formally
defined.

A Bayes factor is a ratio of marginal likelihoods under the specified
hypotheses/models. It is not a posterior probability and it is not a
p-value.

Its interpretation depends on exactly which hypotheses and prior
distributions have been specified. A Bayes factor comparing an
interval-null hypothesis with an alternative can therefore address
evidence for a negligible-effect region, but it should not be assumed to
answer the same question as either TOST or a posterior-probability/ROPE
analysis.

### Do Bayesian approaches require equivalence margins?

Not universally.

Some Bayesian questions about practical negligibility require a
substantively defined region or threshold. For example, a posterior
probability that an effect is negligible cannot be calculated without
defining what "negligible" means.

Other Bayesian analyses may focus on estimation or comparison of
different hypotheses without using a TOST-style equivalence margin.

The substantive threshold and the inferential machinery should therefore
be distinguished.

------------------------------------------------------------------------

## E. Comparing Frequentist Equivalence and Bayesian Approaches

### What is the main difference?

Both frequentist and Bayesian approaches can address whether effects are
sufficiently small to be unimportant, but they quantify uncertainty
differently.

A conventional TOST analysis asks whether effects at or beyond specified
equivalence bounds can be rejected while controlling frequentist error
rates.

A Bayesian analysis might instead ask how much posterior probability
lies within a negligible-effect region, whether a posterior interval
lies largely or entirely within such a region under a chosen decision
rule, or how strongly specified hypotheses are supported relative to one
another through a Bayes factor.

The methods should therefore be compared by the inferential question and
quantity they produce rather than by treating one as a simple
translation of the other.

### Is ROPE simply Bayesian TOST?

No.

Both can use substantively defined regions around values regarded as
negligible, but their inferential logic differs.

TOST tests composite null hypotheses against an equivalence alternative
using frequentist sampling distributions and error control.

ROPE-based Bayesian procedures operate on posterior distributions and
require an explicit rule for how the posterior is to be interpreted
relative to the region.

Their substantive thresholds may be similar while their inferential
statements are not.

### Which approach is better?

There is no universal answer.

The appropriate method depends on:

-   the scientific question;
-   the inferential quantity researchers want;
-   the role of prior information;
-   the desired error or decision properties;
-   the quality of the substantive threshold;
-   the design and measurement properties;
-   the audience and intended use of the conclusion.

Reviewers should evaluate **inferential coherence rather than
philosophical labels**.

The important question is whether the method, threshold and conclusion
fit together.

------------------------------------------------------------------------

## F. Precision, Sample Size and Inconclusive Results

Equivalence questions can require substantial precision, especially when
the SESOI or SWE is small.

A study may therefore be able to detect a conventional difference from
zero while remaining too imprecise to establish equivalence, or vice
versa.

When the confidence or posterior interval is wide relative to the
substantive bounds, the appropriate conclusion may simply be that the
data do not distinguish adequately between negligible and meaningful
effects.

Reviewers should resist interpreting such results as evidence for
whichever conclusion is favoured.

Sample-size planning should reflect the intended inferential question. A
study designed only for power to reject a point null of zero may not
have adequate precision or power to establish equivalence against narrow
bounds.

------------------------------------------------------------------------

## G. Reviewing Claims About Negligible Effects

A reviewer should work through the following sequence.

### 1. What is the substantive question?

Is the study asking whether:

-   an effect exists?
-   an effect is negligible?
-   two conditions are equivalent?
-   one condition is non-inferior to another?
-   an effect exceeds a minimum worthwhile magnitude?
-   a particular decision should be made?

These are not interchangeable questions.

### 2. What threshold defines what matters?

Identify the SESOI, SWE, equivalence bound, non-inferiority margin, ROPE
or other substantive threshold.

Ask:

-   What does it represent?
-   Why does that magnitude matter?
-   Was it prespecified?
-   Is it expressed on an appropriate scale?
-   Are asymmetric consequences relevant?
-   Has measurement error or natural variation been confused with
    substantive importance?

### 3. Does the statistical procedure test the intended question?

Examples:

-   ordinary NHST against zero does not establish equivalence;
-   TOST can test equivalence relative to prespecified bounds;
-   non-inferiority is directional and does not automatically establish
    equivalence;
-   posterior probability within a region answers a different question
    from TOST;
-   Bayes factors depend on the hypotheses and priors actually compared.

### 4. Is the conclusion stronger than the analysis supports?

Distinguish carefully between:

-   no statistically detected difference;
-   evidence supporting equivalence;
-   evidence supporting non-inferiority;
-   evidence that an effect exceeds a meaningful threshold;
-   high posterior probability of a negligible region;
-   relative evidence from a Bayes factor;
-   an inconclusive result.

### 5. Are practical importance and detectability being conflated?

An effect can be statistically detectable but too small to matter.

An effect can be worthwhile but estimated too imprecisely to distinguish
it from natural variation or measurement error.

An observed change can exceed estimated natural variation and still be
too small to be worthwhile.

These statements concern different properties and should not be
collapsed into a single label such as "meaningful".

------------------------------------------------------------------------

## Common Problematic Claims

### "The result was not significant, therefore there was no effect."

Not established. Failure to reject a point null does not demonstrate
that effects large enough to matter are absent.

### "The confidence interval includes zero, therefore the treatments are equivalent."

Not established. Equivalence requires comparison with justified
equivalence bounds and an appropriate inferential procedure.

### "The estimate is inside the equivalence bounds, therefore equivalence is established."

Not necessarily. Uncertainty around the estimate matters. For standard
TOST, the corresponding confidence interval must satisfy the equivalence
criterion.

### "The TOST was not significant, therefore the treatments are different."

Incorrect. A failed TOST means equivalence was not established. It does
not establish a meaningful difference.

### "TOST cannot provide evidence of absence."

Too strong. A successful, appropriately specified TOST can provide
frequentist evidence against effects at or beyond the equivalence
bounds.

### "A successful TOST means there is a 95% probability that the treatments are equivalent."

Incorrect. TOST does not produce a posterior probability that
equivalence is true.

### "TOST is binary, so it provides no evidence about equivalence."

Misleading. TOST is an inferential procedure designed to test
equivalence and can provide evidence supporting equivalence relative to
specified bounds. Its reject/fail-to-reject decision should not,
however, be confused with a posterior probability or generic continuous
scale of evidential strength.

### "Bayesian analysis gives the probability that there is no effect."

Too vague. The probability statement depends on the parameter region or
hypothesis defined, the model, the data and the prior.

### "Bayesian methods require an equivalence margin."

Too broad. Some Bayesian analyses of practical negligibility require a
substantively defined region, but Bayesian inference does not
universally require a TOST-style equivalence margin.

### "A ROPE is just the Bayesian version of TOST."

Oversimplified. They may use related substantive thresholds, but their
inferential logic and quantities differ.

### "Cohen's small effect is our SESOI."

Not adequately justified by the label alone. A conventional benchmark
needs a substantive rationale for why that magnitude is important in the
particular context.

### "The observed change exceeded the typical or natural variation, therefore it was worthwhile."

Not necessarily. Exceeding an estimate of ordinary variation concerns
distinguishability from that source of variation. Whether the effect is
worthwhile requires a separate substantive judgement.

### "For TOST at alpha .05, the 95% confidence interval must lie inside the equivalence bounds."

Not for the standard TOST criterion. Two one-sided tests at
(`\alpha`{=tex}=.05) correspond to the 90% confidence interval lying
entirely within the equivalence bounds.

------------------------------------------------------------------------

## Reviewer Checklist

Before accepting a claim about equivalence, negligibility,
non-inferiority or practical importance, ask:

1.  What exact scientific question is being answered?
2.  What parameter or contrast represents that question?
3.  What SESOI, SWE, equivalence bound, margin or negligible-effect
    region has been defined?
4.  Why does that threshold matter substantively?
5.  Was the threshold determined independently of the observed result?
6.  Have substantive importance, natural variation and measurement error
    been kept conceptually distinct?
7.  Does the statistical procedure actually test the stated question?
8.  If TOST is used, are both one-sided hypotheses and the
    confidence-interval criterion interpreted correctly?
9.  Does failure to establish equivalence remain an inconclusive result
    rather than being converted into evidence of difference?
10. If non-inferiority is claimed, is the direction and margin clearly
    defined and justified?
11. If a Bayesian approach is used, what posterior quantity, ROPE rule,
    hypothesis comparison or decision rule is actually being used?
12. Are priors and model assumptions relevant to the conclusion
    adequately described?
13. Are the authors interpreting p-values, confidence intervals,
    posterior probabilities or Bayes factors according to what those
    quantities actually mean?
14. Is the estimate sufficiently precise relative to the substantive
    threshold?
15. Does the conclusion concern statistical detectability, substantive
    importance, or both---and are these kept distinct?

------------------------------------------------------------------------

## References

Lakens, D. (2017). Equivalence tests: A practical primer for *t* tests,
correlations, and meta-analyses. *Social Psychological and Personality
Science, 8*(4), 355--362. DOI: 10.1177/1948550617697177

Lakens, D., Scheel, A. M., & Isager, P. M. (2018). Equivalence testing
for psychological research: A tutorial. *Advances in Methods and
Practices in Psychological Science, 1*(2), 259--269. DOI:
10.1177/2515245918770963

Schuirmann, D. J. (1987). A comparison of the two one-sided tests
procedure and the power approach for assessing the equivalence of
average bioavailability. *Journal of Pharmacokinetics and
Biopharmaceutics, 15*(6), 657--680. DOI: 10.1007/BF01068419

Morey, R. D., & Rouder, J. N. (2011). Bayes factor approaches for
testing interval null hypotheses. *Psychological Methods, 16*(4),
406--419. DOI: 10.1037/a0024377

Kruschke, J. K., & Liddell, T. M. (2018). The Bayesian New Statistics:
Hypothesis testing, estimation, meta-analysis, and power analysis from a
Bayesian perspective. *Psychonomic Bulletin & Review, 25*(1), 178--206.
DOI: 10.3758/s13423-016-1221-4

Lakens, D., Adolfi, F. G., Albers, C. J., Anvari, F., Apps, M. A. J.,
Argamon, S. E., et al. (2018). Justify your alpha. *Nature Human
Behaviour, 2*, 168--171. DOI: 10.1038/s41562-018-0311-x

Anvari, F., & Lakens, D. (2021). Using anchor-based methods to determine
the smallest effect size of interest. *Journal of Experimental Social
Psychology, 96*, 104159. DOI: 10.1016/j.jesp.2021.104159

------------------------------------------------------------------------

*Original methodological guidance prepared by Tony Myers.*
