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

##### Does a 95% credible interval excluding zero mean statistical significance?

A 95% credible interval excluding zero indicates that zero lies outside the reported posterior interval.

Authors may describe this as evidence that the parameter is likely to have a particular sign, but treating it automatically as "statistically significant" imports a frequentist-style threshold into Bayesian inference.

Bayesian analyses can usually report the evidence more directly.

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

##### What is Bayesian decision theory?

Bayesian decision theory combines:

- posterior uncertainty;
- available actions;
- utilities or losses associated with possible outcomes.

The optimal decision minimises expected loss or maximises expected utility.

A posterior probability alone does not determine a decision unless the consequences of different actions are also specified.

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

---

*Based on:* Kruschke, J. K. (2021), https://doi.org/10.1038/s41562-021-01177-7; and general Bayesian decision-theory literature. See also the notes on effect sizes and on reviewing Bayesian studies after Lee and Yin.
