# Effect Sizes, Standardised Mean Differences and Practical Importance

#### Purpose

This guide helps reviewers evaluate the calculation, reporting and interpretation of effect sizes. It focuses on standardised mean differences (SMDs), including Cohen's *d* and Hedges' *g*, the influence of the standard deviation used in the denominator, uncertainty around effect estimates, and the use of conventional effect-size benchmarks. The emphasis is on interpreting magnitude in substantive context rather than mechanically applying generic thresholds.

#### What reviewers should look for

✓ The manuscript reports an effect size appropriate for the study design and outcome.

✓ The calculation of the effect size is sufficiently described to identify the numerator, denominator and any bias correction.

✓ For a standardised mean difference (SMD), the standard deviation used in the denominator is explicitly defined and applied consistently.

✓ Hedges' *g* is distinguished from Cohen's *d* and includes an appropriate small-sample bias correction.

✓ Effect sizes from within-participants designs are standardised in a way that is stated and comparable with the other effects reported.

✓ The direction of benefit is stated, and effect sizes measured on oppositely scored instruments are reoriented before being compared or combined.

✓ Confidence intervals or Bayesian credible intervals are reported so that uncertainty around effect magnitude can be assessed.

✓ Effect sizes are interpreted in the scientific, clinical or practical context rather than solely by generic labels such as small, medium and large.

#### Common reviewer questions

##### What is an effect size?

An **effect size** describes the magnitude of a difference, association or treatment effect.

Examples include:

- raw mean difference;
- standardised mean difference (SMD);
- Cohen's *d*;
- Hedges' *g*;
- correlation coefficients;
- odds ratios;
- risk ratios;
- hazard ratios;
- eta-squared (η²) and partial eta-squared;
- rank-biserial correlation.

An effect size should usually be interpreted together with its uncertainty and substantive importance.

##### What is a standardised mean difference (SMD)?

A **standardised mean difference (SMD)** expresses a difference between means relative to a measure of variability, usually a within-study standard deviation.

Standardisation allows effects measured using different scales to be expressed in common standard-deviation units.

Common SMDs include **Cohen's *d*** and **Hedges' *g***.

An SMD is dimensionless, but it is not independent of the population or study from which its standard deviation is obtained.

##### What is Hedges' g?

**Hedges' *g*** is a standardised mean difference that applies a small-sample bias correction to Cohen's *d*.

The correction is most important in small samples and becomes negligible as sample size increases.

Reviewers should check:

- how the uncorrected SMD was calculated;
- which standard deviation formed the denominator;
- whether the small-sample correction was applied;
- whether the same definition was used consistently across studies.

##### Why does the denominator of an SMD matter?

The denominator of an SMD contains a **study-specific estimate of variability**.

Consequently, the same absolute mean difference can produce different SMDs in different studies:

- a smaller SD produces a larger SMD;
- a larger SD produces a smaller SMD.

Differences in Hedges' *g* or Cohen's *d* therefore do not necessarily reflect differences in the underlying absolute treatment effect.

The SMD is influenced by both the **mean difference in the numerator** and the **variability in the denominator**.

##### Why might standard deviations differ between studies?

Study-specific SDs can differ because of:

- differences in population heterogeneity;
- inclusion and exclusion criteria;
- measurement reliability;
- range restriction;
- ceiling or floor effects;
- different instruments;
- baseline severity;
- genuine biological or behavioural variability.

Measurement error contributes to the observed standard deviation, so a less reliable instrument tends to inflate the denominator and shrink the SMD. A study using a noisier measure can report a smaller standardised effect than a study of the same underlying effect using a more reliable one, and a study with a narrowly defined sample can report a larger one.

Reviewers should therefore be cautious about interpreting differences in SMD solely as differences in treatment efficacy.

##### Which standard deviation should be used?

The appropriate denominator depends on the study design and effect-size definition.

Possible denominators include:

- pooled within-group post-intervention SD;
- control-group SD, which gives Glass's Δ;
- baseline SD;
- SD of change scores.

These are **not interchangeable**.

The manuscript should state clearly which denominator was used and why.

##### How should an SMD be calculated for a within-participants design?

Repeated-measures designs permit more than one standardiser, and they do not produce comparable numbers.

- Dividing by the **standard deviation of the change scores** gives a paired effect size, often written *d*z. Its size depends on the correlation between the repeated measurements: the more strongly the measurements correlate, the smaller the SD of the change scores and the larger the effect size, for the same mean change.
- Dividing by the **pooled SD of the raw scores** places the effect on the same footing as a between-groups SMD.

A *d*z can be considerably larger than the between-groups effect size derived from the same data, so the two should not be pooled or compared without conversion. Reviewers should expect the standardiser to be named, and should treat unusually large within-participants effects reported alongside between-groups effects as a reporting question before a substantive one.

##### Are effect sizes aligned in direction?

Where outcomes are scored in opposite directions — one instrument on which higher scores indicate better function, another on which higher scores indicate worse — effect sizes must be reoriented before they are compared or combined.

