Version: 1.0.0

# Multi-Category T-Shirt Sizes

## TL;DR 
Add named T-shirt size categories (`bug`, `story`, `epic`, `business`, `initiative`) so teams can express differently-scoped work with the right calibration. `t_shirt_size: "M"` keeps working exactly as today. A new qualified form `t_shirt_size: "epic.M"` resolves to a different category.

Config keeps `t_shirt_sizes` as the canonical top-level key and extends it to a nested category map. The transitional alias key `t_shirt_size_categories` is accepted as input and normalized to canonical `t_shirt_sizes` during load.
A `t_shirt_size_default_category` setting (default: `story`) controls the legacy resolution path. A `--tshirt-category` CLI flag overrides it at run time.


## Overview

Today `mcprojsim` supports a single set of T-shirt size estimates. Every task that uses a T-shirt size — whether it is a two-hour bug fix or a six-month cross-team initiative — maps to the same table of low/expected/high hour values. This creates an awkward situation: either the table is calibrated for small development tasks and becomes meaningless for large strategic work, or it is stretched to cover all magnitudes and loses precision at both ends.

This feature introduces named T-shirt size categories. A category is simply a named set of size definitions. The built-in categories are `bug`, `story`, `epic`, `business`, and `initiative`, covering the full range from small targeted fixes to program-level changes. The magnitude of sizes increases significantly between categories: a `bug.M` represents a few hours of focused work, while an `initiative.M` spans tens of thousands of hours of coordinated effort across multiple teams.

From a project file perspective the change is minimal. A task that uses the current bare size token `M` continues to work exactly as before; it resolves through a configured default category, which defaults to `story`. Teams that want to mix sizes from different categories in the same project can use a qualified name like `epic.M` or `bug.XS`. The category and size names are both case-insensitive, so `Epic.Medium`, `EPIC.MEDIUM`, and `epic.m` all resolve identically.

On the configuration side, users can define their own categories or override individual size values within a built-in category. The key `t_shirt_sizes` keeps its existing role in the config file but now holds a nested map of categories rather than a flat map of sizes. Old config files that use the flat format are automatically migrated at load time, so existing projects require no changes. The old key `t_shirt_size_categories` is accepted as a transitional alias and silently normalized to the canonical `t_shirt_sizes` key.

At the CLI level, the new `--tshirt-category` flag allows users to override the default category for a single simulation run without editing any config file. This makes it straightforward to compare estimates across categories, for example running the same project description against both `story` and `epic` calibration to see how the schedule shifts.

The implementation is structured as nine sequential phases, each with a concrete verification step. The goal is that at no point during implementation does the test suite break: each phase leaves the codebase in a fully functional and tested state before the next phase begins.

## Motivation

Today a single global T-shirt size table forces a compromise between precision at the top and bottom of the scale. A `story.M` is around 40–120 hours of development work. An `epic.M` represents a feature spanning several sprints. A `business.M` is a substantial cross-team program. These are fundamentally different magnitudes of effort and deserve different calibration tables. Keeping them in a single table produces estimates that are either too coarse for developers planning their sprint or too detailed for executives planning a quarter.

Beyond the magnitude problem, there is also a communication problem. When a product manager writes `M` on a roadmap item, they typically mean something much larger than what a developer means by `M` on a Jira ticket. Named categories give both groups a precise shared vocabulary and allow the same simulation tool to reason about work at every level of planning granularity.








## Design

### Config schema changes

