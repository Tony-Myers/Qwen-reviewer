# Transformations and Back-transformations

#### Purpose

This guide helps reviewers evaluate the use of data transformations, transformed statistical models and back-transformation of results. It focuses on why transformations are used, when they are appropriate, how transformed coefficients should be interpreted and how results should be reported transparently. The principles apply equally to frequentist and Bayesian analyses.

#### What reviewers should look for

✓ The manuscript clearly explains **why** a transformation was applied rather than simply stating that the data were transformed.

✓ The transformation is appropriate for the outcome, predictor or model assumptions.

✓ Regression coefficients, effect estimates and confidence or credible intervals are interpreted on the correct scale.

✓ Back-transformed estimates are reported where they improve interpretability.

✓ The manuscript discusses any limitations introduced by the transformation.

#### Common reviewer questions

##### Why transform data?

Transformations are commonly used to:

- reduce positive skewness;
- stabilise variance (homoscedasticity);
- improve approximate normality of residuals;
- linearise relationships;
- satisfy modelling assumptions;
- improve numerical stability.

Reviewers should ask whether a transformation is preferable to fitting a model with a more appropriate probability distribution (e.g., Gamma rather than log-transforming positive continuous outcomes).

##### Should the outcome or predictor be transformed?

Either may be transformed depending on the scientific question.

Transforming the **outcome** changes the interpretation of regression coefficients.

Transforming a **predictor** changes the scale on which the predictor is measured but does not change the outcome scale.

The manuscript should explain which variables were transformed and why.

##### What is a logarithmic (log) transformation?

A **log transformation** replaces each observation with its logarithm (commonly the natural logarithm, ln, or log10).

Log transformations are commonly used for:

- positively skewed continuous outcomes;
- multiplicative biological processes;
- ratio-scale measurements;
- variables with increasing variance.

Log transformations require positive values unless an offset has been added.

##### How are coefficients interpreted after a log transformation?

Interpretation depends on which variable has been transformed.

- **log(Y) ~ X**: coefficients represent proportional or percentage changes in the outcome.
- **Y ~ log(X)**: coefficients represent changes in the outcome associated with proportional changes in the predictor.
- **log(Y) ~ log(X)**: coefficients are elasticities, representing proportional changes in both variables.

Reviewers should ensure that authors interpret coefficients on the transformed scale correctly.

##### What is back-transformation?

**Back-transformation** converts estimates from the transformed scale back to the original measurement scale.

Examples include:

- exponentiating log-transformed estimates;
- squaring square-root transformed values;
- applying the inverse Box-Cox transformation.

Back-transformed estimates are generally easier for readers to interpret.

##### Should confidence intervals or credible intervals also be back-transformed?

Usually **yes**.

If effect estimates are back-transformed, associated confidence intervals or credible intervals should normally be transformed using the same inverse transformation.

Reviewers should ensure that uncertainty is presented on the same scale as the reported estimates.

##### What are geometric means?

For log-transformed outcomes, **geometric means** are often more appropriate than arithmetic means.

Geometric means describe the central tendency on the original measurement scale while respecting multiplicative relationships.

Reviewers should check that arithmetic and geometric means are not confused.

##### What is the Box-Cox transformation?

The **Box-Cox transformation** is a family of power transformations used to improve approximate normality and variance homogeneity.

The transformation parameter (λ) is estimated from the data.

Different λ values correspond to familiar transformations:

- λ = 1 → no transformation
- λ = 0 → logarithmic transformation
- λ = 0.5 → square-root transformation

##### What is the Yeo-Johnson transformation?

The **Yeo-Johnson transformation** extends the Box-Cox transformation to allow zero and negative values.

It is often preferred when data contain observations that cannot be log-transformed.

##### When should transformation be avoided?

Transformation is not always the best solution.

Reviewers should consider whether an alternative statistical model would better reflect the data-generating process, for example:

- Gamma regression instead of log transformation;
- Negative binomial regression instead of transforming count data;
- Beta regression for proportions;
- Student's *t* models for heavy-tailed continuous data.

Choosing an appropriate probability distribution is often preferable to transforming the data solely to satisfy model assumptions.

#### Common misconceptions

##### "Transformation makes non-normal data normal."

Incorrect.

Transformations may improve approximate normality but do not guarantee normally distributed data or residuals.

##### "A log transformation fixes every assumption."

Incorrect.

Transformations may reduce skewness or heteroscedasticity but cannot correct poor model specification, influential observations or dependence.

##### "Back-transformation restores the original analysis."

Incorrect.

Back-transformed estimates improve interpretation but the statistical model was still fitted on the transformed scale.

##### "Transformation is always preferable to using another distribution."

Incorrect.

Many modern statistical models directly accommodate skewed, bounded or count data without requiring transformation.

##### "All transformations are equally interpretable."

Incorrect.

Some transformations produce coefficients that are straightforward to interpret (e.g., logarithms), whereas others may make scientific interpretation considerably more difficult.

#### Common terminology

**Transformation** – mathematical modification of a variable before analysis.

**Back-transformation** – inverse transformation used to return estimates to the original measurement scale.

**Natural logarithm (ln)** – logarithm to base *e*.

**Log10 transformation** – logarithm to base 10.

**Square-root transformation** – transformation commonly used for moderately skewed count-like data.

**Reciprocal transformation** – inverse transformation (1/X), usually applied to strongly skewed positive variables.

**Box-Cox transformation** – family of power transformations for positive continuous data.

**Yeo-Johnson transformation** – Box-Cox extension allowing zero and negative values.

**Geometric mean** – average on the multiplicative scale, commonly reported after log transformation.

**Standardisation (z-score transformation)** – subtracting the mean and dividing by the standard deviation to place variables on a common scale.

**Centring** – subtracting a constant (often the mean) from a predictor to improve interpretation or numerical stability.

**Scaling** – changing measurement units without altering relationships between observations.

#### Common reviewer red flags

- Transformation applied without explanation.
- Choice of transformation not justified.
- Regression coefficients interpreted on the wrong scale.
- Back-transformed estimates reported without back-transforming confidence or credible intervals.
- Log transformation applied to variables containing zero or negative values without explanation.
- Transformation used solely to force normality when a more appropriate statistical distribution exists.
- Authors fail to specify which logarithm (ln or log10) was used.

#### Quick reviewer checklist

□ The manuscript explains why transformation was necessary.

□ The transformation is appropriate for the variable and scientific question.

□ Regression coefficients are interpreted correctly on the transformed scale.

□ Back-transformed estimates and associated confidence or credible intervals are reported where appropriate.

□ Alternative probability distributions were considered where relevant.

□ The chosen transformation improves interpretation rather than obscuring it.

□ Conclusions are presented on the original measurement scale whenever practical.

---

*Based on:* Duan, N. (1983). Smearing estimate: a nonparametric retransformation method. *JASA*, 78, 605-610. https://doi.org/10.1080/01621459.1983.10478017; Xiao, X., et al. (2011). On the use of log-transformation vs nonlinear regression. *Ecology*, 92, 1887-1894. https://doi.org/10.1890/11-0538.1

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
