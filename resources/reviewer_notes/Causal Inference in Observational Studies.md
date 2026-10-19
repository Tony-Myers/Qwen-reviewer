# Causal Inference in Observational Studies

#### Purpose

This guide helps reviewers evaluate causal claims made from data that were not produced by randomisation. It focuses on what makes an estimate causal rather than associational: the estimand, the identifying assumptions of exchangeability, positivity and consistency, what estimation methods such as matching, weighting and causal forests do and do not supply, the role of directed acyclic graphs, variables that should not be adjusted for, the additional problem created by time-varying treatment, and what can be asked of a manuscript when confounding may be unmeasured.

#### What reviewers should look for

✓ The causal quantity being estimated is named, not merely implied by the word "effect".

✓ The identifying assumptions are stated, and defended with subject knowledge rather than asserted.

✓ The set of variables adjusted for is reported, and its choice is justified.

✓ Overlap between treated and untreated groups is examined and reported, not assumed.

✓ Variables affected by the treatment are excluded from the adjustment set, or their inclusion is defended.

✓ The estimation method is distinguished from the identification argument.

✓ Sensitivity to unmeasured confounding is examined where the design cannot rule it out.

✓ The language of the conclusions matches the strength of the design and the assumptions the authors are willing to defend.

#### Common reviewer questions

##### What makes an estimate causal?

An estimate is causal when it answers a question about what would have happened under an intervention, rather than what is observed to accompany what.

That requires three things, in order:

- a **causal estimand**: the quantity to be estimated, defined in terms of outcomes under treatment and under its absence;
- an **identification argument**: assumptions under which that quantity can be recovered from the data available;
- an **estimator**: a procedure for computing it.

The middle step is the one manuscripts most often omit. Identification is an argument about the world, not a property of a statistical method, and no amount of estimation sophistication supplies it.

```references
- cite: Hernán, M. A., & Robins, J. M. (2020). Causal inference: What if. Chapman & Hall/CRC.
  url: https://miguelhernan.org/whatifbook
  supports: The separation of a causal question into an estimand, the assumptions that identify it, and an estimator.
  short: textbook on causal estimands, identification and estimation
  type: Book
  access: author-copy
  access_url: https://miguelhernan.org/whatifbook
  access_checked: 2026-10-01, authors' book page: free download stated; print edition not yet published
  checked: 2026-10-01, authors' book page (online book; no DOI or ISBN)
- cite: Lundberg, I., Johnson, R., & Stewart, B. M. (2021). What is your estimand? Defining the target quantity connects statistical evidence to theory. American Sociological Review, 86(3), 532–565.
  doi: 10.1177/00031224211004187
  supports: Defining the target quantity explicitly before choosing a statistical procedure.
  short: defining the estimand before choosing a method
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
```

##### What is an estimand, and why should it be named?

Common estimands include:

- **ATE (average treatment effect)** – the average difference in outcome if everyone were treated compared with if nobody were;
- **ATT (average treatment effect on the treated)** – the same difference among those who actually received the treatment;
- **CATE (conditional average treatment effect)** – the average effect within a stratum defined by covariates.

These are different quantities and can differ substantially. A paper reporting "the effect" without saying which has not defined what it estimated, and a reviewer cannot judge whether the analysis recovers it.

```references
- cite: Lundberg, I., Johnson, R., & Stewart, B. M. (2021). What is your estimand? Defining the target quantity connects statistical evidence to theory. American Sociological Review, 86(3), 532–565.
  doi: 10.1177/00031224211004187
  supports: Why the estimand must be stated, and how different estimands answer different questions.
  short: defining the estimand before choosing a method
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
- cite: Hernán, M. A., & Robins, J. M. (2020). Causal inference: What if. Chapman & Hall/CRC.
  url: https://miguelhernan.org/whatifbook
  supports: Definitions of average causal effects in the population and among the treated.
  short: textbook on causal estimands, identification and estimation
  type: Book
  access: author-copy
  access_url: https://miguelhernan.org/whatifbook
  access_checked: 2026-10-01, authors' book page: free download stated; print edition not yet published
  checked: 2026-10-01, authors' book page (online book; no DOI or ISBN)
```

##### What assumptions are required?