### Canonical key (new shape)
```yaml
t_shirt_sizes:
  story:
    XS: {low: 3, expected: 5, high: 15}
    S: {low: 5, expected: 16, high: 40}
    M: {low: 40, expected: 60, high: 120}
    L: {low: 160, expected: 240, high: 500}
    XL: {low: 320, expected: 400, high: 750}
    XXL: {low: 400, expected: 500, high: 1200}
  bug:
    XS: {low: 0.5, expected: 1, high: 4}
    S: {low: 1, expected: 3, high: 10}
    M: {low: 3, expected: 8, high: 24}
    L: {low: 8, expected: 20, high: 60}
    XL: {low: 20, expected: 40, high: 100}
    XXL: {low: 40, expected: 80, high: 200}
  epic:
    XS: {low: 40, expected: 80, high: 200}
    S: {low: 80, expected: 200, high: 600}
    M: {low: 200, expected: 480, high: 1200}
    L: {low: 480, expected: 1200, high: 3000}
    XL: {low: 1200, expected: 2400, high: 6000}
    XXL: {low: 2400, expected: 4800, high: 12000}
  business:
    XS: {low: 400, expected: 800, high: 2000}
    S: {low: 800, expected: 2000, high: 5000}
    M: {low: 2000, expected: 4000, high: 10000}
    L: {low: 4000, expected: 8000, high: 20000}
    XL: {low: 8000, expected: 16000, high: 40000}
    XXL: {low: 16000, expected: 32000, high: 80000}
  initiative:
    XS: {low: 2000, expected: 4000, high: 10000}
    S: {low: 4000, expected: 10000, high: 25000}
    M: {low: 10000, expected: 20000, high: 50000}
    L: {low: 20000, expected: 40000, high: 100000}
    XL: {low: 40000, expected: 80000, high: 200000}
    XXL: {low: 80000, expected: 160000, high: 400000}

t_shirt_size_default_category: story
t_shirt_size_unit: hours
```

### Compatibility and migration behavior
1. Old format accepted (flat map):
```yaml
t_shirt_sizes:
  M: {low: 40, expected: 60, high: 120}
```
This is migrated to:
`t_shirt_sizes[<default_category>]`.

2. Alias key accepted for transition:
`t_shirt_size_categories` can be read as input alias, normalized to canonical `t_shirt_sizes` internally.

3. Conflict handling:
If both `t_shirt_sizes` and `t_shirt_size_categories` are present in one config file, validation fails with a clear error.

### Supported user config examples

#### Supported: old flat style
```yaml
t_shirt_sizes:
  XS: {low: 3, expected: 5, high: 15}
  S: {low: 5, expected: 16, high: 40}
  M: {low: 40, expected: 60, high: 120}

t_shirt_size_default_category: story
t_shirt_size_unit: hours
```
Behavior:
- accepted for backward compatibility
- interpreted as overrides for a single category
- migrated internally to `t_shirt_sizes.story` when default category is `story`
- if `t_shirt_size_default_category: bug`, the same flat map is migrated to `t_shirt_sizes.bug`

#### Supported: new canonical nested style
```yaml
t_shirt_sizes:
  story:
    XS: {low: 3, expected: 5, high: 15}
    M: {low: 40, expected: 60, high: 120}
  bug:
    XS: {low: 0.5, expected: 1, high: 4}
    M: {low: 3, expected: 8, high: 24}

t_shirt_size_default_category: story
t_shirt_size_unit: hours
```
Behavior:
- this is the canonical format to document and generate
- bare project value `M` resolves via `story`
- qualified project value `bug.M` resolves via `bug`

#### Supported: transition alias key
```yaml
t_shirt_size_categories:
  story:
    M: {low: 40, expected: 60, high: 120}
  initiative:
    M: {low: 10000, expected: 20000, high: 50000}

t_shirt_size_default_category: initiative
t_shirt_size_unit: hours
```
Behavior:
- accepted as input alias only
- normalized internally to canonical `t_shirt_sizes`
- documented as transitional support, not the preferred long-term key

#### Not supported: mixed old and new structure under one key
```yaml
t_shirt_sizes:
  M: {low: 40, expected: 60, high: 120}
  story:
    L: {low: 160, expected: 240, high: 500}
```
Reason:
- ambiguous whether `t_shirt_sizes` is flat or nested
- validation should fail and tell the user to choose one shape

#### Not supported: both canonical and alias keys together
```yaml
t_shirt_sizes:
  story:
    M: {low: 40, expected: 60, high: 120}

t_shirt_size_categories:
  bug:
    M: {low: 3, expected: 8, high: 24}
```
Reason:
- duplicate sources of truth
- validation should fail and tell the user to use only `t_shirt_sizes`

