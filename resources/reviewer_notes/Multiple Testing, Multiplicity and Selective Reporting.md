# Multiple Testing, Multiplicity and Selective Reporting

## Reviewer principle

The existence of several statistical tests does not by itself determine whether a multiplicity adjustment is required. Reviewers should identify the **inferential family**, the claims being made, how outcomes and analyses were selected, and which error criterion the analysis is intended to control.

Multiplicity matters because making several opportunities to declare a finding can alter the error properties of the overall inferential procedure. However, there is no universal rule that every analysis containing multiple tests must apply the same adjustment, or that unadjusted p-values are automatically invalid.

The appropriate interpretation depends on the scientific question, the structure of the hypotheses, whether analyses were prespecified or selected after seeing the data, and whether inference concerns individual hypotheses, a family of hypotheses, or discoveries across a larger collection of tests.

---

## Reviewer checklist

When a manuscript reports several statistical tests, ask:

- What hypotheses or outcomes were tested?
- Which hypotheses were primary, secondary or exploratory?
- Were these distinctions prespecified?
- Which tests belong to the same inferential family?
- What claims are being made from the collection of tests?
- Were analyses or outcomes selected after examining the results?
- Is the aim to control the probability of **any false rejection**, the expected proportion of false discoveries, or some other error criterion?
- Are tests statistically dependent because outcomes, predictors or observations are related?
- Was a multiplicity procedure used and, if so, does it correspond to the inferential objective?
- Are results for the complete relevant family reported, rather than only statistically significant findings?
- Are effect estimates and their uncertainty reported alongside p-values?
- Does the interpretation distinguish confirmatory from exploratory evidence?

The number of tests alone is not sufficient to determine the appropriate analysis.

---

## What is multiplicity?

Multiplicity arises when an inferential process provides multiple opportunities to make a claim or reject a null hypothesis.

Examples include:

- testing several outcomes;
- comparing several treatment groups;
- making several pairwise comparisons;
- testing many predictors;
- examining multiple subgroups;
- evaluating several time points;
- trying several model specifications;
- conducting interim analyses;
- selecting outcomes or analyses after inspecting the results.

These situations are not statistically identical. The appropriate treatment of multiplicity depends on what collection of hypotheses forms the relevant **family** and what inferential claim is intended.

Simply counting every p-value appearing in a paper is therefore not an adequate multiplicity assessment.

---

## Families of hypotheses

Multiplicity procedures generally operate on a defined collection, or **family**, of hypotheses.

What constitutes an appropriate family is partly determined by the scientific and inferential context. Tests should not automatically be combined into one family merely because they appear in the same manuscript, nor should closely related tests automatically be treated as unrelated simply because they appear in different tables.

For example, a trial may distinguish:

- one prespecified primary outcome;
- several secondary outcomes;
- exploratory outcomes;
- subgroup analyses.

Whether and how multiplicity should be controlled depends on the claims attached to these analyses.

A reviewer should therefore ask what set of hypotheses supports the claim being made rather than applying a correction mechanically to every statistical test in the manuscript.

---

## Type I error and multiple testing

For a single hypothesis test conducted at significance level \(\alpha\), the Type I error probability is \(\alpha\) when the null hypothesis is true and the assumptions defining that test are satisfied.

With multiple opportunities to reject true null hypotheses, the probability of making **at least one false rejection** can exceed the per-test significance level.

This motivates the concept of the **family-wise error rate (FWER)**.

\[
FWER = P(V \geq 1)
\]

where \(V\) is the number of false rejections within the specified family of hypotheses.

FWER is therefore the probability of making one or more false rejections within that family under the relevant configuration of true and false null hypotheses.

---

## The familiar \(1-(1-\alpha)^m\) calculation

If:

1. \(m\) hypothesis tests are statistically independent;
2. all \(m\) null hypotheses are true; and
3. each test is conducted at level \(\alpha\),

then the probability of obtaining at least one false rejection is:

\[
FWER = 1-(1-\alpha)^m.
\]

For 20 independent tests conducted at \(\alpha=.05\):

\[
1-(1-.05)^{20} \approx .642.
\]

Thus, **under those conditions**, there is approximately a 64% probability of at least one false rejection somewhere among the 20 tests.

This calculation should not be generalised beyond its assumptions. Dependence between tests changes the exact joint probability, and if some null hypotheses are false the calculation no longer represents the complete-null scenario.

Most importantly:

> A 64% FWER does **not** mean that a particular statistically significant result has a 64% probability of being false.

FWER is a repeated-sampling property of the testing procedure across a specified family. It is not the posterior probability that a particular null hypothesis is true, nor the probability that an observed significant finding is a false positive.

---

## Dependence between tests

Tests within a family are often dependent.

For example:

- physiological outcomes may be correlated;
- repeated outcomes may be measured on the same participants;
- several contrasts may share a common control group;
- related regression coefficients may be estimated from the same model.