Three, and only the second is meaningfully checkable.

**Conditional exchangeability**, also called unconfoundedness, conditional ignorability or no unmeasured confounding. Given the measured covariates, treatment assignment is unrelated to what the outcomes would have been under each treatment. This is untestable from the observed data. It is defended with subject knowledge about how treatment came to be assigned, not with a statistic.

**Positivity**, also called overlap. Every combination of covariates that occurs must have some chance of receiving each treatment. Where a subgroup is always treated, or never treated, nothing in the data speaks to what would have happened otherwise, and any estimate for that subgroup comes from the model rather than the evidence. This one is partly checkable.

**Consistency**, which requires a well-defined intervention and no interference. The treatment must be specific enough that "receiving it" means the same thing for everyone, and one participant's treatment must not affect another's outcome. Vaguely defined exposures and clustered settings — teams, classes, squads sharing a coach — strain this assumption in ways that are rarely acknowledged.

```references
- cite: Hernán, M. A., & Robins, J. M. (2020). Causal inference: What if. Chapman & Hall/CRC.
  url: https://miguelhernan.org/whatifbook
  supports: Exchangeability, positivity and consistency as the conditions for identifying a causal effect.
  short: textbook on causal estimands, identification and estimation
  type: Book
  access: author-copy
  access_url: https://miguelhernan.org/whatifbook
  access_checked: 2026-10-01, authors' book page: free download stated; print edition not yet published
  checked: 2026-10-01, authors' book page (online book; no DOI or ISBN)
- cite: Petersen, M. L., Porter, K. E., Gruber, S., Wang, Y., & van der Laan, M. J. (2012). Diagnosing and responding to violations in the positivity assumption. Statistical Methods in Medical Research, 21(1), 31–54.
  doi: 10.1177/0962280210386207
  supports: What positivity violations are and how they show themselves in an analysis.
  short: diagnosing and responding to positivity violations
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref (published online 2010; volume 21 is 2012)
```

##### Can a statistical method establish causality?

No.

Matching, propensity-score weighting, doubly robust estimation, targeted learning and causal forests all estimate a quantity that is causal **only if** the identifying assumptions hold. They differ in efficiency, in robustness to model misspecification, and in what they can represent, not in whether they need those assumptions.

A method cannot supply exchangeability, because exchangeability is a claim about variables that were not measured.

```references
- cite: Hernán, M. A., & Robins, J. M. (2020). Causal inference: What if. Chapman & Hall/CRC.
  url: https://miguelhernan.org/whatifbook
  supports: Why estimation methods recover a causal effect only under the identifying assumptions.
  short: textbook on causal estimands, identification and estimation
  type: Book
  access: author-copy
  access_url: https://miguelhernan.org/whatifbook
  access_checked: 2026-10-01, authors' book page: free download stated; print edition not yet published
  checked: 2026-10-01, authors' book page (online book; no DOI or ISBN)
- cite: Hernán, M. A. (2018). The C-word: Scientific euphemisms do not improve causal inference from observational data. American Journal of Public Health, 108(5), 616–619.
  doi: 10.2105/AJPH.2018.304337
  supports: Why the causal question and its assumptions must be stated rather than replaced by associational language.
  short: state causal questions as causal, with their assumptions
  type: Journal article
  access: repository
  access_url: https://www.ncbi.nlm.nih.gov/pmc/articles/5888052
  access_checked: 2026-10-01, OpenAlex: green, submitted version in PubMed Central
  checked: 2026-10-01, Crossref
```

##### What does a causal forest estimate?

A **causal forest** estimates conditional average treatment effects: how the effect of treatment varies with measured covariates. It is a method for finding and quantifying heterogeneity, not for establishing that the underlying contrast is causal.

Implementations typically use honest splitting, in which one part of the data chooses the splits and another estimates the effects within them, and cross-fitting, so that the nuisance models used to adjust for covariates are not fitted on the same observations as the effects. Both exist to make the intervals trustworthy, and neither addresses confounding by anything unmeasured.

Reviewers should expect a manuscript reporting a causal forest to state the conditioning set, the number of trees and the tuning approach, whether honest splitting and cross-fitting were used, and how overlap was assessed.

