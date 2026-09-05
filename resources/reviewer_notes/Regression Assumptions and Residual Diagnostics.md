# Regression Assumptions, Residual Diagnostics and Model Checking

#### Purpose

This guide helps reviewers evaluate whether a regression model is appropriate for the data and whether the reported results are likely to be reliable. It focuses on model assumptions, residual diagnostics, influential observations, model misspecification and appropriate alternatives when assumptions are not adequately met. The principles apply to both frequentist and Bayesian regression models, although assessment methods may differ.

#### What reviewers should look for

✓ The manuscript explains why the chosen regression model is appropriate for the outcome and study design.

✓ Model assumptions are assessed using appropriate diagnostic plots or quantitative measures rather than assumed to hold.

✓ Residual diagnostics are reported and interpreted correctly.

✓ Influential observations, outliers and leverage points are investigated where appropriate.

✓ If assumptions appear violated, the manuscript justifies why the model remains appropriate or explains the alternative approach used.

#### Common reviewer questions

##### What are the assumptions of linear regression?

Classical linear regression assumes:

- linearity between predictors and outcome;
- independent observations;
- residuals are approximately Normally distributed;
- constant residual variance (homoscedasticity);
- absence of excessive multicollinearity among predictors (for coefficient estimation);
- no highly influential observations dominating the fitted model.

Not every assumption is equally important. Reviewers should consider whether any departures materially affect the scientific conclusions.

##### Does the outcome (Y) have to be Normally distributed?

Usually **no**.

One of the most common reviewer misconceptions is that the outcome variable itself must be Normally distributed.

For ordinary linear regression, the assumption concerns the **residuals**, not necessarily the observed outcome.

Strongly skewed outcomes may still produce approximately Normal residuals after accounting for predictors.

Reviewers should examine residual diagnostics rather than judging the distribution of the raw outcome alone.

##### What are residuals?

**Residuals** are the differences between observed outcomes and the values predicted by the fitted model.

Residuals are used to assess:

- model fit;
- linearity;
- variance assumptions;
- outliers;
- influential observations;
- possible model misspecification.

Most regression assumptions concern residuals rather than the original outcome variable.

##### What does a residual versus fitted plot show?

A **residual versus fitted values plot** helps assess:

- linearity;
- constant variance (homoscedasticity);
- model misspecification.

Reviewers generally hope to see:

- residuals centred around zero;
- approximately constant spread across fitted values;
- no obvious systematic pattern.

Curved patterns suggest non-linearity.

Increasing or decreasing spread suggests heteroscedasticity.

##### What does a Normal Q-Q plot show?

A **Normal quantile-quantile (Q-Q) plot** compares observed residuals with those expected from a Normal distribution.

If residuals are approximately Normal, observations should lie close to the reference line.

Systematic departures may indicate:

- skewness;
- heavy tails;
- outliers;
- model misspecification.

Minor departures are common and often unimportant, particularly in larger samples.

##### What is homoscedasticity?

**Homoscedasticity** means that residual variance remains approximately constant across the range of fitted values.

Unequal variance is called **heteroscedasticity**.

Heteroscedasticity may lead to:

- incorrect standard errors;
- unreliable confidence intervals;
- misleading p-values.

The estimated regression coefficients themselves often remain unbiased.

##### What should authors do if heteroscedasticity is present?

Possible approaches include:

- robust (heteroscedasticity-consistent) standard errors;
- weighted regression;
- transforming the outcome;
- selecting a more appropriate probability distribution (e.g., Gamma regression);
- generalised least squares.

Reviewers should expect authors to justify the chosen approach rather than simply acknowledge unequal variance.

##### What are leverage and influential observations?

Some observations have greater influence on the fitted model than others.

Common diagnostics include:

- leverage;
- Cook's distance;
- DFBETAs;
- DFFITS.

An influential observation is not necessarily an error.

Reviewers should expect authors to investigate influential observations rather than automatically remove them.

##### What is Cook's distance?

**Cook's distance** measures the overall influence of an individual observation on the fitted regression model.

Large Cook's distance values suggest that removing a single observation substantially changes the fitted model.

Cook's distance identifies influential observations but does not automatically justify excluding them.

##### What is model misspecification?

Model misspecification occurs when the statistical model does not adequately represent the underlying data-generating process.

Possible causes include:

