# Bayesian Computation, Convergence and Diagnostics

#### Purpose

This guide helps reviewers evaluate Bayesian computation, Markov chain Monte Carlo (MCMC) convergence, Hamiltonian Monte Carlo (HMC) diagnostics and computational reproducibility. It focuses on whether posterior estimates are likely to be reliable and whether the computational methods have been reported transparently.

##### What reviewers should look for

✓ The manuscript reports the Bayesian software, package and version (e.g., Stan, brms, CmdStanR, JAGS or PyMC).

✓ The manuscript reports sufficient computational details, including the number of chains, warm-up (burn-in), sampling iterations, thinning (if used), random seed and sampler settings where appropriate.

✓ The manuscript reports convergence diagnostics such as R-hat (potential scale reduction factor, PSRF), effective sample size (ESS), trace plots or equivalent diagnostics.

✓ Hamiltonian Monte Carlo (HMC) diagnostics, including divergent transitions, maximum tree depth and Bayesian Fraction of Missing Information (BFMI), are reported where Stan or NUTS is used.

✓ Posterior summaries are based on adequately converged Markov chains.

#### Common reviewer questions

##### What is Markov chain Monte Carlo (MCMC)?

**Markov chain Monte Carlo (MCMC)** is a computational method that generates samples from the posterior distribution when direct calculation is difficult or impossible. Posterior estimates are reliable only if the Markov chains have converged and mixed well.

##### What is Hamiltonian Monte Carlo (HMC)?

**Hamiltonian Monte Carlo (HMC)** is an efficient MCMC algorithm that uses gradient information to explore the posterior distribution more efficiently than traditional random-walk samplers.

Many Bayesian analyses using **Stan** or **brms** employ HMC through the **No-U-Turn Sampler (NUTS)**.

##### What is NUTS?

**NUTS (No-U-Turn Sampler)** is an adaptive version of Hamiltonian Monte Carlo that automatically selects an appropriate trajectory length during sampling. NUTS is the default sampler used by Stan.

##### What is R-hat?

**R-hat (potential scale reduction factor, PSRF)** compares variation within Markov chains to variation between chains.

Typical interpretation:

- R-hat ≈ 1.00 → good convergence
- R-hat ≤ 1.01 → generally considered acceptable
- Larger values suggest incomplete convergence

Reviewers should expect R-hat values close to 1.00 for all important parameters.

##### What is Effective Sample Size (ESS)?

**Effective Sample Size (ESS)** estimates how many independent samples are represented by the correlated MCMC draws.

Because MCMC samples are autocorrelated, the effective sample size is usually smaller than the total number of iterations.

Larger ESS generally produces more stable posterior summaries.

Many software packages report:

- Bulk ESS (accuracy of posterior means and medians)
- Tail ESS (accuracy of credible interval tails)

##### What are trace plots?

**Trace plots** display sampled parameter values against iteration number.

Well-converged chains should show:

- good mixing
- stable behaviour
- no long-term trends
- substantial overlap between chains

Poor mixing or drifting chains may indicate lack of convergence.

##### What is autocorrelation?

**Autocorrelation** measures similarity between successive MCMC samples.

High autocorrelation reduces the effective sample size and increases Monte Carlo error.

Modern HMC algorithms usually exhibit lower autocorrelation than older Gibbs or Metropolis samplers.

##### What is Monte Carlo Standard Error (MCSE)?

**Monte Carlo Standard Error (MCSE)** estimates uncertainty arising from finite MCMC sampling rather than statistical uncertainty in the model itself.

Small MCSE indicates that posterior summaries have been estimated precisely.

##### What are divergent transitions?

A **divergent transition** occurs when Hamiltonian Monte Carlo cannot accurately follow the posterior geometry.

Divergent transitions suggest that posterior summaries may be unreliable.

Common causes include:

- poorly scaled parameters
- difficult posterior geometry
- inadequate parameterisation

Reviewers should expect authors either to eliminate divergent transitions or explain their impact.

##### What is maximum tree depth?

**Maximum tree depth** limits how far NUTS explores each trajectory.

Repeated tree-depth warnings may indicate inefficient sampling or a difficult posterior geometry.

Increasing tree depth alone does not necessarily solve the underlying modelling problem.

##### What is BFMI?

