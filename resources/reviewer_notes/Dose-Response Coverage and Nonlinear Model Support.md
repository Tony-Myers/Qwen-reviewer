# Dose-Response Coverage and Nonlinear Model Support

#### Purpose

This guide helps reviewers assess whether observed data adequately support a claimed linear or nonlinear dose-response relationship. It focuses on coverage of the dose range, functional-form choice, interpolation versus extrapolation, sparse data at extremes, uncertainty in turning points and claims about optimal doses.

#### What reviewers should look for

✓ The manuscript describes how observations are distributed across the dose range.

✓ The chosen functional form is scientifically plausible and compared with reasonable alternatives.

✓ Nonlinear features are supported by data rather than created mainly by model assumptions.

✓ Sparse data at very low or high doses are reflected in wider uncertainty.

✓ Extrapolation beyond observed doses is clearly distinguished from interpolation.

✓ Claims about thresholds, plateaux or optimal doses include uncertainty.

#### Common reviewer questions

##### What does adequate dose-range coverage mean?

A dose-response model is best supported when observations occur across the range over which the curve is interpreted.

Coverage should be assessed by considering:

- number of studies or observations at each dose;
- gaps in the observed range;
- concentration of data around only a few doses;
- representation of low and high doses;
- sample sizes at each dose.

Where several doses come from the same study, those observations usually share a common comparison group and are correlated, in the same way as the arms of a multi-arm trial. Counting them as independent overstates the coverage as well as the precision.

A smooth fitted curve does not imply equally strong evidence everywhere along that curve.

##### Why does sparse coverage matter for nonlinear models?

Nonlinear models can estimate curvature even when relatively little information exists at the extremes.

In sparse regions, the fitted shape may be determined more by:

- the assumed mathematical form;
- prior distributions;
- spline constraints;
- a small number of influential studies;

than by direct evidence.

##### What is interpolation?

**Interpolation** estimates effects between observed doses that are reasonably supported by nearby data.

Interpolation still requires assumptions but is usually better supported than extrapolation.

##### What is extrapolation?

**Extrapolation** predicts beyond the range of observed evidence.

Uncertainty usually increases outside the observed dose range, and conclusions become more dependent on the assumed functional form.

Reviewers should be cautious when authors present extrapolated doses as though they were directly studied.

##### How should the nonlinear functional form be chosen?

Possible approaches include:

- Emax models;
- restricted cubic splines;
- fractional polynomials;
- ordinary polynomials;
- exponential models;
- other biologically motivated functions.

The functional form should ideally be justified before examining the final results.

Alternative plausible forms should be compared when substantive conclusions depend on the curve shape.

##### Does better DIC, WAIC or LOO automatically justify a nonlinear model?

No.

Model-comparison criteria should be considered together with:

- uncertainty in the difference between models;
- graphical model fit;
- predictive checks;
- scientific plausibility;
- stability of the fitted curve.

A numerically preferred model may offer little substantive improvement.

##### How large should a WAIC or LOO difference be?

There is no universal significance-style cut-off.

For predictive criteria, reviewers should compare the estimated model difference with its **standard error**.

A difference that is small relative to its standard error provides weak evidence that predictive performance differs.

A difference several times larger than its standard error is more persuasive.

This advice belongs to the predictive criteria. DIC as ordinarily reported carries no standard error for the difference between models, so a DIC gap cannot be judged in the same way. Where a dose-response model has been selected on DIC alone, reviewers should ask what else supports the choice: graphical fit, posterior predictive checks, stability of the fitted curve under alternative forms, and scientific plausibility.

##### Can an optimal dose be identified from a fitted curve?

Sometimes, but claims should be cautious.

The dose with the largest posterior mean or fitted effect is not automatically a well-established **optimal dose**.

An optimum is weakly identified when:

- the curve is flat near its maximum;
- credible intervals overlap across many doses;
- few observations occur near the estimated maximum;
- the maximum lies near the edge of the observed range;
- the maximum depends strongly on model specification.

##### What should be reported for an estimated optimum?

Where possible, authors should report:

- uncertainty around the optimal dose;
- uncertainty around the predicted effect at that dose;
- observed dose coverage near the optimum;
- sensitivity to alternative functional forms.

#### Common misconceptions

##### "A smooth nonlinear curve means the dose-response relationship is well established."

Incorrect.

Smoothness is a property of the model, not necessarily of the evidence.

##### "A statistically preferred nonlinear model proves biological nonlinearity."

Incorrect.

Model comparison provides relative support among fitted models, not proof of the biological mechanism.

##### "Predictions within the plotted curve are all equally reliable."

Incorrect.

Uncertainty depends strongly on where observations actually occur.

##### "The maximum fitted effect identifies the optimal dose."

Not necessarily.

A clinically useful optimum also depends on uncertainty, harms, feasibility, cost and the density of evidence.

#### Common terminology

**Dose-response relationship** – association between dose and outcome or treatment effect.

**Nonlinear model** – model allowing effect changes that are not proportional to dose.

**Emax model** – saturating dose-response model approaching a maximum effect.

**Spline** – flexible piecewise polynomial function used to represent nonlinear relationships.

**Interpolation** – prediction within the observed data range.

**Extrapolation** – prediction beyond the observed data range.

**Dose coverage** – distribution of observed evidence across the range of doses.

**Optimal dose** – dose selected according to a prespecified criterion, not simply the largest fitted point estimate.

#### Common reviewer red flags

- Nonlinear curve shown without displaying dose coverage.
- Few observations at the doses driving the apparent curvature.
- Extrapolated effects discussed as observed evidence.
- Functional form selected only after seeing results.
- Optimal dose reported without uncertainty.
- Model selected solely because it has the lowest DIC or WAIC.
- Sparse evidence at the dose-range boundaries ignored.
- Multiple doses from one study treated as independent observations.
- A DIC difference interpreted as though it carried a standard error.

#### Quick reviewer checklist

□ Dose coverage is shown or described.

□ The nonlinear functional form is justified.

□ Alternative plausible models are considered.

□ Interpolation is distinguished from extrapolation.

□ Sparse regions of the dose range have appropriately greater uncertainty.

□ Model-comparison differences are interpreted relative to their uncertainty.

□ Claims about thresholds, plateaux and optimal doses are supported by observed evidence.

---

*Based on:* General dose-response modelling and predictive model-comparison literature; no single source. See also the notes on Bayesian model comparison and on network meta-analysis assumptions.