Dependence affects the joint distribution of the test statistics and therefore affects the exact probability of one or more false rejections.

Consequently, the simple calculation

\[
1-(1-\alpha)^m
\]

should not be presented as the FWER for correlated tests without additional justification.

However, correlation between tests does **not** make multiplicity disappear. The inferential family and the claims being made still need to be considered.

---

## Bonferroni correction

For \(m\) hypotheses and a desired family-wise significance level \(\alpha\), the Bonferroni procedure tests each hypothesis against:

\[
\frac{\alpha}{m}.
\]

Equivalently, individual p-values may be multiplied by \(m\), with adjusted p-values bounded above by 1.

Bonferroni controls the FWER using the probability bound

\[
P\left(\bigcup_i A_i\right)
\leq
\sum_i P(A_i).
\]

Its usual FWER guarantee therefore does **not require the hypothesis tests to be statistically independent**.

Bonferroni can nevertheless be conservative, particularly when the number of tests is large or the tests are strongly dependent.

The existence of multiple tests does not imply that Bonferroni is necessarily the most appropriate procedure.

---

## Holm's procedure

The Holm procedure is a sequentially rejective, or step-down, method for controlling FWER.

The p-values are ordered from smallest to largest:

\[
p_{(1)} \leq p_{(2)} \leq \ldots \leq p_{(m)}.
\]

They are then compared sequentially with thresholds based on:

\[
\frac{\alpha}{m-i+1}.
\]

Testing proceeds from the smallest p-value until a hypothesis fails its corresponding criterion; subsequent hypotheses are then not rejected.

Holm's procedure controls FWER and, when applied to the same family at the same \(\alpha\), rejects at least every hypothesis rejected by the ordinary Bonferroni procedure.

A reviewer should nevertheless consider whether controlling FWER is the appropriate objective before choosing between Bonferroni, Holm or another procedure.

---

## Family-wise error rate and false discovery rate are different

FWER and **false discovery rate (FDR)** address different error criteria.

FWER concerns the probability of making **at least one false rejection** in a family.

FDR concerns the expected proportion of false discoveries among the hypotheses that are rejected.

Using \(V\) for the number of false rejections and \(R\) for the total number of rejections, FDR is commonly represented as:

\[
FDR =
E\left[
\frac{V}{\max(R,1)}
\right].
\]

FDR-controlling procedures can be useful when many hypotheses are investigated and accepting some false discoveries in exchange for greater ability to detect signals is consistent with the scientific objective.

The Benjamini-Hochberg procedure is a widely used FDR-controlling approach.

FWER and FDR should not be treated as interchangeable. A procedure designed to control FDR does not thereby control the probability of making any false rejection at the same numerical level.

The assumptions and guarantees of particular FDR procedures also differ. Reviewers should not assume that every procedure described as controlling FDR has identical properties under arbitrary dependence structures.

---

## Benjamini-Hochberg procedure

For \(m\) hypotheses, order the p-values:

\[
p_{(1)} \leq p_{(2)} \leq \ldots \leq p_{(m)}.
\]

For a target FDR level \(q\), identify the largest \(k\) satisfying:

\[
p_{(k)} \leq \frac{k}{m}q.
\]

The hypotheses corresponding to \(p_{(1)},\ldots,p_{(k)}\) are rejected.

The original Benjamini-Hochberg result established FDR control under independence. Extensions and related procedures address particular forms of dependence.

The Benjamini-Hochberg procedure should therefore not be described simply as a Bonferroni alternative with the same error-control objective. It targets a different error criterion.

---

## Choosing between FWER and FDR

Neither FWER nor FDR is universally preferable.

FWER control is particularly relevant where even one false positive conclusion within a family would be consequential.

FDR control may be more appropriate in settings involving many hypotheses where the objective is to identify promising discoveries while controlling the expected proportion of false discoveries.

The appropriate criterion depends on the scientific and decision context.

A reviewer should therefore ask:

> What error is the analysis intended to control, and does that error criterion correspond to the claims being made?

rather than assuming that one multiplicity procedure is universally required.

---

## Prespecified primary outcomes

Multiplicity should be interpreted in relation to the planned inferential structure of the study.

A study with one clearly prespecified primary hypothesis and several secondary or exploratory analyses differs from a study in which 20 outcomes are examined and whichever results cross \(p<.05\) are subsequently highlighted as evidence of effectiveness.

Prespecification can help distinguish confirmatory from exploratory inference, but it does not by itself solve every multiplicity problem. For example, a study may have several prespecified co-primary outcomes, multiple treatment comparisons or a hierarchical testing strategy.

Reviewers should therefore examine both:

1. what was prespecified; and
2. what claims are ultimately made from the analyses.

---

## Co-primary outcomes

Several outcomes may be designated as co-primary.

The multiplicity implications depend on the decision rule.

If success requires **all** co-primary outcomes to satisfy their respective criteria, this differs from a rule under which success can be declared if **any one** of several primary outcomes is significant.

