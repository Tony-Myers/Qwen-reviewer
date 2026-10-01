# Missing Data, Dropout and Analysis Populations

#### Purpose

This guide helps reviewers evaluate whether missing data have been handled appropriately and whether the conclusions remain credible despite incomplete observations. It focuses on dropout, analysis populations, missing-data mechanisms, complete-case analysis, multiple imputation, full-information maximum likelihood (FIML), sensitivity analyses and the assumptions required for each approach.

#### What reviewers should look for

✓ The amount and pattern of missing data are reported separately for each treatment group and important outcome.

✓ Reasons for missingness and dropout are described.

✓ The analysis population (intention-to-treat, modified intention-to-treat, per-protocol or as-treated) is clearly defined.

✓ The method used to handle missing observations is explicitly reported.

✓ The assumptions underlying that method are discussed and appear scientifically plausible.

✓ Sensitivity analyses assess whether conclusions depend on unverifiable assumptions about missing data.

#### Common reviewer questions

##### Can a study still claim intention-to-treat if participants have missing outcomes?

Usually **yes**, but only if the missing outcomes are handled using an appropriate statistical method.

Simply excluding participants with missing data generally does **not** preserve a complete intention-to-treat analysis.

Reviewers should distinguish:

- analysing participants in their randomised groups (ITT); and
- how missing outcomes were handled.

These are separate issues.

##### What is complete-case analysis?

**Complete-case analysis** includes only participants with complete observations.

It is simple and transparent but may:

- reduce statistical power;
- reduce precision;
- introduce bias if complete cases differ systematically from incomplete cases.

Reviewers should ask whether excluding incomplete observations is scientifically justified.

##### When is complete-case analysis reasonable?

Complete-case analysis may be reasonable when:

- very little information is missing;
- missingness is plausibly unrelated to important outcomes after conditioning on observed variables;
- sensitivity analyses produce similar conclusions.

Simply stating that "only 5% was missing" is not sufficient.

The mechanism producing missingness matters more than the percentage alone.

MCAR is sufficient for unbiased complete-case estimation in many settings, but it is not a universally necessary condition. Under some MAR mechanisms, complete-case estimates can remain unbiased; this depends on the analysis model, the estimand, and how missingness relates to the variables in that model. Reviewers should therefore not assume either that complete-case analysis is unbiased only under MCAR or that MAR automatically implies biased complete-case estimates.

##### What are MCAR, MAR and MNAR?

**MCAR (Missing Completely At Random)**

Missingness is unrelated to both observed and unobserved information relevant to the analysis.

**MAR (Missing At Random)**

After accounting for observed variables included in the model, missingness no longer depends on the missing value itself.

**MNAR (Missing Not At Random)**

Even after conditioning on observed variables, missingness still depends on unobserved values.

MAR is often plausible.

MNAR is often possible.

Neither assumption can usually be confirmed from the observed data alone.

A partial exception is worth knowing. MCAR is testable to a limited extent, and a reviewer may meet Little's MCAR test in a manuscript. Failing it is evidence against MCAR; passing it is not evidence for it, and it says nothing at all about the distinction between MAR and MNAR, which is the distinction that matters.

##### What can baseline comparisons between completers and dropouts show?

Comparing observed baseline characteristics between participants who complete follow-up and those who drop out can describe whether the groups differ on those measured characteristics. Such comparisons do not establish the missing-data mechanism. In particular, finding no statistically significant baseline differences does not demonstrate MCAR and does not show that restricting the analysis to complete cases is unbiased. A non-significant comparison may reflect limited information or statistical power rather than absence of a meaningful difference.

Conversely, observed baseline differences may provide evidence that dropout is related to measured participant characteristics, but they do not by themselves establish MAR or MNAR. Baseline comparisons cannot determine whether missingness depends on unobserved information or on the missing outcome itself. Reviewers should therefore treat completer-dropout comparisons as descriptive information about observed differences, not as a test that validates a missing-data assumption.

##### Can MAR be tested?

No.

MAR is fundamentally an assumption rather than a hypothesis that can be demonstrated from the observed data.

Observed missing-data patterns may support or weaken its plausibility, but they cannot establish that MAR is true.

Reviewers should therefore look for scientific justification rather than statistical proof.

##### What is multiple imputation?

**Multiple imputation (MI)** replaces each missing value with several plausible values generated from an imputation model.

Each completed dataset is analysed separately before combining the results using Rubin's rules.

Unlike single imputation, MI propagates uncertainty arising from the missing values into the final estimates.

##### When should multiple imputation be preferred?

