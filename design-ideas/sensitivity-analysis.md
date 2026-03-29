Version: 0.1.0

Date: 2026-03-29

Status: Design and Research Proposal

# Sensitivity Analysis

## Executive Summary

This document proposes an incremental sensitivity-analysis strategy for `mcprojsim` that helps non-statistical users identify practical schedule risks from Monte Carlo results.

Recommended next-release approach:

1. Keep rank-based sensitivity (Spearman correlation) as the default core signal.
2. Combine sensitivity with criticality and risk-impact signals to produce one user-facing concept: schedule drivers.
3. Present findings in plain language with an intuitive 5-level influence scale and action-oriented guidance in the HTML report.
4. Treat advanced global methods (Morris, Sobol, PAWN, FAST, HDMR) as future phases, not immediate defaults.

This balances statistical quality, runtime cost, and end-user comprehension.

## Problem Statement

Monte Carlo output can be statistically rich but difficult to act on for everyday users. The practical question is usually: which tasks and risks should we manage first to reduce late-delivery probability?

Sensitivity analysis in `mcprojsim` should therefore prioritize:

1. Actionability over technical depth in the default report.
2. Robust schedule-risk identification over isolated statistical values.
3. Clear narrative interpretation over raw coefficients.

## Current State in mcprojsim

Current capabilities already provide a strong baseline:

1. Rank-based task sensitivity using Spearman correlation between sampled task durations and total project duration.
2. Criticality frequency (how often each task is on the critical path).
3. Full critical-path sequence frequency.
4. Risk impact tracking, including trigger rate and mean impact.
5. Schedule slack estimation per task.
6. HTML tornado chart and statistical summary sections.

Current gap:

1. Metrics are shown mostly as separate technical values.
2. There is no unified schedule-driver interpretation layer.
3. Non-expert wording is limited and does not fully map to practical risk actions.

# Research Summary: Relevant Methods

## Methods Relevant Now

1. Rank correlation methods (Spearman, tornado ranking)
Widely used in Monte Carlo reporting for factor prioritization.
Computationally cheap and easy to explain.
Fits current `mcprojsim` outputs.

2. Conditional tail-uplift analysis
Example question: when this task is in its slow tail, how much does project P80 or P90 shift?
Directly connects sensitivity to overrun risk.

3. Criticality-aware sensitivity
A task can have moderate correlation but high practical risk if it is frequently critical.
Combining sensitivity and criticality improves prioritization.

4. Risk-event leverage analysis
Tasks with high risk trigger rate and high mean impact should be emphasized, especially when also highly critical.

## Methods for Future Scope

1. Morris (elementary effects)
Useful screening method when many uncertain inputs exist.

2. Sobol first-order and total-order indices
Strong for nonlinear behavior and interaction-aware decomposition.
Requires extended sampling/evaluation workflows and higher compute budget.

3. PAWN and Monte Carlo filtering
Useful for threshold and tail-focused questions.

4. FAST and RBD-FAST
Efficient global screening alternatives in suitable setups.

5. HDMR or surrogate-model approaches
Useful when deeper global sensitivity is needed with constrained compute.

## Deep Dive: Applying Morris and Sobol in mcprojsim

This section describes how Morris and Sobol methods could be introduced in a staged way without disrupting the current Monte Carlo workflow.

### Why Add Morris and Sobol

Current default signals in `mcprojsim` are strong for prioritization and communication:

1. Spearman-based rank influence.
2. Criticality frequency and path sequence behavior.
3. Risk impact and trigger statistics.

These are practical, fast, and actionable, but they do not fully isolate:

1. Nonlinear effects.
2. Interaction effects between uncertain tasks and risks.
3. Variance decomposition by factor contribution.

Morris and Sobol address those gaps.

### Applying Morris Method in mcprojsim

Morris (elementary effects) is a global screening method intended to rank influential factors with moderate compute cost.

#### Candidate Input Factors

For `mcprojsim`, each uncertain quantity can be represented as a factor in normalized input space:

1. Task duration distribution parameters (optimistic, most likely, pessimistic).
2. Risk trigger probabilities.
3. Risk impact magnitudes.
4. Optional resource-availability perturbation factors (future).

Initial rollout should focus on task-duration and risk-event factors only.

#### Practical Implementation Mapping