Requiring all co-primary outcomes to succeed does not automatically create the same inflation of Type I error as allowing success to be declared from any one of several opportunities.

Therefore:

> “There are two primary outcomes, so alpha must always be divided by two.”

is not a valid general rule.

The reviewer should identify the actual success criterion and the error rate that the design intends to control.

---

## Secondary outcomes

Secondary outcomes can provide important additional evidence, but their inferential role should be clear.

Questions include:

- Are secondary hypotheses formally confirmatory?
- Are they tested only after success on a primary outcome?
- Do they belong to one or more defined hypothesis families?
- Are they descriptive or exploratory?
- Does the multiplicity strategy cover them?

A label such as “secondary” does not itself determine whether multiplicity adjustment is or is not required.

---

## Exploratory analyses

Exploratory analyses are not inherently inappropriate.

Multiplicity becomes particularly important when exploratory analyses are presented as though they provide the same confirmatory evidence as a single prespecified hypothesis test.

Calling analyses “exploratory” does not make multiplicity irrelevant. Instead, exploratory analyses should generally be reported transparently and interpreted according to their data-dependent and hypothesis-generating role.

A large set of exploratory analyses can be scientifically useful without every p-value being converted into a confirmatory decision.

---

## Prespecification

Prespecification can reduce ambiguity about:

- which hypotheses were primary;
- which outcomes were intended to support confirmatory claims;
- which testing sequence was planned;
- which multiplicity procedure was intended;
- which analyses were exploratory.

Prespecification does not guarantee that an analysis is methodologically appropriate, but it helps distinguish an inferential procedure planned before observing the results from one selected after seeing the data.

This distinction is important because a correction applied to the final reported tests does not necessarily account for a larger unreported process of data-dependent analysis selection.

---

## Selective reporting

Multiplicity is not solely a matter of the number of statistical tests. **Selection** can be equally important.

Suppose 20 outcomes are analysed but only the two with \(p<.05\) are emphasised or reported. Interpretation of those two p-values differs from a situation in which those outcomes were prespecified as the sole primary hypotheses.

Selection may occur through:

- selective outcome reporting;
- choosing among alternative model specifications;
- selecting subgroups;
- selecting time points;
- choosing transformations or covariate adjustments;
- highlighting only statistically significant analyses.

When analytical choices are influenced by the observed results, the nominal properties of the final reported analysis may not describe the full procedure that generated the finding.

A reviewer should therefore consider the **analysis and selection process**, not merely the final p-values shown in the manuscript.

---

## Multiple testing and selective reporting are related but distinct

Multiplicity can occur even when every analysis is fully reported.

Selective reporting can make the problem more difficult because the reader may not know how many analyses or outcomes provided opportunities for the reported finding.

For example:

- 20 transparently reported tests create an identifiable multiplicity problem;
- reporting only the two significant tests may conceal the size and structure of that problem.

Transparent reporting of all relevant analyses does not automatically resolve multiplicity, but it makes the inferential process more assessable.

A conventional multiplicity correction applied only to the analyses eventually reported also does not necessarily address an undisclosed data-dependent process through which those analyses were selected.

---

## What does an unadjusted p-value mean?

An unadjusted p-value is not automatically “invalid” because other tests were performed.

It remains the p-value associated with its particular test under that test's assumptions.

The important question is whether interpreting that p-value using a conventional threshold such as \(p<.05\) supports the **larger inferential claim being made**, given the family of analyses and any selection process.

Therefore statements such as:

> “No multiplicity correction was used, so the p-values are invalid.”

are generally too strong.

The concern is the relationship between the reported individual tests and the error properties of the overall inferential procedure.

---

## Two significant findings among many tests

Suppose a study conducts 20 outcome tests and reports:

\[
p=.03
\]

and

\[
p=.04
\]

for two outcomes, with the remaining 18 not statistically significant.

Those facts alone do not establish that the intervention is effective.

They also do not establish that the two significant findings are false.

Interpretation depends on matters including:

- whether the outcomes were prespecified;
- whether they form a common inferential family;
- the study's intended error criterion;
- dependence among outcomes;
- whether the analyses were selected after examining the data;
- the effect estimates and their uncertainty;
- whether an appropriate multiplicity procedure was planned or applied;
- the scientific plausibility and coherence of the pattern of results.

It is therefore inappropriate to infer simply:

> “Two p-values are below .05, therefore there is a genuine signal.”

It is equally inappropriate to infer:

> “There were 20 tests, therefore the two significant findings must be false positives.”

Neither conclusion follows from the number of tests and p-values alone.

---

## Adjustment changes the decision rule, not the observed data

Multiplicity procedures change how evidence is evaluated across a family of hypotheses.

They do not ordinarily change the observed effect estimates themselves.

For example, applying a multiplicity procedure may change whether a hypothesis satisfies a decision threshold, while leaving the estimated treatment effect unchanged.

This distinction is useful when reviewing claims such as:

