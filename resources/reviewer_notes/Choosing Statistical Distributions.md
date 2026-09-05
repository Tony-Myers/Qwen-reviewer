# Choosing Statistical Distributions

#### Purpose

This guide helps reviewers evaluate whether the chosen probability distribution (likelihood) is appropriate for the outcome being analysed. It focuses on selecting distributions that reflect the data-generating process rather than transforming data to satisfy model assumptions. The principles apply equally to frequentist and Bayesian analyses because the likelihood plays the same role in both frameworks.

#### What reviewers should look for

✓ The manuscript explains why the selected probability distribution is appropriate for the outcome.

✓ The distribution reflects the scale of the data (continuous, count, binary, ordinal, proportion or time-to-event).

✓ Distributional assumptions are discussed and, where possible, assessed.

✓ Alternative distributions are considered where obvious departures from assumptions exist.

✓ The interpretation of model parameters is consistent with the chosen distribution and link function.

#### Common reviewer questions

##### Why does the choice of distribution matter?

The probability distribution (likelihood) describes how the observed outcome is assumed to arise.

An inappropriate distribution may lead to:

- biased parameter estimates;
- incorrect standard errors;
- misleading confidence or credible intervals;
- poor predictions;
- invalid statistical inference.

Reviewers should ask whether the chosen distribution reflects the scientific process that generated the data rather than simply whether it satisfies statistical assumptions.

##### When is the Normal (Gaussian) distribution appropriate?

The **Normal (Gaussian) distribution** is commonly used for continuous outcomes that are approximately symmetric.

Typical examples include:

- height;
- body mass;
- blood pressure;
- many physiological measurements.

The Normal distribution assumes residuals (or outcomes, depending on the model) are approximately normally distributed with constant variance.

Small departures from normality are often unimportant, particularly in large samples.

##### When should Student's *t* distribution be used?

The **Student's *t* distribution** resembles the Normal distribution but has heavier tails.

It is often preferable when:

- outliers are present;
- extreme observations occur more frequently than expected under Normality;
- robust estimation is desired.

Student's *t* models often provide greater robustness without removing observations.

##### When is a Gamma distribution appropriate?

The **Gamma distribution** is commonly used for continuous positive outcomes that are right-skewed.

Examples include:

- waiting times;
- healthcare costs;
- reaction times;
- biological concentrations.

Gamma regression is often preferable to log-transforming positive continuous outcomes because inference remains on the original outcome scale.

##### When is a Lognormal distribution appropriate?

The **Lognormal distribution** assumes that the logarithm of the outcome follows a Normal distribution.

It is appropriate when:

- outcomes are strictly positive;
- variability increases with the mean;
- multiplicative rather than additive processes generate the data.

Lognormal models are common for income, environmental exposure and some biomedical outcomes.

##### When should Poisson regression be used?

The **Poisson distribution** is appropriate for count data.

Examples include:

- injuries;
- hospital admissions;
- goals scored;
- adverse events.

Poisson models assume that the mean equals the variance.

Reviewers should assess whether this assumption appears reasonable.

##### What is overdispersion?

**Overdispersion** occurs when the observed variance exceeds that expected under a Poisson model.

Common consequences include:

- underestimated standard errors;
- inflated Type I error rates;
- misleading statistical significance.

When substantial overdispersion exists, reviewers should consider whether a Negative Binomial model would be more appropriate.

##### When should a Negative Binomial distribution be used?

The **Negative Binomial distribution** extends the Poisson distribution by allowing the variance to exceed the mean.

It is commonly preferred when analysing overdispersed count data.

Reviewers should expect authors to justify using Poisson regression when clear overdispersion is present.

##### What are zero-inflated and hurdle models?

Some count outcomes contain more zero observations than expected under standard count models.

Examples include:

- injuries in low-risk populations;
- hospital admissions;
- disease episodes.

**Zero-inflated models** assume that some observations are structurally unable to experience the event.

**Hurdle models** assume that zero and positive counts arise from different processes.

Reviewers should look for justification when these more complex models are used.

