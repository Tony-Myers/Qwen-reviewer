# Distribution Shape, Normality and Modality

## Purpose

This note supports critical review of claims about normality,
unimodality, multimodality, distributional shape, and the existence of
distinct subpopulations or clusters. These concepts are related but are
not interchangeable. Reviewers should check that the statistical method
used addresses the claim being made.

## Normality and unimodality are different concepts

A normal distribution is unimodal: it has a single mode. However, a test
of normality does not directly test whether a distribution is unimodal.

Normality tests, such as the Shapiro--Wilk test, assess evidence
concerning compatibility with a specified normal distribution. They do
not test a null hypothesis of unimodality against an alternative of
multimodality.

Consequently, a statement such as:

> "Normality tests indicated unimodal distributions."

is not justified by a normality test alone.

The direction of the distinction is important:

-   A normal distribution is unimodal.
-   A unimodal distribution does not have to be normal.
-   A non-normal distribution does not have to be multimodal.

For example, a distribution may be skewed or heavy-tailed while still
having only one mode.

```references
- cite: Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality (complete samples). Biometrika, 52(3–4), 591–611.
  doi: 10.1093/biomet/52.3-4.591
  supports: What a normality test such as Shapiro–Wilk tests: compatibility with a normal distribution, not unimodality.
  short: the Shapiro–Wilk test of normality
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
- cite: Hartigan, J. A., & Hartigan, P. M. (1985). The dip test of unimodality. The Annals of Statistics, 13(1), 70–84.
  doi: 10.1214/aos/1176346577
  supports: Unimodality as a separate hypothesis with a test designed for it.
  short: the dip test of unimodality
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, OpenAlex (title, volume and issue); authors and pages confirmed by hand by Tony Myers
```

## Failure to reject normality is not evidence that normality has been established

A non-significant normality test should not be interpreted as
demonstrating that the data are normally distributed. Failure to reject
a null hypothesis means that the available data do not provide
sufficient evidence against it; it does not establish the null
hypothesis as true.

This is particularly important with small samples, where normality tests
may have limited power to detect departures from normality.

Conversely, with large samples, normality tests may detect relatively
minor deviations from a normal distribution that have little practical
consequence for the analysis. Distributional assessment should therefore
consider the purpose of the analysis, graphical evidence, sample size,
and the robustness of the statistical method rather than relying
mechanically on a normality-test p-value.

```references
- cite: Altman, D. G., & Bland, J. M. (1995). Statistics notes: Absence of evidence is not evidence of absence. BMJ, 311(7003), 485.
  doi: 10.1136/bmj.311.7003.485
  supports: Why failing to reject a null hypothesis does not establish it.
  short: absence of evidence is not evidence of absence
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read)
  checked: 2026-09-30, Crossref
- cite: Lumley, T., Diehr, P., Emerson, S., & Chen, L. (2002). The importance of the normality assumption in large public health data sets. Annual Review of Public Health, 23, 151–169.
  doi: 10.1146/annurev.publhealth.23.100901.140546
  supports: Why, in large samples, departures from normality matter little for methods based on means, so a normality-test result should not decide the analysis.
  short: why normality matters little for means in large samples
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
```

## Non-normality does not imply multimodality

Evidence against normality does not establish the presence of multiple
modes. Many common non-normal distributions are unimodal.

A reviewer should therefore question reasoning of the form:

> normality rejected → multiple modes or distinct groups

unless modality has been assessed directly.

## Unimodality does not establish a homogeneous population

An observed unimodal distribution should not automatically be
interpreted as evidence that all observations arise from a single
homogeneous population.

Distinct underlying groups or mixture components can overlap
sufficiently that their combined marginal distribution appears unimodal.
The number of visible modes in an observed distribution therefore does
not necessarily equal the number of underlying populations, classes, or
latent groups.

Accordingly, reasoning of the form:

> unimodal distribution → no distinct subpopulations

requires additional justification.

This distinction is especially important when a manuscript uses
distributional shape to support conclusions about latent classes,
phenotypes, behavioural patterns, pacing strategies, or other proposed
subpopulations.

```references
- cite: Schilling, M. F., Watkins, A. E., & Watkins, W. (2002). Is human height bimodal? The American Statistician, 56(3), 223–229.
  doi: 10.1198/00031300265
  supports: How a mixture of two distinct groups can produce a unimodal distribution unless the groups are well separated.
  short: when a mixture of two groups looks unimodal
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (DOI and access); bibliographic details confirmed by hand by Tony Myers
```

## Assessing modality

If the scientific question specifically concerns whether a distribution
is unimodal or multimodal, the assessment should address modality
directly rather than substitute a test of normality.

Useful evidence may include graphical examination of the distribution
and statistical methods designed to assess modality. Hartigan's dip test
is one example of a formal test concerned with unimodality. Other
approaches may be appropriate depending on the data and scientific
question.

A reviewer should avoid assuming that one particular modality test is
mandatory. The important question is whether the evidence and method
used are capable of supporting the claim about modality.

