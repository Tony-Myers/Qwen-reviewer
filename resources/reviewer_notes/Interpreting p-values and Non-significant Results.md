# Interpreting *p*-values and Non-significant Results

#### Purpose

This guide helps reviewers interpret frequentist hypothesis tests appropriately. It focuses on *p*-values, statistical significance, non-significant results (*p* > 0.05), confidence intervals, statistical power and common reporting errors. The emphasis is on avoiding over-interpretation and distinguishing **absence of evidence** from **evidence of absence**. 

#### What reviewers should look for

✓ The manuscript interprets the *p*-value as a measure of compatibility between the observed data and the statistical model under the null hypothesis, **not** as the probability that the null hypothesis is true. 

✓ The manuscript interprets statistically non-significant results (*p* > 0.05) cautiously and avoids concluding that there is "no effect", "no association" or "no difference" without additional justification.

✓ Confidence intervals are interpreted alongside *p*-values to assess both the estimated effect and the remaining uncertainty.

✓ Conclusions distinguish statistical significance from scientific, clinical or practical importance.

✓ If the goal is to demonstrate similarity or absence of a meaningful effect, the manuscript uses methods designed for that purpose (e.g., equivalence testing, non-inferiority designs or Bayes factors) rather than relying on a non-significant superiority test. 

#### Common reviewer questions

##### What does a *p*-value measure?

A ***p*-value** is the probability of observing results at least as extreme as those obtained, **assuming the null hypothesis and all modelling assumptions are correct**.

A *p*-value is **not**:

- the probability that the null hypothesis is true;
- the probability that the alternative hypothesis is true;
- the probability that the observed result occurred "by chance";
- the probability that the study will replicate. 

##### What does statistical significance mean?

A result described as **statistically significant** (for example, *p* < 0.05) indicates that the observed data would be relatively unusual if the null hypothesis were exactly true and all model assumptions correct.

Statistical significance does **not** measure:

- the magnitude of an effect;
- the importance of an effect;
- the certainty that the alternative hypothesis is correct. 

##### What does a non-significant result mean?

A **non-significant result** (*p* > 0.05) means that the observed data are **not sufficiently incompatible** with the null hypothesis, given the statistical model and assumptions.

It does **not** demonstrate:

- no effect;
- no association;
- no difference;
- equivalence;
- absence of a clinically important effect.

Most non-significant results should be interpreted as **inconclusive** unless additional evidence supports stronger conclusions. 

##### Why can an overall regression F-test be significant when individual predictor t-tests are non-significant?

This situation is relatively common in multiple regression and is **not** a problem of p-value interpretation.

It usually reflects characteristics of the regression model such as:

- multicollinearity (correlated or collinear predictors);
- suppression effects;
- shared explanatory variance among predictors;
- limited statistical power for individual regression coefficients.

The overall **F-test** asks whether the regression model explains variation better than a model with no predictors.

Individual **t-tests** ask whether each regression coefficient contributes independently after adjusting for the other predictors.

A statistically significant **F-test** with non-significant **t-tests** therefore often reflects **multicollinearity** rather than contradictory statistical evidence.

This guide explains the interpretation of p-values. Interpretation of regression coefficients, multicollinearity, variance inflation factors (VIFs) and regression diagnostics are covered in the companion note on multiple regression.

##### What is the difference between "absence of evidence" and "evidence of absence"?

These phrases are not equivalent.

**Absence of evidence** means that the available data do not provide sufficiently strong evidence for an effect.

**Evidence of absence** means that the available evidence supports the conclusion that any effect is absent or too small to be important.

A non-significant *p*-value usually provides **absence of evidence**, **not evidence of absence**. Demonstrating evidence of absence generally requires methods specifically designed for that purpose, such as equivalence testing, the Two One-Sided Tests (TOST) procedure, non-inferiority testing, or Bayesian methods that directly quantify evidence for negligible effects. A non-significant superiority test (p > 0.05) is not evidence of equivalence.

##### Can I conclude "there is no difference"?

Usually **no**.

A statement such as:

> "There was no statistically significant difference between groups (*p* = 0.18)."

is acceptable.

A statement such as:

> "There was no difference between groups."

is usually **not** justified unless the study was specifically designed to demonstrate equivalence or the confidence interval excludes clinically important differences.  

##### Why are confidence intervals important?

