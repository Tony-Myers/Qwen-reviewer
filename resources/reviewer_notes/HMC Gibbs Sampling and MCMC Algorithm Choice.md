# HMC, Gibbs Sampling and MCMC Algorithm Choice

#### Purpose

This guide helps reviewers interpret the computational method used to obtain Bayesian posterior samples. It focuses on Hamiltonian Monte Carlo (HMC), the No-U-Turn Sampler (NUTS), Gibbs sampling and related Markov chain Monte Carlo (MCMC) methods. The aim is not to rank algorithms universally, but to identify what each method implies for convergence assessment and computational reliability.

#### What reviewers should look for

✓ The manuscript identifies the MCMC algorithm or software sufficiently clearly to understand how posterior sampling was performed.

✓ Convergence diagnostics are appropriate for the sampler being used.

✓ HMC/NUTS analyses report sampler-specific problems such as divergent transitions where relevant.

✓ Gibbs or Metropolis-based analyses assess mixing and autocorrelation rather than relying only on the number of iterations.

✓ Authors do not claim that one sampler is universally superior simply because it is newer or more computationally sophisticated.

#### Common reviewer questions

##### What is Gibbs sampling?

**Gibbs sampling** is an MCMC algorithm that repeatedly samples each parameter from its conditional posterior distribution given the current values of the other parameters.

It is widely used by software such as:

- BUGS;
- WinBUGS;
- OpenBUGS;
- JAGS.

Gibbs sampling can be highly effective when conditional distributions are easy to sample.

##### What are the weaknesses of Gibbs sampling?

Gibbs samplers may mix slowly when:

- parameters are strongly correlated;
- posterior geometry is difficult;
- hierarchical models are weakly identified;
- conditional updates move only short distances through the posterior.

Slow mixing leads to high autocorrelation and low effective sample size (ESS).

##### What is Hamiltonian Monte Carlo?

**Hamiltonian Monte Carlo (HMC)** uses gradient information to propose distant moves through continuous parameter space while maintaining high acceptance probability.

It can explore complex and high-dimensional posterior distributions more efficiently than random-walk MCMC methods.

##### What is NUTS?

The **No-U-Turn Sampler (NUTS)** is an adaptive form of HMC that automatically determines an appropriate trajectory length.

Stan and `brms` commonly use NUTS for posterior sampling.

##### Is HMC always better than Gibbs sampling?

No.

HMC often performs very well for high-dimensional continuous models, but no sampler is universally superior.

Gibbs sampling can be efficient when conditional distributions have convenient forms.

Algorithm suitability depends on:

- model structure;
- parameterisation;
- dimensionality;
- discrete versus continuous parameters;
- posterior geometry.

##### Why can Stan not directly sample discrete parameters using HMC?

HMC requires gradients of a continuous parameter space.

Discrete parameters do not have the required differentiable geometry.

Stan therefore generally marginalises discrete latent variables analytically when possible rather than sampling them directly.

Gibbs-based software can sometimes sample discrete parameters explicitly.

##### Do HMC and Gibbs require different diagnostics?

Some diagnostics apply broadly:

- R-hat / PSRF;
- effective sample size (ESS);
- trace plots;
- Monte Carlo standard error (MCSE).

R-hat is informative only when the chains begin from dispersed starting values. Chains started from the same or similar initial values can agree closely while all having failed to explore the posterior, and an R-hat near 1 then means very little. Reviewers should expect the initial values, or the method used to generate them, to be reported.

HMC/NUTS additionally requires attention to:

- divergent transitions;
- maximum tree depth;
- energy behaviour;
- Bayesian Fraction of Missing Information (BFMI).

For Gibbs and Metropolis algorithms, particularly important concerns include:

- autocorrelation;
- poor chain mixing;
- low ESS;
- chains becoming stuck in different regions;
- the convergence diagnostics associated with this tradition, such as Geweke, Heidelberger-Welch and Raftery-Lewis, where these are reported.

##### What does better computational efficiency mean?

Efficiency should be judged by the quality of effectively independent posterior draws obtained for the computational effort.

A sampler producing 100,000 highly autocorrelated draws may contain less useful information than one producing 5,000 well-mixed draws.

The **effective sample size**, not the raw number of MCMC iterations alone, is therefore important.

##### Can changing the sampler fix a bad model?

Not necessarily.

Computational problems may reflect:

- poor parameterisation;
- weak identification;
- pathological posterior geometry;
- inappropriate priors;
- model misspecification.

Changing algorithms without understanding the source of the problem may merely hide rather than solve it.

#### Common misconceptions

##### "HMC is simply a more accurate version of Gibbs sampling."

Incorrect.

They are different MCMC strategies with different computational strengths and limitations.

##### "More Gibbs iterations solve poor mixing."

Not necessarily.

Severe autocorrelation or poor exploration may persist even in very long chains.

##### "No divergences means an HMC model has converged."

Incorrect.

R-hat, ESS and other diagnostics remain important.

##### "Thinning the chain fixes autocorrelation."

Not really.

Thinning discards draws and usually lowers the effective sample size obtained for a given amount of computation. It can be justified to limit storage, but it is not a remedy for poor mixing.

##### "Gibbs sampling is obsolete."

Incorrect.

It remains useful and is still widely employed in Bayesian software and specialised model classes.

##### "The same number of iterations means the same computational quality across samplers."

Incorrect.

Autocorrelation and effective sample size can differ dramatically between algorithms.

#### Common terminology

**MCMC (Markov Chain Monte Carlo)** – family of algorithms used to generate samples from posterior distributions.

**Gibbs sampler** – MCMC algorithm using repeated draws from conditional posterior distributions.

**Metropolis-Hastings** – MCMC algorithm proposing parameter values and accepting or rejecting them according to an acceptance rule.

**HMC (Hamiltonian Monte Carlo)** – gradient-based MCMC algorithm for continuous parameters.

**NUTS (No-U-Turn Sampler)** – adaptive HMC algorithm used by Stan.

**Autocorrelation** – dependence between successive MCMC draws.

**ESS (Effective Sample Size)** – number of effectively independent draws represented by correlated MCMC output.

**Divergent transition** – HMC warning indicating difficulty accurately exploring posterior geometry.

**BFMI (Bayesian Fraction of Missing Information)** – HMC diagnostic concerning exploration of posterior energy.

#### Common reviewer red flags

- Sampler not identified.
- Gibbs or Metropolis analysis judged only by number of iterations.
- HMC divergences ignored.
- R-hat reported without ESS.
- Very high autocorrelation ignored.
- Sampler described as "better" without reference to the model.
- Computational warnings addressed only by increasing iterations.
- Raw iteration count confused with effective sample size.
- Initial values, or the method of generating them, not reported.
- Thinning presented as a solution to autocorrelation.

#### Quick reviewer checklist

□ The MCMC algorithm is identified.

□ Diagnostics match the sampler being used.

□ R-hat and ESS are reported.

□ Gibbs/Metropolis mixing and autocorrelation are assessed.

□ HMC/NUTS divergences and related diagnostics are examined.

□ Computational efficiency is judged using effective rather than raw sample size.

□ Sampler choice is appropriate for the model rather than treated as universally superior.

---

*Based on:* Gelman, A., & Rubin, D. B. (1992). Inference from iterative simulation using multiple sequences. *Statistical Science*, 7, 457-511; and general MCMC methodological literature. See also the note on Bayesian computation, convergence and diagnostics.
