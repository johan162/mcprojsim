# mcprojsim Learning Walkthrough Report — Learning3

**Reviewer:** Simulated new, intelligent user  
**Scope:** All 16 chapters under `docs/user_guide/` (sequentially numbered 01–16) plus `docs/grammar.md`  
**Tool version:** mcprojsim 0.13.0, Python 3.13, Poetry-managed installation  
**Experiment directory:** `design-ideas/new-user/learning3/`

---

## Executive Summary

The user guide has been substantially improved since its initial release. The chapter sequencing is logical, the grammar document is a useful reference, and most core features work as documented. However, several issues were found during systematic hands-on testing that would significantly impede a new user:

- **One confirmed code/doc discrepancy** (field aliases) that causes silent documentation mismatch
- **Two significant stale example outputs** (chapters 11 and 13)
- **One missing CLI flag** from the CLI reference (chapter 12)
- **Misleading inline comment** about `--quiet` behaviour
- **Naming inconsistency** between `simulate --config` and `config --config-file`
- **Raw Python enum name** in sprint-planning output (UI polish issue)

---

## Findings by Severity

### 🔴 CRITICAL — Code/Doc Discrepancy

#### C1 — Field Aliases `min` / `most_likely` / `max` Rejected by Validator

**Chapters:** `05_task_estimation.md` (lines 38–48), `grammar.md` (§ TaskEstimate table)  
**Description:** Both documents state that `min`, `most_likely`, and `max` are valid aliases for `low`, `expected`, and `high` respectively in explicit task estimates. The Pydantic model (`src/mcprojsim/models/project.py`) does define `AliasChoices` for them. However, the YAML parser layer (`parsers/yaml_parser.py`) performs a strict unknown-field check *before* Pydantic validation runs, and rejects these names outright with an "Unknown field" error.

**Tested with (`05_task_estimation.yaml` snippet):**
```yaml
tasks:
  - name: Test Task
    estimate:
      min: 5
      most_likely: 10
      max: 20
      unit: days
```
**Actual error:**
```
Validation Error: task 'Test Task': Unknown field(s) in estimate: {'min', 'most_likely', 'max'}
```

**Impact:** High. A user who reads the documentation and types `min`/`most_likely`/`max` will receive a confusing validation error that contradicts the documentation. The grammar document also needs updating.

**Fix:** Either (a) add `min`, `most_likely`, `max` to the YAML parser's accepted field set for estimates, or (b) remove them from the documentation if they are not intended to be supported.

---

### 🟠 HIGH — Stale/Misleading Documentation

#### H1 — `--target-budget` Flag Missing from Chapter 12 CLI Reference

**Chapter:** `12_running_simulations.md` (options table, lines 126–146)  
**Description:** Chapter 07 (`07_cost_handling.md`) introduces `--target-budget` as a core cost feature, with examples. But the complete CLI reference in chapter 12 does **not** list `--target-budget` in the `mcprojsim simulate` options table at all. A user reading chapter 12 as a reference would never know this flag exists.

**Tested:** `mcprojsim simulate project.yaml --target-budget 40000` works correctly (output section appears), so the feature is implemented. It is simply absent from the reference table.

**Fix:** Add `--target-budget AMOUNT` to the simulate options table in chapter 12.

---

#### H2 — Chapter 13 Example Shows Stale Version Number

**Chapter:** `13_interpreting_results.md` (line 12)  
**Description:** The example output block at the top of the chapter shows:
```
mcprojsim, version 0.3.0
```
Current version is 0.13.0. The discrepancy is jarring and makes the documentation feel abandoned.

**Fix:** Update the version number in the example (or use a placeholder like `x.y.z`).

---

#### H3 — Chapter 11 Two-Pass Example Output Is Stale

**Chapter:** `11_multi_phase_simulation.md` (lines 142–220)  
**Description:** The chapter instructs the reader to run `examples/contention.yaml` with `--seed 1234` and shows expected output:
```
Single-pass Mean: 567.49 hours
Two-pass Mean:   470.91 hours (17.0% improvement)
```
Actual output with v0.13.0 using the identical command:
```
Single-pass Mean: 360.44 hours
Two-pass Mean:   298.03 hours (~17.3% improvement)
```
The percentage improvement is approximately correct, but the absolute numbers differ substantially (~37% lower). No version disclaimer appears in this chapter (unlike chapter 01 which has a note about version variance).

**Fix:** Update the example output to match the current version, or add a disclaimer that "numbers will vary by version" as chapter 01 does.

---

#### H4 — `--quiet` Inline Comment Is Misleading

