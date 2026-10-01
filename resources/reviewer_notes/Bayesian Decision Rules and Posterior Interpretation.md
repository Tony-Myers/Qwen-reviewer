# Bayesian Decision Rules and Posterior Interpretation

#### Purpose

This guide helps reviewers evaluate Bayesian decision rules and interpretation of posterior uncertainty. It focuses on posterior probabilities, credible intervals, decision thresholds, clinically meaningful effects, regions of practical equivalence (ROPE), predictive probabilities, and why simply checking whether a credible interval crosses zero is an incomplete Bayesian analysis.

#### What reviewers should look for

✓ Bayesian results are interpreted using posterior probabilities and effect magnitudes rather than only a binary zero-crossing rule.

✓ Any formal decision threshold is prespecified and scientifically justified.

✓ Clinically or practically meaningful thresholds are distinguished from the mathematical null value of zero.

✓ Credible intervals are interpreted as posterior intervals, not as frequentist confidence intervals.

✓ Decisions incorporate costs, benefits or utilities where the scientific problem requires them.

#### Common reviewer questions

##### What does it mean if a 95% credible interval excludes zero?

A 95% credible interval excluding zero indicates that zero lies outside the reported posterior interval. It does **not** by itself give the posterior probability that the parameter is exactly zero, nor should interval exclusion be mechanically translated into a probability that the effect is positive or negative.

For a parameter with a continuous posterior distribution, the posterior probability of any exact point, including exactly zero, is ordinarily zero whether or not that point lies inside the credible interval. A non-zero posterior probability for an exact point null requires a model that assigns discrete probability mass to that point, or an explicit comparison between models or hypotheses that includes the point null.

If the scientific question concerns the direction of an effect, the relevant posterior probability should be calculated directly, for example **P(effect > 0 | data)** or **P(effect < 0 | data)**. The relationship between such directional probabilities and a 95% credible interval depends on how the interval is constructed and on the posterior distribution.

Authors may describe exclusion of zero as evidence about the likely direction of an effect, but treating it automatically as "statistically significant" imports a frequentist-style threshold into Bayesian inference.

Bayesian analyses can usually report the evidence more directly.

##### Are all 95% credible intervals the same?

No. A 95% credible interval describes an interval containing 95% of the posterior probability, but different rules can be used to construct that interval.

An **equal-tailed interval (ETI)** leaves equal posterior probability in each tail. For a 95% ETI, 2.5% of the posterior probability lies below the lower bound and 2.5% lies above the upper bound.

A **highest-density region (HDR)** contains the specified posterior probability while including values of higher posterior density in preference to values of lower density. An HDR may be disconnected. When the relevant highest-density region is a single interval, it is commonly described as a **highest-density interval (HDI or HPDI)**.

For a continuous posterior where the highest-density region forms a single interval, that HDI is a minimum-width credible interval for the specified probability content. It therefore cannot be wider than an ETI containing the same posterior probability, because the ETI is one candidate interval with that probability content. This minimum-width property should not be extended uncritically to a single contiguous "HDI" when the highest-density region is disconnected or otherwise irregular.

ETIs and HDIs coincide in common symmetric unimodal cases; for skewed unimodal posteriors their endpoints generally differ and the minimum-width HDI may be narrower. Interval width alone does not make one construction more precise, more credible, or scientifically preferable. Reviewers should therefore identify which interval or region has been reported and interpret it according to its construction rather than assuming that a "95% credible interval" is a **central 95% interval**.

For multimodal or otherwise irregular posterior distributions, a highest-density **region** can be disconnected and may not be well represented by a single contiguous interval. Reviewers should consider the posterior distribution itself where a single interval could obscure important features.

When the scientific question concerns the probability that an effect is positive, negative, or exceeds a meaningful threshold, that posterior probability should generally be calculated directly rather than inferred from the endpoints of a credible interval.

Reviewers should be cautious of several common overstatements:

