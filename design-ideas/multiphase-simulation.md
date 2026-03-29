Version: 2.0.1

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

### Introduce Constrained Assignment Policy

Add a constrained scheduling policy field in config:

```yaml
constrained_scheduling:
  sickness_prob: 0.0
  assignment_mode: greedy_single_pass   # greedy_single_pass or criticality_two_pass
  pass1_iterations: 1000                # optional cap for pass-1 ranking
  priority_blend_alpha: 1.0             # optional, default pure criticality ranking
```

Default remains `greedy_single_pass`.

### Add CLI Override

Add optional simulate-time overrides:
- `--two-pass` (enables `criticality_two_pass` for this run)
- `--pass1-iterations N` (optional pass-1 rank calculation budget)

CLI precedence should follow existing pattern:
- CLI override > config file > defaults.


### Two-Pass Flow in Engine

When policy is `criticality_two_pass` and constrained scheduling is active:

1. **Pass 1 (baseline constrained policy)**
   - Run constrained scheduling baseline across pass-1 iteration budget.
   - Compute task criticality index from pass-1 critical path frequency:
     $$
     CI(t) = \frac{critical\_count(t)}{pass1\_iterations}
     $$
   - Produce a deterministic rank vector, tie-breaking by task ID.

2. **Pass 2 (criticality-prioritized policy)**
   - Re-run constrained scheduling with ready-task ordering by:
     - descending `CI(t)`, then
     - task ID tie-break.
   - Keep all existing hard constraints unchanged.

3. **Delta computation**
   - Compare pass-2 vs pass-1 aggregate metrics and expose deltas.

### Scheduler Policy Injection

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

### Traceability Payload

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

### Determinism Strategy

Two robust options:

1. **Paired Replay (preferred)**
   - Cache pass-1 sampled task-duration vectors per iteration.
   - Reuse exact vectors in pass-2.
   - Minimizes sampling noise in deltas.

2. **Independent Re-run (simpler)**
   - Run pass-2 with same seed and deterministic flow.
   - Easier to implement but noisier deltas due to random stream drift.

Recommendation: implement paired replay for schedule-driven delta accuracy.

### Paired Replay Cache Architecture

Implementation sketch for cache structure:

```python
class DurationCache:
    """Stores sampled durations from pass-1 for replay in pass-2."""
    
    def __init__(self):
        # Key: (iteration_index, task_id)
        # Value: sampled task duration (hours)
        self._cache: dict[tuple[int, str], float] = {}
    
    def store(self, iteration_idx: int, task_id: str, duration_hours: float) -> None:
        """Called during pass-1 after sampling each task in iteration i."""
        self._cache[(iteration_idx, task_id)] = duration_hours
    
    def retrieve(self, iteration_idx: int, task_id: str) -> float:
        """Called during pass-2 to fetch the cached duration."""
        key = (iteration_idx, task_id)
        if key not in self._cache:
            raise KeyError(f"No cached duration for task {task_id} iteration {iteration_idx}")
        return self._cache[key]
```

**Integration points:**

- **Pass-1 (lines post-sampling)**: After `SimulationEngine._sample_task_duration(task_id)` returns duration, call `cache.store(iteration_i, task_id, duration)`
- **Pass-2 (lines pre-scheduling)**: Before `TaskScheduler._schedule_tasks_with_resources(...)`, inject a sampler override that pulls from `cache.retrieve(iteration_i, task_id)` instead of re-sampling
- **Ordering**: Store immediately after sampling (before any scheduling), retrieve during pass-2 scheduler in same iteration order

**Memory estimate**: For 10,000 iterations and 100 tasks, ~4–8 MB (float64 per entry).

**Determinism check**: Two runs with same seed and cache must produce bit-identical results; add regression assertion in tests.

### Performance Controls

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

### Criticality Index Definition

The criticality index (CI) for a task t is computed as:

$$CI(t) = \frac{\text{iterations where } t \text{ appears in ANY critical path}}{\text{pass1_iterations}}$$