Two requirements are easy to overlook because they are properties of the estimator rather than of the design.

The covariates must be **pre-treatment**. A variable measured after treatment, or affected by it, does not belong in the conditioning set, and putting one there reintroduces the mediator and collider problems below with a flexible model to hide them in. Non-parametric estimation does not make post-treatment adjustment safe.

The confidence intervals rest on **regularity conditions** that are rarely stated: the conditional effect is assumed to vary smoothly with the covariates, and the outcome to be well behaved in its tails. Where the true pattern is a sharp discontinuity, or the outcome is heavy-tailed, the intervals are optimistic rather than wrong in an obvious way. This bears directly on subgroup claims: a forest asked to find a step change will render it as a gradient, and report a tidy interval for it.

```references
- cite: Wager, S., & Athey, S. (2018). Estimation and inference of heterogeneous treatment effects using random forests. Journal of the American Statistical Association, 113(523), 1228–1242.
  doi: 10.1080/01621459.2017.1319839
  supports: The causal forest: conditional average treatment effects, honest splitting and the conditions for its intervals.
  short: causal forests, honest splitting and intervals for conditional effects
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
- cite: Athey, S., Tibshirani, J., & Wager, S. (2019). Generalized random forests. The Annals of Statistics, 47(2).
  doi: 10.1214/18-AOS1709
  supports: The generalized random forest framework that implements causal forests.
  short: generalized random forests, the framework behind grf causal forests
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, Crossref (no page range recorded)
```

##### How should heterogeneity from a causal forest be interpreted?

Cautiously, and more cautiously than the average effect.

Estimated heterogeneity is a fitted pattern, and subgroup effects have wider intervals than the overall effect while being drawn from the same data that suggested the subgroups. Implementations commonly provide a calibration check of whether the estimated heterogeneity actually predicts differences in effect; where such a check exists it should be reported.

Heterogeneity that was not pre-specified is exploratory, however it was estimated. A subgroup finding produced by a flexible method and then narrated as though it had been hypothesised is the same problem as a subgroup analysis chosen after the fact, wearing better clothes.

```references
- cite: Athey, S., & Wager, S. (2019). Estimating treatment effects with causal forests: An application. Observational Studies, 5(2), 37–51.
  doi: 10.1353/obs.2019.0001
  supports: An applied causal-forest analysis, including a calibration check of whether estimated heterogeneity predicts differences in effect.
  short: applied causal-forest analysis with a calibration check
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (diamond, CC BY-NC)
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
- cite: Wager, S., & Athey, S. (2018). Estimation and inference of heterogeneous treatment effects using random forests. Journal of the American Statistical Association, 113(523), 1228–1242.
  doi: 10.1080/01621459.2017.1319839
  supports: The statistical conditions under which causal-forest intervals for conditional effects are valid.
  short: causal forests, honest splitting and intervals for conditional effects
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
```

##### What is overlap, and how can a reviewer check it?

Overlap is the requirement that comparable units exist in both treatment conditions.

It is the one identifying assumption with a visible diagnostic. Reviewers can reasonably ask for the distribution of the estimated propensity score in each group, and for a statement of what was done where it approaches zero or one — trimming, restriction to a region of common support, or a limitation acknowledged.

Where a treatment was defined by dichotomising a continuous variable, overlap deserves particular attention, because units close to the cut point differ trivially in exposure while being compared as though they differ completely.

```references
- cite: Petersen, M. L., Porter, K. E., Gruber, S., Wang, Y., & van der Laan, M. J. (2012). Diagnosing and responding to violations in the positivity assumption. Statistical Methods in Medical Research, 21(1), 31–54.
  doi: 10.1177/0962280210386207
  supports: Diagnosing violations of positivity and the options for responding to them.
  short: diagnosing and responding to positivity violations
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref (published online 2010; volume 21 is 2012)
- cite: Crump, R. K., Hotz, V. J., Imbens, G. W., & Mitnik, O. A. (2009). Dealing with limited overlap in estimation of average treatment effects. Biometrika, 96(1), 187–199.
  doi: 10.1093/biomet/asn055
  supports: Restricting estimation to a region of adequate overlap in the propensity score.
  short: trimming to a region of adequate overlap
  type: Journal article
  access: repository
  access_url: http://nrs.harvard.edu/urn-3:HUL.InstRepos:3007645
  access_checked: 2026-10-01, OpenAlex: green, submitted version in Harvard DASH (CC BY)
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
```