> “After correction, the treatment effect disappeared.”

Usually the observed estimate did not disappear. Rather, the inferential decision or uncertainty statement changed under a procedure accounting for multiplicity.

Selection based on observed results can additionally produce exaggerated estimates among selected findings. This is a separate issue from the numerical adjustment of a p-value.

---

## Confidence intervals and multiplicity

When several parameters are considered simultaneously, ordinary pointwise confidence intervals do not generally provide the same coverage guarantee as a simultaneous confidence procedure.

A 95% confidence interval for each parameter is designed to have its stated coverage for that individual interval under its assumptions. It does not generally imply 95% simultaneous coverage of all corresponding parameters across a collection of intervals.

Where simultaneous inference is the objective, simultaneous confidence intervals or other procedures designed for that purpose may be appropriate.

Reviewers should distinguish **pointwise** uncertainty from **simultaneous** uncertainty.

---

## Effect sizes and uncertainty remain important

Multiplicity should not reduce interpretation to whether adjusted p-values cross a threshold.

Effect estimates and appropriate measures of uncertainty remain important for understanding:

- direction;
- magnitude;
- precision;
- compatibility with scientifically meaningful effects.

Where many outcomes are analysed, reporting effect estimates and uncertainty across the relevant outcomes can also reduce the distortions produced by focusing exclusively on statistically significant results.

However, effect sizes and confidence intervals do not automatically solve multiplicity. Their interpretation must still correspond to whether inference is pointwise or simultaneous and to how outcomes were selected.

---

## Non-significant results after multiplicity adjustment

Failure to reject a null hypothesis after a multiplicity adjustment does not establish that the effect is absent.

For example, a result that no longer crosses a decision threshold after adjustment has a *p*-value above the stricter threshold that the adjustment applies to that test in order to control the chosen error rate (for example, the family-wise error rate or the false discovery rate) across the family of tests. That error rate is a property of the procedure across the family, not of the individual result. Because the stricter threshold also lowers the power of each test, failure to reject after adjustment is even less informative about whether the effect is negligible than an unadjusted non-significant result, and it is not positive evidence that the underlying effect is zero or negligible.

Evidence for absence or practical equivalence requires an inferential framework capable of addressing that question, such as an appropriately designed equivalence analysis or other methods that directly quantify evidence concerning negligible effects.

Therefore:

> “The result was no longer significant after correction, so there is no effect.”

is not generally justified.

---

## Does every study with several p-values require multiplicity adjustment?

Not necessarily.

There is no rule that every collection of p-values must receive a mechanical multiplicity adjustment.

Whether adjustment is appropriate depends on the inferential objective, the hypothesis family, the claims being made and the error criterion that is relevant to those claims.

Examples where reviewers should examine the structure rather than automatically demand a correction include:

- a single prespecified primary hypothesis accompanied by clearly labelled descriptive or exploratory analyses;
- separate hypotheses addressing substantively distinct questions for which no joint family-wise claim is made;
- analyses where estimation rather than dichotomous hypothesis-testing decisions is the primary objective;
- procedures that already incorporate multiplicity through a hierarchical, simultaneous or otherwise structured inferential design.

This does not mean that these situations are automatically free from multiplicity concerns. It means the reviewer should identify the relevant inferential structure before deciding what control is required.

---

## Hierarchical and gatekeeping strategies

Some confirmatory analyses specify an ordered testing strategy.

For example, a secondary hypothesis may be tested formally only if a primary hypothesis has first met a prespecified criterion.

Such hierarchical or gatekeeping procedures can be constructed to control an overall error rate while preserving more power than treating every hypothesis as an unordered family.

A manuscript using such a strategy should describe:

- the testing sequence;
- the conditions under which subsequent hypotheses are tested;
- the error criterion being controlled;
- whether the procedure was prespecified.

A post hoc ordering chosen after observing the results should not automatically be interpreted as equivalent to a prespecified hierarchical testing procedure.

---

## Bayesian inference and multiplicity

Multiplicity also arises in Bayesian work, but there is no single universally accepted Bayesian analogue of frequentist multiple-testing correction.

The relevance and treatment of multiplicity depend on matters including:

- the Bayesian inferential framework being used;
- whether hypotheses are considered separately or jointly;
- the prior structure;
- whether effects are exchangeable or related;
- whether a hierarchical model is used;
- whether analyses were prespecified or selected after observing the data;
- whether inference concerns posterior estimation, Bayes factors, posterior model probabilities or explicit decisions;
- what operating characteristics the analysis is intended to have.

It is therefore inappropriate simply to transfer frequentist procedures such as Bonferroni correction to every Bayesian analysis. It is equally inappropriate to conclude that multiplicity becomes irrelevant merely because an analysis is Bayesian.

---

## A Bayesian modelling perspective

One influential Bayesian perspective is that many apparent multiple-comparison problems are better addressed through the statistical model than through a separate correction applied after fitting.