- distinguish a highest-density **region**, which may be disconnected, from a contiguous highest-density **interval**;
- do not assume that an arbitrary contiguous interval around a mode inherits the minimum-width property of a highest-density region;
- do not generalise the minimum-width HDI relationship to cases where the highest-density region is disconnected or otherwise irregular;
- a narrower interval is not automatically more precise, more credible or preferable;
- an ETI should not be described as analogous to a frequentist confidence interval merely because both may use quantile-based endpoints.

```references
- cite: Hyndman, R. J. (1996). Computing and graphing highest density regions. The American Statistician, 50(2), 120–126.
  doi: 10.1080/00031305.1996.10474359
  supports: Definition and computation of highest density regions, including regions that are not a single interval.
  short: highest-density regions, including disconnected regions
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-09-30, Crossref
- cite: Kruschke, J. K. (2015). Doing Bayesian data analysis: A tutorial with R, JAGS, and Stan (2nd ed.). Academic Press.
  isbn: 9780124058880
  url: https://www.sciencedirect.com/book/9780124058880/doing-bayesian-data-analysis
  supports: Textbook treatment of the highest density interval and its use to summarise a posterior.
  short: textbook treatment of HDIs and posterior summaries
  type: Book
  checked: 2026-09-30, publisher record (no DOI confirmed)
- cite: Makowski, D., Ben-Shachar, M. S., & Lüdecke, D. (2019). bayestestR: Describing effects and their uncertainty, existence and significance within the Bayesian framework. Journal of Open Source Software, 4(40), 1541.
  doi: 10.21105/joss.01541
  supports: Software implementing the HDI, ETI, ROPE and probability of direction for summarising posteriors.
  short: practical posterior summaries including HDI, ETI and ROPE
  type: Software paper
  access: open
  access_checked: 2026-10-01, OpenAlex: open (diamond, CC BY)
  checked: 2026-09-30, Crossref
- cite: bayestestR documentation. Credible Intervals (CI). easystats.
  url: https://easystats.github.io/bayestestR/articles/credible_interval.html
  supports: Practical comparison of HDI and ETI, including that the ETI is unchanged by monotone transformations while the HDI is not. Documentation, not peer reviewed.
  short: practical ETI/HDI comparison, including behaviour under transformations
  type: Documentation
  access: open
  access_checked: 2026-09-30, page read directly
  checked: 2026-09-30, page read
```

##### What should be reported instead of only whether the interval crosses zero?

Useful summaries include:

- **P(effect > 0 | data)**;
- **P(effect < 0 | data)**;
- probability that the effect exceeds a minimally important threshold;
- probability that the effect is clinically beneficial;
- probability that the effect lies within a ROPE;
- posterior expected utility or loss.

These summaries make the decision-relevant quantity explicit.

##### Is a high P(effect > 0 | data) enough on its own?

Not usually.

The probability that an effect has a particular sign says nothing about its size. A posterior can place 99% of its mass above zero and almost all of that mass on effects too small to matter.

Where the question is whether an effect is large enough to act on, the informative quantity is the probability that it exceeds a meaningful threshold, not the probability that it exceeds zero.

##### What if the credible interval includes zero?

A credible interval containing zero does **not** mean there is no effect.

The posterior may still assign substantial probability to benefit or harm.

For example, a posterior could assign 90% probability to a beneficial effect while its 95% credible interval still includes zero.

##### Why is zero often a poor decision threshold?

Zero represents exactly no effect.

Scientific or clinical decisions often concern whether an effect is large enough to matter.

A meaningful threshold might instead represent:

- a minimally important difference;
- clinically important benefit;
- clinically important harm;
- acceptable non-inferiority margin.

##### What is a ROPE?

A **Region of Practical Equivalence (ROPE)** is a prespecified range of parameter values regarded as practically negligible.

For example, effects between −δ and +δ might be treated as scientifically trivial.

The ROPE must be justified substantively rather than selected after inspecting the posterior.

