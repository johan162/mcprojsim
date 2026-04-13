# Onboarding New Users to mcprojsim

This directory contains the report and experiments from two new users trying to familiarize themselves with mcprojsim by following the documentation in order. The goal is to identify areas where the documentation could be improved to reduce confusion and errors for new users.

---

## Synthesized Findings: Summary of Both Learning Reports

Two independent new users (`learning01/01_report01.md` and `learning02/01_report02.md`) completed systematic walkthroughs of the full Quick Start and User Guide documentation. This section synthesizes their findings, with special emphasis on issues **both users found equally confusing**.

### Key Takeaways

The simulation engine is solid and feature-complete. However, documentation contains **critical inaccuracies** (wrong defaults, stale example outputs) and **moderate clarity gaps** (confusing schema patterns, missing conceptual explanations) that derail new users early in the learning journey. Fixing the critical issues and clarifying 5–6 moderate issues would eliminate most first-user friction.

---

## Critical Issues (Both Users Affected)

### 🔴 1. Uncertainty Factor Defaults Are Documented Incorrectly
FIXED
**Severity**: CRITICAL  
**Both Users**: ✅ YES (Report 1 found defaults confusing; Report 2 found concrete evidence of wrongness)

**The Problem**:
- **Documentation claims**: Default uncertainty factors are `team_experience: medium (1.0×)`, `requirements_maturity: medium (1.15×)`, `technical_complexity: medium (1.20×)`, etc., with a compound multiplier of ~1.587× (59% stretch).
- **Actual behavior**: Defaults are `requirements_maturity: high (1.0×)`, `technical_complexity: low (1.0×)`, `integration_complexity: low (1.0×)`, yielding a compound multiplier of **1.0× (no stretch)**.
- **Impact on User**: A new user estimates a task at 20/30/50 hours. The doc claims Mean ~42h; the tool produces ~26h. The user spends time debugging, thinking the tool is broken.

**Concrete Evidence** (Report 2):
```
Documented example shows:  Mean: 42.23 hours, Median: 38.31 hours, P80: 55.84 hours
Actual with --seed 42:    Mean: 26.56 hours, Median: 27.20 hours, P80: 34.94 hours
Discrepancy:              ~37% lower across all percentiles
```

**Recommended Fix**:
- Update `docs/user_guide/uncertainty_factors.md` lines ~117–133 to reflect actual defaults.
- Update the compound multiplier claim from 1.587× to 1.0×.
- Re-generate all example outputs in `docs/user_guide/your_first_project.md` (all 6 steps) with correct defaults.
- Consider adding a version note: "Exact outputs vary with mcprojsim version due to config changes; expected ranges are ±10%."

---

### 🔴 2. Stale Example Outputs Throughout "Your First Project" Tutorial
FIXED
**Severity**: CRITICAL  
**Both Users**: ✅ YES (Report 1 noted discrepancies; Report 2 quantified them)

**The Problem**:
- The tutorial shows expected output from running specific commands with `--seed 42`.
- All shown values (Mean, Median, P50, P80, P90, dates) are 30–40% higher than actual.
- This is the **first guided experience** a new user has; seeing drastically different numbers immediately undermines trust.

**Impact**:
- New user wastes time checking for typos or re-installing the tool.
- New user questions whether the documentation is maintained.

**Recommended Fix**:
- Re-run all 6 steps of "Your First Project" with actual code, capture output with `--seed 42`, and update the documented expected values.
- Add a note at the top of the section: "Expected outputs were generated with mcprojsim v0.13.0. Version differences may produce ±5–10% variations."

---

## Moderate Issues (High Priority, Both Users Affected)

### ⚠️ 3. Task Estimation Schema Patterns Are Easy to Confuse

**Severity**: MODERATE  
**Both Users**: ✅ YES (both hit validation errors trying wrong field combinations)

**The Problem**:
- New users try lognormal with `min/max/confidence` (wrong) instead of `low/expected/high` + `distribution: lognormal` (correct).
- New users try symbolic estimates with explicit `unit: "hours"` (forbidden) because it's intuitive.
- Neither error has helpful guidance in the docs.

**Recommended Fix**:
- Add a "Common Mistakes" callout in `docs/user_guide/task_estimation.md`:
  ```
  ❌ Do NOT use:
  estimate:
    distribution: lognormal
    min: 3
    max: 12
    confidence: 80
  
  ✅ Use instead:
  estimate:
    distribution: lognormal
    low: 3
    expected: 8
    high: 20
    unit: "days"
  ```
- Add a note: "Symbolic estimates (T-shirt, story points) do NOT accept a `unit` field; unit is determined by configuration."

---

### ⚠️ 4. Risk Impact Syntax Is Underdocumented
FIXED
**Severity**: MODERATE  
**Both Users**: ✅ YES (both initially wrote `unit` at top level of risk, which is invalid)

