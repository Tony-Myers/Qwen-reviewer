# Model Fit, Information Criteria and R²

#### Purpose

This guide helps reviewers interpret measures of model fit, explained variation and model comparison. It focuses on R², adjusted R², Bayesian R², pseudo-R² measures, information criteria (AIC, AICc, BIC, DIC, WAIC and LOOIC), deviance, log-likelihood and expected predictive performance. The emphasis is on choosing appropriate measures, interpreting them correctly and avoiding common reporting errors.

#### What reviewers should look for

✓ The manuscript reports model fit statistics appropriate for the statistical model being used.

✓ Measures of explained variation (e.g., R²) are interpreted as descriptive summaries of model performance rather than proof of predictive accuracy or causal explanation.

✓ Information criteria (e.g., AIC, BIC, DIC, WAIC or LOOIC) are used for comparing models fitted to the same data and response variable.

✓ The manuscript interprets the direction of each statistic correctly (e.g., higher R² or Bayesian R² means more explained variation, lower AIC is preferred, higher ELPD is better).

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

```references
- cite: Kvålseth, T. O. (1985). Cautionary note about R². The American Statistician, 39(4), 279–285.
  doi: 10.1080/00031305.1985.10479448
  supports: Cautions on defining and interpreting R², whose alternative formulas agree only in linear models with an intercept.
  short: cautions on R²
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
```

##### What is adjusted R²?

**Adjusted R²** modifies R² by accounting for the number of predictors in the model.

Unlike ordinary R², adjusted R² can decrease when additional variables contribute little explanatory value.

Adjusted R² is often used when comparing linear regression models with different numbers of predictors, but its penalty is weak: adding a predictor increases adjusted R² whenever that predictor's *t* statistic exceeds 1 in absolute value. Information criteria or cross-validation are usually better for choosing between models.

##### What is Bayesian R²?

**Bayesian R²** estimates the proportion of outcome variation explained by a Bayesian model. It is calculated for each posterior draw as the variance of the fitted values divided by that variance plus the expected residual variance, so it always lies between 0 and 1. It is an in-sample measure; a leave-one-out version estimates explained variation for new data.

Bayesian R² is reported as a posterior distribution, allowing posterior means, medians and credible intervals to be presented.

Higher Bayesian R² indicates greater explained variation, but should not be interpreted as evidence that a Bayesian model is "better" than another model without considering predictive performance.

```references
- cite: Gelman, A., Goodrich, B., Gabry, J., & Vehtari, A. (2019). R-squared for Bayesian regression models. The American Statistician, 73(3), 307–309.
  doi: 10.1080/00031305.2018.1549100
  supports: The definition of Bayesian R², calculated for each posterior draw, and why it lies between 0 and 1.
  short: R² for Bayesian regression models
  type: Journal article
  access: repository
  access_url: https://aaltodoc.aalto.fi/handle/123456789/38878
  access_checked: 2026-10-01, OpenAlex: green, submitted version in Aaltodoc (Aalto University); repository page checked
  checked: 2026-10-01, Crossref
```

##### Which R² should be used for mixed-effects models?

For mixed-effects or multilevel models, reviewers should distinguish between:

- **Marginal R²** – variation explained by the fixed effects only.
- **Conditional R²** – variation explained by both fixed and random effects.

Both measures are often informative and answer different scientific questions.

```references
- cite: Nakagawa, S., & Schielzeth, H. (2013). A general and simple method for obtaining R² from generalized linear mixed-effects models. Methods in Ecology and Evolution, 4(2), 133–142.
  doi: 10.1111/j.2041-210x.2012.00261.x
  supports: Marginal and conditional R² for mixed-effects models.
  short: marginal and conditional R² for mixed models
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, Crossref (published online 2012; volume 4 is 2013)
```

##### What are pseudo-R² measures?

Many regression models do not have a single universally accepted R².

Examples include:

- McFadden's R²
- Cox and Snell R²
- Nagelkerke R²
- Tjur's R²

Pseudo-R² measures are not directly comparable with ordinary R² from linear regression and should not be interpreted using the same thresholds.