1. Define a factor vector $x \in [0,1]^k$ where each dimension maps to one uncertain model parameter.
2. Use Morris trajectories over a grid with $p$ levels and step size $\Delta$.
3. For each trajectory step, run the simulation summary metric of interest (for example mean duration, P80, or late probability).
4. Compute elementary effects for each factor and aggregate into:
	$\mu^*$ (mean absolute effect, influence strength) and
	$\sigma$ (effect variability, proxy for nonlinearity or interactions).

#### Morris Outputs and Interpretation

1. High $\mu^*$, low $\sigma$: strong mostly monotonic driver.
2. High $\mu^*$, high $\sigma$: strong driver with nonlinear or interaction behavior.
3. Low $\mu^*$, high $\sigma$: weak average but unstable or context-dependent effect.
4. Low $\mu^*$, low $\sigma$: low-priority factor.

#### Advantages of Morris

1. Much cheaper than full Sobol for high-dimensional screening.
2. Detects likely nonlinear and interaction-heavy factors early.
3. Produces a clean shortlist for deeper analysis.
4. Works well as a periodic advanced analysis, not necessarily every user run.

#### Limitations of Morris

1. Screening quality depends on trajectory count and factor scaling.
2. Does not provide exact variance decomposition percentages.
3. Interpretation can be sensitive if factors are strongly correlated in the model design.

### Applying Sobol Method in mcprojsim

Sobol methods provide variance decomposition and interaction-aware sensitivity indices.

#### Candidate Sobol Outputs

For each factor $i$ and response metric $Y$ (for example project duration):

1. First-order index $S_i$: fraction of variance explained by factor $i$ alone.
2. Total-order index $S_{T_i}$: fraction of variance involving factor $i$ including interactions.
3. Optional second-order indices $S_{ij}$ for selected pairs.

#### Practical Implementation Mapping

1. Use quasi-random sampling (for example Saltelli-style designs) in factor space.
2. Map each sampled factor vector to one simulation configuration.
3. Evaluate response metrics from simulation outputs (mean, P80, P95, late probability).
4. Estimate Sobol indices for top factors.

For a high-dimensional model, begin with:

1. First-order and total-order only.
2. Second-order only for top-N shortlisted factors.

#### Advantages of Sobol

1. Clear variance attribution per factor.
2. Explicit interaction visibility via total-order minus first-order gap.
3. Strong foundation for rigorous decision support and governance contexts.

#### Limitations of Sobol

1. Higher compute cost than Spearman and Morris.
2. Requires careful convergence checks and sample-size planning.
3. Full interaction matrices become hard to interpret for large numbers of factors.

### How Morris and Sobol Complement Existing Methods

Treat methods as layered, not competing:

1. Existing default layer (always-on):
	Spearman + criticality + risk impact to produce user-facing schedule drivers.
2. Morris screening layer (advanced optional):
	periodic identification of nonlinear or interaction-prone factors.
3. Sobol decomposition layer (expert optional):
	deep variance attribution on shortlisted factors and key delivery metrics.

This layered model gives:

1. Fast default guidance for all users.
2. Better scientific confidence for difficult projects.
3. Controlled runtime by limiting heavy methods to targeted workflows.

### Suggested Rollout Strategy

1. Phase A: Add optional Morris analysis command/report block for top driver candidates.
2. Phase B: Add optional Sobol first-order and total-order for shortlisted factors.
3. Phase C: Add limited pairwise Sobol interactions for top-N factors.

Guardrails:

1. Keep default report unchanged unless advanced mode is requested.
2. Add runtime estimates before execution.
3. Cache intermediate response evaluations where feasible.

### Visualization Recommendations

Use visual separation between default and advanced views.

#### Morris Visuals

1. Morris scatter plot ($\mu^*$ on x-axis, $\sigma$ on y-axis):
	highlights strong-linear versus strong-nonlinear factors.
2. Ranked lollipop/bar chart by $\mu^*$:
	simple shortlist view for decision makers.
3. Optional color by driver archetype:
	consistent with schedule-driver framing.

#### Sobol Visuals

1. Grouped bars per factor: first-order $S_i$ and total-order $S_{T_i}$ side-by-side.
2. Interaction gap chart: $S_{T_i} - S_i$ to reveal interaction-heavy factors.
3. Heatmap for selected pairwise $S_{ij}$ indices (top factors only).
4. Metric tabs (mean, P80, P95, late probability) to show sensitivity by decision objective.