**Chapter:** `12_running_simulations.md` (line 169)  
**Description:** The examples section shows:
```bash
# Quiet mode (suppress progress bars)
mcprojsim simulate project.yaml --quiet
```
The comment "suppress progress bars" is significantly misleading. In practice, `--quiet` (`-q`) suppresses the entire simulation results section — statistics, confidence intervals, critical paths, risk impact, staffing — leaving only the version line and timing. Progress bars are suppressed too, but that is a side effect, not the primary behaviour.

**Tested:** `-q` shows only:
```
mcprojsim, version 0.13.0
Simulation time: 0.XX seconds
Peak simulation memory: XX MiB
```

**Fix:** Change the comment to `# Quiet mode (suppress simulation results output)` and clarify the description in the options table accordingly.

---

### 🟡 MODERATE — Usability / Confusion Issues

#### M1 — Step 5 T-Shirt Walkthrough Conflates Two Different Configurations

**Chapter:** `03_your_first_project.md` (Step 5 section, lines ~676–716)  
**Description:** The chapter first shows an inline YAML example with T-shirt sizes (XS, S, M), then immediately instructs the user to run `examples/tshirt_walkthrough_project.yaml --config examples/tshirt_walkthrough_config.yaml`. The inline YAML is structurally identical to the examples file, so a reader may assume running their own copy of the inline YAML (without the examples config) will give the same output.

**However:** The examples config file uses tiny custom size values (M = 5h, XL = 10h) that are completely different from the built-in defaults (M = 60h story points). A user running their own file without the config gets **~114 hours** while the doc shows **~9.67 hours** from the examples command.

**Fix:** Either (a) explicitly tell the reader "run the examples file with its config, not your own copy", or (b) after showing the examples output, show what happens with the default config so the contrast is clear and expected.

---

#### M2 — `config --config-file` vs `simulate --config` Naming Inconsistency

**Chapter:** `12_running_simulations.md` (lines 327, 129)  
**Description:** The two subcommands that accept a custom config file use different flag names:
- `mcprojsim simulate` uses `--config` / `-c`
- `mcprojsim config` uses `--config-file` / `-c`

Additionally, `mcprojsim config --generate` writes to `~/.mcprojsim/config.yaml` (template), but the auto-loaded user default is `~/.mcprojsim/configuration.yaml` — different filenames. A user running `--generate` and expecting auto-load will be confused.

**Fix:** Align flag names (`--config` everywhere, or `--config-file` everywhere). Also add a clear warning in the `config` section that the generated file must be *renamed* to `configuration.yaml` to be picked up automatically (the current note is subtle and easy to miss).

---

#### M3 — Sprint Planning Output Shows Raw Python Enum Name

**Chapter:** `09_sprint_planning.md` (output examples)  
**Description:** When sprint planning is active and `removed_work_treatment` is set, the output includes:
```
Removed Work Treatment: RemovedWorkTreatment.CHURN_ONLY
```
This exposes a raw Python enum class path to the user. The expected output would be something like `churn_only` or `Churn Only`. A new user has no way to interpret what `RemovedWorkTreatment.CHURN_ONLY` means without reading the source code.

**Fix:** Format enum values using their `.value` attribute or apply a user-friendly formatter in the output rendering code.

---

#### M4 — Constrained Scheduling Diagnostics Are Unexplained

**Chapter:** `10_constrained_scheduling.md` (diagnostics section)  
**Description:** When running resource-constrained scheduling, the output includes two fields that a new user finds contradictory:
```
Average Resource Wait: 0.00h
Calendar Delay Contribution: 651.95h
```
The first says "no waiting", the second says "651 hours of calendar delay". The user is left to guess whether this is a bug or two different concepts. The docs do not explain what "Calendar Delay Contribution" measures (working vs calendar time gaps) or why it can be large when average wait is zero.

**Fix:** Add a glossary-style explanation in the constrained scheduling chapter: "Resource Wait time" measures how long tasks are held waiting for an available resource, while "Calendar Delay Contribution" measures elapsed calendar time beyond active working hours (weekends, off-hours, etc.).

---

#### M5 — NL Parser Artifact `()` in Task Names Is Acknowledged but Jarring

**Chapter:** `15_nl_processing.md` (example output)  
**Description:** The NL parser produces output with `()` parenthetical fragments in task names, for example:
```
Task: Implement backend REST API ()
Task: Implement backend REST API (probably
```
The documentation actually shows these artifacts in the example output, which means the documentation is technically accurate. But showing these artifacts as expected output sets a low bar for quality. A new user running this will think something is broken even after reading the docs.

