Version: 1.0.0

# Multi-Phased Constrained Simulation

## Executive Summary

`mcprojsim` currently uses a deterministic single-pass greedy scheduler in constrained mode: ready tasks are processed in sorted task ID order and resources are assigned in sorted resource name order. This is correct, reproducible, and aligned with current FR-033/FR-038 behavior, but it does not use any explicit criticality-aware prioritization when resource contention exists.

FR-034 and FR-042 describe a future two-pass mode where:
1. Pass 1 computes constrained criticality indices.
2. Pass 2 schedules with those indices as task priority.
3. The system reports pass-1 vs pass-2 deltas for traceability.

Recommendation: implement the two-pass mode as an optional constrained-scheduling policy with default disabled. The expected benefit is lower tail-risk (`P80/P90/P95`) and reduced makespan in contention-heavy dependency networks. The primary tradeoff is runtime cost (roughly 2x constrained scheduling work) and extra implementation complexity around deterministic traceability.

The best-fit design for this repository is:
- Keep existing single-pass greedy as the default policy.
- Add a constrained scheduling assignment policy enum.
- Run a baseline constrained pass to compute global criticality rank.
- Re-run constrained scheduling with priority ordering by rank.
- Return and export pass-delta metrics in a dedicated traceability section.

This document proposes a phased implementation plan with explicit verification gates and risk controls.

## Query Type

This is a technical deep-dive architecture and rollout proposal for adding two-pass criticality-aware resource scheduling to the existing Monte Carlo simulation engine while preserving deterministic behavior and backward compatibility.

## Current Architecture and Gap

### What exists today

- Constrained scheduling exists in `TaskScheduler._schedule_tasks_with_resources(...)`.
- Scheduling policy in constrained mode is deterministic greedy:
  - ready tasks in sorted order,
  - eligible resources in sorted order,
  - start-now behavior (no waiting for better allocations).
- Critical path frequency and full critical-path sequence aggregation already exist in simulation outputs.
- Constrained diagnostics already exist:
  - `resource_wait_time_hours`,
  - `resource_utilization`,
  - `calendar_delay_time_hours`.

### What is missing for FR-034/FR-042

- No config toggle for two-pass mode.
- No CLI toggle for two-pass mode.
- No scheduler policy branch that uses pass-1 criticality as pass-2 priority.
- No pass-1 vs pass-2 delta payload in results/exporters.
- No acceptance tests for pass-delta and two-pass determinism.

## Should This Feature Be Implemented?

## Benefit Profile

Two-pass mode is likely beneficial when all of the following are true:
- resource contention is frequent,
- multiple dependency branches compete for the same limited resources,
- delay to high-criticality tasks propagates strongly to project completion,
- constrained mode is active (resources/calendars/team-size based resources).

Expected improvements:
- lower high-percentile completion times (`P80+`),
- reduced frequency of non-critical work preempting critical chain progress,
- better traceability for schedule-policy impact.

## Limited-Benefit Cases

Two-pass mode will likely have low or no benefit when:
- resources are abundant relative to ready-task demand,
- projects are mostly linear chains with little contention ambiguity,
- constrained mode is inactive (dependency-only scheduling).

## Potential Downsides

- Runtime overhead (roughly two constrained runs per simulation request).
- Noisy improvement signal if pass comparison is not paired/deterministic.
- Potential fairness concerns (low-criticality tasks may be delayed more often).

## Recommendation

Implement with strict guardrails:
- default off,
- constrained mode only,
- deterministic implementation,
- explicit pass-delta reporting,
- acceptance tests that prove no constraint violations and stable reproducibility.

## Design Goals

1. Preserve backward compatibility and default behavior.
2. Keep deterministic reproducibility for fixed seeds.
3. Make two-pass behavior observable and auditable in outputs.
4. Minimize scheduler complexity growth by isolating policy logic.
5. Keep implementation incremental with verifiable phases.

## Non-Goals (Initial Release)

- No preemptive task execution.
- No multi-objective optimization (cost/fairness balancing).
- No machine-learned dispatch policy.
- No replacement of existing critical-path computation semantics.

## Proposed Technical Design

### 1. Introduce Constrained Assignment Policy

Add a constrained scheduling policy field in config:

```yaml
constrained_scheduling:
  sickness_prob: 0.0
  assignment_mode: greedy_single_pass   # greedy_single_pass | criticality_two_pass
  pass1_iterations: 1000                # optional cap for pass-1 ranking
  priority_blend_alpha: 1.0             # optional, default pure criticality ranking
```

Default remains `greedy_single_pass`.

### 2. Add CLI Override

Add optional simulate-time overrides:
- `--two-pass` (enables `criticality_two_pass` for this run)
- `--pass1-iterations N` (optional pass-1 rank calculation budget)

CLI precedence should follow existing pattern:
- CLI override > config file > defaults.

### 3. Two-Pass Flow in Engine

When policy is `criticality_two_pass` and constrained scheduling is active:

1. **Pass 1 (baseline constrained policy)**
   - Run constrained scheduling baseline across pass-1 iteration budget.
   - Compute task criticality index from pass-1 critical path frequency:
     \[
     CI(t) = \frac{critical\_count(t)}{pass1\_iterations}
     \]
   - Produce a deterministic rank vector, tie-breaking by task ID.

2. **Pass 2 (criticality-prioritized policy)**
   - Re-run constrained scheduling with ready-task ordering by:
     - descending `CI(t)`, then
     - task ID tie-break.
   - Keep all existing hard constraints unchanged.

3. **Delta computation**
   - Compare pass-2 vs pass-1 aggregate metrics and expose deltas.

### 4. Scheduler Policy Injection

Refactor scheduler minimally to support task-order strategy injection.

Current:
- ready tasks sorted by task ID.

Proposed:
- add optional `task_priority: dict[str, float]` argument in constrained path,
- build ready queue sort key:
  - two-pass policy: `(-priority, task_id)`,
  - default policy: `(task_id)`.

Hard constraints remain unchanged:
- dependencies,
- eligibility/experience,
- max resources and practical cap,
- calendar/sickness availability,
- non-preemptive execution.

### 5. Traceability Payload

Extend `SimulationResults` with optional two-pass trace object.

Suggested shape:

```python
class TwoPassDelta(BaseModel):
    enabled: bool
    pass1_iterations: int
    pass2_iterations: int
    ranking_method: str
    top_ranked_tasks: list[str]
    pass1_mean_hours: float
    pass2_mean_hours: float
    delta_mean_hours: float
    pass1_p80_hours: float
    pass2_p80_hours: float
    delta_p80_hours: float
    pass1_resource_wait_time_hours: float
    pass2_resource_wait_time_hours: float
    delta_resource_wait_time_hours: float
    pass1_calendar_delay_time_hours: float
    pass2_calendar_delay_time_hours: float
    delta_calendar_delay_time_hours: float
```

Include in:
- CLI (`simulate`) as a dedicated section,
- JSON export (`two_pass_traceability` block),
- CSV export (new section),
- HTML export (summary panel).

### 6. Determinism Strategy

Two robust options:

1. **Paired Replay (preferred)**
   - Cache pass-1 sampled task-duration vectors per iteration.
   - Reuse exact vectors in pass-2.
   - Minimizes sampling noise in deltas.

2. **Independent Re-run (simpler)**
   - Run pass-2 with same seed and deterministic flow.
   - Easier to implement but noisier deltas due to random stream drift.

Recommendation: implement paired replay for schedule-driven delta accuracy.

### 7. Performance Controls

- `pass1_iterations` default less than full iterations (for example 1000).
- If total iterations < pass1 budget, use full iterations.
- Emit warning when two-pass is enabled on very large iteration counts.

## Verification-Oriented Implementation Plan

The implementation plan is intentionally phase-based so each phase can be fully verified before the next one.

## Phase 1: Config and Defaults Foundation

Success criteria:
- config accepts `assignment_mode` with default single-pass,
- invalid assignment mode rejected,
- pass-1 iteration budget validated (`> 0`).

Files:
- `src/mcprojsim/config.py`
- `tests/test_config.py`

Verify:
- `poetry run pytest tests/test_config.py --no-cov`

Risk controls:
- keep defaults unchanged,
- additive fields only (no semantic change when unset).

## Phase 2: CLI Surface and Precedence

Success criteria:
- `simulate --two-pass` works,
- CLI override precedence works over config,
- help text clearly explains constrained-only applicability.

Files:
- `src/mcprojsim/cli.py`
- `tests/test_cli.py`

Verify:
- `poetry run pytest tests/test_cli.py --no-cov -v`