A task **appears in a critical path** if it is part of any path whose total duration equals the project's critical path length in that iteration. When multiple equally-long critical paths exist, the task is counted if it appears in ANY of them.

**Concrete Example:**

Consider 3 iterations with the following critical path lengths and membership:

| Iteration | Critical Path Length | Tasks in ANY Path | CI(TaskA) | CI(TaskB) | CI(TaskC) |
|-----------|----------------------|-------------------|-----------|-----------|----------|
| 1         | 100h                | A, B              | 1         | 1         | 0        |
| 2         | 100h                | A, C              | 1         | 0         | 1        |
| 3         | 100h                | B, C              | 0         | 1         | 1        |

Result: `CI(A) = 2/3 ≈ 0.667`, `CI(B) = 2/3 ≈ 0.667`, `CI(C) = 2/3 ≈ 0.667`. All tied; sorting by task ID produces deterministic order.

### Tie-Breaking Rule

When two tasks have identical CI values, order by **lexicographic task ID**. This ensures determinism independent of task insertion order.

Success criteria:
- engine can run pass-1 constrained baseline,
- criticality index map produced and stable for fixed seed,
- tie-breaking stable by lexicographic task ID,
- worked example in acceptance test fixture verifies CI computation matches manual calculation.

Files:
- `src/mcprojsim/simulation/engine.py`
- `src/mcprojsim/models/simulation.py`
- `tests/test_simulation.py`

Verify:
- new tests asserting deterministic rank vector with fixed seed,
- fixture-based test showing CI(task) computation against known iteration history,
- no constraint violation regressions.

Risk controls:
- isolate ranking logic into helper with explicit unit tests,
- add defensive assertion: CI(t) must be in range [0.0, 1.0].

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

## Test Fixtures and Acceptance Scenarios

Before Phase 7 begins, establish concrete test fixtures that can be used throughout acceptance testing.

### Fixture 1: Resource Contention Benchmark Project

A minimal 7-task project with clear contention that benefits from two-pass scheduling:

```yaml
# test_fixture_contention.yaml
project:
  name: contention-benchmark
  task_groups:
    - id: critical_chain
      tasks:
        - task_id: A1
          description: "Critical start"
          duration_hours: 10
          dependencies: []
        - task_id: A2
          description: "Critical middle"
          duration_hours: 15
          dependencies: [A1]
        - task_id: A3
          description: "Critical end"
          duration_hours: 10
          dependencies: [A2]
    
    - id: parallel_branch
      tasks:
        - task_id: B1
          description: "Parallel start (competes for dev-senior)"
          duration_hours: 20
          dependencies: []
        - task_id: B2
          description: "Parallel continuation"
          duration_hours: 10
          dependencies: [B1]
    
    - id: joining_tasks
      tasks:
        - task_id: C1
          description: "Joins both branches"
          duration_hours: 5
          dependencies: [A3, B2]
        - task_id: C2
          description: "Final integration"
          duration_hours: 8
          dependencies: [C1]

resources:
  - resource_id: dev-senior
    max_capacity: 1.0
  - resource_id: dev-junior
    max_capacity: 1.0

assignments:
  - task_id: A1
    resource_id: dev-senior
  - task_id: A2
    resource_id: dev-senior
  - task_id: A3
    resource_id: dev-senior
  - task_id: B1
    resource_id: dev-senior  # <-- Contention: B1 wants senior but A-chain is critical
  - task_id: B2
    resource_id: dev-junior
  - task_id: C1
    resource_id: dev-junior
  - task_id: C2
    resource_id: dev-junior
```

**Expected behavior:**
- **Single-pass (greedy by ID)**: Tasks sorted A1, A2, A3, B1, B2, C1, C2. B1 waits for A2 to complete on dev-senior (contention). Makespan ≈ 10 + 15 + 10 + (waits for A-chain) + 5 + 8 ≈ 58–60 hours.
- **Two-pass (criticality-aware)**: Pass-1 identifies A-chain as 100% critical. Pass-2 prioritizes A-chain, schedules B1 later. Expected makespan reduction: 3–5 hours (P50 improvement ~5%; P80 likely higher).