When several related effects are modelled jointly in a hierarchical or multilevel model, the model can estimate their population distribution and partially pool individual estimates towards that distribution.

This can reduce the tendency for the most extreme estimates among a large collection to be interpreted at face value.

Under this perspective, the response to multiplicity is not necessarily:

> fit many separate models and then adjust the resulting probabilities.

Instead, it may be:

> construct a model representing the collection of related effects and estimate them jointly.

This perspective is particularly associated with work by Andrew Gelman and colleagues on multiple comparisons and multilevel modelling.

However, hierarchical modelling should not be treated as a universal automatic solution. Its appropriateness depends on whether the effects can reasonably be represented by the hierarchical structure, the prior and model specification, and the inferential question.

Partial pooling also does not make selective analysis or selective reporting irrelevant.

---

## Partial pooling and multiplicity

Suppose many related group effects, treatment effects or subgroup effects are estimated independently.

Even when all underlying effects are modest, sampling variation can produce some apparently extreme estimates simply because many estimates have been examined.

A hierarchical model can represent those effects as arising from a common population distribution.

The estimated effects are then generally partially pooled, with noisier estimates typically receiving more shrinkage towards the estimated group distribution than more precisely estimated effects.

This can reduce exaggeration of extreme estimates and can address an important feature of multiple-comparison problems.

However:

- partial pooling does not guarantee that every multiplicity concern has disappeared;
- the amount of shrinkage depends on the model and data;
- inappropriate exchangeability assumptions can be problematic;
- hierarchical modelling does not automatically account for an undisclosed search across outcomes, models or hypotheses;
- posterior inference remains conditional on the specified model and prior.

Therefore:

> “The analysis used a hierarchical Bayesian model, so multiplicity cannot be a problem.”

is too strong.

---

## Bayesian analyses can incorporate multiplicity explicitly

Bayesian approaches can also represent multiplicity explicitly through mechanisms such as:

- hierarchical priors;
- prior probabilities assigned to hypotheses or models;
- mixture or spike-and-slab structures;
- posterior model probabilities;
- multiplicity-aware variable-selection priors;
- explicit Bayesian decision rules.

In these approaches, increasing the number of candidate hypotheses can alter prior or posterior probabilities through the joint model rather than through a separate adjustment of individual p-values.

Consequently, Bayesian multiplicity adjustment need not resemble Bonferroni or Holm correction even when it serves a related purpose.

The appropriate interpretation depends on the model and decision framework actually used.

---

## Bayesian posterior probabilities are not adjusted p-values

Posterior probabilities should not be treated as though they were p-values requiring an automatic Bonferroni-style correction.

A posterior probability is conditional on the specified model, prior and observed data.

If many related hypotheses are being considered, their relationship may be represented through the prior or hierarchical model.

The relevant reviewer question is therefore not simply:

> “Were the posterior probabilities corrected for multiple testing?”

Instead ask:

> “How does the Bayesian model represent the collection of hypotheses, and do the model, priors and decision rule support the claims being made?”

---

## Multiple Bayes-factor tests

Bayes factors compare the predictive support provided by the observed data for specified competing models.

They are not p-values.

Consequently, performing 20 Bayes-factor comparisons does not automatically imply that each Bayes factor should receive a Bonferroni, Holm or FDR correction.

Such procedures were developed for particular frequentist error-control objectives and should not be transferred mechanically to Bayes factors.

However, this does **not** imply that multiplicity or selection becomes irrelevant.

For example, if many possible comparisons are examined and only those producing large Bayes factors are reported, the resulting evidential presentation has been affected by a selection process.

Relevant questions include:

- Were the comparisons prespecified?
- How many hypotheses or models were considered?
- Were only favourable Bayes factors reported?
- Are the hypotheses related?
- Are prior model probabilities specified coherently across the collection of models?
- Does the model structure account for relationships among the hypotheses?
- Was a decision threshold chosen in advance or after examining the results?

Therefore:

> “Bayes factors are Bayesian, so multiplicity is irrelevant.”

is too strong.

Equally:

> “Twenty Bayes factors require a Bonferroni correction.”

is not a general Bayesian rule.

---

## Bayes factors and prior model probabilities

A Bayes factor represents the change in relative evidence between two specified models supplied by the data.

Posterior model odds additionally depend on prior model odds.

For two models \(M_1\) and \(M_0\):

\[
\frac{P(M_1 \mid y)}{P(M_0 \mid y)}
=
BF_{10}
\times
\frac{P(M_1)}{P(M_0)}.
\]

When many models or hypotheses are considered, the prior probability assigned across that model space can therefore matter substantially.

A Bayesian analysis involving many candidate models should not automatically assign the same interpretation to a Bayes factor without considering the larger model space and the prior structure where these are relevant to the inferential procedure.

This provides one route through which Bayesian modelling can address multiplicity without applying a frequentist correction to the Bayes factors themselves.

---

## Bayesian decision rules and frequentist operating characteristics