**The Problem**:
- Numeric `impact: 3` looks unitless, but the unit is implicit (hours).
- Structured `impact: {type: "absolute", value: 3, unit: "days"}` is more explicit but the transition between the two forms isn't clear.

**Recommended Fix**:
- In `docs/user_guide/project_files.md` (risks section), add a compact side-by-side "Do This / Not This" snippet:
  ```
  ✅ Correct:
  risks:
    - id: "risk_001"
      name: "Delay"
      probability: 0.2
      impact:
        type: "absolute"
        value: 3
        unit: "days"
  
  ❌ Wrong:
  risks:
    - id: "risk_001"
      name: "Delay"
      probability: 0.2
      impact: 3
      unit: "days"  ← unit goes inside impact, not outside
  ```

---

### ⚠️ 5. CLI Flags and Config Keys Use Inconsistent Names
FIXED
**Severity**: MODERATE  
**Both Users**: ✅ YES (both tried `output.number_bins` in config, matching `--number-bins` CLI flag)

**The Problem**:
- CLI flag: `--number-bins`
- Config key: `output.number_bins` (not `output.histogram_bins`)
- Similar confusion likely for other flag↔config mappings.

**Recommended Fix**:
- Add a small table in `docs/user_guide/configuration.md`:
  | CLI Flag | Config Path | Notes |
  |----------|------------|-------|
  | `--number-bins` | `output.number_bins` | Number of bins in distribution histogram |
  | `--iterations` | `simulation.default_iterations` | Default Monte Carlo iterations |
  | (continue for other mappings) |

---

### ⚠️ 6. Constrained Scheduling Results Are Unexpectedly Much Longer

**Severity**: MODERATE  
**Both Users**: ✅ YES (both found the jump surprising and confusing)

**The Problem**:
- Dependency-only (naive) scheduling: P50 might be 100 hours.
- Constrained scheduling with same tasks: P50 might be 400 hours.
- New users assume "something is wrong" rather than understanding why.

**Recommended Fix**:
- Add a callout box early in `docs/user_guide/constrained_scheduling.md`:
  ```
  ⚠️  Constrained schedules are often much longer than dependency-only estimates.
  
  Example: A 3-person team working on 10 tasks in parallel (dependency-only) 
  might complete in 100 hours. The same team with resource constraints might 
  need 400 hours because resources unavailability creates wait time.
  
  This is NOT a bug; it's a more realistic picture of how work actually gets done.
  ```

---

### ⚠️ 7. Staffing Recommendations Look Counterintuitive

**Severity**: MODERATE  
**Both Users**: ✅ YES (both saw results recommending 1 person for multi-task projects and questioned correctness)

**The Problem**:
- Many projects get "1 people recommended (mixed team)" even with 5+ tasks.
- New users assume larger projects → larger team; they don't understand that serial critical paths + overhead can make large teams inefficient.

**Recommended Fix**:
- In `docs/user_guide/interpreting_results.md`, add a worked example:
  ```
  Example: A serial 4-task project
  
  Tasks: Design (5 days) → Backend (10 days) → Frontend (8 days) → Test (3 days)
  Total parallelism ratio: 1.0 (entirely serial)
  Recommended team size: 1 person
  
  Why? Adding a second person increases communication overhead (Brooks's Law) 
  without any parallelism benefit, so the schedule actually worsens. The tool 
  correctly recommends staying with 1.
  ```

---

## Moderate Issues (High Priority, Report 2 Only)

### ⚠️ 8. CLI Flag `--quiet` Is Misleadingly Documented

**Severity**: MODERATE  
**Reported By**: Report 2

**The Problem**:
- `docs/quickstart.md` says `--quiet` is for "suppress progress output."
- Actual behavior: `--quiet` suppresses **all results** (not just progress bars).
- New user wanting less noise but still wanting to see output uses `--quiet` and gets nothing.
- Correct flag for "less output, more results" is `--minimal`, which is underdiscovered.

**Recommended Fix**:
- In `docs/quickstart.md` and `docs/user_guide/running_simulations.md`, add clarity:
  | Flag | Output |
  |------|--------|
  | (none) | Full output with progress bars |
  | `--minimal` | Key results only (no progress bars, no detailed tables) |
  | `-q` / `--quiet` | Timing and version only (almost no results) |
  | `-qq` | Completely silent |

---

### ⚠️ 9. T-Shirt Size Default Category Is Misidentified

**Severity**: MODERATE  
**Reported By**: Report 2

**The Problem**:
- `docs/user_guide/your_first_project.md` (Step 5) claims: "defaults bare sizes like M to the **epic** category."
- Actual: Default category is **story** (confirmed by `mcprojsim config show`).
- Impact: M/epic ≈ 449h vs M/story ≈ 113h — a 4× difference.

**Recommended Fix**:
- Update the doc to say "story" (or grep all references to "default category" and make them consistent).

---

### ⚠️ 10. Two-Pass Scheduling Lacks Conceptual Explanation

**Severity**: MODERATE  
**Reported By**: Report 2