**Fixture placement**: `tests/fixtures/test_fixture_contention.yaml`

### Fixture 2: No-Benefit Scenario (Abundant Resources)

Project with plenty of resources should show near-zero delta:

```yaml
# test_fixture_abundant_resources.yaml
project:
  name: abundant-resources
  task_groups:
    - id: linear_chain
      tasks:
        - task_id: T1
          duration_hours: 10
          dependencies: []
        - task_id: T2
          duration_hours: 10
          dependencies: [T1]
        - task_id: T3
          duration_hours: 10
          dependencies: [T2]

resources:
  - resource_id: dev1
    max_capacity: 1.0
  - resource_id: dev2
    max_capacity: 1.0
  - resource_id: dev3
    max_capacity: 1.0

assignments:
  - task_id: T1
    resource_id: dev1
  - task_id: T2
    resource_id: dev2
  - task_id: T3
    resource_id: dev3
```

**Expected behavior**: Single-pass and two-pass deltas ≈ 0 (no contention means no reordering benefit).

**Fixture placement**: `tests/fixtures/test_fixture_abundant_resources.yaml`

### Acceptance Test Cases

1. **test_two_pass_criticality_ranking_matches_fixture_expectation**
   - Run contention_benchmark with `pass1_iterations=100` and fixed seed
   - Assert: CI(A1), CI(A2), CI(A3) all > 0.95 (critical)
   - Assert: CI(B1) < 0.5 (non-critical in this fixture)
   - Assert: Ranking order is [A1, A2, A3, ...] after sorting

2. **test_two_pass_no_constraint_violations**
   - Run contention_benchmark with `assignment_mode: criticality_two_pass`
   - Assert for each iteration:
     - All dependencies respected (no task starts before dependencies finish)
     - No resource capacity exceeded at any time
     - No task assigned to multiple resources simultaneously

3. **test_two_pass_makespan_improvement_on_contention**
   - Run contention_benchmark, single-pass vs. two-pass with 1000 iterations
   - Assert: `two_pass_mean_hours < single_pass_mean_hours` (improvement expected)
   - Assert: improvement is stable across 5 independent runs (fixed seed)

4. **test_two_pass_zero_delta_on_abundant_resources**
   - Run abundant_resources fixture
   - Assert: `delta_mean_hours ≈ 0` (±0.1 hours tolerance for sampling noise)
   - Assert: `delta_p80_hours ≈ 0`

5. **test_two_pass_determinism_paired_replay**
   - Run contention_benchmark twice with same seed; cache pass-1 durations
   - Assert: full critical path frequency arrays identical
   - Assert: delta values identical (bit-for-bit)

## Phase 7: Acceptance Tests for FR-042

