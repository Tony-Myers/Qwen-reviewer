# Between-Study Heterogeneity and Priors on Tau

#### Purpose

This guide helps reviewers evaluate between-study heterogeneity in frequentist and Bayesian meta-analysis. It focuses on the heterogeneity standard deviation τ (tau), heterogeneity variance τ², priors on τ, sensitivity analysis, and why uncertainty about heterogeneity becomes particularly important when few studies are available.

#### What reviewers should look for

✓ The manuscript distinguishes sampling error from genuine between-study heterogeneity.

✓ A random-effects model reports the estimated heterogeneity parameter, usually τ or τ².

✓ In Bayesian meta-analysis, the prior distribution for τ is explicitly reported and justified.

✓ Prior sensitivity is assessed when the number of studies is small or heterogeneity is weakly identified.

✓ The consequences of heterogeneity for interpretation of the pooled effect are discussed.

✓ Prediction intervals are considered where the aim is to understand the range of effects expected in future studies or settings.

#### Common reviewer questions

##### What is between-study heterogeneity?

**Between-study heterogeneity** is genuine variation in underlying study effects beyond sampling error.

In a random-effects meta-analysis, study-specific effects are assumed to vary around an overall mean effect.

Heterogeneity is commonly described using:

- **τ (tau)** – the between-study standard deviation;
- **τ² (tau-squared)** – the between-study variance;
- **I²** – the proportion of observed variation attributed to heterogeneity rather than sampling error.

These quantities are related but are not interchangeable.

##### Why does τ matter?

τ is expressed on the same scale as the meta-analytic effect measure.

A larger τ indicates greater variation in true study effects.

When heterogeneity is substantial, the pooled mean effect may describe the evidence poorly if presented without acknowledging that effects may differ considerably between settings.

##### How is τ estimated in a frequentist meta-analysis?

Several estimators are in use, including DerSimonian-Laird, restricted maximum likelihood (REML) and Paule-Mandel.

They do not give the same answer, and the differences matter most when studies are few. DerSimonian-Laird tends to underestimate heterogeneity in small meta-analyses, which narrows the confidence interval around the pooled effect and overstates precision.

The Hartung-Knapp adjustment is often recommended to give better interval coverage when the number of studies is small.

Reviewers should expect the estimator, and any adjustment, to be named rather than described only as "a random-effects model".

##### Why does the prior on τ matter in Bayesian meta-analysis?

A Bayesian random-effects model requires a prior distribution for τ.

When many informative studies are available, the likelihood may dominate the prior.

When few studies are available, the data often contain little information about heterogeneity, so the posterior distribution of τ can depend appreciably on the prior.

The choice of prior may therefore affect:

- the estimated heterogeneity;
- uncertainty around the pooled effect;
- credible intervals;
- prediction intervals;
- treatment rankings or other downstream summaries.

##### Why is sensitivity analysis most important when there are few studies?

Estimating heterogeneity is intrinsically difficult with a small number of studies.

A sparse dataset may support a wide range of plausible τ values.

Reviewers should therefore ask whether conclusions remain similar under several reasonable heterogeneity priors rather than relying on a single default prior.

##### What kinds of prior may be used for τ?

Common choices include positive-valued distributions such as:

- half-Normal;
- half-*t*;
- half-Cauchy;
- log-Normal;
- empirically informed heterogeneity priors.

There is no universally correct prior.

The scale of the prior should make sense for the effect measure being synthesised.

##### Are inverse-gamma priors on τ² a safe default?

Not reliably.

An inverse-gamma(ε, ε) prior with a very small ε was a common default for hierarchical variances in BUGS-lineage software, and is often described as uninformative.

It is not. Where studies are few, the posterior for τ can depend appreciably on the value chosen for ε, and the prior can place substantial mass away from zero, inflating apparent heterogeneity.

Where such a prior is used, reviewers should expect a sensitivity analysis across alternative scales and families rather than an assertion that the prior was uninformative.

##### Is using a software default prior necessarily wrong?

No.

A default prior can be reasonable, but reviewers should still expect authors to:

- report it explicitly;
- explain its implications;
- check whether it is appropriate for the effect-size scale;
- assess sensitivity when the evidence is sparse.

##### What is a prediction interval?

A **prediction interval** estimates the range in which the true effect of a future comparable study may plausibly lie.

This answers a different question from the confidence or credible interval around the pooled mean effect.

Prediction intervals become especially informative when heterogeneity is substantial.

#### Common misconceptions

##### "A random-effects model removes heterogeneity."

Incorrect.

It models heterogeneity; it does not make heterogeneous studies homogeneous.

##### "I² tells me everything I need to know about heterogeneity."

Incorrect.

I² depends partly on study precision and does not directly express the absolute magnitude of between-study variation.

τ is often more interpretable for modelling purposes.

##### "The prior on τ cannot matter if the treatment-effect prior is weak."

Incorrect.

The heterogeneity prior is a separate component of the model and can materially influence uncertainty when few studies are available.

##### "A pooled effect is sufficient even when heterogeneity is large."

Not necessarily.

Substantial heterogeneity may make prediction intervals and study-level variation more informative than the pooled mean alone.

#### Common terminology

**Heterogeneity** – genuine variation in effects between studies.

**τ (tau)** – between-study standard deviation.

**τ² (tau-squared)** – between-study variance.

**I²** – relative measure of observed variability attributed to heterogeneity.

**Random-effects meta-analysis** – model allowing true study effects to vary.

**Heterogeneity prior** – prior distribution placed on τ in a Bayesian random-effects model.

**Prediction interval** – interval describing plausible effects in a future comparable study.

**DerSimonian-Laird** – method-of-moments estimator of τ², prone to underestimation when studies are few.

**REML** – restricted maximum likelihood estimation of the heterogeneity variance.

**Hartung-Knapp adjustment** – modification improving confidence-interval coverage for the pooled effect in small meta-analyses.

#### Common reviewer red flags

- τ or τ² not reported in a random-effects analysis.
- Prior on τ omitted from a Bayesian analysis.
- Default heterogeneity prior used without explanation.
- No sensitivity analysis despite very few studies.
- Large heterogeneity ignored when interpreting the pooled effect.
- I² treated as the only relevant measure of heterogeneity.
- Prediction interval omitted despite substantial between-study variability.
- Heterogeneity estimator not named in a frequentist analysis.
- An inverse-gamma prior on τ² described as uninformative.

#### Quick reviewer checklist

□ Between-study heterogeneity is explicitly modelled.

□ τ or τ² is reported.

□ The heterogeneity prior is stated and justified in Bayesian analyses.

□ Sensitivity to alternative priors is examined when studies are few.

□ Heterogeneity is incorporated into interpretation of the pooled effect.

□ Prediction intervals are reported or considered where informative.

□ The heterogeneity estimator, or the prior on τ, is named rather than implied.

---

*Based on:* Higgins, J. P. T., & Thompson, S. G. (2002). Quantifying heterogeneity in a meta-analysis. *Statistics in Medicine*, 21, 1539-1558; Gelman, A. (2006). Prior distributions for variance parameters in hierarchical models. *Bayesian Analysis*, 1, 515-534; and general meta-analytic guidance on heterogeneity estimation. See also the note on network meta-analysis assumptions.