```references
- cite: Nagelkerke, N. J. D. (1991). A note on a general definition of the coefficient of determination. Biometrika, 78(3), 691–692.
  doi: 10.1093/biomet/78.3.691
  supports: A general definition of R² for models fitted by maximum likelihood, the basis of Nagelkerke's R².
  short: Nagelkerke's general R²
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); confirmed by hand by Tony Myers
- cite: Tjur, T. (2009). Coefficients of determination in logistic regression models—A new proposal: The coefficient of discrimination. The American Statistician, 63(4), 366–372.
  doi: 10.1198/tast.2009.08210
  supports: Tjur's coefficient of discrimination as an R² for logistic regression.
  short: Tjur's R² for logistic regression
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
```

##### What is AIC?

**Akaike's Information Criterion (AIC)** estimates the trade-off between model fit and model complexity.

Lower AIC values indicate a better balance between fit and complexity.

AIC is useful for comparing competing models fitted to the **same response variable and dataset**.

AIC should not be interpreted as an absolute measure of model quality.

```references
- cite: Akaike, H. (1974). A new look at the statistical model identification. In E. Parzen, K. Tanabe, & G. Kitagawa (Eds.), Selected papers of Hirotugu Akaike (Springer Series in Statistics). Springer.
  doi: 10.1007/978-1-4612-1694-0_16
  supports: The introduction of the information criterion now known as AIC.
  short: the paper that introduced AIC
  type: Book chapter
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, confirmed by hand by Tony Myers (reprint in Selected Papers of Hirotugu Akaike; first published in IEEE Transactions on Automatic Control, 19(6), 716–723)
- cite: Burnham, K. P., & Anderson, D. R. (2004). Multimodel inference: Understanding AIC and BIC in model selection. Sociological Methods & Research, 33(2), 261–304.
  doi: 10.1177/0049124104268644
  supports: Interpreting AIC and differences in AIC in model selection.
  short: AIC and BIC in model selection
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); full title confirmed by hand by Tony Myers
```

##### What is AICc?

**Corrected Akaike's Information Criterion (AICc)** adjusts AIC for finite sample sizes.

When the sample size is relatively small compared with the number of estimated parameters, AICc is generally preferred over AIC.

As with AIC, **smaller values indicate better expected predictive performance**.

```references
- cite: Hurvich, C. M., & Tsai, C.-L. (1989). Regression and time series model selection in small samples. Biometrika, 76(2), 297–307.
  doi: 10.1093/biomet/76.2.297
  supports: The small-sample correction to AIC, AICc.
  short: the small-sample corrected AIC
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); confirmed by hand by Tony Myers
```

##### What is BIC?

**Bayesian Information Criterion (BIC)** also balances model fit and complexity but, in all but very small samples, applies a stronger penalty for additional parameters than AIC.

Lower BIC values indicate a preferred model.

Compared with AIC, BIC tends to favour simpler models, particularly in larger samples.

BIC is a large-sample approximation to the Bayesian marginal likelihood, so differences in BIC approximate Bayes factors under an implicit prior. It is calculated from the maximum likelihood without an explicit prior, however, and is not a full Bayesian analysis.

```references
- cite: Schwarz, G. (1978). Estimating the dimension of a model. The Annals of Statistics, 6(2).
  doi: 10.1214/aos/1176344136
  supports: The derivation of BIC as a large-sample approximation in Bayesian model choice.
  short: the paper that introduced BIC
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, Crossref (no page numbers in the Crossref record; OpenAlex gives pages that do not look right)
- cite: Kass, R. E., & Raftery, A. E. (1995). Bayes factors. Journal of the American Statistical Association, 90(430), 773–795.
  doi: 10.1080/01621459.1995.10476572
  supports: BIC as an approximation to Bayes factors, and its implicit prior.
  short: Bayes factors and BIC
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
- cite: Burnham, K. P., & Anderson, D. R. (2004). Multimodel inference: Understanding AIC and BIC in model selection. Sociological Methods & Research, 33(2), 261–304.
  doi: 10.1177/0049124104268644
  supports: How AIC and BIC differ in what they target and in their penalties.
  short: AIC and BIC in model selection
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); full title confirmed by hand by Tony Myers
```

##### What is DIC?

**Deviance Information Criterion (DIC)** is an older Bayesian criterion that combines model fit, measured by the deviance, with a penalty for model complexity based on the effective number of parameters (*p*D).

Like AIC, WAIC and LOOIC, **lower DIC values indicate a better trade-off between fit and complexity because DIC is reported on a deviance scale.**

