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
