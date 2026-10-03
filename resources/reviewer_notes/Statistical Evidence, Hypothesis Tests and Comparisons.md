# Statistical Evidence, Hypothesis Tests and Comparisons

#### Purpose

This guide helps reviewers assess whether the **statistical question
actually tested matches the scientific claim being made**.

It focuses on hypothesis tests, *p*-values, significance thresholds,
comparisons between effects, and the distinction between statistical
evidence and statistical decision rules. Particular attention is given
to a common inferential error: concluding that two effects differ
because one is described as statistically significant and the other is
not.

The guide does not require authors to adopt a particular philosophy of
statistical inference. Conventional null-hypothesis significance testing
(NHST) is widely used and contemporary NHST practice commonly combines
elements historically associated with Fisherian significance testing and
Neyman--Pearson hypothesis testing. These traditions assign different
roles to p-values, hypotheses, decision thresholds and long-run error
rates. Reviewers should therefore examine **what was tested, what
statistical result was obtained, how that result was interpreted, and
whether the scientific conclusion follows from the analysis**, rather
than inferring the meaning of an analysis from terminology alone.

#### What reviewers should look for

✓ The hypothesis or statistical contrast being tested corresponds to the
scientific question.

✓ The *p*-value is interpreted in relation to the specified hypothesis,
statistical model and test statistic that generated it.

✓ The *p*-value is not interpreted as the probability that the null
hypothesis is true or that the result occurred "by chance".

✓ Statistical evidence is not reduced unnecessarily to whether *p* falls
immediately above or below a conventional threshold.

✓ Where a formal significance threshold such as α = 0.05 is used as a
decision rule, the threshold is prespecified and, where relevant,
justified.

✓ Separate hypothesis tests are not treated as though they directly test
the difference between the quantities tested.

✓ If the scientific claim concerns whether two effects differ, the
relevant contrast between those effects is estimated or tested directly.

✓ Statistical evidence is distinguished from effect magnitude and
scientific, clinical or practical importance.

✓ Claims about interventions or causal effects are supported by an
appropriate design and estimand rather than by statistical significance
alone.

------------------------------------------------------------------------

#### What question does a statistical test actually answer?

A statistical test addresses a **specified hypothesis or contrast under
a statistical model**.

The interpretation of the resulting test statistic and *p*-value
therefore depends on what was actually tested.

For example, these are different statistical questions:

-   Is effect A different from zero?
-   Is effect B different from zero?
-   Is effect A different from effect B?

Evidence concerning the first two questions does not automatically
answer the third.

Before interpreting a hypothesis test, reviewers should therefore
identify:

1.  the quantity or parameter of scientific interest;
2.  the hypothesis or contrast actually tested;
3.  the statistical model and assumptions under which the test was
    constructed; and
4.  whether the tested hypothesis corresponds to the scientific claim
    being made.

A technically correct statistical test can still provide inadequate
support for a conclusion if it tests a different quantity from the one
required by that conclusion.

------------------------------------------------------------------------

#### What does a *p*-value tell us?

A ***p*-value** is calculated under a specified statistical model that
includes the hypothesis being tested. It describes how extreme the
observed value of the chosen test statistic is relative to the
distribution expected under that model.

Smaller *p*-values indicate greater incompatibility between the observed
data and the tested statistical model, subject to the assumptions and
analysis that generated the test.

A *p*-value is **not**:

-   the probability that the null hypothesis is true;
-   the probability that the alternative hypothesis is true;
-   the probability that the observed result occurred "by chance";
-   the probability that the result will replicate;
-   the magnitude of the effect;
-   the practical importance of the effect.

The same numerical *p*-value can also have different scientific
implications depending on the hypothesis tested, study design, model
assumptions, multiplicity of analyses and scientific context.

Detailed guidance on interpreting *p*-values, confidence intervals,
non-significant results and evidence of absence is provided in the
companion note **Interpreting p-values and Non-significant Results**.

```references
- cite: Wasserstein, R. L., & Lazar, N. A. (2016). The ASA statement on p-values: Context, process, and purpose. The American Statistician, 70(2), 129–133.
  doi: 10.1080/00031305.2016.1154108
  supports: What p-values do and do not measure, and why scientific conclusions should not depend only on whether a threshold is crossed.
  short: ASA guidance on interpreting p-values
  type: Journal article
  access: open
  checked: 2026-10-03
  access_checked: 2026-10-03
- cite: Greenland, S., Senn, S. J., Rothman, K. J., Carlin, J. B., Poole, C., Goodman, S. N., & Altman, D. G. (2016). Statistical tests, P values, confidence intervals, and power: A guide to misinterpretations. European Journal of Epidemiology, 31(4), 337–350.
  doi: 10.1007/s10654-016-0149-3
  supports: Interpretation of p-values in relation to statistical models, test statistics and assumptions, and common inferential misinterpretations.
  short: common misinterpretations of tests, p-values and intervals
  type: Journal article
  access: open
  checked: 2026-10-03
  access_checked: 2026-10-03
```