##### What is a directed acyclic graph for?

A **directed acyclic graph (DAG)** is a diagram of assumed causal relationships: variables as nodes, an arrow from cause to effect, and no path that returns to its origin.

Its purpose is to make assumptions explicit and to derive their consequences. Given a DAG, the **back-door criterion** identifies which sets of variables must be adjusted for to recover the effect of interest, and equally which must not be. That is its practical value to a reviewer: it converts an argument about confounding into a question about a drawn structure that can be examined.

```references
- cite: Greenland, S., Pearl, J., & Robins, J. M. (1999). Causal diagrams for epidemiologic research. Epidemiology, 10(1), 37–48.
  doi: 10.1097/00001648-199901000-00008
  supports: Causal diagrams and how they identify which variables need to be adjusted for.
  short: introduction to causal diagrams for confounding
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
- cite: Tennant, P. W. G., Murray, E. J., Arnold, K. F., Berrie, L., Fox, M. P., Gadd, S. C., Harrison, W. J., Keeble, C., Ranker, L. R., Textor, J., Tomova, G. D., Gilthorpe, M. S., & Ellison, G. T. H. (2021). Use of directed acyclic graphs (DAGs) to identify confounders in applied health research: Review and recommendations. International Journal of Epidemiology, 50(2), 620–632.
  doi: 10.1093/ije/dyaa213
  supports: How DAGs are used and reported in applied research, with recommendations.
  short: review and reporting recommendations for DAGs
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (hybrid, CC BY)
  checked: 2026-10-01, Crossref (published online 2020; volume 50 is 2021)
```

##### Can a DAG be tested, and does it establish causality?

Not established, and only partly tested.

A DAG is a statement of assumptions. It does not follow from the data, and drawing one does not make its arrows true. A DAG produced after the analysis, to justify the adjustment set that was used, is a rationalisation rather than an argument.

It is not entirely unfalsifiable, however. A DAG implies conditional independencies among the observed variables, and those implications can be tested. Failing them is evidence against the diagram; passing them is weak evidence for it, since many different structures imply the same independencies.

```references
- cite: Textor, J., van der Zander, B., Gilthorpe, M. S., Liśkiewicz, M., & Ellison, G. T. H. (2016). Robust causal inference using directed acyclic graphs: The R package 'dagitty'. International Journal of Epidemiology, 45(6).
  doi: 10.1093/ije/dyw341
  supports: Deriving and testing the conditional independencies implied by a DAG.
  short: dagitty: adjustment sets and testable implications of a DAG
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, Crossref (online 2017-01-15, no volume or pages) and OpenAlex (45(6))
- cite: Tennant, P. W. G., Murray, E. J., Arnold, K. F., Berrie, L., Fox, M. P., Gadd, S. C., Harrison, W. J., Keeble, C., Ranker, L. R., Textor, J., Tomova, G. D., Gilthorpe, M. S., & Ellison, G. T. H. (2021). Use of directed acyclic graphs (DAGs) to identify confounders in applied health research: Review and recommendations. International Journal of Epidemiology, 50(2), 620–632.
  doi: 10.1093/ije/dyaa213
  supports: Why a DAG states assumptions rather than establishing causal structure, with reporting recommendations.
  short: review and reporting recommendations for DAGs
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (hybrid, CC BY)
  checked: 2026-10-01, Crossref (published online 2020; volume 50 is 2021)
```

##### Which variables should not be adjusted for?

Adjusting for more variables is not safer.

- A **mediator** lies on the causal path from treatment to outcome. Adjusting for it removes part of the effect being estimated, so the reported effect is not the total effect the paper usually claims.
- A **collider** is a common effect of two variables. Conditioning on it creates an association between them where none existed, and can manufacture an effect entirely.
- **Post-treatment variables** in general risk being one or the other, and should be excluded unless there is a specific argument for including them.
- A variable that strongly predicts treatment but has no independent effect on the outcome can **amplify** whatever bias remains from unmeasured confounding rather than reducing it.