**Bayesian Fraction of Missing Information (BFMI)** measures how efficiently Hamiltonian Monte Carlo explores the posterior energy distribution.

Low BFMI suggests inefficient exploration and possible sampling problems.

BFMI should be considered together with divergent transitions and other HMC diagnostics rather than interpreted in isolation.

##### What is DIC?

**DIC (Deviance Information Criterion)** is an older Bayesian model comparison criterion that combines model fit with a penalty for model complexity.

Like WAIC and LOOIC, **smaller DIC values indicate a better trade-off between fit and complexity because DIC is reported on a deviance scale.**

DIC remains widely reported in Bayesian network meta-analysis and disease-modelling software, including WinBUGS, OpenBUGS, JAGS, `gemtc` and `MBNMAdose`.

However, reviewers should recognise its limitations:

- DIC is not invariant to parameterisation.
- DIC may perform poorly for hierarchical, mixture or weakly identified models.
- DIC uses an asymptotic approximation and may underestimate predictive uncertainty.

Where available, **PSIS-LOO and WAIC are generally preferred because they estimate out-of-sample predictive performance more directly and provide additional diagnostics.**

#### Common misconceptions

##### "The model converged because the software finished."

Incorrect.

Successful completion of MCMC sampling does not guarantee convergence.

##### "R-hat = 1 proves convergence."

Incorrect.

R-hat close to 1 is reassuring but should be interpreted together with ESS, trace plots and other diagnostics.

---

##### "A very large number of iterations guarantees convergence."

Incorrect.

Longer chains cannot compensate for poor model specification or pathological posterior geometry.

---

##### "No divergent transitions means the model is perfect."

Incorrect.

Absence of divergent transitions is reassuring but does not guarantee that the model is correctly specified.

---

##### "Thinning improves inference."

Usually incorrect.

Modern Bayesian software rarely requires thinning, as increasing the number of posterior draws is generally preferable unless storage limitations are important.

---

#### Common terminology

**MCMC (Markov chain Monte Carlo)** generates samples from the posterior distribution.

**HMC (Hamiltonian Monte Carlo)** uses gradients to improve sampling efficiency.

**NUTS (No-U-Turn Sampler)** automatically adapts HMC trajectory length.

**R-hat (Potential Scale Reduction Factor; PSRF)** assesses agreement between Markov chains.

**ESS (Effective Sample Size)** estimates the number of effectively independent posterior samples.

**Bulk ESS** assesses precision of posterior location estimates.

**Tail ESS** assesses precision of posterior tail probabilities and credible intervals.

**MCSE (Monte Carlo Standard Error)** measures simulation error due to finite MCMC sampling.

**BFMI (Bayesian Fraction of Missing Information)** assesses whether HMC efficiently explores posterior energy.

**Trace plot** visualises sampling behaviour across iterations.

**Divergent transition** indicates numerical difficulties during Hamiltonian Monte Carlo sampling.



---

#### Common reviewer red flags

- Software or package versions not reported.
- Number of chains or iterations omitted.
- R-hat not reported.
- Effective sample size (ESS) not reported.
- Trace plots unavailable when convergence is uncertain.
- Divergent transitions ignored.
- Tree-depth warnings ignored.
- BFMI warnings ignored.
- Convergence stated without supporting diagnostics.
- Computational settings insufficient for reproduction.

---

#### Quick reviewer checklist

□ Software, package and version are reported.

□ Number of chains, warm-up, iterations and random seed are reported.

□ R-hat (PSRF) values indicate adequate convergence.

□ Effective sample size (ESS) is adequate for key parameters.

□ Trace plots show good mixing.

□ Divergent transitions are absent or appropriately addressed.

□ Maximum tree depth warnings are investigated.

□ BFMI is acceptable when using Stan or HMC.

□ Posterior summaries appear based on well-converged Markov chains.

□ Computational methods are reproducible.

---

*Based on:* Kruschke, J. K. (2021), https://doi.org/10.1038/s41562-021-01177-7; van Doorn, J., et al. (2021). The JASP guidelines for conducting and reporting a Bayesian analysis. *Psychonomic Bulletin & Review*, 28, 813-826. https://doi.org/10.3758/s13423-020-01798-5

*This note is original work by Tony Myers. It summarises and restates guidance from the sources above; it does not reproduce them.*
