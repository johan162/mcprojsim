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

## Research Summary: Relevant Methods

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

## Risk Identification Framework

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

## Plain-Language Scale and Wording

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

## HTML Report Proposal

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

## Decision Summary

1. Recommended default: rank-based sensitivity plus criticality and risk overlays.
2. Report strategy: meaning-first narrative and scale, technical plots as secondary support.
3. UX language: prefer schedule drivers or delay drivers over sensitivity indices in primary display.
4. Roadmap: evaluate Morris and Sobol first among advanced methods after baseline UX improvements are in place.