------------------------------------------------------------------------

#### Are *p*-values evidence or decision rules?

Different frequentist traditions have assigned different roles to
statistical tests.

In an **evidential use of significance testing**, an observed *p*-value
can be considered continuously as information about the degree of
incompatibility between the data and a specified null model. A smaller
*p*-value represents greater incompatibility under that model, subject
to the assumptions and analysis that produced it.

A **decision or error-control approach** instead uses a prespecified
testing procedure with defined long-run operating characteristics. In a
Neyman--Pearson framework, hypotheses, decision rules and error rates
such as Type I and Type II errors are considered as part of the
procedure.

These ideas should not be treated as interchangeable.

Contemporary NHST practice commonly combines elements historically
associated with Fisherian significance testing and Neyman--Pearson
hypothesis testing. These traditions assign different roles to p-values,
hypotheses, decision thresholds and long-run error rates.

The existence of such a hybrid practice does not by itself invalidate an
analysis. Reviewers should instead ask whether the interpretation is
**inferentially coherent**.

In particular:

-   Is the *p*-value being interpreted as evidence concerning
    compatibility with a model?
-   Is a prespecified threshold being used to make a formal statistical
    decision?
-   Are concepts such as Type I error, Type II error and power being
    invoked consistently with that decision procedure?
-   Does the scientific conclusion follow from either interpretation?

Reviewers should not require authors to label themselves as Fisherian,
Neyman--Pearson, or otherwise. The important issue is what inferential
meaning is actually attached to the statistical procedure.

```references
- cite: Pernet, C. R. (2017). Null hypothesis significance testing: A guide to commonly misunderstood concepts and recommendations for good practice. F1000Research, 4, 621.
  doi: 10.12688/f1000research.6963.5
  supports: The conceptual distinction between Fisherian significance testing and Neyman–Pearson hypothesis testing, and the combination of elements from these traditions in contemporary NHST practice.
  short: Fisher, Neyman–Pearson and contemporary NHST
  type: Journal article
  access: open
  checked: 2026-10-03
  access_checked: 2026-10-03
```

------------------------------------------------------------------------

#### What role does α play?

The significance level **α** is a threshold specified as part of a
hypothesis-testing procedure.

Under the usual repeated-sampling interpretation, α controls the
probability of rejecting the null hypothesis when the null hypothesis is
true under the conditions specified by the testing procedure.

The observed *p*-value and α therefore play different roles:

-   **α** is a property of the decision rule specified for the testing
    procedure;
-   the ***p*-value** is calculated from the observed data.

A conventional value such as α = 0.05 is not a natural boundary
separating real effects from unreal effects.

Where a formal threshold is being used, reviewers should expect it to be
specified before the results are known. Where the decision context makes
the consequences of false-positive and false-negative decisions
important, the choice of threshold should be justified rather than
treated as automatically correct because 0.05 is conventional.

A threshold selected or altered after examining the results cannot
provide the same prespecified error-control interpretation.

Where many hypotheses are tested, interpretation of α must also be
considered alongside multiplicity. Detailed guidance is provided in
**Multiple Testing, Multiplicity and Selective Reporting**.

```references
- cite: Lakens, D., Adolfi, F. G., Albers, C. J., et al. (2018). Justify your alpha. Nature Human Behaviour, 2(3), 168–171.
  doi: 10.1038/s41562-018-0311-x
  supports: The case for treating alpha as an explicit design choice that should be reported and justified rather than automatically defaulting to 0.05.
  short: justifying alpha rather than automatically using 0.05
  type: Journal article
  access: repository
  checked: 2026-10-03
  access_url: https://www.repository.cam.ac.uk/handle/1810/286595
  access_checked: 2026-10-03
```

------------------------------------------------------------------------

#### Does "significant" versus "non-significant" establish a difference?

No.

Suppose two estimated effects are tested separately:

-   effect A produces *p* = 0.03;
-   effect B produces *p* = 0.08.

It does **not** follow that A and B are statistically distinguishable
from one another.

The two tests address whether each effect satisfies its own tested
hypothesis. They do not directly test the contrast between A and B.