DIC remains widely reported in Bayesian network meta-analysis and in software such as WinBUGS, OpenBUGS, JAGS, `gemtc` and `MBNMAdose`.

Reviewers should recognise its limitations:

- DIC is not invariant to parameterisation, because it is calculated at a point estimate of the parameters, usually the posterior mean.
- In a hierarchical model, DIC depends on which level is treated as the focus. A DIC based on the likelihood conditional on the random effects and one based on the likelihood with the random effects integrated out answer different questions and should not be compared with each other.
- The effective number of parameters can be poorly estimated, and can even be negative, in mixture models, in weakly identified models and when the prior conflicts with the data.
- DIC tends to under-penalise complexity when the effective number of parameters is not small relative to the number of observations, so it can favour overfitted models.

Where DIC is reported, reviewers can ask which version was calculated, at which level of the model, and whether the reported *p*D is plausible.

Where available, **PSIS-LOO and WAIC are generally preferred because they estimate out-of-sample predictive performance more directly and provide additional diagnostics.**

```references
- cite: Spiegelhalter, D. J., Best, N. G., Carlin, B. P., & van der Linde, A. (2002). Bayesian measures of model complexity and fit. Journal of the Royal Statistical Society Series B: Statistical Methodology, 64(4), 583–639.
  doi: 10.1111/1467-9868.00353
  supports: The definition of DIC and of the effective number of parameters, pD, including their dependence on parameterisation.
  short: the paper that introduced DIC and pD
  type: Journal article
  checked: 2026-10-01, Crossref; access not recorded because OpenAlex links this DOI to the published discussion of the paper rather than the paper itself
- cite: Spiegelhalter, D. J., Best, N. G., Carlin, B. P., & van der Linde, A. (2014). The deviance information criterion: 12 years on. Journal of the Royal Statistical Society Series B: Statistical Methodology, 76(3), 485–493.
  doi: 10.1111/rssb.12062
  supports: The limitations of DIC identified since its introduction, including the choice of focus in hierarchical models.
  short: limitations of DIC, twelve years on
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref (the fourth author's surname is recorded as "Linde"; "van der Linde" is from OpenAlex)
- cite: Celeux, G., Forbes, F., Robert, C. P., & Titterington, D. M. (2006). Deviance information criteria for missing data models. Bayesian Analysis, 1(4).
  doi: 10.1214/06-BA122
  supports: Why DIC is not uniquely defined for mixture and other latent-variable models, and the alternative versions that result.
  short: DIC for mixture and missing-data models
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (diamond, CC BY, free to read at the publisher)
  checked: 2026-10-01, Crossref (no page numbers in the Crossref or OpenAlex record)
- cite: Plummer, M. (2008). Penalized loss functions for Bayesian model comparison. Biostatistics, 9(3), 523–539.
  doi: 10.1093/biostatistics/kxm049
  supports: DIC as an approximation that under-penalises complexity unless the effective number of parameters is small relative to the number of observations.
  short: why DIC can under-penalise complex models
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
- cite: Gelman, A., Hwang, J., & Vehtari, A. (2013). Understanding predictive information criteria for Bayesian models. Statistics and Computing, 24(6), 997–1016.
  doi: 10.1007/s11222-013-9416-2
  supports: How AIC, DIC and WAIC relate as estimates of out-of-sample predictive accuracy.
  short: AIC, DIC and WAIC compared
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable; OpenAlex gives 2013, the year of online publication)
- cite: Vehtari, A., Gelman, A., & Gabry, J. (2017). Practical Bayesian model evaluation using leave-one-out cross-validation and WAIC. Statistics and Computing, 27(5), 1413–1432.
  doi: 10.1007/s11222-016-9696-4
  supports: PSIS-LOO and WAIC as estimates of out-of-sample predictive performance, with the Pareto k diagnostic.
  short: PSIS-LOO and WAIC in practice
  type: Journal article
  access: repository
  access_url: https://arxiv.org/abs/1507.04544
  access_checked: 2026-10-01, OpenAlex: green, submitted version on arXiv
  checked: 2026-10-01, Crossref (published online 2016; volume 27 is 2017)
- cite: Dias, S., Sutton, A. J., Ades, A. E., & Welton, N. J. (2013). Evidence synthesis for decision making 2: A generalized linear modeling framework for pairwise and network meta-analysis of randomized controlled trials. Medical Decision Making, 33(5), 607–617.
  doi: 10.1177/0272989X12458724
  supports: The use of DIC and residual deviance to compare models in network meta-analysis.
  short: DIC in network meta-analysis
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (hybrid, CC BY-NC, free to read at the publisher)
  checked: 2026-10-01, Crossref (published online 2012; volume 33 is 2013)
```