Risk controls:
- fail fast with clear message when two-pass requested without constrained mode.

## Phase 3: Scheduler Priority Hook (No Behavior Change Yet)

Success criteria:
- scheduler accepts optional priority map,
- default path produces byte-for-byte equivalent schedules to current behavior.

Files:
- `src/mcprojsim/simulation/scheduler.py`
- `tests/test_simulation.py`

Verify:
- targeted scheduler tests (existing constrained scheduling suite),
- deterministic regression test for unchanged default policy.

Risk controls:
- preserve old sort as exact fallback when no priority map.

## Phase 4: Pass-1 Criticality Rank Computation

Success criteria:
- engine can run pass-1 constrained baseline,
- criticality index map produced and stable for fixed seed,
- tie-breaking stable by task ID.

Files:
- `src/mcprojsim/simulation/engine.py`
- `src/mcprojsim/models/simulation.py`
- `tests/test_simulation.py`

Verify:
- new tests asserting deterministic rank vector with fixed seed,
- no constraint violation regressions.

Risk controls:
- isolate ranking logic into helper with explicit unit tests.

## Phase 5: Pass-2 Prioritized Scheduling

Success criteria:
- ready-task dispatch uses rank-first ordering,
- hard constraints still always hold,
- pass-2 runs only when constrained scheduling active.

Files:
- `src/mcprojsim/simulation/engine.py`
- `src/mcprojsim/simulation/scheduler.py`
- `tests/test_simulation.py`
- `tests/test_e2e_combinations.py`

Verify:
- acceptance tests that dependencies/resource rules are never violated,
- reproducibility test for two-pass mode with fixed seed.

Risk controls:
- keep policy implementation read-only with respect to constraints,
- assert invariants in tests (no overlap violations per resource, dependency ordering preserved).

## Phase 6: Pass-Delta Traceability in Results and Exports

Success criteria:
- `SimulationResults.to_dict()` includes two-pass trace block,
- CLI table output shows pass-1 vs pass-2 deltas,
- JSON/CSV/HTML include traceability fields.

Files:
- `src/mcprojsim/models/simulation.py`
- `src/mcprojsim/cli.py`
- `src/mcprojsim/exporters/json_exporter.py`
- `src/mcprojsim/exporters/csv_exporter.py`
- `src/mcprojsim/exporters/html_exporter.py`
- `tests/test_results.py`
- `tests/test_exporters.py`
- `tests/test_cli_output.py`

Verify:
- exporter/CLI regression tests,
- snapshot-style assertions for traceability section presence.

Risk controls:
- additive export schema only,
- avoid renaming existing output fields.

## Phase 7: Acceptance Tests for FR-042

Success criteria:
- explicit tests prove:
  - mode configurable and default off,
  - pass-1 ranking computed,
  - pass-2 uses ranking,
  - no constraints violated,
  - pass-delta reported.

Files:
- `tests/test_simulation.py`
- `tests/test_cli_output.py`
- `tests/test_exporters.py`

Verify:
- `poetry run pytest tests/test_simulation.py tests/test_cli_output.py tests/test_exporters.py -n auto --no-cov`

Risk controls:
- acceptance fixtures with known contention topology,
- deterministic seed and expected ordering assertions.

## Phase 8: Documentation and Examples

Success criteria:
- user docs show config and CLI usage,
- migration note clarifies default unchanged,
- examples include one two-pass constrained project.

Files:
- `docs/user_guide/running_simulations.md`
- `docs/configuration.md`
- `docs/user_guide/constrained.md`
- `examples/` (new constrained two-pass example)

Verify:
- `poetry run mkdocs build`
- `poetry run mcprojsim simulate <new-example> --two-pass --table`

Risk controls:
- explicit caveats on runtime cost and when to use mode.

## Full Verification Sequence

1. `poetry run pytest tests/test_config.py --no-cov`
2. `poetry run pytest tests/test_cli.py --no-cov`
3. `poetry run pytest tests/test_simulation.py --no-cov`
4. `poetry run pytest tests/test_results.py tests/test_exporters.py tests/test_cli_output.py --no-cov`
5. `poetry run pytest tests/test_e2e_combinations.py --no-cov`
6. `poetry run pytest tests/ -n auto --cov=src/mcprojsim --cov-fail-under=80`
7. `poetry run mkdocs build`

## Risk Register and Mitigations