#### Combined Narrative View

For each top factor, include one advanced insight line:

1. Influence summary from existing driver stack.
2. Nonlinearity/interaction hint from Morris.
3. Variance share summary from Sobol when available.

Example narrative:

"This task is a High schedule driver in default analysis, shows elevated Morris variability (possible interactions), and contributes a large total-order Sobol share to P90 variance."

### Validation Expectations for Advanced Methods

Before exposing Morris or Sobol broadly, verify:

1. Stability under repeated runs with fixed seeds and fixed sampling plans.
2. Convergence behavior versus sample count.
3. Directional agreement with existing high-confidence driver signals.
4. Runtime budget fit for representative project sizes.

Acceptance criteria for initial advanced release:

1. Morris top-factor shortlist is stable across repeated runs.
2. Sobol first-order plus selected interaction insights are reproducible within tolerance.
3. HTML advanced visualizations remain understandable with concise explanatory text.

## Methods Not Recommended as Default End-User Approach

1. One-factor-at-a-time (OAT), because it does not represent simultaneous uncertainty well.
2. Local derivative-only methods, because they are harder for non-experts to interpret and can miss nonlinear interaction behavior.

## Recommended Next-Release Method Stack

Use a three-signal schedule-driver model:

1. Sensitivity strength
Rank-based influence between task variation and project duration variation.

2. Path leverage
Criticality index and frequent critical-path membership.

3. Event leverage
Risk trigger rate, mean impact, and mean impact when triggered.

Output a combined driver ranking and expose component signals in the report.

# Risk Identification Framework

Define practical driver archetypes:

1. Consistent Schedule Driver
High sensitivity and high criticality.
Main action: reduce estimate uncertainty and protect execution flow.

2. Risk-Driven Hotspot
Moderate sensitivity with high risk-event leverage.
Main action: mitigation and contingency planning for specific risks.

3. Tail-Risk Driver
Moderate average influence but large uplift in high percentiles.
Main action: protect deadlines with targeted tail controls.

4. Watchlist
Low current leverage.
Main action: monitor only, avoid over-investment.

This maps statistical output directly to project risk treatment.

# Plain-Language Scale and Wording

Replace raw statistical emphasis with a 5-level influence scale:

1. Very Low
Delays here rarely move delivery date outcomes.

2. Low
This can influence delivery date occasionally, usually with small effect.

3. Moderate
Variation here can meaningfully shift expected delivery outcomes.

4. High
This is a strong driver of schedule uncertainty and late-delivery risk.

5. Very High
This is one of the strongest delay drivers and should be prioritized.

Guideline: each level must include one explanation sentence plus one suggested action.

# HTML Report Proposal

## Primary Section: Top Schedule Drivers

Show ranked rows/cards with:

1. Task
2. Driver level (Very Low to Very High)
3. Why it matters (sensitivity, criticality, risk summary)
4. Suggested action

## Secondary Section: Technical Details

Keep tornado chart as an expert/secondary view rather than primary interpretation.

## Tail-Risk Subsection

Highlight tasks that disproportionately shift P80, P90, or P95 outcomes, even if average correlation is not dominant.

## Narrative Rule

For each top driver, include a concise narrative line, for example:

"This task is frequently critical and has high triggered-risk impact, making it a key source of late-delivery variance."

## Confidence and Caution Notes

Include short guidance in the report:

1. Sensitivity indicates influence, not strict causality.
2. Rankings can change after major scope, dependency, or risk-model changes.
3. Stability across repeated runs with the same setup increases confidence.

## Scope Boundaries

Included now:

1. Schedule-duration sensitivity and project-risk linkage.
2. User-facing interpretation model.
3. HTML report guidance centered on practical decision support.

Future scope only:

1. Effort sensitivity.
2. Resource sensitivity.
3. Staffing sensitivity.
4. Full interaction-decomposition methods as default outputs.

## Implementation and Verification Guidelines

1. Confirm baseline metrics match current engine outputs and analysis modules.
2. Ensure each next-release metric is derivable from existing iteration arrays or explicitly mark minimal required extensions.
3. Validate interpretation stability on representative example projects.
4. Verify HTML output remains understandable without statistical expertise.
5. Keep advanced methods clearly labeled as optional future analyses.