**Fix:** If this is a known parser limitation, add a note: "The NL parser sometimes leaves parenthetical fragments in task names; review generated YAML before running a simulation." Also consider a parser cleanup step that strips malformed trailing fragments.

---

### 🟢 POSITIVE — What Works Well

The following areas were tested and work exactly as documented:

- **Basic simulation** (chapter 01): Two-task project runs immediately; output format matches documented format closely.
- **Your First Project steps 1–4**: The numerical output in the step-by-step walkthrough matches actual output well (within expected Monte Carlo variance).
- **Uncertainty factors** (chapter 04): Compound multiplier formula is correct; all five levels behave as documented; default "medium" correctly gives 1.0× multiplier.
- **Risk modeling** (chapter 06): Both task-level and project-level risks work; risk impact section appears correctly in output.
- **Cost estimation** (chapter 07): `default_hourly_rate`, `overhead_rate`, `fixed_cost`, `cost_impact` on risks all work; `--target-budget` analysis section appears correctly.
- **Story points and T-shirt sizes** (chapter 05): The primary fields `low`/`expected`/`high` work correctly; T-shirt and story-point syntaxes work; `unit` field correctly enforced.
- **Sprint planning** (chapter 09): Velocity models, sprint history, `removed_work_treatment` all function correctly.
- **Two-pass scheduling** (chapter 11): Produces real improvement; falls back gracefully to single-pass when no named resources are defined (as documented).
- **Configuration system** (chapter 14): YAML config merges onto defaults correctly; partial overrides work; `mcprojsim config --config-file` displays merged configuration.
- **CLI export flags** (chapter 12): `--output-format json,csv,html`, `--seed`, `--target-date`, `--table`, `--minimal` all work as documented.
- **`mcprojsim generate`** (chapter 15): NL-to-YAML generation works; the grammar is followed; generated output matches what the doc shows.

---

## Findings by Chapter

### Chapter 01 — Getting Started
- ✅ Quick start works out of the box
- ⚠️ Version number and output numbers differ from doc (0.12.0 → 0.13.0, Mean 126.93h → 90.65h) — *doc has disclaimer, good*

### Chapter 02 — Introduction
- ✅ Conceptual overview is accurate and well-written

### Chapter 03 — Your First Project
- ✅ Steps 1–4 match documented output well
- ⚠️ **Step 5 T-shirt walkthrough [M1 above]**: Inline YAML + examples/ file causes output confusion due to different config contexts

### Chapter 04 — Uncertainty Factors
- ✅ All five levels documented correctly
- ✅ Compound multiplier formula verified correct
- ✅ Default levels all produce 1.0× multiplier (as documented)

### Chapter 05 — Task Estimation
- 🔴 **Field aliases `min`/`most_likely`/`max` rejected [C1 above]**: Documented as valid but actually rejected by validator
- ✅ All other estimation methods (explicit, T-shirt, story points, combined) work correctly
- ✅ `unit` field correctly enforced (rejected when using T-shirt/story-point methods)

### Chapter 06 — Risks
- ✅ All risk features work as documented
- ✅ Risk impact analysis section appears in output

### Chapter 07 — Cost Handling
- ✅ All cost fields work correctly
- ✅ `--target-budget` analysis works
- ⚠️ **`--target-budget` not listed in chapter 12 [H1 above]**

### Chapter 08 — Project Files (Grammar Reference)
- 🔴 **Field aliases listed in grammar but rejected [C1 above]** (grammar.md, TaskEstimate table)
- ✅ Otherwise accurate reference for all documented fields

### Chapter 09 — Sprint Planning
- ✅ Sprint history, velocity models, removed work treatment all work
- 🟡 **Raw enum name in output [M3 above]**: `RemovedWorkTreatment.CHURN_ONLY` shown instead of user-friendly value

### Chapter 10 — Constrained Scheduling
- ✅ Resource-constrained scheduling works
- ✅ Calendar-aware scheduling works
- 🟡 **Diagnostics unexplained [M4 above]**: "Average Resource Wait: 0.00h" + "Calendar Delay Contribution: 651.95h" appears contradictory without explanation

### Chapter 11 — Multi-Phase / Two-Pass Simulation
- ✅ Feature works correctly
- 🟠 **Stale example output [H3 above]**: Doc shows 567h→471h; actual with same file+seed is 360h→298h

### Chapter 12 — Running Simulations (CLI Reference)
- 🟠 **`--target-budget` missing from options table [H1 above]**
- 🟠 **`--quiet` comment misleading [H4 above]**: Says "suppress progress bars", actually suppresses all results
- 🟡 **`config --config-file` vs `simulate --config` [M2 above]**: Inconsistent flag names

