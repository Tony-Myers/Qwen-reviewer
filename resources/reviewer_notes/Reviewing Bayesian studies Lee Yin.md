# Reviewing Bayesian studies based on Lee & Yin (2021) **Principles and Reporting of Bayesian Trials**

#### Common Reviewer Misconceptions

Bayesian analyses are often criticised for reasons that reflect unfamiliarity with Bayesian inference rather than genuine methodological problems. The following issues should not automatically be considered weaknesses.

###### "Where are the p-values?"

Bayesian analyses do not require p-values.

Posterior probabilities, credible intervals, predictive probabilities, and Bayes factors are legitimate Bayesian measures of evidence and often answer the scientific question more directly than null-hypothesis significance tests.

###### **Reasonable reviewer question**

> Why were these Bayesian summaries chosen?

###### **Less appropriate criticism**

> The paper should report p-values instead.

---

###### "Where is the power calculation?"

Many Bayesian studies are designed using simulation rather than analytical power calculations.

Instead of conventional power, Bayesian designs often evaluate:

- probability of correctly declaring success
- false positive probability
- false negative probability
- expected sample size
- operating characteristics across plausible scenarios

The important question is whether these operating characteristics were evaluated—not whether a classical power calculation was presented.

---

###### "The prior is subjective."

Every Bayesian analysis requires assumptions.

Priors should certainly be questioned and justified, but subjectivity alone is not a flaw.

A reviewer should instead ask:

- Was the prior justified?
- Is it scientifically plausible?
- Was robustness demonstrated through sensitivity analysis?

Well-justified informative priors are often preferable to arbitrary vague priors.

---

###### "The credible interval is just a confidence interval."

These are different concepts.

A 95% credible interval means

> Given the model and prior, there is a 95% posterior probability that the parameter lies within the interval.

A 95% confidence interval **does not** have this interpretation.

Reviewers should ensure authors do not conflate the two.

---

###### "Bayesian methods remove the need to control false positives."

Incorrect.

Bayesian adaptive trials still require good operating characteristics.

Lee & Yin explicitly recommend reporting simulation studies showing properties such as Type I error and power, particularly for adaptive designs.

---

###### "Default priors are automatically inappropriate."

Not necessarily.

Using package defaults is acceptable provided:

- they are reported explicitly;
- they are scientifically reasonable;
- sensitivity analyses demonstrate that conclusions are robust.

The problem is **unreported defaults**, not necessarily default priors themselves.

---

#### What Makes a Bayesian Paper Convincing?

A convincing Bayesian analysis is characterised by transparency rather than complexity.

Look for:

✓ The manuscript clearly specifies the Bayesian statistical model, likelihood, regression model and any hierarchical or random-effects structure.

✓ The manuscript explicitly reports every prior distribution (prior specification) used in the analysis.

✓ The manuscript scientifically justifies each prior distribution and modelling choice.

✓ The manuscript evaluates robustness using sensitivity analyses with alternative prior distributions.

✓ The manuscript reports simulation-based operating characteristics such as Type I error, false-positive rate, power, bias, precision or expected sample size where appropriate.

✓ The manuscript reports software, package versions, MCMC settings and computational details sufficient for reproduction.

✓ The manuscript interprets posterior probabilities, credible intervals and predictive probabilities consistently with Bayesian inference.

More complicated models are not inherently better.

Good Bayesian analyses should demonstrate that the Markov chain Monte Carlo (MCMC) algorithm converged adequately.

Look for reporting of:

\- R-hat (potential scale reduction factor, PSRF)

\- effective sample size (ESS)

\- bulk ESS

\- tail ESS

\- trace plots

\- autocorrelation

\- Monte Carlo standard error (MCSE)

\- divergent transitions

\- maximum tree depth

\- BFMI (Bayesian Fraction of Missing Information), when using Stan

Typical reviewer expectation:

\- R-hat close to 1.00

\- no divergent transitions

\- adequate effective sample size

\- trace plots showing good mixing

Red flags

\- convergence not assessed

\- only "the model converged" stated without evidence

\- no diagnostics reported

---

###### Bayesian Reviewer Decision Tree

```
Is the model clearly described?
        │
        ├── No → Major concern
        │
        ▼
Are priors fully specified?
        │
        ├── No → Major concern
        │
        ▼
Are all prior distributions explicitly reported, scientifically justified and appropriate for the available prior information?
        │
        ├── No → Request clarification
        │
        ▼
Were sensitivity analyses performed?
        │
        ├── No → Usually major concern
        │
        ▼
Were convergence diagnostics reported (e.g., R-hat, potential scale reduction factor (PSRF), effective sample size (ESS), trace plots, divergent transitions or equivalent MCMC diagnostics)?
        │
        ├── No → Major concern
        │
        ▼
Were simulation-based operating characteristics (Type I error, false-positive rate, power, bias, precision or expected sample size) evaluated?
        │
        ├── No → Important concern
        │
        ▼
Are the scientific conclusions consistent with the reported posterior probabilities, credible intervals and prespecified decision thresholds?
        │
        ├── No → Major concern
        │
        ▼
Overall Bayesian reporting is likely adequate.
```

---



---

#### Common Bayesian Terminology

- Prior = prior distribution = prior specification
- Posterior = posterior distribution
- Credible interval = posterior interval
- R-hat = PSRF = potential scale reduction factor
- ESS = effective sample size (bulk ESS, tail ESS)
- Posterior predictive check = PPC
- LOO = leave-one-out cross-validation
- WAIC = Widely Applicable Information Criterion
- HMC = Hamiltonian Monte Carlo
- NUTS = No-U-Turn Sampler


###### Final Review Questions

Before recommending publication, ask yourself:

1. Could another statistician reproduce this Bayesian analysis?
2. Could I explain why these prior distributions or prior specifications were chosen?
3. Would the conclusions remain similar under reasonable alternative priors?
4. Are posterior probabilities, credible intervals and other Bayesian summaries interpreted correctly?
5. Have the authors demonstrated that the design behaves well (e.g., through simulation)?
6. Are the conclusions proportional to the strength of the evidence?
7. Does the manuscript explain *why* Bayesian methods were used rather than simply stating that they were?

---

*Based on:* Lee, J. J., & Yin, G. (2021). Principles and reporting of Bayesian trials.

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