Multiple imputation is often appropriate when:

- missingness is plausibly MAR;
- important covariates predict missingness;
- complete-case analysis would discard substantial information.

Reviewers should check whether the imputation model includes variables related to both the outcome and missingness.

The imputation model should be at least as rich as the analysis model. If the analysis contains an interaction, a non-linear term or a random effect, the imputation model should accommodate it, or the imputed values will be drawn from a simpler world than the one being analysed and the association of interest will be diluted.

The common error is omitting the outcome when imputing covariates, on the intuition that using the outcome to fill in a predictor is circular. It is not: excluding the outcome biases the estimated association towards the null. Auxiliary variables that predict missingness or the missing values, even if they are not in the analysis model, belong in the imputation model.

##### How many imputations are enough?

There is no universal number.

The traditional recommendation of five imputations is often inadequate.

The required number generally increases with the **fraction of missing information (FMI)**. FMI describes the information lost about a particular estimand because of missing data; it should not be confused with the proportion or percentage of cases that contain missing values. The two quantities can differ substantially.

Authors should use enough imputations that Monte Carlo error from the imputation procedure is acceptably small.

A commonly cited practical rule of thumb is to use approximately **m = 100 × FMI** imputations, where FMI is the fraction of missing information expressed as a proportion. Thus, an FMI of 0.30 would suggest about thirty imputations. This is a rule of thumb rather than a universal requirement, and it is not equivalent to saying that the number of imputations should equal the percentage of incomplete cases.

The direction matters as much as the number. More missing information generally requires **more** imputations, not fewer, because finite-multiple-imputation estimates become more sensitive to Monte Carlo error as FMI increases. Any rule that reduces m as FMI rises has the relationship inverted.

##### How does FMI affect relative efficiency?

For a fixed number of imputations, the relative efficiency of using **m** imputations rather than an infinite number of imputations, for an estimand with fraction of missing information FMI, is commonly approximated by **RE ≈ 1 / (1 + FMI/m)**.

This relationship means that, for a fixed **m**, relative efficiency decreases as FMI increases. Conversely, increasing **m** makes the finite-imputation estimate approach the result that would be obtained with infinitely many imputations. For example, when FMI is high, more imputations are needed to achieve the same relative efficiency than when FMI is low.

Relative efficiency is usually high even with few imputations: with FMI = 0.3, five imputations give RE ≈ 0.94, and RE ≥ 0.95 requires only m ≥ 19 × FMI, about six imputations. The rule m ≈ 100 × FMI corresponds to RE ≈ 0.99. The case for using many more than five imputations therefore rests mainly on the stability and replicability of standard errors, confidence intervals and *p*-values, which the relative efficiency of the point estimate does not capture.

This finite-imputation relative efficiency should not be confused with the loss of information caused by the missing data themselves. Increasing **m** reduces the additional Monte Carlo uncertainty arising from using a finite number of imputations; it does not recover information that was not observed.

##### Does imputing missing outcomes always add something?

Not always.

In a randomised trial where the covariates are fully observed and the outcomes are missing at random given those covariates, a likelihood-based analysis of the observed outcomes and multiple imputation will generally agree, because both use the same information.

The value of imputation in that setting comes from auxiliary variables outside the analysis model that predict either the missing outcome or its missingness. Where a manuscript reports imputation but no such variables, reviewers may reasonably ask what the imputation added.

##### Does multiple imputation solve MNAR?

No.

Standard multiple imputation generally assumes MAR.

If MNAR is plausible, reviewers should expect sensitivity analyses under alternative assumptions.

Possible approaches include:

- delta adjustment;
- pattern-mixture models;
- selection models;
- tipping-point analyses.

##### What is Full Information Maximum Likelihood (FIML)?

**Full Information Maximum Likelihood (FIML)** estimates model parameters directly from all available observations without explicitly imputing missing values.

FIML commonly performs well under MAR assumptions and is widely used in structural equation modelling and mixed-effects models.

Reviewers should remember that FIML and multiple imputation answer the same missing-data problem using different statistical approaches.

Neither is automatically superior.

##### Do mixed-effects models automatically solve missing-data problems?

No.

Mixed-effects models and FIML commonly remain valid under MAR assumptions.

They do **not** remove bias arising from MNAR missingness.

Reviewers should therefore ask whether the assumed missing-data mechanism is plausible.

##### Is Last Observation Carried Forward (LOCF) acceptable?

Usually **no**.

LOCF assumes that an individual's unobserved future outcome equals the last recorded value.