- omitted predictors;
- incorrect functional form;
- inappropriate probability distribution;
- omitted interactions;
- dependence between observations.

Residual diagnostics often provide the first indication of model misspecification.

##### When should transformation be considered?

Transformation may improve:

- linearity;
- residual normality;
- variance stability.

However, reviewers should also consider whether selecting a different probability distribution (e.g., Gamma, Negative Binomial or Student's *t*) would better reflect the data without requiring transformation.

##### What if regression assumptions are violated?

Not every violation invalidates the analysis.

Reviewers should consider:

- the severity of the violation;
- sample size;
- robustness of the estimation procedure;
- sensitivity analyses;
- whether conclusions remain unchanged under alternative models.

The appropriate response depends on the scientific consequences rather than the mere presence of assumption violations.

##### What are robust standard errors?

**Robust standard errors** (heteroscedasticity-consistent standard errors or sandwich estimators) adjust standard error estimates when residual variance is unequal.

They improve statistical inference without changing the estimated regression coefficients.

Robust standard errors do not correct model misspecification, omitted variables or non-linearity.

##### What are alternatives to ordinary ANOVA when variances differ?

When variance differs substantially between groups, reviewers should consider whether alternatives are more appropriate, including:

- Welch's ANOVA;
- heteroscedasticity-consistent methods;
- robust regression;
- suitable generalised linear models;
- Bayesian models with appropriate likelihoods.

The choice depends on the study design and outcome type.

#### Common misconceptions

##### "The outcome must be Normally distributed."

Incorrect.

For ordinary linear regression, assumptions concern the **residuals**, not necessarily the observed outcome.

##### "Residuals must be perfectly Normal."

Incorrect.

Small departures from Normality are common and often have little practical impact, particularly in moderate or large samples.

##### "Heteroscedasticity biases regression coefficients."

Usually incorrect.

Unequal variance primarily affects standard errors and statistical inference rather than the estimated coefficients themselves.

##### "One influential observation should always be removed."

Incorrect.

Influential observations should be investigated, explained and reported. Removal requires scientific justification.

##### "A significant test of normality proves the model is invalid."

Incorrect.

Formal tests become extremely sensitive in large samples.

Diagnostic plots, effect sizes and scientific judgement are generally more informative than relying solely on significance tests.

#### Common terminology

**Residual** – observed outcome minus fitted value.

**Residual diagnostics** – methods used to assess model assumptions through residual behaviour.

**Residual versus fitted plot** – diagnostic plot assessing linearity and homoscedasticity.

**Normal Q-Q plot** – diagnostic plot assessing whether residuals approximately follow a Normal distribution.

**Homoscedasticity** – approximately constant residual variance.

**Heteroscedasticity** – residual variance changes across fitted values.

**Leverage** – measure of how unusual an observation is with respect to predictor values.

**Cook's distance** – measure of an observation's influence on the fitted model.

**Influential observation** – observation that materially changes model estimates when removed.

**Model misspecification** – mismatch between the fitted statistical model and the underlying data-generating process.

**Robust standard errors** – standard errors adjusted for heteroscedasticity.

#### Common reviewer red flags

- Assumptions stated but never assessed.
- Outcome distribution discussed while residual diagnostics are absent.
- Residual plots omitted.
- Q-Q plots interpreted as requiring perfect Normality.
- Heteroscedasticity identified but ignored.
- Influential observations removed without justification.
- Normality tests reported without diagnostic plots.
- Robust standard errors used without explanation.
- Alternative models not considered despite clear assumption violations.

#### What this guide does **not** cover

This guide explains regression assumptions and diagnostic assessment.

It does **not** explain:

- multicollinearity or variance inflation factors (VIF);
- why an overall regression **F-test** may be significant while individual coefficient **t-tests** are not;
- suppression effects;
- regression model selection;
- choosing probability distributions;
- transformations and back-transformations.

These topics are covered in separate reviewer notes.

#### Quick reviewer checklist

□ Model assumptions are appropriate for the chosen regression model.

□ Residual diagnostics have been assessed.

□ Residuals, rather than the raw outcome, are evaluated for Normality.

□ Homoscedasticity appears reasonable or has been appropriately addressed.

□ Influential observations have been investigated.

□ Model misspecification has been considered.

□ Any assumption violations are discussed and justified.

□ Conclusions remain supported despite any departures from assumptions.

---

*Based on:* General regression-diagnostics literature; no single source.

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