```references
- cite: Kruschke, J. K. (2018). Rejecting or accepting parameter values in Bayesian estimation. Advances in Methods and Practices in Psychological Science, 1(2), 270–280.
  doi: 10.1177/2515245918771304
  supports: Decision rules combining the HDI with a region of practical equivalence, and how a ROPE can be set.
  short: HDI and ROPE decision rules, and setting a ROPE
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read)
  checked: 2026-09-30, Crossref
- cite: Makowski, D., Ben-Shachar, M. S., & Lüdecke, D. (2019). bayestestR: Describing effects and their uncertainty, existence and significance within the Bayesian framework. Journal of Open Source Software, 4(40), 1541.
  doi: 10.21105/joss.01541
  supports: Software implementing the HDI, ETI, ROPE and probability of direction for summarising posteriors.
  short: practical posterior summaries including HDI, ETI and ROPE
  type: Software paper
  access: open
  access_checked: 2026-10-01, OpenAlex: open (diamond, CC BY)
  checked: 2026-09-30, Crossref
```

##### What is a posterior probability threshold?

A decision rule may require a probability such as:

- P(effect > 0 | data) > 0.95;
- P(effect > clinically important threshold | data) > 0.90.

There is no universal Bayesian analogue of *p* < 0.05.

The probability threshold should reflect the costs of false positive and false negative decisions and ideally be prespecified.

##### What is predictive probability?

**Posterior predictive probability** concerns future observations or future trial outcomes rather than uncertainty only about a model parameter.

It is often useful for:

- interim monitoring;
- futility decisions;
- probability of eventual trial success;
- planning future research.

```references
- cite: Spiegelhalter, D. J., Abrams, K. R., & Myles, J. P. (2003). Bayesian approaches to clinical trials and health-care evaluation. Wiley.
  doi: 10.1002/0470092602
  supports: Bayesian methods for trials, including clinically important thresholds, predictive probabilities and interim monitoring.
  short: Bayesian trial methods, clinical thresholds and predictive probability
  type: Book
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-09-30, Crossref
```

##### What is Bayesian decision theory?

Bayesian decision theory combines:

- posterior uncertainty;
- available actions;
- utilities or losses associated with possible outcomes.

The optimal decision minimises expected loss or maximises expected utility.

A posterior probability alone does not determine a decision unless the consequences of different actions are also specified.

```references
- cite: Berger, J. O. (1985). Statistical decision theory and Bayesian analysis (2nd ed.). Springer.
  doi: 10.1007/978-1-4757-4286-2
  supports: Formal Bayesian decision theory: losses, utilities, and choosing an action by expected loss.
  short: formal Bayesian decision theory
  type: Book
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-09-30, Crossref
- cite: Gelman, A., Carlin, J. B., Stern, H. S., Dunson, D. B., Vehtari, A., & Rubin, D. B. (2013). Bayesian data analysis (3rd ed.). Chapman and Hall/CRC.
  doi: 10.1201/b16018
  supports: Standard reference for posterior summaries, posterior intervals and Bayesian decision analysis.
  short: standard reference on posterior summaries, intervals and decision analysis
  type: Book
  access: author-copy
  access_url: https://sites.stat.columbia.edu/gelman/book/BDA3.pdf
  access_checked: 2026-10-01, authors' book page read: PDF for non-commercial use; not in OpenAlex
  checked: 2026-09-30, Crossref
```

#### Common misconceptions

##### "A 95% credible interval excluding zero is the Bayesian version of p < 0.05."

Not exactly.

Both can produce similar binary classifications under some models, but they arise from different inferential frameworks and support different probability statements.

##### "A credible interval containing zero means there is no evidence."

Incorrect.

The full posterior distribution may still strongly favour one direction.

##### "95% is the correct Bayesian decision threshold."

Incorrect.

Bayesian decision thresholds depend on the decision context.

##### "Bayesian inference eliminates the need for decision rules."

Incorrect.

When an analysis is intended to support an action, the rule linking posterior evidence to that action should be explicit.

#### Common terminology

**Posterior probability** – probability assigned to an event or parameter region conditional on the model, prior and observed data.

**Credible interval (CrI)** – interval containing a specified proportion of posterior probability.

**Decision threshold** – prespecified criterion linking posterior evidence to an action.

**ROPE (Region of Practical Equivalence)** – range of effects considered practically negligible.