##### When should Beta regression be used?

The **Beta distribution** is appropriate for proportions and percentages bounded between 0 and 1 (exclusive).

Examples include:

- body fat proportion;
- adherence rates;
- questionnaire proportions.

Standard Beta regression cannot accommodate exact 0 or 1 values without modification.

##### When should Binomial or Bernoulli models be used?

**Bernoulli models** describe single binary outcomes.

Examples include:

- success or failure;
- injured or not injured;
- disease present or absent.

**Binomial models** describe the number of successes from multiple trials.

Examples include:

- number of successful free throws;
- number of correct answers;
- treatment responders.

##### When should ordinal models be used?

Ordinal regression models should be used when response categories have a natural order but unequal spacing.

Examples include:

- Likert scales;
- disease severity;
- pain scores.

Reviewers should avoid treating ordinal outcomes as continuous without justification.

##### When should survival distributions be used?

Time-to-event outcomes require methods that account for censoring.

Common approaches include:

- Cox proportional hazards models;
- Weibull models;
- Exponential models;
- flexible parametric survival models.

Reviewers should ensure that censoring has been handled appropriately.

#### Common misconceptions

##### "All continuous outcomes should use a Normal distribution."

Incorrect.

Many continuous outcomes are positively skewed or heavy-tailed and may be better modelled using Gamma, Lognormal or Student's *t* distributions.

##### "Transforming the data is always better than changing the distribution."

Incorrect.

Modern regression models often allow an appropriate distribution to be modelled directly.

##### "Poisson regression is suitable for every count outcome."

Incorrect.

Overdispersion and excess zeros frequently require alternative count distributions.

##### "Beta regression can analyse any percentage."

Incorrect.

Standard Beta regression does not naturally accommodate observations equal to exactly 0 or exactly 1.

##### "The same distribution should always be used in Bayesian and frequentist analyses."

Incorrect.

Although the likelihood may be identical, Bayesian and frequentist analyses may differ in priors, estimation and interpretation.

The choice of probability distribution should be driven by the scientific characteristics of the outcome rather than by the inferential framework.

#### Common terminology

**Likelihood** – probability model describing the observed outcome conditional on model parameters.

**Distribution** – mathematical description of how observations are expected to vary.

**Gaussian distribution** – another name for the Normal distribution.

**Student's *t* distribution** – continuous distribution with heavier tails than the Normal distribution.

**Gamma distribution** – distribution for positive continuous skewed outcomes.

**Lognormal distribution** – distribution where the logarithm of the outcome is Normally distributed.

**Poisson distribution** – distribution for count data where the mean equals the variance.

**Negative Binomial distribution** – count distribution allowing overdispersion.

**Overdispersion** – observed variance greater than expected under a Poisson model.

**Bernoulli distribution** – probability distribution for a single binary outcome.

**Binomial distribution** – distribution for the number of successes in repeated trials.

**Beta distribution** – distribution for continuous proportions between 0 and 1.

**Ordinal regression** – regression model for ordered categorical outcomes.

**Link function** – mathematical function connecting the expected outcome to the linear predictor (e.g., identity, log, logit, probit or complementary log-log).

#### Common reviewer red flags

- Distribution not justified.
- Distribution inconsistent with the outcome scale.
- Count data analysed using Normal regression without justification.
- Clear overdispersion ignored.
- Excess zeros ignored.
- Beta regression used with observed 0 or 1 values without explanation.
- Continuous outcomes transformed when a more suitable distribution could have been modelled directly.
- Ordinal outcomes analysed as continuous without justification.
- Link function not reported.

#### Quick reviewer checklist

□ The probability distribution matches the outcome type.

□ Distributional assumptions appear reasonable.

□ Alternative distributions have been considered where appropriate.

□ The chosen likelihood reflects the scientific process generating the data.

□ Model interpretation is consistent with the chosen distribution and link function.

□ The distribution is justified rather than selected by convention.

□ Conclusions remain scientifically plausible given the assumptions of the fitted model.

---

*Based on:* General statistical-modelling literature; no single source.

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