Bayesian inference and frequentist error control are not mutually exclusive.

A Bayesian analysis can use posterior quantities or Bayes factors while choosing a decision rule partly according to its repeated-sampling operating characteristics.

For example, a threshold for a posterior probability or Bayes factor can be calibrated so that a procedure has a desired Type I error rate, FWER, power or other operating characteristic under specified scenarios.

This does not turn the Bayesian evidence measure into a p-value.

It means that the **decision procedure** has been evaluated or designed according to a frequentist operating characteristic.

Reviewers should therefore distinguish:

1. the evidential quantity being calculated;
2. the decision rule applied to that quantity; and
3. the operating characteristics used to evaluate the resulting procedure.

---

## Legitimate disagreement about Bayesian multiplicity

There is legitimate methodological disagreement about how multiplicity should be conceptualised and handled in Bayesian analyses.

One position emphasises that coherent Bayesian inference under a fully specified model does not require a separate frequentist-style correction for every additional comparison.

Another emphasises that multiplicity can and sometimes should be represented explicitly through prior model probabilities, hierarchical priors, decision rules or other model structures.

A further perspective evaluates Bayesian procedures partly according to frequentist operating characteristics such as Type I error, FWER or false discoveries.

These positions are not necessarily mutually exclusive. They can reflect different inferential goals.

For example, a researcher may use:

- a hierarchical Bayesian model for estimation;
- Bayes factors for model comparison;
- and simulation to examine the frequentist operating characteristics of a decision threshold.

The reviewer should therefore avoid treating one statistical philosophy as supplying a universal multiplicity rule.

The relevant question is whether the analysis is coherent within its stated inferential framework and whether the resulting claims are justified by that framework.

---

## Gelman-style multilevel modelling perspective

Gelman and colleagues have argued that many multiple-comparison problems can be reframed as problems of modelling related effects.

Rather than estimating many effects separately and subsequently correcting them, a multilevel model estimates them jointly and partially pools them.

This approach can be especially attractive when the effects represent related groups, sites, outcomes, treatments or interactions for which an exchangeable hierarchical structure is scientifically defensible.

The important principle for a reviewer is not:

> “Bayesian methods eliminate multiple comparisons.”

It is instead that:

> **joint hierarchical modelling can change the multiple-comparison problem by modelling the collection of related effects rather than treating every comparison as an unrelated test.**

The validity of this approach still depends on the adequacy of the model and its assumptions.

---

## Wagenmakers-style Bayesian testing perspective

Another important Bayesian tradition focuses on explicit hypothesis or model comparison using Bayes factors.

From this perspective, evidence for competing hypotheses is quantified through their relative predictive performance under specified prior models.

Multiplicity should therefore be considered through the structure of the hypotheses, model space, prior model probabilities and any decision rule, rather than by automatically applying p-value corrections to Bayes factors.

This does not imply that searching through a large number of hypotheses and selectively reporting favourable Bayes factors is methodologically harmless.

Selection and multiplicity remain relevant to the interpretation of the resulting evidence.

The distinction is therefore between:

- treating Bayes factors as though they were frequentist p-values requiring mechanical correction; and
- recognising that a Bayesian model-comparison procedure may itself need to represent or account for the larger hypothesis space and selection process.

---

## Where Bayesian perspectives can differ

Differences between Bayesian approaches often concern the level at which multiplicity should be addressed.

Possible positions include:

- **no separate adjustment:** posterior inference follows directly from a prespecified coherent joint model;
- **hierarchical modelling:** related effects are partially pooled through a common model;
- **prior multiplicity adjustment:** prior probabilities or prior structures change as the number or configuration of candidate hypotheses changes;
- **Bayesian decision analysis:** posterior quantities are converted into decisions using explicit losses or utilities;
- **operating-characteristic calibration:** Bayesian decision thresholds are selected or evaluated using frequentist quantities such as FWER or power.

A reviewer should not classify these approaches as equivalent merely because they are Bayesian.

Nor should disagreement between them automatically be classified as a methodological error.

The manuscript should explain which framework it adopts and why the resulting inference supports the substantive claims being made.

---

## Bayesian multiplicity and data-dependent searching

A coherent Bayesian model does not automatically protect an analysis from an undisclosed data-dependent search.

If researchers:

- examine many outcomes;
- try numerous transformations;
- explore many subgroups;
- compare many model specifications;
- and report only analyses producing favourable posterior probabilities or Bayes factors,

the selection process remains relevant.

The final posterior or Bayes factor is conditional on the model and data presented to it. It does not automatically encode every alternative analysis that researchers considered and discarded.

Consequently:

> “Bayesian inference automatically accounts for researcher degrees of freedom.”

is too strong.

Transparent reporting, prespecification where appropriate, sensitivity analysis and explicit modelling of the relevant hypothesis space remain important.

---

## Common problematic Bayesian claims

### “Bayesian analyses do not have a multiple-testing problem.”