"We adjusted for all available covariates" is not a justification. It is a description of a dataset.

```references
- cite: Cinelli, C., Forney, A., & Pearl, J. (2024). A crash course in good and bad controls. Sociological Methods & Research, 53(3), 1071–1104.
  doi: 10.1177/00491241221099552
  supports: Which covariates are good and bad controls, including mediators, colliders and treatment-only predictors.
  short: which covariates are good and bad controls
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref (published online 2022; volume 53 is 2024)
- cite: Schisterman, E. F., Cole, S. R., & Platt, R. W. (2009). Overadjustment bias and unnecessary adjustment in epidemiologic studies. Epidemiology, 20(4), 488–495.
  doi: 10.1097/EDE.0b013e3181a819a1
  supports: Overadjustment bias from adjusting for mediators and their descendants.
  short: overadjustment for mediators and their descendants
  type: Journal article
  access: repository
  access_url: https://www.ncbi.nlm.nih.gov/pmc/articles/2744485
  access_checked: 2026-10-01, OpenAlex: green, submitted version in PubMed Central
  checked: 2026-10-01, Crossref
- cite: Elwert, F., & Winship, C. (2014). Endogenous selection bias: The problem of conditioning on a collider variable. Annual Review of Sociology, 40, 31–53.
  doi: 10.1146/annurev-soc-071913-043455
  supports: Collider bias from conditioning on a common effect.
  short: collider bias from conditioning on a common effect
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
- cite: Pearl, J. (2011). Invited commentary: Understanding bias amplification. American Journal of Epidemiology, 174(11), 1223–1227.
  doi: 10.1093/aje/kwr352
  supports: Bias amplification from adjusting for a variable that predicts treatment but not outcome.
  short: how adjusting for a treatment-only predictor amplifies bias
  type: Commentary
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, Crossref
```

##### What changes when treatment varies over time?

A time-varying confounder that is itself affected by earlier treatment cannot be handled by standard adjustment.

Adjusting for it blocks part of the treatment effect, because it lies on the causal path. Not adjusting for it leaves confounding in place. Neither choice is correct, and the problem is structural rather than a matter of specification.

Methods designed for this case include inverse probability weighting with marginal structural models, g-computation and g-estimation. Where a manuscript analyses repeated exposure with a conventional regression and adjusts for intermediate variables, reviewers should ask whether this problem was considered.

```references
- cite: Robins, J. M., Hernán, M. Á., & Brumback, B. (2000). Marginal structural models and causal inference in epidemiology. Epidemiology, 11(5), 550–560.
  doi: 10.1097/00001648-200009000-00011
  supports: Marginal structural models with inverse probability weighting for time-varying treatment and confounding.
  short: marginal structural models for time-varying treatment
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
- cite: Daniel, R., Cousens, S., De Stavola, B., Kenward, M. G., & Sterne, J. A. C. (2013). Methods for dealing with time-dependent confounding. Statistics in Medicine, 32(9), 1584–1618.
  doi: 10.1002/sim.5686
  supports: A comparison of inverse probability weighting, g-computation and g-estimation for time-dependent confounding.
  short: tutorial comparing methods for time-dependent confounding
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable; published online 2012)
```

##### What can be asked when confounding may be unmeasured?

A quantitative sensitivity analysis, rather than an assurance.

The useful form asks how strong an unmeasured confounder would have to be, in its association with both treatment and outcome, to explain away the reported effect. The **E-value** expresses this on a familiar scale: for an observed risk ratio above one it is RR + the square root of RR × (RR − 1), so a risk ratio of 2.0 gives an E-value of about 3.41, meaning a confounder would need associations of at least that size with both exposure and outcome, beyond the measured covariates, to account for the finding. For a ratio below one the calculation is applied to its reciprocal, and reporting the E-value for the confidence limit nearest the null as well as for the point estimate is the more informative practice. Bias analyses that posit a specific confounder and recompute the estimate serve the same purpose.

Such analyses do not demonstrate that no confounding remains. They tell a reader whether the finding would survive a plausible one, which is a question the reader can otherwise only guess at.