Success criteria (using fixtures defined above):
- explicit tests prove:
  - mode configurable and default off,
  - pass-1 ranking computation matches expected CI values (test case #1),
  - pass-2 uses ranking and improves makespan on contention projects (test case #3),
  - no constraints violated on all fixtures (test case #2),
  - zero delta on no-benefit scenarios (test case #4),
  - deterministic paired replay produces bit-identical results (test case #5),
  - pass-delta reported in all exporters.

Files:
- `tests/test_simulation.py` (add: test cases #1–5 using fixtures)
- `tests/fixtures/test_fixture_contention.yaml`
- `tests/fixtures/test_fixture_abundant_resources.yaml`
- `tests/test_cli_output.py` (add: two-pass delta section assertions)
- `tests/test_exporters.py` (add: JSON/CSV/HTML traceability field presence)

Verify:
- `poetry run pytest tests/test_simulation.py tests/test_cli_output.py tests/test_exporters.py -n auto --no-cov`
- Validate: `tests/test_simulation.py::test_two_pass_criticality_ranking_matches_fixture_expectation`
- Validate: `tests/test_simulation.py::test_two_pass_no_constraint_violations`
- Validate: `tests/test_simulation.py::test_two_pass_makespan_improvement_on_contention`

Risk controls:
- acceptance fixtures with known contention topology (defined above),
- deterministic seed and expected ordering assertions,
- manual hand-calculation of fixture CI values included in test docstring for traceability.

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
- When two-pass mode is enabled, pass 1 SHALL run constrained scheduling and compute task criticality indices (CI) from pass-1 critical path membership frequency.
- CI(t) SHALL be defined as: (iterations where t appears in ANY critical path) / pass1_iterations, with value in range [0.0, 1.0].
- A task appears in a critical path if it is part of any path whose duration equals the project's critical path length in that iteration.
- Pass-1 ranking SHALL be deterministic for fixed seed and input, with tie-breaking by lexicographic task ID.
- Pass-1 computation SHALL include defensive assertion that all CI values are in [0.0, 1.0].

## FR-MPS-004: Pass-2 Priority Policy
- Pass 2 SHALL prioritize ready tasks by descending pass-1 criticality index CI(t).
- Equal-criticality ties SHALL be broken deterministically by lexicographic task ID (e.g., "Task_A" before "Task_B").
- Pass 2 SHALL use paired-replay cache to reuse sampled task durations from pass-1, ensuring deterministic deltas.
- Pass 2 SHALL preserve all existing hard constraints (dependencies, resource eligibility, max resources, calendar/sickness availability).

## FR-MPS-005: Constrained-Only Applicability
- Two-pass mode SHALL apply only when constrained scheduling is active.
- If constrained scheduling is inactive, the system SHALL run dependency-only scheduling and SHALL NOT attempt two-pass prioritization.

## FR-MPS-006: Deterministic Acceptance Behavior
- The system SHALL provide acceptance tests (using contention_benchmark and abundant_resources fixtures) demonstrating that two-pass mode does not violate dependency/resource constraints.
- The system SHALL provide deterministic tests showing stable pass ranking (test_two_pass_criticality_ranking_matches_fixture_expectation) and reproducible output for fixed seed (test_two_pass_determinism_paired_replay).
- The system SHALL provide a test (test_two_pass_no_constraint_violations) that asserts for each iteration: dependencies respected, no resource capacity exceeded, no task double-assigned.

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

## FR-MPS-011: Paired Replay Cache for Determinism
- The system SHALL implement a duration cache that stores sampled task durations from pass-1.
- Pass-2 SHALL reuse cached durations from pass-1 (not re-sample) to ensure deterministic delta reporting.
- The cache SHALL be keyed by (iteration_index, task_id) and retrieve SHALL raise KeyError if entry missing.
- The system SHALL assert that two consecutive runs with identical seed and pass1_iterations produce bit-identical critical path frequencies and deltas.

## FR-MPS-012: Pass-1 Iteration Budgeting and Warnings
- If `pass1_iterations` is greater than total simulation iterations, SHALL default to total iterations.
- If `pass1_iterations` is less than 100 and total iterations > 100, the system MAY emit a warning that pass-1 sample is too small.
- The system SHALL validate that `pass1_iterations > 0`; else reject with clear error message.

## Acceptance Criteria Matrix

- FR-034 addressed by: FR-MPS-001, FR-MPS-002, FR-MPS-003, FR-MPS-004, FR-MPS-011.
- FR-042 addressed by: FR-MPS-001, FR-MPS-003, FR-MPS-004, FR-MPS-006, FR-MPS-007, FR-MPS-011, FR-MPS-012.

## Conclusion

This feature is worth implementing for contention-heavy constrained schedules because it targets the exact failure mode of deterministic ID-ordered greedy dispatch: suboptimal resource use on high-criticality chains. The proposed architecture minimizes risk by preserving defaults, isolating policy logic, enforcing deterministic acceptance tests, and making deltas explicit for traceability.