##### Can AIC, BIC, DIC, WAIC or LOOIC be compared across different datasets?

Usually **no**.

Information criteria are intended to compare competing models fitted to the **same outcome and the same observations**.

Comparing information criteria across different datasets or different response variables is generally inappropriate.

Models with different likelihoods, such as a Poisson and a negative binomial model for the same counts, can be compared, provided that both are fitted to the same observations, the response is on the same scale (a model for log(*y*) and a model for *y* cannot be compared without a Jacobian adjustment), and the full likelihoods, including constants, are calculated in the same way.

```references
- cite: Burnham, K. P., & Anderson, D. R. (2004). Multimodel inference: Understanding AIC and BIC in model selection. Sociological Methods & Research, 33(2), 261–304.
  doi: 10.1177/0049124104268644
  supports: Why information criteria are compared only for models fitted to the same data and response.
  short: AIC and BIC in model selection
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); full title confirmed by hand by Tony Myers
```

##### Does the lowest information criterion prove a model is correct?

No.

Information criteria rank competing models according to their expected balance between fit and complexity.

A lower AIC, BIC, DIC, WAIC or LOOIC does **not** prove that the selected model is scientifically correct or causally valid.

```references
- cite: Burnham, K. P., & Anderson, D. R. (2004). Multimodel inference: Understanding AIC and BIC in model selection. Sociological Methods & Research, 33(2), 261–304.
  doi: 10.1177/0049124104268644
  supports: Model-selection uncertainty, and why the model with the lowest criterion is not the true model.
  short: AIC and BIC in model selection
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); full title confirmed by hand by Tony Myers
```

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

Partly.

BIC is derived as an approximation to the Bayesian marginal likelihood, but it is calculated from the maximum likelihood without an explicit prior and is not a full Bayesian analysis.

```references
- cite: Kass, R. E., & Raftery, A. E. (1995). Bayes factors. Journal of the American Statistical Association, 90(430), 773–795.
  doi: 10.1080/01621459.1995.10476572
  supports: In what sense BIC is Bayesian: an approximation to the Bayes factor rather than a full Bayesian analysis.
  short: Bayes factors and BIC
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
```

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

□ The direction of each statistic is interpreted correctly (higher R² means more explained variation; higher ELPD is better; lower AIC, AICc, BIC, DIC, WAIC and LOOIC are preferred).

□ Conclusions are based on the overall evidence rather than a single model fit statistic.

□ Model selection is justified scientifically as well as statistically.

#### References

Checked sources for this topic. A section with its own list shows that list instead. Each entry says what it supports; a source is listed for that purpose only, not as support for every sentence in the note.

```references
- cite: Burnham, K. P., & Anderson, D. R. (2004). Multimodel inference: Understanding AIC and BIC in model selection. Sociological Methods & Research, 33(2), 261–304.
  doi: 10.1177/0049124104268644
  supports: Model selection with information criteria, including AIC, BIC and multimodel inference.
  short: AIC and BIC in model selection
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable); full title confirmed by hand by Tony Myers
- cite: Gelman, A., Hwang, J., & Vehtari, A. (2013). Understanding predictive information criteria for Bayesian models. Statistics and Computing, 24(6), 997–1016.
  doi: 10.1007/s11222-013-9416-2
  supports: How AIC, DIC and WAIC relate as estimates of out-of-sample predictive accuracy.
  short: AIC, DIC and WAIC compared
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable; OpenAlex gives 2013, the year of online publication); confirmed by hand by Tony Myers
- cite: Kass, R. E., & Raftery, A. E. (1995). Bayes factors. Journal of the American Statistical Association, 90(430), 773–795.
  doi: 10.1080/01621459.1995.10476572
  supports: Bayes factors and their large-sample approximation by BIC.
  short: Bayes factors and BIC
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
```

---

*Based on:* General model-selection literature; no single source.

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