Too strong. Bayesian frameworks can address multiplicity differently from frequentist hypothesis testing, but the existence of many hypotheses, model comparisons or data-dependent selections can remain relevant.

### “Bayesian tests require Bonferroni correction when several hypotheses are tested.”

Incorrect as a general rule. Bonferroni is a frequentist FWER-controlling procedure and should not be transferred mechanically to Bayesian evidence measures.

### “Bayes factors should be Bonferroni corrected.”

Not a general rule. Bayes factors are evidence ratios rather than p-values. Multiplicity may instead be addressed through the model space, prior probabilities, hierarchical structure or decision framework.

### “A hierarchical Bayesian model automatically solves multiplicity.”

Too strong. Hierarchical modelling and partial pooling can address important aspects of multiple comparisons, but adequacy depends on the model, assumptions and inferential question.

### “Partial pooling eliminates false positives.”

Incorrect. Partial pooling changes estimation and can reduce exaggeration of noisy extreme effects, but it does not provide a universal guarantee that false discoveries cannot occur.

### “A posterior probability of .95 should be divided by the number of tests.”

Incorrect as a general rule. Posterior probabilities are not p-values, and frequentist alpha-division rules do not transfer mechanically to them.

### “Bayesian evidence is immune to selective reporting.”

Incorrect. Selecting which analyses, hypotheses or Bayes factors to report according to their observed results can affect interpretation.

### “A Bayes factor is unaffected by the number of other hypotheses considered.”

Too general. A pairwise Bayes factor is defined by the two models being compared, but interpretation within a larger model-selection procedure can depend on the model space, prior model probabilities and selection process.

### “Using Bayes factors means Type I error is irrelevant.”

Too strong. A Bayesian analysis need not define evidence through Type I error, but researchers may legitimately evaluate Bayesian decision procedures using frequentist operating characteristics.

### “If a Bayesian procedure controls FWER, it has become frequentist.”

Incorrect. Bayesian quantities can be used within a decision procedure whose repeated-sampling operating characteristics are also evaluated.

### “Gelman's multilevel approach and Bayes-factor approaches give the same solution to multiplicity.”

Incorrect. They can represent different inferential strategies and address multiplicity at different levels of the analysis.

### “There is one accepted Bayesian correction for multiple testing.”

Incorrect. Bayesian approaches to multiplicity differ according to modelling assumptions, priors, hypothesis structures, decision rules and inferential goals.

---

## Common problematic claims

### “Twenty tests at alpha = .05 means the FWER is about 64%.”

Too general unless the required conditions are specified. The approximately 64% calculation follows for 20 independent tests under the complete null when each is conducted at \(\alpha=.05\).

### “A 64% FWER means there is a 64% chance a significant result is false.”

Incorrect. FWER is the probability of at least one false rejection within the family under the specified repeated-sampling conditions. It is not the probability that a particular observed finding is false.

### “Twenty tests means the authors must use Bonferroni.”

Incorrect as a general rule. The relevant hypothesis family, scientific claims and desired error criterion need to be identified first. Bonferroni is one possible FWER-controlling procedure, not a universal requirement.

### “Bonferroni requires independent tests.”

Incorrect for its usual FWER guarantee. Bonferroni's control follows from an inequality that does not require independence, although dependence can affect how conservative the procedure is.

### “Holm is just another name for Bonferroni.”

Incorrect. Holm is a sequentially rejective procedure. When applied to the same family at the same \(\alpha\), it rejects at least every hypothesis rejected by ordinary Bonferroni.

### “FDR and FWER are equivalent.”

Incorrect. They control different error criteria.

### “An FDR of 5% means exactly 5% of the significant findings are false.”

Incorrect. FDR is an expected proportion across the repeated-sampling behaviour of the procedure, not a statement that exactly 5% of the observed rejected hypotheses are false.

### “If no multiplicity correction was used, all of the p-values are invalid.”

Incorrect. Individual p-values do not cease to be p-values. The issue is whether the inferential procedure and claims appropriately account for the multiplicity and selection involved.

### “No correction means the significant findings are probably false positives.”

Incorrect as a general conclusion. Multiplicity can increase opportunities for false rejection, but it does not establish that a particular observed finding is false.

### “Two significant results among 20 tests prove there is a signal.”

Not established by that fact alone. The result must be interpreted in relation to the inferential family, prespecification, selection, dependence and the intended error criterion.

### “Correlated outcomes remove the multiple-testing problem.”

Incorrect. Dependence affects joint error probabilities and the properties of particular procedures; it does not automatically remove multiplicity.

### “Exploratory analyses do not have a multiplicity problem.”

Too strong. Exploratory analyses may be appropriate, but the number and selection of analyses remain relevant to the strength of conclusions that can be drawn.

### “Every statistical test in a paper belongs to one family.”

Incorrect as a general rule. The relevant family depends on the inferential structure and claims being made.

### “Every paper with several p-values requires all of them to be adjusted together.”