#### Not supported: category layer missing estimate objects
```yaml
t_shirt_sizes:
  story:
    M: 60
```
Reason:
- each size entry must still be a full `{low, expected, high}` estimate object

### Python model shape
- Replace old field:
  `t_shirt_sizes: Dict[str, TShirtSizeConfig]`
- With new field:
  `t_shirt_sizes: Dict[str, Dict[str, TShirtSizeConfig]]`
- Keep:
  `t_shirt_size_default_category: str = "story"`

### Project file syntax
```yaml
estimate:
  t_shirt_size: "M"          # default category

estimate:
  t_shirt_size: "epic.M"     # explicit category

estimate:
  t_shirt_size: "Business.L" # case-insensitive category and size
```

### Accepted size tokens
The resolver normalizes the size token and accepts both abbreviation and long form:
- `XS`, `S`, `M`, `L`, `XL`, `XXL`
- `EXTRA_SMALL`, `SMALL`, `MEDIUM`, `LARGE`, `EXTRA_LARGE`, `EXTRA_EXTRA_LARGE`

`Medium` and `Large` are therefore valid and mapped to `M` and `L`.

### Supported project-file `t_shirt_size` values

#### Supported: bare abbreviated size (default category)
```yaml
estimate:
  t_shirt_size: "M"
```
Resolves using `t_shirt_size_default_category` from config (built-in default: `story`).

#### Supported: bare long-form size (case-insensitive)
```yaml
estimate:
  t_shirt_size: "Medium"

estimate:
  t_shirt_size: "large"
```
`Medium` → `M`, `large` → `L`. Both resolve via default category, same as bare abbreviated form.

#### Supported: qualified abbreviated size
```yaml
estimate:
  t_shirt_size: "epic.M"

estimate:
  t_shirt_size: "bug.XS"
```
Category part is case-insensitive. Resolves against named category in loaded config.

#### Supported: qualified long-form size (mixed case)
```yaml
estimate:
  t_shirt_size: "Epic.Medium"

estimate:
  t_shirt_size: "Business.Large"
```
Both parts normalized before lookup. `Epic.Medium` → category `epic`, size `M`.

#### Supported: all-uppercase or all-lowercase
```yaml
estimate:
  t_shirt_size: "EPIC.MEDIUM"

estimate:
  t_shirt_size: "initiative.xl"
```
Fully case-insensitive at resolution time.

#### Not supported: more than one dot separator
```yaml
estimate:
  t_shirt_size: "epic.sub.M"

estimate:
  t_shirt_size: "epic..M"
```
Error: `Invalid t_shirt_size format 'epic.sub.M'. Use '<category>.<size>' or '<size>'.`

#### Not supported: numeric or blank values
```yaml
estimate:
  t_shirt_size: 42

estimate:
  t_shirt_size: ""
```
Error: value must be a non-empty string. Blank and numeric values are rejected at model validation time.

Implementation note:
- `t_shirt_size` must be validated as a strict string type (no numeric coercion).

#### Not supported: qualifying a numeric value
```yaml
estimate:
  t_shirt_size: "epic.42"
```
Error: `Invalid t_shirt_size format 'epic.42'. Use '<category>.<size>' or '<size>'.`

#### Not supported: `t_shirt_size` combined with `unit`
```yaml
estimate:
  t_shirt_size: "M"
  unit: hours
```
Error: `t_shirt_size` and `unit` are mutually exclusive. Category provides the unit context.



## Error Handling Contract

All user-facing failures should include exact invalid input and suggested valid values.

1. Unknown category in qualified project value:
`Invalid t_shirt_size category 'foo' in 'foo.M'. Valid categories: bug, story, epic, business, initiative`

2. Unknown size in category:
`Invalid t_shirt_size 'epic.HUGE'. Valid sizes for category 'epic': XS, S, M, L, XL, XXL`

3. Unknown CLI override category:
`Invalid value for --tshirt-category: 'foo'. Valid categories: bug, story, epic, business, initiative`