```references
- cite: VanderWeele, T. J., & Ding, P. (2017). Sensitivity analysis in observational research: Introducing the E-value. Annals of Internal Medicine, 167(4), 268–274.
  doi: 10.7326/M16-2607
  supports: The E-value: the strength of unmeasured confounding needed to explain away an observed association.
  short: the E-value for unmeasured confounding
  type: Journal article
  access: repository
  access_url: http://nrs.harvard.edu/urn-3:HUL.InstRepos:36874927
  access_checked: 2026-10-01, OpenAlex: green, submitted version in Harvard DASH (CC BY)
  checked: 2026-10-01, Crossref
- cite: Cinelli, C., & Hazlett, C. (2020). Making sense of sensitivity: Extending omitted variable bias. Journal of the Royal Statistical Society Series B: Statistical Methodology, 82(1), 39–67.
  doi: 10.1111/rssb.12348
  supports: Sensitivity analysis expressing how strong an omitted confounder would need to be to change a regression conclusion.
  short: sensitivity analysis for omitted confounders in regression
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
```

##### What do placebo tests and negative controls establish?

Less than they are usually said to.

A **negative control outcome** is one the treatment could not plausibly affect; a **negative control exposure** is one that could not plausibly affect the outcome. If an association appears where none should exist, something is wrong -- residual confounding, selection, or an error in the data or the code. A **permutation or label-shuffling test** is a related device: the grouping label is reassigned at random and the structure of interest should disappear.

What a clean result establishes is narrow. It says that no spurious signal was detected **at the power available**, which is not the same as showing there is none, and it speaks only to the particular route the control was chosen to probe. A negative control cannot demonstrate that unmeasured confounding is absent in general.

It is also worth being clear what a shuffling test addresses. Reassigning group labels destroys all structure at that level, so the test asks whether the observed clustering exceeds what chance would produce. That is a question about model specification, not about identification: a variance component can be real and the effect attached to it still confounded.

Reviewers should ask how many units carry the shuffled label, because with few groups the permutation null is coarse and the test has little power; how many permutations were run; whether the negative control is genuinely one, on the authors' own theory; and whether it was prespecified, since a falsification test chosen after the results are known can be selected for the answer it gives.

```references
- cite: Lipsitch, M., Tchetgen Tchetgen, E., & Cohen, T. (2010). Negative controls: A tool for detecting confounding and bias in observational studies. Epidemiology, 21(3), 383–388.
  doi: 10.1097/EDE.0b013e3181d61eeb
  supports: Negative control outcomes and exposures, and the limits of what they can detect.
  short: what negative controls can and cannot detect
  type: Journal article
  access: repository
  access_url: http://nrs.harvard.edu/urn-3:HUL.InstRepos:25143688
  access_checked: 2026-10-01, OpenAlex: green, submitted version in Harvard DASH (CC BY)
  checked: 2026-10-01, Crossref
```

##### When may a paper use causal language?

When it states the assumptions its causal interpretation requires and defends them.

The objection is not to the word. Observational data can support careful causal claims, and refusing the vocabulary while implying the conclusion is worse than using it openly. What a reviewer should resist is a paper that reports an "effect", titles a section for a causal method, and never says what would have to be true for the number to mean what it is being used to mean.

Where the assumptions cannot be defended, the estimate is an adjusted association and should be described as one.

```references
- cite: Hernán, M. A. (2018). The C-word: Scientific euphemisms do not improve causal inference from observational data. American Journal of Public Health, 108(5), 616–619.
  doi: 10.2105/AJPH.2018.304337
  supports: Why causal questions should be stated as causal, with their assumptions, rather than disguised as associations.
  short: state causal questions as causal, with their assumptions
  type: Journal article
  access: repository
  access_url: https://www.ncbi.nlm.nih.gov/pmc/articles/5888052
  access_checked: 2026-10-01, OpenAlex: green, submitted version in PubMed Central
  checked: 2026-10-01, Crossref
- cite: Hernán, M. A., & Robins, J. M. (2020). Causal inference: What if. Chapman & Hall/CRC.
  url: https://miguelhernan.org/whatifbook
  supports: The assumptions a causal interpretation of observational data requires.
  short: textbook on causal estimands, identification and estimation
  type: Book
  access: author-copy
  access_url: https://miguelhernan.org/whatifbook
  access_checked: 2026-10-01, authors' book page: free download stated; print edition not yet published
  checked: 2026-10-01, authors' book page (online book; no DOI or ISBN)
```