### Chapter 13 — Interpreting Results
- 🟠 **Stale version number [H2 above]**: Shows `version 0.3.0` in example output
- ✅ Conceptual explanations of statistics, percentiles, and critical paths are clear and accurate

### Chapter 14 — Configuration
- ✅ Config merge behaviour documented correctly
- ✅ T-shirt size customisation works
- 🟡 **`--generate` writes `config.yaml` but auto-load needs `configuration.yaml` [M2 above]**: Naming difference buried in a note

### Chapter 15 — NL Processing / Generate Command
- ✅ `mcprojsim generate` works as documented
- 🟡 **Parser artifacts in task names [M5 above]**: `()` fragments appear in output; doc shows them as expected but doesn't warn users
- ✅ Generated YAML is syntactically valid and can be simulated immediately

### Chapter 16 — MCP Server
- ✅ Installation and usage instructions appear accurate
- ✅ Tool inventory table is comprehensive

---

## Suggested Improvements to Documentation

1. **Add a "Known Limitations" section** to chapter 05 (or the grammar) listing fields that appear in models but are not yet parsed (if aliases are intentionally unimplemented).

2. **Add version disclaimer to chapter 11** (two-pass): "Example output reflects version X.Y.Z; numbers will vary."

3. **Update version number in chapter 13** example output.

4. **Add `--target-budget` to chapter 12** options table.

5. **Clarify `--quiet` comment** in chapter 12 (line 169).

6. **Align `--config` flag names** between `simulate` and `config` subcommands (or document the difference explicitly).

7. **Rename auto-load file** to `config.yaml` to match `--generate` output, or add a callout box in chapter 14 clearly stating the rename step.

8. **Add diagnostics glossary** to chapter 10 explaining Resource Wait vs Calendar Delay Contribution.

9. **Chapter 03 Step 5**: Add a sentence explicitly noting that the examples command uses a non-default config file, and show what happens with and without the custom config.

10. **Fix or remove field aliases** (`min`/`most_likely`/`max`) — the largest single source of confusion for advanced users exploring task estimation.

---

## Suggested Code Improvements

1. **Fix field alias support (C1):** Either (a) update `parsers/yaml_parser.py` to accept `min`, `most_likely`, `max` as valid estimate field names, or (b) remove `AliasChoices` for them from the Pydantic models if they're not going to be supported. The current state (documented as valid, silently rejected) is the worst of both worlds.

2. **Format enum values in output (M3):** In the sprint-planning result printer, replace `str(enum_value)` with `enum_value.value` or a mapping to a human-readable string.

3. **Add `--target-budget` to CLI help auto-generation** so it appears in `--help` output with consistent description alongside other cost-related flags.

---

## File Index

Experiment files created during this walkthrough:

| File | Description |
|------|-------------|
| `01_getting_started.yaml` | Chapter 01: Website Refresh two-task example |
| `01_getting_started_output.txt` | Output from chapter 01 experiment |
| `03_step1.yaml` – `03_step6_storypoints.yaml` | Chapter 03 steps 1–6 |
| `03_step3_config.yaml` | Chapter 03 custom uncertainty config |
| `04_uncertainty_factors.yaml` | Chapter 04 compound multiplier test |
| `04_uncertainty_factors_output.txt` | Output from chapter 04 experiment |
| `05_task_estimation.yaml` | Chapter 05 all estimation methods (aliases removed after finding bug) |
| `05_task_estimation_output.txt` | Output from chapter 05 experiment |
| `06_risks.yaml` | Chapter 06 Payment Gateway with task+project risks |
| `06_risks_output.txt` | Output from chapter 06 experiment |
| `07_cost_handling.yaml` | Chapter 07 hourly_rate, fixed_cost, cost_impact |
| `07_cost_handling_output.txt` | Output from chapter 07 experiment |
| `09_sprint_planning.yaml` | Chapter 09 four-sprint history |
| `09_sprint_planning_output.txt` | Output from chapter 09 experiment |
| `10_constrained.yaml` | Chapter 10 three-resource constrained scheduling |
| `10_constrained_output.txt` | Output from chapter 10 experiment |
| `14_custom_config.yaml` | Chapter 14 custom T-shirt sizes + uncertainty overrides |
| `15_nl_input.txt` | Chapter 15 NL description input |
| `15_nl_generated.yaml` | Chapter 15 generated YAML output |

---

*Report generated by systematic new-user walkthrough of all 16 user guide chapters. All findings verified by direct CLI experimentation with mcprojsim 0.13.0.*