**Minimally Important Difference (MID)** – smallest effect considered substantively important; see the note on effect sizes for how such thresholds are established.

**Posterior predictive probability** – probability concerning future data conditional on observed evidence.

**Utility** – numerical representation of benefit associated with an outcome or decision.

**Loss function** – numerical representation of the cost of an incorrect or undesirable decision.

#### Common reviewer red flags

- Credible interval used only as a zero-crossing significance test.
- "Statistically significant" used without defining the Bayesian decision criterion.
- Posterior probability of benefit omitted despite being straightforward to report.
- Zero treated as the only scientifically meaningful threshold.
- Decision threshold selected after looking at the data.
- ROPE or clinically meaningful threshold not justified.
- Posterior probability interpreted without acknowledging the model and prior.

#### Quick reviewer checklist

□ Posterior probabilities are reported where they answer the scientific question directly.

□ Credible intervals are interpreted appropriately.

□ Zero-crossing is not the sole Bayesian decision rule.

□ Clinically or practically meaningful thresholds are considered.

□ Probability or utility thresholds are prespecified where formal decisions are made.

□ Conclusions distinguish posterior evidence from the decision rule applied to that evidence.

#### References

Checked sources for this topic. A section with its own list shows that list instead. Each entry says what it supports; a source is listed for that purpose only, not as support for every sentence in the note.

```references
- cite: Kruschke, J. K. (2021). Bayesian analysis reporting guidelines. Nature Human Behaviour, 5(10), 1282–1291.
  doi: 10.1038/s41562-021-01177-7
  supports: Reporting guidelines for Bayesian analyses, including posterior summaries, credible intervals and decision criteria.
  short: reporting guidelines for Bayesian analyses
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (hybrid, CC BY)
  checked: 2026-09-30, Crossref
- cite: Kruschke, J. K., & Liddell, T. M. (2018). The Bayesian New Statistics: Hypothesis testing, estimation, meta-analysis, and power analysis from a Bayesian perspective. Psychonomic Bulletin & Review, 25(1), 178–206.
  doi: 10.3758/s13423-016-1221-4
  supports: Bayesian estimation compared with hypothesis testing, including credible intervals, ROPE-based decisions and Bayesian power analysis.
  short: Bayesian estimation versus hypothesis testing, ROPEs and power
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read)
  checked: 2026-09-30, Crossref
- cite: Gelman, A., Carlin, J. B., Stern, H. S., Dunson, D. B., Vehtari, A., & Rubin, D. B. (2013). Bayesian data analysis (3rd ed.). Chapman and Hall/CRC.
  doi: 10.1201/b16018
  supports: Standard reference for posterior summaries, posterior intervals and Bayesian decision analysis.
  short: standard reference on posterior summaries, intervals and decision analysis
  type: Book
  access: author-copy
  access_url: https://sites.stat.columbia.edu/gelman/book/BDA3.pdf
  access_checked: 2026-10-01, authors' book page read: PDF for non-commercial use; not in OpenAlex
  checked: 2026-09-30, Crossref
- cite: Berger, J. O. (1985). Statistical decision theory and Bayesian analysis (2nd ed.). Springer.
  doi: 10.1007/978-1-4757-4286-2
  supports: Formal Bayesian decision theory: losses, utilities, and choosing an action by expected loss.
  short: formal Bayesian decision theory
  type: Book
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-09-30, Crossref
- cite: Spiegelhalter, D. J., Abrams, K. R., & Myles, J. P. (2003). Bayesian approaches to clinical trials and health-care evaluation. Wiley.
  doi: 10.1002/0470092602
  supports: Bayesian methods for trials, including clinically important thresholds, predictive probabilities and interim monitoring.
  short: Bayesian trial methods, clinical thresholds and predictive probability
  type: Book
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-09-30, Crossref
```

---

*Based on:* Kruschke, J. K. (2021), https://doi.org/10.1038/s41562-021-01177-7; and general Bayesian decision-theory literature. See also the notes on effect sizes and on reviewing Bayesian studies after Lee and Yin.