1. **Risk: Runtime regression from two-pass doubling compute**
   - Mitigation: bounded `pass1_iterations`, profiling threshold warnings, default off.

2. **Risk: Delta noise from stochastic differences between passes**
   - Mitigation: paired replay of pass-1 sampled durations into pass-2.

3. **Risk: Policy change unintentionally alters default behavior**
   - Mitigation: strict feature flag gating and default-policy regression tests.

4. **Risk: Hidden constraint violations under prioritized ordering**
   - Mitigation: invariant-focused acceptance tests on dependency and resource exclusivity.

5. **Risk: Export schema breakage for existing consumers**
   - Mitigation: additive fields only, keep current keys untouched.

6. **Risk: Overfitting to pass-1 criticality from small sample**
   - Mitigation: minimum pass1 iteration floor, optional warning when too small.

## Scope Decisions

1. Two-pass mode is constrained-scheduling only.
2. Default scheduling remains single-pass greedy.
3. Ranking is global per simulation run (not recomputed mid-pass-2).
4. No preemption in initial version.
5. Delta reporting is aggregate (mean/percentiles/diagnostics), not per-task schedule diff in v1.

# Formal Requirements

The requirements below describe the proposed two-pass constrained scheduling behavior. SHALL denotes mandatory behavior when the feature is enabled. MAY denotes optional behavior.

## FR-MPS-001: Configuration Toggle and Default
- The system SHALL expose a two-pass scheduling mode as a constrained-scheduling configuration option.
- The default mode SHALL be single-pass greedy.
- The two-pass mode SHALL be disabled by default.

## FR-MPS-002: CLI Override
- The system SHALL expose a CLI override to enable two-pass scheduling for a simulation run.
- CLI override SHALL take precedence over config value for that run.

## FR-MPS-003: Pass-1 Criticality Computation
- When two-pass mode is enabled, pass 1 SHALL run constrained scheduling and compute task criticality indices from pass-1 critical path membership frequency.
- Pass-1 ranking SHALL be deterministic for fixed seed and input.

## FR-MPS-004: Pass-2 Priority Policy
- Pass 2 SHALL prioritize ready tasks by descending pass-1 criticality index.
- Equal-criticality ties SHALL be broken deterministically by task ID.
- Pass 2 SHALL preserve all existing hard constraints (dependencies, resource eligibility, max resources, calendar/sickness availability).

## FR-MPS-005: Constrained-Only Applicability
- Two-pass mode SHALL apply only when constrained scheduling is active.
- If constrained scheduling is inactive, the system SHALL run dependency-only scheduling and SHALL NOT attempt two-pass prioritization.

## FR-MPS-006: Deterministic Acceptance Behavior
- The system SHALL provide acceptance tests demonstrating that two-pass mode does not violate dependency/resource constraints.
- The system SHALL provide deterministic tests showing stable pass ranking and reproducible output for fixed seed.

## FR-MPS-007: Traceability Output
- The system SHALL report pass-1 vs pass-2 outcome deltas for traceability.
- Traceability SHALL include at least duration and constrained diagnostics deltas.
- Traceability data SHALL be available in CLI and machine-readable exports.

## FR-MPS-008: Backward Compatibility
- Existing project files and workflows without two-pass configuration SHALL retain current behavior.
- Existing output fields SHALL remain stable; two-pass data SHALL be additive.

## FR-MPS-009: Performance Guardrails
- The system SHALL allow bounded pass-1 iteration budgeting.
- The system MAY warn when two-pass settings are expected to materially increase runtime.

## FR-MPS-010: Documentation and Migration
- User documentation SHALL describe when two-pass mode is useful and when it is unlikely to help.
- Documentation SHALL clearly state default-off behavior and runtime tradeoff.

## Acceptance Criteria Matrix

- FR-034 addressed by: FR-MPS-001, FR-MPS-002, FR-MPS-003, FR-MPS-004.
- FR-042 addressed by: FR-MPS-001, FR-MPS-003, FR-MPS-004, FR-MPS-006, FR-MPS-007.

## Conclusion

This feature is worth implementing for contention-heavy constrained schedules because it targets the exact failure mode of deterministic ID-ordered greedy dispatch: suboptimal resource use on high-criticality chains. The proposed architecture minimizes risk by preserving defaults, isolating policy logic, enforcing deterministic acceptance tests, and making deltas explicit for traceability.