Errors of this kind are easy to make and difficult to see, because a reversed estimate appears simply as an outlying effect rather than as a mistake.

Reviewers should check that the direction of benefit is stated explicitly and applied consistently across outcomes and studies.

##### Can a missing SD be reconstructed?

Sometimes.

A standard deviation may be reconstructed from:

- a standard error;
- a confidence interval;
- a *t*-statistic;
- a *p*-value;
- another reported measure of uncertainty.

However, the correct reconstruction depends on the original study design and statistical analysis.

A statistic from a paired test, Welch test, adjusted regression model or independent-groups test should not automatically be converted using the same formula.

Reviewers should expect the reconstruction method and its assumptions to be reported transparently.

##### Should reconstructed SDs be examined in sensitivity analyses?

Usually yes when reconstructed or imputed SDs contribute materially to the evidence.

Useful sensitivity analyses may compare results:

- with and without studies requiring reconstructed SDs;
- under alternative plausible assumptions;
- using alternative estimates of within-participant correlation where change-score SDs must be derived.

Two things are commonly left out. The within-participant correlation assumed when deriving change-score SDs should be varied across a plausible range rather than fixed at a single convenient value, and the value used should come from studies reporting enough to estimate it rather than from convention. And the sensitivity analysis should report the effect on the estimated heterogeneity as well as on the pooled effect, because imputed variability tends to suppress apparent heterogeneity and so narrows the interval around the pooled estimate twice over.

A statement that results were robust is not a sensitivity analysis. Reviewers should expect both estimates to be shown, and the studies requiring reconstruction to be named along with the route used for each.

The purpose is to determine whether conclusions depend on uncertain estimates of variability.

##### Would the conclusions change if effects were described continuously?

This is worth checking directly rather than in principle.

Take each sentence in the abstract and conclusions that carries a label, and rewrite it with the estimate and its interval in place of the word. If the sentence still stands, the categories were decoration. If it collapses, the categories were carrying the argument, and the conclusion rests on a convention rather than on the evidence.

Comparisons made by label deserve particular attention. A finding described as moderate in one subgroup and small in another, where the two intervals overlap substantially, is an artefact of categorisation rather than a difference between the groups.

The constructive form of the request is for the primary conclusions to be restated in terms of the estimates and their uncertainty, against a meaningful threshold where one can be defended for the outcome in question.

##### What if several effect sizes come from the same participants?

Multiple outcomes, time points or treatment comparisons from the same participants produce **dependent effect sizes**.

Treating these effects as independent can overstate the amount of information and underestimate uncertainty.

Reviewers should check whether dependence was handled using an appropriate approach, such as:

- multilevel or multivariate modelling;
- an explicit covariance structure;
- robust variance estimation, with a small-sample correction where the number of studies is modest;
- a prespecified rule for selecting one effect estimate.

Selecting a single outcome per study, or averaging outcomes within a study, are simpler alternatives that discard information. Whichever approach is taken, it should be prespecified rather than chosen once the results are visible.

##### Are Cohen's 0.2, 0.5 and 0.8 benchmarks standards?

No.

The familiar conventions for standardised mean differences:

- about 0.2 = small;
- about 0.5 = medium;
- about 0.8 = large;

are generic **rules of thumb**, not universal scientific thresholds.

Cohen offered them as a convenience for power calculations where no better basis was available, and cautioned against relying on them routinely. They carry no information about the outcome, the population, the instrument or the decision at hand.

They are best treated as fallback descriptors when more meaningful contextual benchmarks are unavailable.

##### Why can Cohen's benchmarks be misleading?

The practical importance of an effect depends on context.

An SMD of 0.3 may be important when:

- the intervention is cheap and safe;
- the outcome is important;
- effects accumulate over time;
- the population has few effective alternatives.

An SMD of 0.8 may be less important if the outcome is trivial, the intervention is costly, or harms outweigh benefits.

Where possible, reviewers should prefer:

- minimally important differences;
- clinically meaningful thresholds;
- domain-specific benchmarks;
- the distribution of effects reported in the relevant literature;
- comparison with effects from relevant previous studies.

##### Is an effect of 0.49 meaningfully different from 0.51?

No.

Effect sizes are continuous.

Categorising 0.49 as "small" and 0.51 as "medium" creates an artificial distinction that is not present in the underlying evidence.

Reviewers should avoid interpreting conventional effect-size categories as sharp boundaries.

##### Should uncertainty affect the description of effect magnitude?

Yes.

An effect estimate should not be classified from the point estimate alone.

For example, an estimated Hedges' *g* of 0.50 with a wide interval may remain compatible with:

- negligible effects;
- small effects;
- moderate effects;
- or even effects in the opposite direction.

Reviewers should interpret the effect estimate together with its confidence interval or Bayesian credible interval.

##### Is statistical significance the same as a meaningful effect?

No.

