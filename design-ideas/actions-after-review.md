Version: 1.0.0

# Action Plan After Codebase Review

This document translates the review findings into an implementation-ready plan with priorities, detailed tasks, file-level changes, tests, rollout strategy, and acceptance criteria.

## 1. Scope and Objectives

The review identified six high-impact implementation gaps and several quality improvements:

1. Requirement mismatch in story point set (11 vs 13)
2. Missing environment-profile configuration selection (FR-012)
3. Non-pluggable distribution/risk architecture (NFR-008)
4. Exporters not honoring histogram config (`include_histogram`, `number_bins`)
5. NL parser limitations for ambiguous/unstructured text
6. Reporting quality improvements (content presentation/layout)

This plan prioritizes correctness and requirement alignment first, then architecture extensibility, then UX/reporting quality.

## 2. Execution Strategy

### 2.1 Prioritization

- P0: Correctness and requirement alignment defects that can cause user-visible inconsistency
- P1: Architectural changes required by explicit requirements and future velocity
- P2: UX/reporting/NL quality upgrades and optional analytics expansion

### 2.2 Delivery Principles

- Keep behavior backward-compatible unless requirement explicitly says otherwise.
- Introduce feature flags/default-off for potentially disruptive behavior.
- Land work in small PRs with explicit acceptance tests.
- Prefer additive schema changes over renames/deletions.

## 3. Workstreams


## P0-2: Honor Histogram Output Configuration in Exporters

### Problem

Exporters hardcode histogram bins and always include histogram payload/sections even when config disables it.

### Implementation Tasks

1. Thread `Config.output.number_bins` into all histogram generation calls.
2. Respect `Config.output.include_histogram` in JSON/CSV/HTML outputs.
3. Keep output stable when omitted: either absent key/section or null depending on exporter contract decision.
4. Add regression tests for enabled/disabled histogram behavior.

### Files

- src/mcprojsim/exporters/json_exporter.py
- src/mcprojsim/exporters/csv_exporter.py
- src/mcprojsim/exporters/html_exporter.py
- src/mcprojsim/cli.py (only if any display assumptions need sync)

### Tests to Add/Update

- tests/test_exporters.py:
  - histogram disabled => no histogram block/section
  - histogram enabled + custom bins => expected bin count
- tests/test_cli.py or tests/test_cli_output.py if CLI reflects histogram metadata expectations

### Acceptance Criteria

- `include_histogram: false` suppresses histogram output in all exporters.
- `number_bins` controls bin count in all exporters.
- Existing exporter tests still pass.

### Estimated Effort

1 day

---

## P1-1: FR-012 Environment-Based Configuration Profiles

### Problem

No native environment profile selection (`dev`, `prod`, team profiles), despite explicit requirement.

### Proposed Design

Add profile-aware config loading with precedence:

1. Base defaults
2. Base config file
3. Selected profile overlay
4. CLI explicit overrides

### Config Shape Proposal

```yaml
profiles:
  dev:
    simulation:
      default_iterations: 2000
  prod:
    simulation:
      default_iterations: 50000
```

### Implementation Tasks

1. Extend config schema with optional `profiles` mapping.
2. Add `Config.load_from_file(..., profile: str | None = None)` support.
3. Add CLI option (e.g., `--config-profile dev`).
4. Merge profile overlay with validation after merge.
5. Add clear errors for unknown profile names.

### Files

- src/mcprojsim/config.py
- src/mcprojsim/cli.py
- docs/configuration.md
- docs/user_guide/running_simulations.md

### Tests

- tests/test_config.py:
  - profile overlay success
  - unknown profile fails
  - profile + explicit override precedence
- tests/test_cli.py: profile selection wired through simulate path

### Acceptance Criteria

- Profile selection works and is validated.
- Precedence behavior is deterministic and documented.

### Estimated Effort

1.5-2.5 days

---

## P1-2: NFR-008 Pluggable Distribution and Risk Architecture

### Problem

Distribution/risk handling is hardcoded and not extensible as required.

### Architectural Goal

Replace hardcoded `if/elif` dispatch with registry + plugin contract.

### Phase Plan