This distinction is fundamental:

> **A difference between the outcomes of two significance tests is not
> itself a test of the difference between the two effects.**

The same problem occurs when authors report that:

-   an effect is significant in one group but not another;
-   an association is significant in men but not women;
-   an intervention group changes significantly but a control group does
    not;
-   one study reports a significant result while another does not;
-   an effect is significant at one time point but not another.

None of these differences in significance classification, by themselves,
establish that the corresponding effects differ.

Values immediately on opposite sides of a threshold are particularly
poor grounds for a qualitative distinction. For example, *p* = 0.049 and
*p* = 0.051 do not represent fundamentally different states of
scientific evidence.

```references
- cite: Gelman, A., & Stern, H. (2006). The difference between "significant" and "not significant" is not itself statistically significant. The American Statistician, 60(4), 328–331.
  doi: 10.1198/000313006X152649
  supports: Why different significance classifications from separate tests do not establish that the corresponding effects differ.
  short: why significant versus non-significant does not establish a difference
  type: Journal article
  checked: 2026-10-03
```

------------------------------------------------------------------------

#### If the scientific claim concerns a difference, what should be analysed?

The analysis should address the **contrast corresponding to the
scientific claim**.

If the question is whether effect A differs from effect B, the relevant
inferential quantity is some appropriately defined contrast between A
and B, not merely the separate classification of A and B.

For a simple difference this might be represented conceptually as:

\[ A-B. \]

In more complex designs, the relevant contrast may be represented
through:

-   an interaction term;
-   a difference between changes;
-   a planned contrast;
-   a regression coefficient;
-   a marginal contrast;
-   another estimand appropriate to the design.

An **interaction** is therefore one possible parameterisation of a
difference between effects. It is not a universal prescription.

The appropriate analysis depends on:

-   the research question;
-   the study design;
-   the estimand;
-   the outcome distribution;
-   dependence or clustering;
-   covariate structure;
-   measurement timing;
-   missing-data assumptions;
-   other relevant modelling assumptions.

The general principle is therefore not:

> "Always test an interaction."

It is:

> **Identify the quantity required by the scientific claim and analyse
> that quantity directly using a method appropriate to the design.**

This principle also means that a reviewer can identify an inferential
mismatch without necessarily prescribing one particular replacement
analysis.

------------------------------------------------------------------------

#### What about intervention and control groups measured before and after treatment?

Consider a study in which an intervention group and a control group are
measured before and after an intervention.

Suppose:

-   the intervention group shows a statistically significant pre-to-post
    change;
-   the control group does not show a statistically significant
    pre-to-post change.

This does **not**, by itself, establish that the intervention caused a
different change from the control condition.

The separate within-group tests ask questions about change within each
group. If the scientific question concerns whether change differs
**between groups**, that between-group contrast must itself be
addressed.

Depending on the design and estimand, an appropriate analysis might
represent this contrast through a treatment-by-time interaction, a
between-group comparison of change, an adjusted post-intervention
comparison, or another design-appropriate model.

No single one of these methods is automatically correct merely because
measurements were obtained before and after treatment.

Reviewers should therefore first ask:

1.  What treatment effect or other estimand is the study attempting to
    estimate?
2.  Does the statistical analysis estimate that quantity?
3.  Does the comparison preserve the randomisation or other design
    structure?
4.  Does the model appropriately represent repeated measurements or
    other dependence?
5.  Are causal conclusions justified by the design and assumptions?

Detailed guidance on repeated observations and analytical structure is
provided in **Repeated Measures, Clustering and the Unit of Analysis**.
Guidance on baseline adjustment in randomised trials is provided in
**Baseline Balance and Covariate Adjustment in Randomised Trials**.

------------------------------------------------------------------------

#### Does statistical evidence establish practical importance?

No.

A small *p*-value does not indicate that an effect is large or
important.

With a sufficiently precise estimate, a very small effect can produce a
small *p*-value. Conversely, an effect that would be scientifically or
clinically important can remain statistically uncertain when information
is limited.

Reviewers should distinguish:

-   **effect magnitude**;
-   **uncertainty or precision**;
-   **statistical evidence**;
-   **scientific, clinical or practical importance**;
-   **a decision based on that evidence**.

Where practical importance matters, conclusions should be based on the
estimated magnitude and uncertainty relative to substantively meaningful
values, not merely on whether a null hypothesis was rejected.

Detailed guidance is provided in **Effect Sizes, Standardised Mean
Differences and Practical Importance**.

------------------------------------------------------------------------

#### What about non-significant results, equivalence and evidence of absence?