**The Problem**:
- Doc explains *how* to enable it (`--two-pass`) but not *why* results differ.
- Report 2 experiment: Single-pass P50 = 290h, two-pass P50 = 220h (24% improvement).
- Without conceptual explanation, users don't know if they should use it.

**Recommended Fix**:
- In `docs/user_guide/constrained_scheduling.md`, add 1–2 paragraphs:
  ```
  ### How Two-Pass Mode Differs
  
  **Single-pass mode** assigns resources to tasks in a fixed priority order 
  as they become ready.
  
  **Two-pass mode**:
  1. Pass 1: Run a quick simulation to identify which tasks are most frequently 
     on the critical path.
  2. Pass 2: Assign resources with priority given to critical-path tasks, 
     reducing bottleneck delays.
  
  Result: Two-pass typically produces 10–30% shorter schedules because it 
  optimizes for the true bottleneck. Use it when you want the most realistic 
  schedule given resource constraints.
  ```

---

### ⚠️ 11. Natural Language Parser Has Known Quality Issues

**Severity**: MODERATE  
**Reported By**: Report 2

**The Problem**:
- Generated task names contain leftover parentheses: `"Requirements Analysis ()"`.
- Inline size extraction fails: "Size XL" isn't recognized.
- Dependency matching doesn't support fuzzy references: user must say "Task 1" not "requirements."
- Users encounter these immediately and think the tool is buggy.

**Recommended Fix**:
- Fix the parser to strip trailing parentheses and improve size detection.
- In `docs/user_guide/nl_processing.md`, add a "Known Limitations" section:
  ```
  Known Limitations:
  - Task names may retain empty parentheses "()" in output; edit manually if needed.
  - Size formats supported: "Size M", "S", "epic.M". "XL" alone may not parse.
  - Dependencies must reference exact task numbers: "depends on Task 1" works; 
    "depends on requirements" does not. (Fuzzy matching is not yet supported.)
  ```

---

## Minor Issues (Medium Priority, Report 2 Only)
FIXED
### 💡 12. Cost Fields Missing from Project Files Reference

**Location**: `docs/user_guide/project_files.md`

**The Problem**:
- Cost-related fields (`default_hourly_rate`, `fixed_cost`, etc.) are documented in `cost_handling.md` but not listed in the project files reference.
- Report 2 user tried `cost_per_hour` (seemed intuitive) and got validation error.

**Recommended Fix**:
- Add a "Cost Fields" subsection to the project files quick reference, or add a cross-reference link to `cost_handling.md` with field names listed.

---

### 💡 13. Missing Cross-References Between Related Topics

**The Problem**:
- Cost fields not linked from project_files.md.
- Two-pass mode is in constrained_scheduling.md but relevant to running_simulations.md.
- Uncertainty factors interact with task_estimation but neither page links to the other.

**Recommended Fix**:
- Add "See Also:" sections at the bottom of related pages.

---

### 💡 14. JSON Export Structure Undocumented

**The Problem**:
- `--format json` works but the output schema is not documented.
- Users wanting to integrate mcprojsim into pipelines have no reference.

**Recommended Fix**:
- Add a schema example or reference to JSON export in `docs/user_guide/running_simulations.md`.

---

### 💡 15. Missing "Common Patterns" or Cookbook Section

**The Problem**:
- After the tutorial, users need copy-paste YAML snippets for common patterns:
  - "How do I model a 3-person team sharing work?"
  - "How do I add holidays for a US team?"
  - "How do I set up cost tracking?"

**Recommended Fix**:
- Add a new "Common Patterns" or "Cookbook" page with practical examples.

---

## Implementation Priority

### Priority 1 (Critical, Fix Now)
1. **Correct uncertainty factor defaults** in `uncertainty_factors.md` (5–10 min change, massive impact).
2. **Re-generate "Your First Project" example outputs** with actual code and current defaults (30 min work, blocks new users immediately).
3. **Add "Do this / Not this" snippets** for task estimation schema and risk impact syntax (15 min, prevents 70% of early validation errors).

### Priority 2 (High, Fix Soon)
4. Add CLI-to-config flag mapping table.
5. Add "Why constrained is longer" callout to constrained scheduling docs.
6. Clarify `--quiet` vs `--minimal` vs default output.
7. Update T-shirt default category ("story" not "epic").
8. Add conceptual explanation for two-pass mode.

### Priority 3 (Medium)
9. Document NL parser limitations.
10. Add cost field references to project_files.md.
11. Add "Common Patterns" cookbook.
12. Improve cross-references between pages.

---

## What Works Well (Both Users Agree)

- ✅ Simulation engine is solid and reproducible.
- ✅ Progressive "Your First Project" structure is excellent pedagogy.
- ✅ Constrained scheduling system is powerful and correct.
- ✅ CLI design is clean and intuitive (`--table` flag is great).
- ✅ HTML reports are beautiful and compelling for stakeholder communication.
- ✅ Validation error messages are generally clear and helpful.