Incorrect. The relevant family and error criterion must first be identified.

### “Two primary outcomes always require alpha to be divided by two.”

Incorrect. The multiplicity implications depend on the decision rule. Requiring both co-primary outcomes to succeed differs from allowing success if either one succeeds.

### “The result became non-significant after correction, so there is no effect.”

Incorrect. Failure to reject does not establish absence of an effect.

### “Reporting confidence intervals solves the multiplicity problem.”

Incorrect. Ordinary pointwise confidence intervals do not automatically provide simultaneous coverage across multiple parameters.

---

## Reviewer red flags

Potential concerns include:

- many outcomes but no distinction between primary and secondary outcomes;
- only statistically significant outcomes discussed;
- multiple subgroup analyses without clear prespecification;
- many analyses using \(p<.05\) without discussion of multiplicity;
- claims of treatment effectiveness based on a small subset of significant outcomes;
- multiplicity adjustment applied without identifying what family it controls;
- Bonferroni demanded or used solely because “there are multiple tests”;
- FWER interpreted as the probability that a particular finding is false;
- FDR described as controlling the probability of any false positive;
- correlated outcomes claimed to make multiplicity irrelevant;
- exploratory analyses presented as confirmatory;
- adjusted non-significance interpreted as evidence of no effect;
- effect estimates omitted while attention is focused entirely on threshold crossing;
- only the analyses producing favourable results reported.

These are prompts for closer examination, not automatic evidence that the analysis is invalid.

---

## Detailed reviewer checklist

### Study design and prespecification

Determine:

- the primary scientific questions;
- the primary and secondary outcomes;
- whether these were prespecified;
- whether subgroup analyses were planned;
- whether multiple time points or treatment comparisons were planned;
- whether a protocol or statistical analysis plan defines the inferential strategy.

### Hypothesis family

Determine:

- which hypotheses contribute to the same substantive claim;
- whether the manuscript explicitly defines a family;
- whether several apparently separate analyses actually support one overarching claim;
- whether unrelated analyses have been combined unnecessarily into one multiplicity calculation.

### Selection

Determine whether:

- outcomes were selected after examining results;
- model specifications were selected according to statistical significance;
- subgroups or time points were selected after analysis;
- only statistically significant analyses are emphasised or reported.

### Error criterion

Determine whether the analysis seeks to control:

- per-hypothesis Type I error;
- family-wise error rate;
- false discovery rate;
- another explicitly defined criterion.

Do not assume these objectives are interchangeable.

### Statistical procedure

If an adjustment is used, determine:

- which hypotheses it applies to;
- why that procedure was selected;
- whether its assumptions and guarantees match the analysis;
- whether the reported interpretation corresponds to the criterion being controlled.

### Interpretation

Check whether the manuscript:

- distinguishes individual from family-wise inference;
- avoids interpreting FWER as the probability an observed finding is false;
- avoids interpreting non-significance as evidence of absence;
- reports effect estimates and uncertainty where relevant;
- distinguishes exploratory from confirmatory conclusions;
- reports the broader pattern of results rather than selectively highlighting threshold-crossing findings.

---

## Glossary

**Multiplicity**
The inferential consequences arising from multiple opportunities to make claims, reject hypotheses or select favourable results.

**Hypothesis family**
A collection of hypotheses considered together for a particular inferential purpose.

**Type I error**
Rejecting a null hypothesis when that null hypothesis is true.

**Family-wise error rate (FWER)**
The probability of making one or more false rejections within a specified family of hypotheses.

**False discovery rate (FDR)**
The expected proportion of false rejections among the rejected hypotheses, using an appropriate convention when there are no rejections.

**Bonferroni procedure**
An FWER-controlling procedure that, for \(m\) tests and target family-wise level \(\alpha\), can compare each test with \(\alpha/m\).

**Holm procedure**
A sequential step-down FWER-controlling procedure based on ordered p-values.

**Benjamini-Hochberg procedure**
A step-up procedure designed to control FDR under specified conditions.

**Pointwise confidence interval**
An interval whose coverage applies to an individual parameter or inferential target.

**Simultaneous confidence intervals**
Intervals constructed so that a specified joint coverage property applies across a collection of parameters.

**Selective reporting**
Reporting or emphasising analyses partly according to their observed results.

**Confirmatory analysis**
An analysis intended to test prespecified hypotheses under a defined inferential procedure.

**Exploratory analysis**
An analysis used to investigate patterns or generate hypotheses, typically warranting more cautious interpretation when data influenced the analyses considered or highlighted.

---

## Final reviewer question

The key question is not simply:

> “Was a multiple-testing correction applied?”

Instead ask:

> **Were the relevant hypotheses, selection process and inferential claims defined transparently, and does the statistical procedure appropriately control the errors relevant to those claims?**

A multiplicity procedure should follow from the inferential problem. It should not be applied mechanically merely because several p-values appear in a manuscript, nor omitted merely because the analyses have been labelled exploratory.