This assumption is rarely scientifically justified and often produces biased estimates and underestimated uncertainty.

Modern missing-data methods are generally preferred.

##### Why does dropout matter?

Participants rarely leave studies at random.

Dropout may reflect:

- treatment failure;
- adverse effects;
- lack of benefit;
- recovery;
- disease progression.

If dropout differs between treatment groups or relates to prognosis, ignoring it can bias treatment-effect estimates.

##### What is informative dropout?

**Informative dropout** occurs when the probability of leaving the study depends on unobserved outcomes.

This corresponds closely to an MNAR mechanism.

Standard MAR-based analyses may then become unreliable.

##### What should sensitivity analyses demonstrate?

Sensitivity analyses should ask:

*"Would our scientific conclusion change under other plausible assumptions about the missing outcomes?"*

A robust conclusion should not depend entirely on one unverifiable missing-data assumption.

#### Common misconceptions

##### "Very little missing data cannot matter."

Incorrect.

The missing-data mechanism often matters more than the percentage missing.

##### "MAR means the data are missing randomly."

Incorrect.

MAR permits missingness to depend strongly on observed variables.

##### "Multiple imputation recreates the missing observations."

Incorrect.

It represents uncertainty about plausible missing values.

##### "Mixed-effects models automatically remove missing-data bias."

Incorrect.

They generally rely on MAR assumptions.

##### "LOCF is conservative."

Not necessarily.

LOCF may either exaggerate or underestimate treatment effects depending on the outcome trajectory.

##### "Per-protocol analysis is less biased because only compliant participants are analysed."

Incorrect.

Compliance is seldom random and restricting analysis to adherent participants can introduce selection bias.

#### Common terminology

**ITT (Intention-to-Treat)** – participants analysed according to their randomised treatment assignment.

**Modified ITT (mITT)** – restricted form of ITT that must be explicitly defined.

**Per-protocol analysis** – analysis restricted to participants satisfying protocol-defined adherence criteria.

**As-treated analysis** – participants analysed according to treatment actually received.

**Complete-case analysis** – analysis restricted to observations without missing values.

**MCAR** – Missing Completely At Random.

**MAR** – Missing At Random.

**MNAR** – Missing Not At Random.

**Multiple imputation (MI)** – repeated imputation reflecting uncertainty about missing values.

**FIML (Full Information Maximum Likelihood)** – likelihood-based estimation using all observed information without explicit imputation.

**Informative dropout** – dropout related to unobserved outcomes.

**LOCF (Last Observation Carried Forward)** – single-imputation method generally discouraged.

#### Common reviewer red flags

- Amount of missing data not reported.
- Differential dropout between groups ignored.
- ITT claimed but participants with missing outcomes simply excluded.
- Missing-data mechanism never discussed.
- Complete-case analysis performed without justification.
- Imputation model poorly described.
- Important predictors omitted from the imputation model.
- Five imputations used despite extensive missing information.
- LOCF used without strong justification.
- No sensitivity analyses despite plausible MNAR mechanisms.

#### What this guide does **not** cover

This guide concerns **missing observations within studies**.

It does not cover:

- publication bias or missing studies;
- attrition as a formal risk-of-bias tool;
- causal estimands and intercurrent events;
- inverse probability weighting;
- survival censoring.

None of those are covered by any note in this set, so a question about them will return passages that are at best adjacent. Missing *summary statistics* in the studies of a meta-analysis -- a standard deviation that had to be reconstructed from a standard error or a *p* value -- is a different problem from a missing observation, and is covered in the note on effect sizes.

#### Quick reviewer checklist

□ Amount and pattern of missing data reported.

□ Reasons for dropout described.

□ Analysis population clearly defined.

□ Missing-data method explicitly stated.

□ MCAR, MAR or MNAR assumptions discussed.

□ Multiple imputation or FIML appropriately justified.

□ LOCF avoided or exceptionally justified.

□ Sensitivity analyses examine departures from MAR.

□ Conclusions acknowledge uncertainty introduced by missing data.

---

*Based on:* Rubin, D. B. (1987). *Multiple Imputation for Nonresponse in Surveys*. Wiley; White, I. R., Royston, P., & Wood, A. M. (2011). Multiple imputation using chained equations: issues and guidance for practice. *Statistics in Medicine*, 30, 377-399; Little, R. J. A., & Rubin, D. B. (2019). *Statistical Analysis with Missing Data* (3rd ed.). Wiley; and general guidance on the reporting of missing data in trials. See also the note on effect sizes for variability that had to be reconstructed rather than observed.