4. Conflicting config keys:
`Config cannot define both 't_shirt_sizes' and 't_shirt_size_categories'. Use only 't_shirt_sizes'.`

5. Invalid qualified syntax:
`Invalid t_shirt_size format 'epic..M'. Use '<category>.<size>' or '<size>'.`

6. Invalid scalar type for `t_shirt_size`:
`Invalid t_shirt_size value 42 (type int). Expected non-empty string.`



## Defaults for Built-In Categories

`story` remains unchanged from current defaults.

| Category | Rationale | M range |
|---|---|---|
| story | Current defaults, unchanged | 40-120 h |
| bug | Smaller scoped fixes | 3-24 h |
| epic | Collection of stories | 200-1200 h |
| business | Cross-team effort | 2000-10000 h |
| initiative | Program-level effort | 10000-50000 h |

Full per-size values are defined in the canonical schema above.



# Implementation Steps (Verification-Driven)

## Phase 1: Config foundation
Success criteria:
- default config returns all five built-in categories
- bare `M` resolves using `t_shirt_size_default_category`
- qualified `epic.M` resolves using category-specific map
- old flat `t_shirt_sizes` input still works

Files:
- `src/mcprojsim/config.py`

Changes:
1. Add built-in defaults map for five categories.
2. Update `Config.t_shirt_sizes` type to nested dictionary.
3. Add normalization helper:
   - detect old flat format (`low`/`expected`/`high` leaf maps)
   - detect alias `t_shirt_size_categories`
   - reject both keys present together
4. Update load path so file-based configs go through the same normalization path.
5. Update `get_t_shirt_size(...)`:
   - parse optional `category.size`
   - normalize category case
   - normalize long/short size tokens
   - return helpful errors from Error Handling Contract

Verify:
`pytest tests/test_config.py --no-cov`

## Phase 2: Model validation
Success criteria:
- `TaskEstimate(t_shirt_size="epic.M")` valid
- `TaskEstimate(t_shirt_size="Medium")` valid
- invalid dotted syntax rejected with documented message
- `t_shirt_size` with explicit `unit` still rejected

Files:
- `src/mcprojsim/models/project.py`

Changes:
1. Update `TaskEstimate.validate_distribution` to accept:
   - bare token form (`<size>`)
   - qualified token form (`<category>.<size>`)
3. Keep distribution exclusivity behavior unchanged.
4. Enforce strict string validation for `t_shirt_size` so numeric values are not coerced into strings.

Verify:
`pytest tests/test_models.py --no-cov`

## Phase 3: Engine resolution and messages
Success criteria:
- engine resolves bare and qualified values identically to config contract
- resolution errors include valid categories/sizes

Files:
- `src/mcprojsim/simulation/engine.py`

Changes:
1. Keep parser behavior unchanged (still string pass-through).
2. Ensure `_resolve_estimate` passes full token to config resolver.
3. Surface config errors without losing user context.

Verify:
`pytest tests/test_integration.py::TestEndToEnd::test_tshirt_sizing_simulation --no-cov`

## Phase 4: CLI override behavior
Success criteria:
- `--tshirt-category` overrides config default
- override is case-insensitive
- invalid override exits non-zero with contract message
- `config show` displays default category and available categories

Files:
- `src/mcprojsim/cli.py`

Changes:
1. Add `@click.option("--tshirt-category", type=str, default=None)`.
2. Validate category against loaded config categories.
3. Apply override before simulation starts.
4. Update `show_config` output formatting.

Verify:
`pytest tests/test_cli.py --no-cov`

## Phase 5: Unit tests
Success criteria:
- all existing tests adapted
- all new behavior covered (compat + aliases + errors)

Files:
- `tests/test_config.py`
- `tests/test_models.py`
- `tests/test_cli.py`

New tests required:
1. Built-in categories present.
2. Qualified resolution (`story.M`, `epic.L`).
3. Case-insensitive resolution (`Epic.m`).
4. Long-form size normalization (`Medium`, `Large`).
5. Custom default category override from config.
6. Old flat format migration.
7. Alias key normalization from `t_shirt_size_categories`.
8. Conflict error when both config keys exist.
9. CLI override success.
10. CLI override invalid-category error.

