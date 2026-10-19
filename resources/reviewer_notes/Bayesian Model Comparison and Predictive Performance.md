# Bayesian Model Comparison and Predictive Performance

## Purpose

This guide helps reviewers evaluate Bayesian model comparison and predictive performance. It focuses on leave-one-out cross-validation (LOO), Pareto-smoothed importance sampling (PSIS), expected log predictive density (ELPD), the leave-one-out information criterion (LOOIC), the widely applicable information criterion (WAIC), and related diagnostics. The emphasis is on correct interpretation, reporting and common reviewer questions.

---

## What reviewers should look for

✓ The manuscript explains **why** model comparison was undertaken and whether the goal is prediction, explanation or model selection.

✓ The manuscript reports the method used for model comparison (e.g., PSIS-LOO, exact LOO, WAIC, Bayes factors or posterior predictive checks).

✓ The manuscript interprets model comparison statistics correctly and consistently.

✓ Uncertainty in model comparison (e.g., standard errors of ELPD differences) is reported where appropriate.

✓ The limitations of each method are acknowledged, particularly when importance sampling diagnostics indicate unreliable estimates.

---

## Common reviewer questions

### Which direction is better?

This is one of the most common sources of confusion.

| Statistic                                          | Better model                                                 |
| -------------------------------------------------- | ------------------------------------------------------------ |
| **ELPD (Expected Log Predictive Density)**         | **Higher** values indicate better expected out-of-sample predictive performance. |
| **LOOIC (Leave-One-Out Information Criterion)**    | **Lower** values indicate better predictive performance because LOOIC is reported on a deviance scale (approximately −2 × ELPD). |
| **WAIC (Widely Applicable Information Criterion)** | **Lower** values indicate better predictive performance because WAIC is also reported on a deviance scale. |
| **Bayes factor**                                   | Larger values provide stronger evidence for the numerator model, but interpretation depends on the comparison being made. |

---

### What is ELPD?

**Expected Log Predictive Density (ELPD)** estimates how well a fitted Bayesian model is expected to predict new, unseen data.

Higher ELPD values indicate better expected predictive performance.

Small differences in ELPD should be interpreted together with their estimated standard errors rather than treated as absolute evidence for one model.

---

### What is LOO?

**Leave-One-Out Cross-Validation (LOO)** estimates predictive performance by repeatedly fitting or approximating the model while leaving out one observation at a time.

Modern Bayesian analyses usually estimate LOO using **Pareto-Smoothed Importance Sampling (PSIS-LOO)** rather than repeatedly refitting the model.

---

### What is PSIS?

**Pareto-Smoothed Importance Sampling (PSIS)** provides an efficient approximation to leave-one-out cross-validation.

Its reliability should be assessed using the **Pareto *k*** diagnostic.

---

### What is Pareto *k*?

The **Pareto *k*** diagnostic evaluates the reliability of the importance-sampling approximation used by PSIS-LOO. Larger values indicate that the approximation is becoming less reliable and that particular observations may have a strong influence on the leave-one-out estimate.

Current versions of the `loo` package use a **sample-size-dependent diagnostic threshold** for Pareto *k*, rather than treating the older fixed 0.5 and 0.7 cut-offs as universal decision rules. Reviewers should therefore use the diagnostic thresholds and recommendations reported by the current software rather than mechanically applying older fixed categories.

Values approaching or exceeding **0.7** warrant particular attention, and **k ≥ 1** indicates serious problems with the importance-sampling approximation. When problematic observations are present, reviewers should expect authors to report and investigate them and, where appropriate, consider methods recommended by the current `loo` guidance, such as moment matching, exact leave-one-out refitting for problematic observations, or model revision.

Older literature commonly described fixed categories such as *k* < 0.5, 0.5–0.7, 0.7–1.0 and ≥1.0. These can be useful for understanding older reports, but they should **not** be presented as the current universal `loo` diagnostic thresholds.

---

### What is WAIC?

The **Widely Applicable Information Criterion (WAIC)** estimates expected predictive performance using the posterior distribution.

Like LOOIC, **smaller WAIC values indicate better expected predictive performance**.

WAIC and PSIS-LOO often produce similar conclusions, although PSIS-LOO is generally preferred when reliable Pareto diagnostics are available.

---

## Common misconceptions

### "The model with the highest WAIC is best."

Incorrect.

Lower WAIC indicates better expected predictive performance.

---

### "The model with the lowest ELPD is best."

Incorrect.

Higher ELPD indicates better predictive performance.

---

### "LOOIC and ELPD should move in the same direction."

Incorrect.

LOOIC is approximately **−2 × ELPD**, so they move in opposite directions.

Higher ELPD corresponds to lower LOOIC.

---

### "A small difference proves one model is superior."

Not necessarily.

Differences should be interpreted together with their uncertainty (standard errors or confidence/credible intervals where reported).

Very small differences may have little practical importance.

---

### "Model comparison proves a model is true."

Incorrect.

Model comparison evaluates **relative predictive performance**, not whether a model is true.

All models remain approximations.

## Common terminology

**ELPD (Expected Log Predictive Density)** estimates out-of-sample predictive accuracy. Higher values are better.

**LOO (Leave-One-Out Cross-Validation)** estimates predictive performance by systematically leaving out one observation at a time.

**PSIS (Pareto-Smoothed Importance Sampling)** provides an efficient approximation to LOO.

**Pareto *k*** assesses whether PSIS-LOO is reliable.

**LOOIC (Leave-One-Out Information Criterion)** is reported on a deviance scale; lower values indicate better predictive performance.

**WAIC (Widely Applicable Information Criterion)** estimates predictive performance using the posterior distribution; lower values indicate better performance.

**Stacking** combines predictions from multiple Bayesian models using weights chosen to maximise predictive performance rather than selecting a single "best" model.

**Pseudo-BMA (Pseudo Bayesian Model Averaging)** averages predictions across models using weights derived from predictive performance measures such as LOO.

---

## Common reviewer red flags

- Direction of ELPD, WAIC or LOOIC interpreted incorrectly.
- Pareto *k* diagnostics not reported when PSIS-LOO is used.
- High Pareto *k* values ignored.
- Model comparison reported without uncertainty estimates.
- WAIC or LOOIC interpreted as hypothesis tests.
- Model comparison used to claim that a model is "true".
- Predictive performance confused with causal validity or scientific plausibility.

---

## Quick reviewer checklist

□ The manuscript explains why Bayesian model comparison was performed.

□ ELPD is interpreted correctly (higher values indicate better predictive performance).

□ LOOIC is interpreted correctly (lower values indicate better predictive performance).

□ WAIC is interpreted correctly (lower values indicate better predictive performance).

□ PSIS-LOO diagnostics, including Pareto *k*, are reported when appropriate.

□ High Pareto *k* observations are discussed or investigated.

□ Differences between competing models are interpreted together with their uncertainty.

□ Conclusions are based on predictive performance rather than claiming any model is "true".

---

*Based on:* Kruschke, J. K. (2021), https://doi.org/10.1038/s41562-021-01177-7; and the `loo` package documentation for PSIS-LOO and Pareto k diagnostics.

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