#### Common misconceptions

##### "A causal forest, or any machine-learning method, establishes causality."

Incorrect.

It estimates heterogeneity in a contrast that is causal only under assumptions the method neither supplies nor tests.

##### "Controlling for more variables always reduces confounding."

Incorrect.

Adjusting for a mediator removes part of the effect, adjusting for a collider creates association where there was none, and adjusting for a strong predictor of treatment alone can amplify existing bias.

##### "Unconfoundedness can be tested."

Incorrect.

It concerns variables that were not measured. Balance on measured covariates says nothing about the unmeasured ones.

##### "A large sample makes a causal claim more credible."

Incorrect.

Sample size reduces variance. Confounding is bias, and bias does not shrink as the sample grows; a larger study estimates the wrong quantity more precisely.

##### "A DAG proves the causal structure."

Incorrect.

It states assumptions and derives their consequences. Some of those consequences are testable; the structure itself is not recovered from observational data.

##### "The study is observational, so no causal claim is possible."

Too strong.

Causal claims from observational data are possible under stated assumptions, and are made routinely in fields where randomisation would be impossible. What is not acceptable is making the claim while leaving the assumptions unstated.

#### Common terminology

**Estimand** – the quantity to be estimated, defined before any method is chosen.

**Potential outcome** – the outcome a unit would have under a specified treatment, only one of which is observed.

**ATE / ATT / CATE** – average treatment effect in the population, among the treated, and within a covariate stratum.

**Conditional exchangeability (unconfoundedness, conditional ignorability)** – treatment is unrelated to potential outcomes given the measured covariates.

**Positivity (overlap)** – every covariate pattern has a non-zero probability of each treatment.

**Consistency** – the observed outcome equals the potential outcome for the treatment received, which requires a well-defined intervention.

**Interference** – one unit's treatment affects another unit's outcome, violating consistency as usually stated.

**Confounder** – a common cause of treatment and outcome.

**Collider** – a common effect of two variables; conditioning on it induces association.

**Mediator** – a variable on the causal path from treatment to outcome.

**Propensity score** – the probability of receiving treatment given the covariates.

**DAG** – directed acyclic graph representing assumed causal relationships.

**Back-door criterion** – rule identifying, from a DAG, which variables to adjust for.

**Honest splitting** – using separate data to choose splits and to estimate effects within them.

**Cross-fitting** – fitting nuisance models on different observations from those used to estimate the effect.

**E-value** – the minimum strength of association an unmeasured confounder would need with both treatment and outcome to explain away an observed effect.

**Marginal structural model** – model for time-varying treatment fitted with inverse probability weights.

#### Common reviewer red flags

- An "effect" reported without the estimand being named.
- A causal method named in a section heading with no identification argument anywhere in the paper.
- Identifying assumptions never stated.
- The adjustment set not reported, or described only as "all available covariates".
- Post-treatment variables in the adjustment set without explanation.
- Overlap not examined, particularly where treatment was created by dichotomising a continuous measure.
- A causal forest reported without the conditioning set, tuning, honesty or cross-fitting.
- Subgroup heterogeneity narrated as though it had been hypothesised in advance.
- A DAG presented after the analysis to justify the adjustment already performed.
- Repeated exposure analysed by adjusting for intermediate variables, with no mention of time-varying confounding.
- No sensitivity analysis for unmeasured confounding in a design that cannot exclude it.
- Causal language in the abstract and associational language in the limitations.

#### What this guide does **not** cover

This guide concerns identification and interpretation of causal effects in studies without randomised assignment.

It does not cover:

- instrumental variables;
- regression discontinuity designs;
- difference-in-differences and synthetic control;
- formal mediation analysis and the decomposition of direct and indirect effects;
- target trial emulation as a framework.

None of those is covered by any note in this set, so a question about them will return passages that are at best adjacent.

Missing outcomes are a separate route to bias and are covered in the note on missing data; how an effect is scaled once estimated is covered in the note on effect sizes.

#### Quick reviewer checklist

□ The estimand is named.