Failure to reject a null hypothesis does not ordinarily establish that
the null hypothesis is true.

Similarly, a non-significant test of a difference does not establish
that two effects are equivalent.

If the scientific claim concerns whether an effect is sufficiently small
to be considered negligible, or whether two treatments are sufficiently
similar for a specified purpose, the analysis should address that
question directly.

Depending on the question, appropriate approaches may include:

-   equivalence testing;
-   non-inferiority testing;
-   confidence intervals interpreted relative to a prespecified
    meaningful margin;
-   Bayesian approaches that quantify evidence or posterior probability
    for a practically negligible region.

The relevant margin or threshold should be scientifically justified
rather than selected after inspecting the result.

Detailed guidance is provided in **Interpreting p-values and
Non-significant Results** and **Bayesian Decision Rules and Posterior
Interpretation**.

------------------------------------------------------------------------

#### Common problematic claims

##### "The intervention group improved significantly but the control group did not, so the intervention worked."

Not established by those tests alone.

The separate within-group tests do not directly test whether the groups
changed differently.

##### "The association was significant in men but not women, so the association is stronger in men."

Not necessarily.

A direct comparison of the relevant effects is required.

##### "Study A found a significant effect but Study B did not, so the studies contradict each other."

Not necessarily.

The estimates and their uncertainty should be compared directly.
Different significance classifications can arise even when the estimated
effects are compatible.

##### "*p* = 0.049 demonstrates an effect, whereas *p* = 0.051 demonstrates no effect."

Incorrect.

The threshold creates a decision boundary; it does not create a
corresponding discontinuity in the underlying statistical evidence.

##### "*p* = 0.03 means there is a 97% probability that the effect is real."

Incorrect.

A frequentist *p*-value does not provide the posterior probability that
the null or alternative hypothesis is true.

##### "The result is statistically significant, therefore the effect is important."

Incorrect.

Statistical significance does not measure effect magnitude or practical
importance.

##### "The result was non-significant, therefore the treatments are equivalent."

Incorrect.

Failure to reject a difference is not equivalent to demonstrating that
any difference is sufficiently small to be practically unimportant.

##### "The analysis used p \< 0.05, therefore the Type I error rate of the entire study is 5%."

Not necessarily.

That interpretation depends on the testing procedure, number and
structure of hypotheses, multiplicity, selective analysis and other
features of the analysis process.

------------------------------------------------------------------------

#### Common terminology

**Null hypothesis (H₀)** -- the statistical hypothesis being tested,
often specifying a particular parameter value or relationship.

**Alternative hypothesis (H₁)** -- an alternative statistical hypothesis
considered in relation to the null hypothesis.

**Test statistic** -- a quantity calculated from the data whose
distribution under the specified statistical model is used to construct
a hypothesis test.

***p*-value** -- a probability calculated under a specified statistical
model that describes the extremeness of the observed test statistic
relative to its reference distribution.

**Significance level (α)** -- a prespecified threshold used in a
hypothesis-testing decision procedure and associated with control of
Type I error under the conditions of that procedure.

**Type I error** -- rejecting the null hypothesis when it is true within
the specified testing framework.

**Type II error** -- failing to reject the null hypothesis under an
alternative for which the testing procedure is intended to have power.

**Power** -- the probability that a testing procedure rejects the null
hypothesis under a specified alternative.

**Contrast** -- a comparison or combination of model parameters or
estimated quantities corresponding to a particular inferential question.

**Estimand** -- the quantity that the analysis is intended to estimate
for the scientific question of interest.

**Interaction** -- a model term or contrast representing how an
association or effect differs according to another variable; its precise
interpretation depends on the model and scale.

**Statistical significance** -- classification of a statistical result
relative to a specified significance threshold; it does not by itself
indicate effect magnitude or practical importance.

------------------------------------------------------------------------

#### Common reviewer red flags

-   The scientific claim concerns a comparison that was not directly
    estimated or tested.
-   One subgroup is described as different from another solely because
    one result is significant and the other is not.
-   Separate within-group tests are used to claim an intervention effect
    relative to a control condition.
-   A *p*-value is interpreted as the probability that the null
    hypothesis is true.
-   A *p*-value is interpreted as the probability that a result occurred
    by chance.
-   Statistical significance is interpreted as evidence that an effect
    is large or important.
-   *p*-values immediately above and below 0.05 are described as
    qualitatively different evidence.
-   A non-significant result is interpreted as proof of no effect or
    equivalence.
-   α = 0.05 is presented as a natural or universally correct scientific
    boundary.