Confidence intervals show the range of effect sizes that remain reasonably compatible with the observed data under the statistical model.

Reviewers should examine whether the interval includes:

- clinically important benefit;
- clinically important harm;
- trivial effects;
- the null value.

Wide confidence intervals usually indicate considerable uncertainty, even when *p* > 0.05. 

##### What role does statistical power play?

Low statistical power increases the chance of obtaining a non-significant result even when a meaningful effect exists.

However, reviewers should avoid interpreting non-significant findings using post hoc or observed power calculations, which are generally discouraged. Instead, examine the estimated effect and its confidence interval.  

#### Common misconceptions

### "*p* > 0.05 means there is no effect."

Incorrect.

It means the study did not provide sufficiently strong evidence against the null hypothesis under the assumed model.

##### "Non-significant means no difference."

Incorrect.

The data may remain compatible with both meaningful effects and no effect.

##### "Absence of evidence is evidence of absence."

Incorrect.

Failure to obtain statistical significance usually indicates uncertainty rather than proof that no effect exists. 

##### "A statistically significant result is an important result."

Incorrect.

Very small effects can become statistically significant in large samples, while important effects may fail to reach conventional significance in small samples. 

##### "The confidence interval only matters when the *p*-value is non-significant."

Incorrect.

Confidence intervals should be interpreted for **all** estimated effects because they describe both the estimated magnitude and the remaining uncertainty.

#### Common terminology

**Statistically significant** – conventionally, a result with *p* below the chosen significance threshold (often 0.05). Statistical significance does not imply practical importance.

**Non-significant** – a result with *p* above the chosen significance threshold. Non-significance usually indicates insufficient evidence against the null hypothesis, not proof that the null hypothesis is true.

**Null hypothesis (H₀)** – the hypothesis tested by the statistical procedure, often representing no effect or no difference.

**Alternative hypothesis (H₁)** – the competing hypothesis that an effect or difference exists.

**Confidence interval (CI)** – an interval estimate describing values reasonably compatible with the observed data and statistical assumptions.

**Type I error** – concluding that an effect exists when the null hypothesis is true.

**Type II error** – failing to detect an effect that truly exists.

**Equivalence testing** – methods designed to demonstrate that any effect is smaller than a prespecified practically important threshold.

**Non-inferiority testing** – methods designed to show that a treatment is not unacceptably worse than a comparator by more than a predefined margin.

#### **Key principles for interpreting p-values**

- A *p*-value measures compatibility between the observed data and the assumed statistical model; it does not measure the probability that a hypothesis is true.
- Scientific conclusions should never rely solely on whether a *p*-value crosses an arbitrary threshold such as 0.05.
- Statistical significance does not imply scientific, clinical or practical importance.
- Transparent reporting requires effect sizes, uncertainty measures and study design to be considered alongside *p*-values.
- Selective reporting and multiple analyses can make *p*-values misleading.
- A *p*-value alone is not a sufficient measure of evidence.

#### Common reviewer red flags

- "*p* > 0.05 therefore there was no effect."
- "The treatments were equivalent because the result was non-significant."
- "No statistically significant difference" used as evidence that treatments are identical.
- Confidence intervals omitted from interpretation.
- Statistical significance interpreted as practical or clinical importance.
- Post hoc observed power used to explain a non-significant result.
- Conclusions stronger than the evidence supported by the estimated effect and confidence interval.

#### Quick reviewer checklist

□ The *p*-value is interpreted correctly.

□ Statistical significance is not confused with practical importance.

□ Non-significant results are described as inconclusive rather than proving "no effect."

□ Confidence intervals are interpreted alongside *p*-values.

□ Conclusions acknowledge uncertainty.

□ Claims of equivalence or "no difference" are supported by appropriate methodology rather than by a non-significant superiority test.

□ The estimated effect size, confidence interval and scientific context are given greater emphasis than whether *p* is above or below 0.05.

---

*Based on:* Wasserstein, R. L., & Lazar, N. A. (2016). The ASA statement on p-values. *The American Statistician*, 70, 129-133. https://doi.org/10.1080/00031305.2016.1154108; Greenland, S., et al. (2016). Statistical tests, P values, confidence intervals, and power: a guide to misinterpretations. *European Journal of Epidemiology*, 31, 337-350. https://doi.org/10.1007/s10654-016-0149-3

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