□ The identifying assumptions are stated.

□ Exchangeability is defended with subject knowledge, not with balance statistics alone.

□ The adjustment set is reported and justified.

□ Post-treatment variables are excluded or their inclusion defended.

□ Overlap is examined and reported.

□ The estimation method is distinguished from the identification argument.

□ Causal-forest implementation details are reported: conditioning set, tuning, honesty, cross-fitting.

□ Heterogeneity is labelled exploratory unless it was pre-specified.

□ Time-varying confounding is addressed where exposure is repeated.

□ Sensitivity to unmeasured confounding is quantified.

□ The conclusions use language the design and the stated assumptions can carry.

#### References

Checked sources for this topic. A section with its own list shows that list instead. Each entry says what it supports; a source is listed for that purpose only, not as support for every sentence in the note.

```references
- cite: Hernán, M. A., & Robins, J. M. (2020). Causal inference: What if. Chapman & Hall/CRC.
  url: https://miguelhernan.org/whatifbook
  supports: A general account of causal inference from observational data: estimands, identifying assumptions and estimation.
  short: textbook on causal estimands, identification and estimation
  type: Book
  access: author-copy
  access_url: https://miguelhernan.org/whatifbook
  access_checked: 2026-10-01, authors' book page: free download stated; print edition not yet published
  checked: 2026-10-01, authors' book page (online book; no DOI or ISBN)
- cite: Pearl, J. (2009). Causality: Models, reasoning, and inference (2nd ed.). Cambridge University Press.
  doi: 10.1017/CBO9780511803161
  isbn: 9780511803161
  supports: The formal theory of causal diagrams and identification, including the back-door criterion.
  short: causal diagrams, the back-door criterion and identification
  type: Book
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref; Cambridge Core online edition published 2013-03-05 (online ISBN 9780511803161), confirmed by Tony Myers; print second edition 2009
- cite: Hernán, M. A. (2018). The C-word: Scientific euphemisms do not improve causal inference from observational data. American Journal of Public Health, 108(5), 616–619.
  doi: 10.2105/AJPH.2018.304337
  supports: Stating causal questions and their assumptions openly in observational research.
  short: state causal questions as causal, with their assumptions
  type: Journal article
  access: repository
  access_url: https://www.ncbi.nlm.nih.gov/pmc/articles/5888052
  access_checked: 2026-10-01, OpenAlex: green, submitted version in PubMed Central
  checked: 2026-10-01, Crossref
- cite: Wager, S., & Athey, S. (2018). Estimation and inference of heterogeneous treatment effects using random forests. Journal of the American Statistical Association, 113(523), 1228–1242.
  doi: 10.1080/01621459.2017.1319839
  supports: Causal forests for estimating heterogeneous treatment effects.
  short: causal forests, honest splitting and intervals for conditional effects
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
- cite: VanderWeele, T. J., & Ding, P. (2017). Sensitivity analysis in observational research: Introducing the E-value. Annals of Internal Medicine, 167(4), 268–274.
  doi: 10.7326/M16-2607
  supports: Sensitivity analysis for unmeasured confounding using the E-value.
  short: the E-value for unmeasured confounding
  type: Journal article
  access: repository
  access_url: http://nrs.harvard.edu/urn-3:HUL.InstRepos:36874927
  access_checked: 2026-10-01, OpenAlex: green, submitted version in Harvard DASH (CC BY)
  checked: 2026-10-01, Crossref
```

---

*Based on:* Hernán, M. A., & Robins, J. M. (2020). *Causal Inference: What If*. Chapman & Hall/CRC; Pearl, J. (2009). *Causality: Models, Reasoning, and Inference* (2nd ed.). Cambridge University Press; Wager, S., & Athey, S. (2018). Estimation and inference of heterogeneous treatment effects using random forests. *Journal of the American Statistical Association*, 113, 1228-1242; Athey, S., Tibshirani, J., & Wager, S. (2019). Generalized random forests. *The Annals of Statistics*, 47, 1148-1178; VanderWeele, T. J., & Ding, P. (2017). Sensitivity analysis in observational research: introducing the E-value. *Annals of Internal Medicine*, 167, 268-274. See also the notes on missing data and on effect sizes.