A small effect can be statistically significant in a large sample, while an important effect may remain statistically uncertain in a small sample.

Reviewers should distinguish:

- **effect magnitude**;
- **uncertainty or precision**;
- **statistical evidence**;
- **clinical, scientific or practical importance**.

#### Common misconceptions

##### "A standardised effect size removes differences between studies."

Incorrect.

Standardisation removes the original measurement units, but the effect remains influenced by the study-specific standard deviation.

##### "Hedges' g measures only the difference between means."

Incorrect.

Its magnitude depends on both the mean difference and the variability used to standardise that difference.

##### "An SMD of 0.8 is always a large and important effect."

Incorrect.

Cohen's benchmarks are generic conventions. Practical importance depends on the outcome, population, intervention and decision context.

##### "Small, medium and large are objective categories."

Incorrect.

They are descriptive labels imposed on a continuous effect-size scale.

##### "A within-participants effect size can be compared directly with a between-groups one."

Not without care.

An effect standardised by the SD of change scores is on a different footing from one standardised by the pooled SD of raw scores, and is frequently the larger of the two.

##### "A reconstructed SD is equivalent to a directly reported SD."

Not necessarily.

Its validity depends on the information available, the study design and the assumptions required for reconstruction.

#### Common terminology

**Effect size** – quantitative measure of the magnitude of a difference, association or treatment effect.

**SMD (Standardised Mean Difference)** – mean difference divided by a measure of within-study variability.

**Cohen's d** – widely used form of the standardised mean difference.

**Hedges' g** – bias-corrected standardised mean difference, particularly useful in smaller samples.

**Glass's Δ** – standardised mean difference using the control-group SD as the denominator.

**d z** – paired standardised mean difference using the SD of the change scores; not comparable with a between-groups SMD.

**Pooled SD** – combined estimate of within-group variability used as an SMD denominator.

**Small-sample correction** – correction applied to Cohen's *d* to reduce small-sample bias, producing Hedges' *g*.

**Effect-size benchmark** – reference value used to aid interpretation of effect magnitude.

**Minimally Important Difference (MID)** – smallest effect considered substantively or clinically important.

**Dependent effect sizes** – effect estimates that share participants, treatment arms, outcomes or other information and are therefore statistically correlated.

**Robust variance estimation (RVE)** – method for obtaining standard errors when effect sizes are dependent and the covariance structure is unknown.

#### Common reviewer red flags

- Effect size reported without explaining how it was calculated.
- SMD reported without identifying the denominator SD.
- Cohen's *d* and Hedges' *g* used interchangeably.
- Small-sample correction not described.
- Different definitions of the denominator mixed across studies.
- Within-participants effects standardised by change-score SD and reported alongside between-groups effects without comment.
- Direction of benefit not stated, or oppositely scored instruments combined without reorientation.
- Effect sizes converted between metrics, for example odds ratios to standardised mean differences, without stating the conversion or its assumptions.
- SDs reconstructed without reporting the method or assumptions.
- Numerous reconstructed SDs used without sensitivity analysis.
- Multiple effect sizes from the same participants treated as independent.
- Cohen's 0.2, 0.5 and 0.8 conventions presented as universal standards.
- Effect magnitude classified solely from the point estimate.
- Statistical significance confused with practical importance.

#### What this guide does **not** cover

This guide concerns the **calculation and interpretation of effect sizes**.

It does not address:

- between-study heterogeneity, or priors on τ in meta-analysis;
- network meta-analysis assumptions such as transitivity and consistency;
- small-study effects and publication bias;
- nonlinear dose-response modelling;
- Bayesian decision rules based on posterior probabilities or meaningful thresholds.

Model comparison using DIC, WAIC, LOO and ELPD is covered in the notes on model fit and on Bayesian model comparison. The remaining topics above are not covered by any note in this set, so a question about them will return passages that are at best adjacent.

#### Quick reviewer checklist

□ The effect-size measure is explicitly identified.

□ The calculation of the effect size is transparent.

□ For an SMD, the denominator SD is clearly defined.

□ Hedges' *g* includes an appropriate small-sample correction.

□ Within-participants effects state their standardiser and are comparable with the other effects reported.

□ The direction of benefit is stated and applied consistently.

□ Reconstructed SDs and their assumptions are reported.

□ Dependence among multiple effect sizes from the same participants is addressed.

□ Confidence or credible intervals accompany effect estimates.

□ Cohen's 0.2, 0.5 and 0.8 benchmarks are treated as fallback conventions rather than universal standards.

□ Context-specific or clinically meaningful benchmarks are preferred where available.

□ Magnitude, uncertainty, statistical evidence and practical importance are interpreted as distinct concepts.

---

*Based on:* Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum; Hedges, L. V. (1981). Distribution theory for Glass's estimator of effect size and related estimators. *Journal of Educational Statistics*, 6, 107-128. https://doi.org/10.3102/10769986006002107; and general meta-analytic guidance on effect-size calculation, dependence and reconstruction of missing variability.