#### Phase A: Distribution Registry and Built-ins

1. Add `DistributionPlugin` protocol.
2. Add registry module with `register/get/registered_names`.
3. Wrap existing triangular/lognormal as built-in plugins.
4. Migrate sampler dispatch to registry.

Files:

- src/mcprojsim/simulation/distributions.py
- src/mcprojsim/simulation/distribution_registry.py (new)
- src/mcprojsim/simulation/builtin_distributions.py (new)
- src/mcprojsim/simulation/__init__.py

#### Phase B: First New Distribution (PERT)

1. Implement PERT plugin and config block.
2. Add parser/model acceptance for `distribution: pert`.
3. Add docs and examples.

Files:

- src/mcprojsim/config.py
- src/mcprojsim/models/project.py
- docs/user_guide/task_estimation.md
- examples/sample_config.yaml

#### Phase C: Risk Plugin Registry

1. Add `RiskPlugin` contract and registry.
2. Convert current percentage/absolute to built-ins.
3. Introduce optional stochastic impact plugin (default off).

Files:

- src/mcprojsim/simulation/risk_evaluator.py
- src/mcprojsim/simulation/risk_registry.py (new)
- src/mcprojsim/models/project.py (if schema additions needed)

### Tests

- tests/test_distribution_contract.py (new, registry-driven)
- tests/test_distribution_pert.py (new)
- tests/test_distribution_integration.py (new)
- tests/test_risk_model_contract.py (new)
- Existing simulation/parser/export tests updated as needed

### Acceptance Criteria

- No hardcoded distribution dispatch remains in production path.
- New distribution can be added with no sampler branch edits.
- Contract tests automatically cover all registered plugins.

### Estimated Effort

4-7 days (distribution + risk)

---

## P1-3: Progress Tracking Requirement Reconciliation (FR-013)

### Problem

Requirement says 10% OR every 1000 iterations; implementation currently follows 10% buckets.

### Options

1. Update implementation to include 1000-iteration cadence fallback.
2. Update requirement text to current behavior if accepted.

### Implementation Tasks (if option 1)

1. Add combined condition:
   - report at 10% boundary
   - or every 1000 completed iterations
2. Preserve non-TTY behavior and avoid excessive spam.

### Files

- src/mcprojsim/simulation/engine.py
- docs/mcprojsim_reqs.md (if wording adjustments needed)

### Tests

- tests/test_simulation.py progress-reporting behavior with controlled iterations

### Estimated Effort

0.5 day

---

## P2-1: NL Parser Capability Expansion

### Current Status

Good for semi-structured input; weak for ambiguous/unstructured prose and confidence/provenance reporting.

### Desired Improvements

1. Clarification-first mode:
   - return explicit ambiguity questions instead of silent assumptions.
2. Field-level provenance:
   - source span and parser confidence per extracted field.
3. Unknown-line diagnostics:
   - collect and report ignored lines.
4. Incremental patch mode for updating existing YAML.

### Implementation Tasks

1. Extend parsed model to include parse diagnostics metadata.
2. Add parser output mode (`strict`, `lenient`, `clarify`).
3. Add MCP tool response shape for clarification questions.
4. Add confidence/provenance in generated YAML metadata comments or separate diagnostics object.

### Files

- src/mcprojsim/nl_parser.py
- src/mcprojsim/mcp_server.py
- tests/test_nl_parser.py
- tests/test_mcp_server.py
- docs/user_guide/nl_input.md (new or expanded)

### Tests

- Ambiguous phrase fixtures with expected clarification prompts
- Round-trip parse diagnostics assertions
- Existing deterministic parser tests unchanged in strict mode

### Estimated Effort

3-5 days

---

## P2-2: Reporting Content and Layout Improvements

### Problem

Content is rich but visual density and responsiveness are weak for larger outputs.

### Improvements

1. Responsive table wrappers and mobile-safe typography.
2. Print stylesheet for HTML export.
3. Optional compact mode and section collapse.
4. Stronger visual hierarchy for key percentiles/risk diagnostics.

### Files

- src/mcprojsim/exporters/html_exporter.py
- docs/user_guide/reports.md

