# Model Fit, Information Criteria and R²

#### Purpose

This guide helps reviewers interpret measures of model fit, explained variation and model comparison. It focuses on R², adjusted R², Bayesian R², pseudo-R² measures, information criteria (AIC, AICc, BIC, DIC, WAIC and LOOIC), deviance, log-likelihood and expected predictive performance. The emphasis is on choosing appropriate measures, interpreting them correctly and avoiding common reporting errors.

#### What reviewers should look for

✓ The manuscript reports model fit statistics appropriate for the statistical model being used.

✓ Measures of explained variation (e.g., R²) are interpreted as descriptive summaries of model performance rather than proof of predictive accuracy or causal explanation.

✓ Information criteria (e.g., AIC, BIC, DIC, WAIC or LOOIC) are used for comparing models fitted to the same data and response variable.

✓ The manuscript interprets the direction of each statistic correctly (e.g., higher Bayesian R² is better, lower AIC is better, higher ELPD is better).

✓ Differences between competing models are interpreted cautiously rather than relying solely on the smallest information criterion.

#### Common reviewer questions

##### What is R²?

**R² (coefficient of determination)** measures the proportion of variation in the observed outcome that is explained by the fitted model.

Higher R² values generally indicate better fit to the observed data.

R² does **not** measure:

- whether the model is correct;
- whether predictors are causal;
- whether predictions will generalise to new data;
- whether the model is clinically or scientifically useful.

##### What is adjusted R²?

**Adjusted R²** modifies R² by accounting for the number of predictors in the model.

Unlike ordinary R², adjusted R² can decrease when additional variables contribute little explanatory value.

Adjusted R² is often preferred when comparing multiple linear regression models containing different numbers of predictors.

##### What is Bayesian R²?

**Bayesian R²** estimates the proportion of outcome variation explained by the posterior predictive distribution rather than by a single fitted model.

Bayesian R² is reported as a posterior distribution, allowing posterior means, medians and credible intervals to be presented.

Higher Bayesian R² indicates greater explained variation, but should not be interpreted as evidence that a Bayesian model is "better" than another model without considering predictive performance.

##### Which R² should be used for mixed-effects models?

For mixed-effects or multilevel models, reviewers should distinguish between:

- **Marginal R²** – variation explained by the fixed effects only.
- **Conditional R²** – variation explained by both fixed and random effects.

Both measures are often informative and answer different scientific questions.

##### What are pseudo-R² measures?

Many regression models do not have a single universally accepted R².

Examples include:

- McFadden's R²
- Cox and Snell R²
- Nagelkerke R²
- Tjur's R²

Pseudo-R² measures are not directly comparable with ordinary R² from linear regression and should not be interpreted using the same thresholds.

##### What is AIC?

**Akaike's Information Criterion (AIC)** estimates the trade-off between model fit and model complexity.

Lower AIC values indicate a better balance between fit and complexity.

AIC is useful for comparing competing models fitted to the **same response variable and dataset**.

AIC should not be interpreted as an absolute measure of model quality.

##### What is AICc?

**Corrected Akaike's Information Criterion (AICc)** adjusts AIC for finite sample sizes.

When the sample size is relatively small compared with the number of estimated parameters, AICc is generally preferred over AIC.

As with AIC, **smaller values indicate better expected predictive performance**.

##### What is BIC?

**Bayesian Information Criterion (BIC)** also balances model fit and complexity but applies a stronger penalty for additional parameters than AIC.

Lower BIC values indicate a preferred model.

Compared with AIC, BIC tends to favour simpler models, particularly in larger samples.

Despite its name, BIC is derived from frequentist likelihood theory and should not be confused with Bayesian model comparison.

##### What is DIC?

**Deviance Information Criterion (DIC)** combines model fit with a penalty for model complexity.

Like AIC, WAIC and LOOIC, **lower DIC values indicate a better trade-off between fit and complexity because DIC is reported on a deviance scale.**

DIC remains widely reported in Bayesian network meta-analysis and software such as WinBUGS, OpenBUGS, JAGS, `gemtc` and `MBNMAdose`.

Reviewers should recognise its limitations:

- DIC is not invariant to parameterisation.
- DIC may perform poorly for hierarchical, mixture or weakly identified models.
- DIC estimates predictive performance less reliably than modern approaches.

Where available, WAIC or PSIS-LOO are generally preferred.

##### Can AIC, BIC, DIC, WAIC or LOOIC be compared across different datasets?

Usually **no**.

Information criteria are intended to compare competing models fitted to the **same outcome and the same observations**.

Comparing information criteria across different datasets, different response variables or different likelihoods is generally inappropriate.

##### Does the lowest information criterion prove a model is correct?

No.

Information criteria rank competing models according to their expected balance between fit and complexity.

A lower AIC, BIC, DIC, WAIC or LOOIC does **not** prove that the selected model is scientifically correct or causally valid.

#### Common misconceptions

##### "A larger R² always means a better model."

Incorrect.

Higher R² indicates greater explained variation but does not guarantee better prediction, better generalisation or causal validity.

##### "Adjusted R² should always increase."

Incorrect.

Adjusted R² often decreases when unnecessary predictors are added.

##### "The model with the smallest AIC is the true model."

Incorrect.

Information criteria compare competing models; they do not identify a true model.

##### "BIC is a Bayesian method."

Incorrect.

Despite its name, BIC is derived from an approximation to the Bayesian marginal likelihood but is not itself a Bayesian posterior analysis.

##### "Information criteria can compare any models."

Incorrect.

Models should generally be fitted to the same response variable and data before information criteria are compared.

#### Common terminology

**R² (coefficient of determination)** – proportion of observed variation explained by the fitted model.

**Adjusted R²** – R² corrected for model complexity.

**Bayesian R²** – posterior estimate of explained variation.

**Marginal R²** – explained variation due to fixed effects.

**Conditional R²** – explained variation due to fixed and random effects.

**Pseudo-R²** – family of R²-like measures for non-Gaussian models.

**AIC (Akaike's Information Criterion)** – information criterion; lower values indicate better expected predictive performance.

**AICc** – small-sample correction to AIC.

**BIC (Bayesian Information Criterion)** – information criterion with a stronger complexity penalty than AIC.

**DIC (Deviance Information Criterion)** – Bayesian information criterion commonly reported by WinBUGS, OpenBUGS and JAGS; lower values indicate better model fit after penalising complexity.

**Log-likelihood** – measure of how well the model explains the observed data.

**Deviance** – likelihood-based measure of model fit; lower deviance generally indicates better fit.

#### Common reviewer red flags

- R² interpreted as proof of prediction or causation.
- Pseudo-R² interpreted as ordinary R².
- Information criteria compared across different datasets.
- AIC, BIC or DIC interpreted as hypothesis tests.
- The smallest information criterion presented without discussing the magnitude of differences.
- Bayesian R² confused with classical R².
- Mixed-effects models reported without specifying whether R² is marginal or conditional.

#### Quick reviewer checklist

□ The manuscript reports model fit measures appropriate for the statistical model.

□ R² measures are interpreted correctly.

□ Bayesian, marginal, conditional or pseudo-R² measures are clearly identified.

□ Information criteria are compared only across models fitted to the same data.

□ The direction of each information criterion is interpreted correctly (higher R² and ELPD are better; lower AIC, AICc, BIC, DIC, WAIC and LOOIC are better).

□ Conclusions are based on the overall evidence rather than a single model fit statistic.

□ Model selection is justified scientifically as well as statistically.

---

*Based on:* General model-selection literature; no single source.

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