-   The significance threshold appears to have been selected after
    examining the results.
-   Exact *p*-values are described as graded evidence in one part of the
    manuscript while threshold-based decisions are given a different
    inferential meaning elsewhere without explanation.
-   Type I or Type II error language is used without identifying the
    testing procedure to which those error rates apply.
-   An interaction, subgroup comparison or repeated-measures analysis is
    interpreted causally without adequate design or causal
    justification.
-   A statistical procedure is technically correct but tests a different
    quantity from the one required by the substantive conclusion.

------------------------------------------------------------------------

#### Quick reviewer checklist

□ What scientific quantity or comparison does the conclusion concern?

□ What hypothesis or contrast was actually tested?

□ Does the statistical test address the quantity required by the
scientific claim?

□ Is the *p*-value interpreted conditionally on the specified
statistical model rather than as a probability that a hypothesis is
true?

□ Is statistical evidence being treated continuously where appropriate
rather than reduced unnecessarily to significant/non-significant labels?

□ If α is being used as a formal decision threshold, was it prespecified
and is its role clear?

□ Are separate tests being incorrectly treated as a direct test of the
difference between their corresponding effects?

□ If the claim concerns a difference between effects, was that contrast
itself estimated or tested?

□ Does the chosen analysis match the study design, estimand and
dependence structure?

□ Are effect magnitude and uncertainty reported alongside statistical
evidence?

□ Is practical importance distinguished from statistical significance?

□ Are claims of equivalence or absence supported by methods designed to
address those claims?

□ Are causal conclusions supported by the study design and assumptions
rather than by statistical significance alone?

□ Does the final scientific conclusion follow from the statistical
quantity that was actually analysed?

------------------------------------------------------------------------

#### References

Checked sources for this topic. A section with its own list shows that
list instead. Each entry says what it supports; a source is listed for
that purpose only, not as support for every sentence in the note.

```references
- cite: Wasserstein, R. L., & Lazar, N. A. (2016). The ASA statement on p-values: Context, process, and purpose. The American Statistician, 70(2), 129--133.
  doi: 10.1080/00031305.2016.1154108
  supports: What p-values do and do not measure, and why scientific conclusions should not depend only on whether a threshold is crossed.
  short: ASA guidance on interpreting p-values
  type: Journal article
  access: open
  checked: 2026-10-03
  access_checked: 2026-10-03
- cite: Greenland, S., Senn, S. J., Rothman, K. J., Carlin, J. B., Poole, C., Goodman, S. N., & Altman, D. G. (2016). Statistical tests, P values, confidence intervals, and power: A guide to misinterpretations. European Journal of Epidemiology, 31(4), 337--350.
  doi: 10.1007/s10654-016-0149-3
  supports: Interpretation of statistical tests and p-values in relation to models and assumptions, and common inferential misinterpretations.
  short: common misinterpretations of statistical tests and p-values
  type: Journal article
  access: open
  checked: 2026-10-03
  access_checked: 2026-10-03
- cite: Gelman, A., & Stern, H. (2006). The difference between "significant" and "not significant" is not itself statistically significant. The American Statistician, 60(4), 328--331.
  doi: 10.1198/000313006X152649
  supports: Why different significance classifications from separate tests do not establish that the corresponding effects differ.
  short: why significant versus non-significant does not establish a difference
  type: Journal article
  checked: 2026-10-03
- cite: Lakens, D., Adolfi, F. G., Albers, C. J., et al. (2018). Justify your alpha. Nature Human Behaviour, 2(3), 168--171.
  doi: 10.1038/s41562-018-0311-x
  supports: The case for explicitly choosing and justifying alpha rather than automatically defaulting to 0.05.
  short: justifying alpha
  type: Journal article
  access: repository
  checked: 2026-10-03
  access_url: https://www.repository.cam.ac.uk/handle/1810/286595
  access_checked: 2026-10-03
- cite: Pernet, C. R. (2017). Null hypothesis significance testing: A guide to commonly misunderstood concepts and recommendations for good practice. F1000Research, 4, 621.
  doi: 10.12688/f1000research.6963.5
  supports: The conceptual distinction between Fisherian significance testing and Neyman--Pearson hypothesis testing, and the combination of elements from these traditions in contemporary NHST practice.
  short: Fisher, Neyman--Pearson and contemporary NHST
  type: Journal article
  access: open
  checked: 2026-10-03
  access_checked: 2026-10-03
```

------------------------------------------------------------------------

*This note is original work by Tony Myers. It summarises and restates
methodological guidance from the sources above; it does not reproduce
them.*
