# 'mcprojsim` - New User Learning Journey Report 2

> **Context**: This report documents findings from a systematic walkthrough of the
> mcprojsim documentation as a new (but technical) user, following the Quick Start
> Guide and then every page in the User Guide in the order defined by `mkdocs.yml`.
> For each topic, experimental YAML files were created, simulations run, and output
> compared against the documentation's claims. All experiment files are in
> `new_user/learning02/`.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Issues (Documentation ≠ Code)](#critical-issues)
3. [Moderate Issues (Confusing or Misleading)](#moderate-issues)
4. [Minor Issues (Polish & Discoverability)](#minor-issues)
5. [Natural Language Parser Issues](#nl-parser-issues)
6. [What Works Well](#what-works-well)
7. [Suggested Structural Improvements](#structural-improvements)
8. [Per-Page Findings](#per-page-findings)
9. [Appendix: Experiment File Index](#appendix)

---

## 1. Executive Summary {#executive-summary}

The mcprojsim documentation is generally well-structured and covers the full
feature set. The simulation engine itself is solid — results are reproducible,
constrained scheduling works correctly, and the progressive complexity of the
User Guide is a good pedagogical choice.

However, there are **stale example outputs and incorrect default claims** that
will confuse new users. The most impactful issue is the **uncertainty factor
defaults documentation**, which describes behavior that no longer matches the
code. This cascades into wrong expected output in "Your First Project" and
undermines trust in the documentation early in the learning journey.

### Issue Count by Severity

| Severity | Count | Summary |
|----------|-------|---------|
| **Critical** | 2 | Defaults documented incorrectly; stale example output |
| **Moderate** | 5 | Misleading CLI flags, missing cross-references, NL parser quality |
| **Minor** | 6 | Polish, discoverability, wording suggestions |

---

## 2. Critical Issues {#critical-issues}

### 2.1 Uncertainty Factor Defaults Are Wrong

**Location**: `docs/user_guide/uncertainty_factors.md`, lines ~117–133

**What the doc says**:
> Default levels are: `team_experience: medium (1.0×)`,
> `requirements_maturity: medium (1.15×)`, `technical_complexity: medium (1.20×)`,
> `team_distribution: colocated (1.0×)`, `integration_complexity: medium (1.15×)`.
> Compound multiplier ≈ 1.587×.
>
> "A task with no explicit uncertainty factors will still have its sampled base
> duration stretched by roughly 59%."

**What actually happens** (verified with `learning/uncertainty_factors.yaml`):

The simulation output shows:
```
requirements_maturity  : high        (×1.00)
technical_complexity   : low         (×1.00)
integration_complexity : low         (×1.00)
```
Compound multiplier = **1.0×** (no stretch at all).

**Impact**: This is the single most confusing issue for a new user. A task
estimated at 20/30/50 hours should yield a Mean near 33h (triangular mean),
but the doc's Step 1 example claims ~42h because it assumes the old 1.587×
compound. A new user running the simulation will get ~26–27h and immediately
question whether the tool is broken.

**Suggested fix**: Update the default levels table and the compound multiplier
claim to match the current code defaults. Re-run and update all example outputs
that depend on these defaults.

---

### 2.2 Stale Example Output Throughout "Your First Project"

**Location**: `docs/user_guide/your_first_project.md`, all 6 steps

**What the doc shows** (Step 1 example):
```
Mean:     42.23 hours
Median:   38.31 hours
P80:      55.84 hours
P90:      65.61 hours
```

**What actually happens** (with `--seed 42`):
```
Mean:     26.56 hours
Median:   27.20 hours
P80:      34.94 hours
P90:      39.55 hours
```

The numbers are ~37% lower across the board because the uncertainty factor
defaults have changed (see §2.1). Every step's expected output in the
tutorial is similarly outdated.

**Impact**: This is the *first guided experience* for a new user. Seeing
dramatically different numbers from the tutorial immediately undermines
confidence. A new user will spend time debugging whether they made a typo
rather than learning the tool.

**Suggested fix**: Re-generate all example outputs with the current defaults
and a fixed seed. Consider adding a note like "Your exact numbers may vary
slightly depending on version" as a safety net.

---

## 3. Moderate Issues {#moderate-issues}

### 3.1 `--quiet` Flag Description Is Misleading

**Location**: `docs/quickstart.md`, line ~289

**What the doc says**: `--quiet` is for "suppress progress output"

**What actually happens**:
- `-q` / `--quiet`: Suppresses **all simulation results** (only version line and timing shown)
- `-qq`: Suppresses **everything** (completely silent)
- `--minimal`: Reduced output while still showing key results

**Impact**: A new user wanting less noise but still wanting to see results will
use `--quiet` and get *nothing*. `--minimal` is the flag they actually want.

**Suggested fix**: Clarify the distinction in the quickstart and in
`running_simulations.md`. A table like this would help:

| Flag | What it does |
|------|-------------|
| *(none)* | Full output |
| `--minimal` | Reduced output — key statistics only |
| `-q` / `--quiet` | Suppress all results (timing only) |
| `-qq` | Completely silent |

---

### 3.2 T-Shirt Default Category: "story" vs "epic" Confusion

**Location**: `docs/user_guide/your_first_project.md` (Step 5)

**What the doc says**: "the application ships with built-in mappings... and
defaults bare sizes like M to the **epic** category"

**What actually happens**: The simulation output shows
`T-Shirt Category Used: story`, and `mcprojsim config show` confirms
`default_category: story`.

**Impact**: Moderate confusion. A user reading the tutorial will expect epic
ranges but get story ranges. The numbers will be very different (e.g., M/epic
~449h vs M/story ~113h).

**Suggested fix**: Update the doc to say "story" (or whichever is actually the
current default). Grep the docs for all mentions of the default category and
make them consistent.

---

### 3.3 Cost Estimation Not Mentioned in Project Files Reference

**Location**: `docs/user_guide/project_files.md` (the YAML quick reference)

**Issue**: Cost-related fields (`default_hourly_rate`, `fixed_cost`, resource
`hourly_rate`) are documented in `cost_handling.md` but not mentioned in the
project file reference page.

**My first attempt**: I added `cost_per_hour` to tasks (seemed intuitive) and got
a validation error. The actual field is `fixed_cost` on tasks and
`default_hourly_rate` at the project level.

**Suggested fix**: Add a "Cost Fields" subsection to `project_files.md`, or at
minimum a cross-reference to `cost_handling.md` with the field names listed.

---

### 3.4 Sprint Planning: Sparse Entry on How History Rows Are Used

**Location**: `docs/user_guide/sprint_planning.md`

**Issue**: The doc explains *what* to put in `sprint_history` but doesn't fully
explain *how* the history is used to produce the velocity model. It mentions
"empirical" and "neg_binomial" models but doesn't explain the difference or
when you'd choose one.

**My experience**: I set up `learning/sprint_planning.yaml` with 4 sprint
history rows and got sensible results, but I had to trust the tool because I
couldn't verify the math from the docs alone.

**Suggested fix**: Add a brief explanation of how the empirical model samples
from history vs. how neg_binomial fits a distribution. Even one paragraph would
help.

---

### 3.5 Two-Pass Mode: No Explanation of *Why* Results Differ

**Location**: `docs/user_guide/constrained_scheduling.md` (two-pass section)

**Issue**: The doc explains *how* to enable two-pass (`--two-pass`) and that it
uses "criticality-aware" scheduling, but doesn't explain *why* results differ
or *when* to prefer it.

**My experiment**: Single-pass P50 was 290.35h, two-pass P50 was 220.52h (24%
lower). That's a dramatic difference! But the docs don't help a user understand
whether the two-pass result is "more realistic" or "more optimistic" or
"better scheduled."

**Suggested fix**: Add a brief conceptual explanation: "In single-pass mode,
resources are assigned to tasks in a fixed priority order. Two-pass mode first
identifies which tasks are most often on the critical path, then prioritizes
those tasks for resource allocation, reducing bottleneck delays."

---

## 4. Minor Issues {#minor-issues}

### 4.1 Unit Not Allowed on Symbolic Estimates (Undiscoverable Error)

When using T-shirt sizes or story points, adding `unit: "hours"` to a task
causes a validation error. This makes sense (the unit comes from config), but
the error message doesn't explain *why*. A new user's instinct is to specify
units explicitly.

**Suggested fix**: Either make the error message say "Unit is determined by the
T-shirt/story-point configuration and cannot be set per-task" or add a note in
the task estimation docs.

---

### 4.2 `max_resources` Default Behavior Surprising

In constrained scheduling, `max_resources` defaults to 1, and there's also an
automatic practical cap of 3 (based on a "granularity heuristic" of effort/16h).
This isn't documented and can surprise users who set `max_resources: 5` but see
utilization suggesting only 3 are used.

**Suggested fix**: Document the practical cap heuristic, even briefly.

---

### 4.3 Distribution Override Precedence Not Explicit

The docs mention you can set `distribution` at the project level and override
per-task, but don't spell out the precedence rules. I confirmed experimentally
that per-task `distribution` wins over project-level (as expected), but a
sentence saying this explicitly would save time.

---

### 4.4 JSON Export: Output Structure Undocumented

`--format json` works and produces a rich JSON file, but the structure (what
keys exist, what they contain) isn't documented anywhere. For users wanting to
integrate mcprojsim into a pipeline, a schema reference or example would help.

---

### 4.5 HTML Report: Not Mentioned in Running Simulations

The `--format html` flag produces a beautiful interactive report, but the
Running Simulations page doesn't mention it prominently. It deserves a
screenshot or at least a callout.

---

### 4.6 Config File Discovery Order

The docs mention config files but don't clearly state the search/merge order.
Does `--config` override a `mcprojsim.yaml` in the project directory? Is there
a global config location? A brief "Config Resolution Order" section would help.

---

## 5. Natural Language Parser Issues {#nl-parser-issues}

The NL parser (`mcprojsim generate`) is a useful feature but has noticeable
quality issues that a new user will encounter immediately.

### Issues Found (using `learning/nl_input.txt`):

1. **Task names contain leftover parenthetical debris**: Generated names like
   `"Requirements Analysis ()"` with empty parens.

2. **Dependency text leaks into task names**: Input "Implementation (depends on
   requirements)" produces a task named `"Implementation (depends on
   requirements)"` instead of just `"Implementation"`.

3. **Size extraction fails for inline format**: "Size XL" in the input wasn't
   parsed, resulting in a task with *no estimate at all*, which fails validation.

4. **Dependency resolution fails for natural references**: "depends on
   requirements" or "depends on database schema" aren't resolved to task IDs.
   The user must use exact task numbers ("depends on Task 1").

5. **The introductory example in `nl_processing.md`** itself shows task names
   with "()" artifacts, suggesting this is a known cosmetic issue.

### Suggested Improvements:

- Strip parenthetical text from generated task names after extracting
  dependency/size info
- Support fuzzy dependency matching (match "requirements" to a task named
  "Requirements Analysis")
- Make size extraction more robust (handle "Size XL", "size: XL", "XL" etc.)
- Add a note in the docs about what dependency reference formats are supported

---

## 6. What Works Well {#what-works-well}

It's important to highlight what's already good:

1. **Simulation Engine**: Rock-solid. Results are reproducible with `--seed`,
   distributions behave as expected, and the Monte Carlo sampling is fast.

2. **Progressive Tutorial Structure**: The "Your First Project" 6-step
   progression from single task → dependencies → uncertainty → risks → T-shirt
   → story points is excellent pedagogy. (Just needs updated numbers.)

3. **Constrained Scheduling**: The resource/calendar constraint system is
   powerful and the diagnostics output (utilization, wait time, calendar delay)
   is genuinely useful. It "just works."

4. **Sprint Planning**: Clean integration of historical velocity data. The
   commitment guidance output is practical and actionable.

5. **Cost Estimation**: Well-designed with sensible defaults (project-level rate,
   resource overrides, task fixed costs). Budget probability analysis is a nice
   touch.

6. **Validation Error Messages**: Generally excellent. The YAML parser gives
   line/column context and the Pydantic validation errors are descriptive.

7. **CLI Design**: Clean Click-based CLI with sensible defaults. The `--table`
   flag for compact output is great for terminal use.

8. **HTML Reports**: Beautiful, interactive, and comprehensive. A real selling
   point for stakeholder communication.

---

## 7. Suggested Structural Improvements {#structural-improvements}

### 7.1 Add a "Common Patterns" or "Cookbook" Page

After the tutorial, users need a reference for common patterns:
- "How do I model a team of 3 developers sharing work?"
- "How do I add holidays for a US team?"
- "How do I set up cost tracking for a fixed-bid project?"

A cookbook with copy-paste YAML snippets would massively accelerate adoption.

### 7.2 Cross-Reference Between Related Pages

Several topics are split across pages without cross-links:
- Cost fields aren't referenced from the project files page
- Two-pass mode is in constrained scheduling but relevant to running simulations
- Uncertainty factors interact with task estimation but neither page links to
  the other

Adding "See also:" links at the bottom of each page would help navigation.

### 7.3 Add a YAML Quick Reference Card

A single page with every valid YAML field, its type, default value, and which
section it belongs to would be invaluable. The project files page is close to
this but doesn't cover every field (especially cost, sprint, and constrained
scheduling fields).

### 7.4 Version the Example Outputs

Consider generating example outputs from a CI job with a fixed seed, so they're
always current. This would prevent the staleness problem (§2.1–2.2) from
recurring.

### 7.5 Add a "Troubleshooting" Section

Common issues I hit that would benefit from a troubleshooting guide:
- "Why are my numbers different from the docs?" → Seed, uncertainty defaults
- "Why does validation reject my `unit` field?" → Symbolic estimates
- "Why does `--quiet` suppress everything?" → Use `--minimal` instead
- "Why does generate produce tasks with empty estimates?" → NL parser
  limitations

---

## 8. Per-Page Findings {#per-page-findings}

### Quick Start (`docs/quickstart.md`)
- ⚠️ `--quiet` described as "suppress progress output" — actually suppresses all results
- ✅ Generate → validate → simulate flow is clear and works
- 💡 Could mention `--seed` earlier for reproducibility

### Introduction (`docs/user_guide/introduction.md`)
- ✅ Good conceptual overview
- 💡 The "Why Monte Carlo?" section is persuasive and well-written

### Your First Project (`docs/user_guide/your_first_project.md`)
- 🔴 All example outputs are stale (wrong numbers due to changed uncertainty defaults)
- ⚠️ Step 5 claims default T-shirt category is "epic" but it's actually "story"
- ✅ Progressive 6-step structure is excellent

### Uncertainty Factors (`docs/user_guide/uncertainty_factors.md`)
- 🔴 Default factor levels table is wrong (shows medium/1.15× etc. but actual is high/low/1.0×)
- 🔴 "roughly 59% stretch" claim is wrong (actual compound is 1.0×, no stretch)
- ✅ The concept explanation and factor descriptions are clear

### Task Estimation (`docs/user_guide/task_estimation.md`)
- ✅ Clear explanation of all estimation methods
- ✅ Distribution override mechanics work as described
- 💡 Could explicitly state that per-task distribution overrides project-level

### Risks (`docs/user_guide/risks.md`)
- ✅ Well-documented, examples work correctly
- ✅ Risk Impact Analysis output is useful and clear

### Sprint Planning (`docs/user_guide/sprint_planning.md`)
- ⚠️ Velocity model selection (empirical vs neg_binomial) not well explained
- ✅ Setup and output work correctly

### Constrained Scheduling (`docs/user_guide/constrained_scheduling.md`)
- ⚠️ Two-pass mode needs better conceptual explanation
- ⚠️ `max_resources` practical cap not documented
- ✅ Resource/calendar constraint system works flawlessly

### Running Simulations (`docs/user_guide/running_simulations.md`)
- ⚠️ `-q`/`-qq`/`--minimal` distinction unclear
- 💡 HTML export deserves more prominence
- ✅ All CLI flags work as implemented

### Interpreting Results (`docs/user_guide/interpreting_results.md`)
- ✅ Good explanations of P-values and confidence intervals
- 💡 Could add guidance on "which percentile should I commit to?"

### Cost Handling (`docs/user_guide/cost_handling.md`)
- ✅ Well-written, accurate, complete
- ⚠️ Not cross-referenced from project_files.md

### Natural Language Processing (`docs/user_guide/nl_processing.md`)
- ⚠️ Example output shows task names with "()" artifacts
- ⚠️ Supported dependency reference formats not clearly listed
- 💡 Should mention known limitations (fuzzy matching not supported)

### Configuration (`docs/user_guide/configuration.md`)
- ✅ Config override mechanics are clear
- 💡 Config file discovery/merge order could be more explicit

### Project Files (`docs/user_guide/project_files.md`)
- ⚠️ Missing cost fields, sprint fields, constrained scheduling fields
- 💡 Should be a comprehensive field reference (or link to one)

---

## 9. Appendix: Experiment File Index {#appendix}

| File | Topic | Notes |
|------|-------|-------|
| `description.txt` | Quick Start | NL input for generate |
| `quickstart_project.yaml` | Quick Start | Generated YAML |
| `quickstart_output.txt` | Quick Start | Simulation output |
| `first_project_step1.yaml` | Your First Project | Single task |
| `first_project_step2.yaml` | Your First Project | Dependencies |
| `first_project_step3.yaml` | Your First Project | Uncertainty factors |
| `first_project_step4.yaml` | Your First Project | Risks |
| `first_project_step5.yaml` | Your First Project | T-shirt sizes |
| `first_project_step6_storypoints.yaml` | Your First Project | Story points |
| `first_project_config.yaml` | Your First Project | Custom config |
| `first_project_output.txt` | Your First Project | Combined output |
| `uncertainty_factors.yaml` | Uncertainty Factors | 3 tasks, varying factors |
| `uncertainty_factors_output.txt` | Uncertainty Factors | Shows actual defaults |
| `task_estimation.yaml` | Task Estimation | Mixed methods |
| `task_estimation_distribution.yaml` | Task Estimation | Distribution override |
| `task_estimation_output.txt` | Task Estimation | Combined output |
| `risks.yaml` | Risks | Task-level + project-level |
| `risks_output.txt` | Risks | Risk impact analysis |
| `sprint_planning.yaml` | Sprint Planning | 4 history rows |
| `sprint_planning_output.txt` | Sprint Planning | Sprint forecast |
| `constrained.yaml` | Constrained Scheduling | 3 resources, 2 calendars |
| `constrained_output.txt` | Constrained Scheduling | Diagnostics output |
| `cost_estimation.yaml` | Cost Estimation | Hourly + fixed costs |
| `cost_estimation_output.txt` | Cost Estimation | Budget analysis |
| `two_pass.yaml` | Two-Pass | Resource contention |
| `two_pass_output.txt` | Two-Pass | Single vs two-pass comparison |
| `nl_input.txt` | NL Processing | Natural language input |
| `nl_generated.yaml` | NL Processing | Generated (with issues) |
| `nl_processing_output.txt` | NL Processing | Parser output log |
| `custom_config.yaml` | Configuration | Custom T-shirt sizes |
| `configuration.yaml` | Configuration | Test project |
| `configuration_output.txt` | Configuration | Default vs custom |
| `running_simulations.yaml` | Running Simulations | Multi-flag testing |
| `running_simulations_output.txt` | Running Simulations | Combined output |
| `interpreting_results_output.txt` | Interpreting Results | Detailed output |

---

*Report generated by systematic walkthrough of mcprojsim v0.13.0 documentation.*
*All experiments used `--seed 42` for reproducibility unless otherwise noted.*