```references
- cite: Hartigan, J. A., & Hartigan, P. M. (1985). The dip test of unimodality. The Annals of Statistics, 13(1), 70–84.
  doi: 10.1214/aos/1176346577
  supports: The dip test, one formal test of unimodality.
  short: the dip test of unimodality
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, OpenAlex (title, volume and issue); authors and pages confirmed by hand by Tony Myers
- cite: Silverman, B. W. (1981). Using kernel density estimates to investigate multimodality. Journal of the Royal Statistical Society Series B: Statistical Methodology, 43(1), 97–99.
  doi: 10.1111/j.2517-6161.1981.tb01155.x
  supports: Kernel density estimation as a way to examine the number of modes.
  short: kernel density estimates for assessing multimodality
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
```

## Distributional shape and clustering

The apparent shape of a marginal distribution does not, by itself,
validate or invalidate a clustering solution.

A unimodal distribution does not rule out meaningful clusters, and
multimodality does not automatically establish that a particular
clustering solution is valid. Clustering may depend on multiple
variables or features whose joint structure is not represented by a
single marginal distribution.

Claims that identified clusters represent distinct or reproducible
subpopulations require evidence appropriate to the clustering method and
scientific purpose. Depending on the analysis, relevant considerations
may include cluster stability, separation, sensitivity to analytical
choices, and agreement between alternative clustering solutions.

Similar-looking cluster centroids across different algorithms do not
necessarily demonstrate that the algorithms assigned the same
observations to the same clusters. If agreement between clustering
methods is presented as evidence of robustness, quantitative assessment
of partition agreement or stability may be needed.

```references
- cite: Hennig, C. (2007). Cluster-wise assessment of cluster stability. Computational Statistics & Data Analysis, 52(1), 258–271.
  doi: 10.1016/j.csda.2006.11.025
  supports: Assessing whether individual clusters are stable under resampling.
  short: assessing the stability of individual clusters
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable; published online 2006; volume 52 is 2007)
- cite: Hubert, L., & Arabie, P. (1985). Comparing partitions. Journal of Classification, 2(1), 193–218.
  doi: 10.1007/BF01908075
  supports: Quantifying agreement between two clusterings with the adjusted Rand index, rather than by comparing centroids.
  short: the adjusted Rand index for agreement between partitions
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
```

## Questions for reviewers

When a manuscript discusses normality, modality, or subpopulations,
consider:

-   What exact property is the authors' statistical procedure testing?
-   Is a normality test being interpreted as a test of unimodality?
-   Is failure to reject normality being interpreted as proof of
    normality?
-   Is rejection of normality being interpreted as evidence of
    multimodality?
-   Is unimodality being interpreted as evidence that distinct
    underlying subpopulations do not exist?
-   If modality is scientifically important, has it been assessed using
    evidence appropriate to modality?
-   Are claims about clusters or latent groups being supported merely by
    the shape of a marginal distribution?
-   If multiple clustering algorithms are claimed to give consistent
    results, has agreement between their partitions actually been
    assessed?

## Reviewer interpretation

The key principle is to match the statistical evidence to the claim.

**Normality, unimodality, multimodality, homogeneity, and cluster
structure are different properties. Evidence about one should not be
treated automatically as evidence about another.**

When a manuscript moves from a normality test to a conclusion about
modality, or from modality to a conclusion about underlying
subpopulations, the reviewer should examine each inferential step
separately and ask what evidence supports it.

## References

Checked sources for this topic. A section with its own list shows that list instead. Each entry says what it supports; a source is listed for that purpose only, not as support for every sentence in the note.

```references
- cite: Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality (complete samples). Biometrika, 52(3–4), 591–611.
  doi: 10.1093/biomet/52.3-4.591
  supports: What a test of normality tests.
  short: the Shapiro–Wilk test of normality
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, Crossref
- cite: Hartigan, J. A., & Hartigan, P. M. (1985). The dip test of unimodality. The Annals of Statistics, 13(1), 70–84.
  doi: 10.1214/aos/1176346577
  supports: Testing unimodality directly rather than through a normality test.
  short: the dip test of unimodality
  type: Journal article
  access: open
  access_checked: 2026-10-01, OpenAlex: open (bronze, free to read at the publisher)
  checked: 2026-10-01, OpenAlex (title, volume and issue); authors and pages confirmed by hand by Tony Myers
- cite: Schilling, M. F., Watkins, A. E., & Watkins, W. (2002). Is human height bimodal? The American Statistician, 56(3), 223–229.
  doi: 10.1198/00031300265
  supports: Why the number of visible modes need not equal the number of underlying groups.
  short: when a mixture of two groups looks unimodal
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (DOI and access); bibliographic details confirmed by hand by Tony Myers
- cite: Hubert, L., & Arabie, P. (1985). Comparing partitions. Journal of Classification, 2(1), 193–218.
  doi: 10.1007/BF01908075
  supports: Comparing clustering solutions by the agreement of their partitions.
  short: the adjusted Rand index for agreement between partitions
  type: Journal article
  access: subscription
  access_checked: 2026-10-01, OpenAlex: closed
  checked: 2026-10-01, OpenAlex (Crossref unavailable)
```