Verify:
`pytest tests/test_config.py tests/test_models.py tests/test_cli.py -n auto --no-cov`

## Phase 6: Integration and E2E combinations
Success criteria:
- mixed bare and qualified values supported in same project
- invalid category and invalid size errors are stable

Files:
- `tests/test_integration.py`
- `tests/test_e2e_combinations.py`

New tests required:
1. Qualified category resolution.
2. Mixed bare and qualified usage.
3. Unknown category failure message.
4. Unknown size-in-category failure message.
5. Combination matrix includes qualified names.

Verify:
`pytest tests/test_integration.py tests/test_e2e_combinations.py -n auto --no-cov`

## Phase 7: Exporters
Success criteria:
- HTML/JSON/CSV output does not regress
- qualified labels are rendered/readable where shown

Files:
- `src/mcprojsim/exporters/html_exporter.py`
- `tests/test_exporters.py`

Changes:
1. Ensure label rendering supports `category.size` values.
2. Update config fixtures to nested `t_shirt_sizes` structure.

Verify:
`pytest tests/test_exporters.py --no-cov`

## Phase 8: Examples
Files to add:
- `examples/multi_category_config.yaml`
- `examples/multi_category_project.yaml`

Files to update:
- `examples/sample_config.yaml`

Example requirements:
1. Show canonical `t_shirt_sizes` nested format.
2. Show `t_shirt_size_default_category` override.
3. Show mixed `M`, `Medium`, and `epic.M` in a project.

Verify:
`poetry run mcprojsim validate examples/multi_category_project.yaml`

## Phase 9: Grammar and docs
Files:
- `docs/grammar.md`
- `docs/configuration.md`
- `docs/user_guide/task_estimation.md`
- `docs/user_guide/project_files.md`

Required updates:
1. Config grammar for canonical nested `t_shirt_sizes`.
2. Compatibility note for old flat `t_shirt_sizes`.
3. Transition note for alias key `t_shirt_size_categories` (accepted, deprecated in docs).
4. Project grammar for `<size>` and `<category>.<size>`.
5. CLI docs for `--tshirt-category`, including precedence over config.

Verify:
`poetry run mkdocs build`



## Relevant Files

Source files:
- `src/mcprojsim/config.py`
- `src/mcprojsim/models/project.py`
- `src/mcprojsim/simulation/engine.py`
- `src/mcprojsim/cli.py`
- `src/mcprojsim/exporters/html_exporter.py`

Test files:
- `tests/test_config.py`
- `tests/test_models.py`
- `tests/test_cli.py`
- `tests/test_integration.py`
- `tests/test_e2e_combinations.py`
- `tests/test_exporters.py`

Examples/docs files:
- `examples/multi_category_config.yaml` (new)
- `examples/multi_category_project.yaml` (new)
- `examples/sample_config.yaml`
- `docs/grammar.md`
- `docs/configuration.md`
- `docs/user_guide/task_estimation.md`
- `docs/user_guide/project_files.md`



## Full Verification Sequence
1. `pytest tests/test_config.py --no-cov`
2. `pytest tests/test_models.py --no-cov`
3. `pytest tests/test_cli.py --no-cov`
4. `pytest tests/test_integration.py tests/test_e2e_combinations.py -n auto --no-cov`
5. `pytest tests/test_exporters.py --no-cov`
6. `poetry run pytest tests/ -m "not heavy" -n auto --cov=src/mcprojsim --cov-fail-under=80`
7. `poetry run mkdocs build`



## Scope Decisions
1. `t_shirt_size_unit` remains global (no per-category units).
2. Category and size matching is case-insensitive.
3. `story` category keeps current defaults unchanged.
4. Backward compatibility remains for old flat `t_shirt_sizes`.
5. Parser layers remain pass-through; resolution is centralized in config/engine.
6. Out of scope: auto-detect category, MCP category parameter, per-size custom units.