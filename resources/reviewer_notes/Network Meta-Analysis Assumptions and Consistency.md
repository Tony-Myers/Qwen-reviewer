# Network Meta-Analysis Assumptions and Consistency

#### Purpose

This guide helps reviewers assess the assumptions underlying network meta-analysis (NMA). It focuses on connectedness, transitivity, direct and indirect evidence, consistency or coherence, effect modifiers, multi-arm trials and whether the network supports the comparisons being made.

#### What reviewers should look for

✓ The treatment network is sufficiently connected to estimate the comparisons of interest.

✓ The transitivity assumption is scientifically plausible.

✓ Important effect modifiers are similarly distributed across treatment comparisons.

✓ Agreement between direct and indirect evidence is assessed where both are available.

✓ Multi-arm trials are analysed using methods that preserve the correlation between comparisons sharing a common group.

✓ Claims based largely on indirect evidence are distinguished from those supported directly.

#### Common reviewer questions

##### What is transitivity?

**Transitivity** is the assumption that studies comparing different treatments are sufficiently similar that indirect comparisons are meaningful.

For example, if studies compare A versus B and other studies compare B versus C, an indirect A-versus-C comparison requires the studies to be comparable with respect to factors that modify treatment effects.

Potential effect modifiers may include:

- age;
- baseline severity;
- disease duration;
- intervention intensity;
- follow-up duration;
- risk of bias;
- concomitant treatment.

##### What is consistency or coherence?

**Consistency** (also called **coherence**) means that direct and indirect evidence estimate compatible treatment effects.

For example, the directly observed A-versus-C effect should broadly agree with the effect implied indirectly through A-versus-B and B-versus-C evidence.

Important disagreement is called **inconsistency** or **incoherence**.

##### How should inconsistency be assessed?

Possible approaches include:

- node-splitting;
- unrelated mean effects models;
- design-by-treatment interaction models;
- local inconsistency checks;
- comparison of direct and indirect estimates.

Reviewers should consider both statistical evidence and the scientific explanation for any inconsistency.

##### What is a connected network?

A treatment network is **connected** when every treatment included in a comparative analysis can be linked through at least one chain of treatment comparisons.

Disconnected components cannot provide relative treatment effects across the disconnected parts without additional assumptions.

##### Why do effect modifiers matter?

If an effect modifier is distributed differently across treatment comparisons, indirect comparisons may be biased.

For example, if high-dose interventions are studied mainly in younger populations and low-dose interventions mainly in older populations, the apparent treatment difference may partly reflect age rather than treatment.

##### How should multi-arm trials be handled?

Comparisons from a multi-arm trial share participants in the common treatment group and are statistically correlated.

Treating these comparisons as independent double-counts information and can underestimate uncertainty.

NMA software should account for this covariance structure.

##### What is direct versus indirect evidence?

**Direct evidence** comes from studies directly comparing two interventions.

**Indirect evidence** estimates a comparison through one or more common comparators.

Network estimates may combine both.

Reviewers should be wary when apparently precise conclusions are driven almost entirely by indirect evidence from a sparse network.

##### What do treatment rankings such as SUCRA mean?

Ranking statistics summarise how often each treatment occupies each position in the network.

They are frequently over-interpreted. A ranking:

- reflects the ordering of point estimates, not the size of the differences between them;
- is sensitive to the precision of each estimate, so a sparsely studied treatment with a wide interval can rank highly;
- can impose a definite order on effects that are close to indistinguishable.

Reviewers should expect rankings to be presented alongside the estimated effects and their uncertainty, and should be cautious wherever the ranking is itself the main claim.

##### Does random-effects NMA guarantee transitivity?

No.

Random effects model unexplained variation between studies.

They do not correct systematic imbalance in effect modifiers across treatment comparisons.

A random-effects NMA also commonly assumes a single heterogeneity parameter shared across every comparison in the network. That is a further assumption, not a consequence of the model, and it is rarely tested. See the note on between-study heterogeneity.

#### Common misconceptions

##### "A connected network is automatically a valid network."

Incorrect.

Connectedness is necessary but does not establish transitivity or consistency.

##### "No statistically significant inconsistency means the network is consistent."

Incorrect.

Inconsistency tests may have low power, especially in sparse networks.

Scientific assessment of effect modifiers remains essential.

##### "Direct and indirect evidence are interchangeable."

Incorrect.

They rely on different evidence structures and assumptions.

##### "A random-effects model solves violations of transitivity."

Incorrect.

Heterogeneity and transitivity are different issues.

#### Common terminology

**NMA (Network Meta-Analysis)** – simultaneous synthesis of evidence across multiple interventions.

**Direct evidence** – evidence from head-to-head comparisons.

**Indirect evidence** – evidence inferred through common comparators.

**Transitivity** – assumption allowing valid indirect comparison across sufficiently comparable studies.

**Consistency / coherence** – agreement between direct and indirect evidence.

**Inconsistency / incoherence** – disagreement between direct and indirect evidence.

**Effect modifier** – study or participant characteristic that changes treatment effect.

**Node-splitting** – comparison of direct and indirect evidence for a particular treatment contrast.

**Multi-arm trial** – study containing three or more treatment groups.

**SUCRA / P-score** – summary statistics describing a treatment's position in the ranking distribution, not the magnitude of its effect.

#### Common reviewer red flags

- Transitivity never discussed.
- Important effect modifiers differ markedly across comparisons.
- No assessment of direct versus indirect agreement.
- Sparse network interpreted with excessive certainty.
- Multi-arm trial comparisons treated as independent.
- Disconnected network used to estimate unsupported contrasts.
- Treatment rankings emphasised without discussing network uncertainty.

#### Quick reviewer checklist

□ The network is connected for the comparisons being estimated.

□ Transitivity is scientifically plausible.

□ Important effect modifiers are examined.

□ Direct and indirect evidence are distinguished.

□ Consistency or incoherence is assessed.

□ Multi-arm trial dependence is handled correctly.

□ Conclusions reflect the strength and structure of the network evidence.

---

*Based on:* General network meta-analysis methodological literature; no single source. See also the notes on between-study heterogeneity and on dose-response coverage.