### Tests

- tests/test_exporters.py snapshot assertions for major sections
- Optional visual regression baseline (if introduced)

### Estimated Effort

1.5-3 days

---

## P2-3: Statistical Analysis Enhancements

### Candidate Analyses to Add

1. Calibration/backtesting
   - empirical coverage of P50/P80/P90
2. Tail-risk metrics
   - Expected Shortfall / CVaR for schedule overrun
3. Forecast reliability score
   - combined bias + calibration + sharpness indicator
4. Scenario deltas
   - baseline vs variants with percentile deltas

### Implementation Tasks

1. Add analysis module for backtesting/reliability metrics.
2. Add result model fields and exporter sections.
3. Add CLI subcommand for backtest mode.

### Files

- src/mcprojsim/analysis/ (new modules)
- src/mcprojsim/models/simulation.py
- src/mcprojsim/exporters/*.py
- src/mcprojsim/cli.py

### Tests

- Unit tests for metric formulas
- Integration tests against synthetic calibrated/biased fixtures

### Estimated Effort

4-8 days (can be phased)

## 4. Cross-Cutting Test Plan

## 4.1 Baseline Test Matrix

For each workstream, run:

1. Focused unit tests
2. Parser/model integration tests
3. Exporter tests
4. Full check pipeline (`make check`)

## 4.2 New Reusable Contract Suites

1. Distribution plugin contract suite (registry parameterized)
2. Risk plugin contract suite
3. NL parser ambiguity suite
4. Export output schema consistency suite

## 4.3 Regression Strategy

- Keep golden fixtures for:
  - sample project parsing
  - JSON/CSV output schema shape
  - HTML major section presence
- Add changelog entries for any payload-level changes.

## 5. Milestone Plan

## Milestone M1 (P0 completion)

- Story point set aligned
- Histogram config honored in exporters

Exit gate:

- all P0 tests green
- `make check` passes

## Milestone M2 (P1 core)

- Environment profile config support
- Distribution plugin architecture + PERT
- Risk plugin scaffolding

Exit gate:

- contract tests for distribution/risk pass
- no regressions in existing simulation outputs

## Milestone M3 (P2 quality)

- NL parser clarification/provenance improvements
- HTML reporting layout improvements
- optional statistical enhancements started

Exit gate:

- MCP/NL acceptance tests updated
- report usability review complete

## 6. Risks and Mitigations

1. Risk: schema churn breaks existing project files.
   - Mitigation: additive fields, fallback defaults, migration notes.

2. Risk: plugin architecture introduces runtime misconfiguration.
   - Mitigation: strict registration validation + contract tests.

3. Risk: NL parser expansion increases false positives.
   - Mitigation: mode-based behavior (`strict` default), ambiguity prompts.

4. Risk: exporter shape changes break downstream consumers.
   - Mitigation: keep existing keys, add new keys additively, version notes.

## 7. Definition of Done (Program-Level)

Program is considered complete when:

1. P0 and P1 items are merged and tested.
2. Requirement and implementation docs are aligned for FR-012, FR-013, NFR-008.
3. Exporters honor output config controls consistently.
4. Distribution/risk extensibility is implemented with reusable contract tests.
5. `make check` passes on clean checkout.
6. User docs include migration notes and examples for new capabilities.

## 8. Suggested PR Breakdown

1. PR-1: Story point set alignment + docs/tests
2. PR-2: Histogram config honoring across exporters + tests
3. PR-3: Config profiles (FR-012) + CLI wiring + tests
4. PR-4: Distribution registry + built-ins + contract tests
5. PR-5: PERT distribution + docs + examples
6. PR-6: Risk registry scaffold + stochastic risk plugin (optional default-off)
7. PR-7: NL parser ambiguity/provenance mode
8. PR-8: HTML report layout and responsiveness improvements

## 9. Immediate Next Actions

1. Confirm canonical story point set decision (11 vs 13).
2. Implement PR-1 and PR-2 first (highest correctness impact, lowest risk).
3. Start FR-012 config profile design branch with schema tests first.
4. Parallelize architectural prototype for distribution registry in a feature branch.
