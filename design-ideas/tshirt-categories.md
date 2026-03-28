Version: 1.1.0

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



# Implementation  

The implementation plan is divided in phases that each can be fully verified with integration tests.

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


# Formal Requirements

The requirements below describe the implemented multi-category T-shirt sizing behavior as it currently exists in the product. They are grouped by configuration, project-file semantics, runtime resolution, CLI behavior, output behavior, validation, and implementation structure. SHALL denotes mandatory implemented behavior. MAY denotes explicitly permitted optional behavior.

## Configuration Requirements

### FR-TS-001: Category-Based T-Shirt Sizing Integration
- The system SHALL support category-based T-shirt sizing as an extension of the existing symbolic estimate mechanism.
- Existing project files that use bare T-shirt values such as `M` SHALL remain valid.
- Category-based T-shirt sizing SHALL coexist with explicit numeric estimates and story-point estimates without changing their existing semantics.

### FR-TS-002: Built-In Categories and Defaults
- The system SHALL ship with five built-in T-shirt categories: `story`, `bug`, `epic`, `business`, and `initiative`.
- The built-in default category for bare T-shirt tokens SHALL be `epic`.
- The built-in category ordering exposed by configuration and CLI reporting SHALL be `story`, `bug`, `epic`, `business`, `initiative`.
- The system SHALL ship built-in size tables for each category as part of the default configuration payload.
- The global unit for T-shirt size mappings SHALL default to `hours`.

### FR-TS-003: Canonical Configuration Shape
- The canonical configuration key SHALL be `t_shirt_sizes`.
- The canonical shape of `t_shirt_sizes` SHALL be a nested mapping of category name to size token to estimate range object.
- Each estimate range object SHALL contain `low`, `expected`, and `high` numeric values.
- The configuration SHALL expose a single `t_shirt_size_default_category` field used to resolve bare T-shirt tokens.
- The configuration SHALL expose a single global `t_shirt_size_unit` field used for all T-shirt categories.

### FR-TS-004: Configuration Merge Semantics
- File-based configuration overrides SHALL be merged onto the built-in defaults rather than replacing the entire T-shirt sizing structure.
- A user configuration MAY override a single category or a single size entry while leaving the remaining built-in categories and sizes available.
- Partial category overrides SHALL preserve any untouched built-in size entries for that category.

### FR-TS-005: Backward-Compatible Configuration Input
- The system SHALL accept the legacy flat-map form of `t_shirt_sizes` where size tokens are defined directly under `t_shirt_sizes` without a category layer.
- When the legacy flat-map form is provided, the system SHALL normalize it into the category identified by `t_shirt_size_default_category`.
- If `t_shirt_size_default_category` is omitted while normalizing a legacy flat-map form, the system SHALL use `epic` as the default category.
- The system SHALL accept `t_shirt_size_categories` as an input alias for `t_shirt_sizes`.
- When `t_shirt_size_categories` is provided, the system SHALL normalize it to the canonical `t_shirt_sizes` key before validation and merge behavior are applied.
- The system SHALL reject configurations that define both `t_shirt_sizes` and `t_shirt_size_categories`.
- The system SHALL reject mixed flat and nested structures under `t_shirt_sizes`.

### FR-TS-006: Configuration Token Normalization
- Category names in configuration SHALL be normalized case-insensitively to lowercase.
- Size keys in configuration SHALL be normalized to canonical short tokens.
- The system SHALL reject empty category names in configuration.
- The system SHALL reject category entries that do not map to a dictionary of size estimates.
- The system SHALL reject unknown size tokens in configuration with a message that names the invalid token and the category in which it appeared.

## Project File Requirements

### FR-TS-007: Supported Task Estimate Syntax
- A task estimate MAY specify `t_shirt_size` as either a bare size token or a qualified `category.size` token.
- A bare size token SHALL resolve through `t_shirt_size_default_category`.
- A qualified token SHALL resolve directly against the named category.
- A task estimate MAY use long-form size names instead of short abbreviations.
- A task estimate SHALL NOT contain more than one dot in `t_shirt_size`.

### FR-TS-008: Strict Scalar Validation
- The `t_shirt_size` field SHALL be validated as a strict non-empty string.
- Numeric, boolean, null-coerced, and blank-string values SHALL be rejected rather than silently converted.
- The accepted token shape SHALL be alphabetic after normalization of spaces, hyphens, and underscores.
- Invalid dotted syntax such as `epic..M` or `epic.sub.M` SHALL be rejected with the documented format guidance.

### FR-TS-009: Accepted Size Aliases
- Size matching SHALL be case-insensitive.
- The system SHALL accept the canonical short forms `XS`, `S`, `M`, `L`, `XL`, and `XXL`.
- The system SHALL accept long-form aliases equivalent to extra small, small, medium, large, extra large, and extra extra large.
- The system SHALL accept the short aliases `MED`, `LRG`, `XLRG`, and `XXLRG`.
- The system SHALL treat hyphen, underscore, and space variants of supported aliases as equivalent during normalization.
- Category matching SHALL be case-insensitive.
- The system SHALL NOT define category aliases beyond case-insensitive matching of the configured category names.

### FR-TS-010: Symbolic Estimate Exclusivity
- A task estimate SHALL allow at most one symbolic estimate mode at a time.
- A task estimate SHALL reject any case where both `t_shirt_size` and `story_points` are provided.
- When `t_shirt_size` is present, the project file SHALL NOT specify `unit`.
- The unit for a T-shirt estimate SHALL come exclusively from configuration.
- Explicit numeric estimate validation rules SHALL remain unchanged when `t_shirt_size` is absent.

## Runtime Resolution Requirements

### FR-TS-011: Resolution API Semantics
- The configuration layer SHALL expose a strict resolution path that either returns a resolved T-shirt estimate range or raises a validation error.
- The configuration layer MAY also expose a compatibility helper that returns no result instead of raising on invalid input.
- Bare values such as `M` SHALL resolve using the currently active `t_shirt_size_default_category`.
- Qualified values such as `epic.M` SHALL resolve using the explicitly named category regardless of the default category.
- Mixed bare and qualified T-shirt values SHALL be supported within the same project.

### FR-TS-012: Unknown Category and Size Handling
- If a qualified token references a category that does not exist in the active configuration, resolution SHALL fail with an error that includes the invalid category and the list of valid categories.
- If a token references a size that is not defined in the resolved category, resolution SHALL fail with an error that includes the invalid value and the list of valid sizes for that category.
- If a token is syntactically malformed rather than merely unknown, resolution SHALL fail with a format error instructing the user to use either `category.size` or `size`.

### FR-TS-013: Simulation-Engine Resolution
- The simulation engine SHALL resolve T-shirt estimates at runtime through the configuration resolver before sampling task durations.
- The simulation engine SHALL use the globally configured `t_shirt_size_unit` as the unit for resolved T-shirt ranges.
- The simulation engine SHALL preserve the existing project-level distribution selection behavior when constructing the resolved estimate.
- Resolution failures arising from invalid T-shirt category or size tokens SHALL surface as user-visible errors rather than being silently ignored.

## CLI Requirements

### FR-TS-014: Per-Run Default Category Override
- The `simulate` command SHALL support a `tshirt-category` option that overrides the default category used for bare T-shirt tokens during that run.
- The CLI override SHALL be applied after configuration loading and before project simulation.
- The CLI override SHALL be validated against the categories present in the active merged configuration.
- CLI category override matching SHALL be case-insensitive.
- If the CLI override category is invalid, the command SHALL exit with an error that includes the invalid value and the list of valid categories.

### FR-TS-015: Configuration Reporting
- The `config` command SHALL report the active T-shirt unit.
- The `config` command SHALL report the active default T-shirt category.
- The `config` command SHALL report the available category names.
- The `config` command SHALL report the configured `low`, `expected`, and `high` values for each category and size entry.
- The `config` command SHALL reflect user-level configuration overrides when such overrides are active.

## Output Requirements

### FR-TS-016: Exporter Labeling
- Output that displays task estimate labels SHALL preserve the user-specified T-shirt token form.
- HTML export SHALL render bare labels such as `M` together with the resolved numeric range from the active configuration.
- HTML export SHALL render qualified labels such as `epic.M` without collapsing them to bare forms.
- When a caller provides an explicit configuration object to the exporter, the exporter SHALL use that configuration when rendering resolved T-shirt ranges.

## Validation Requirements

### FR-TS-017: Error Contract
- Invalid scalar types for `t_shirt_size` SHALL identify the rejected value and its runtime type.
- Blank-string `t_shirt_size` values SHALL be rejected as empty-string errors rather than as generic format errors.
- Invalid dotted formats SHALL produce the message pattern that instructs the user to use `category.size` or `size`.
- Unknown categories SHALL produce an error that includes the valid categories.
- Unknown sizes SHALL produce an error that includes the valid sizes for the resolved category.
- Conflicting canonical and alias config keys SHALL produce an explicit single-source-of-truth error.
- Invalid `t_shirt_sizes` structure SHALL produce an explicit shape error.

## Implementation Structure Requirements

### FR-TS-018: Responsibility Boundaries
- Raw project parsing SHALL continue to pass T-shirt tokens through as strings rather than resolving them in the parser layer.
- Project-model validation SHALL own strict scalar validation, symbolic exclusivity checks, and syntactic token-shape validation.
- Configuration SHALL own category normalization, alias normalization, backward-compatibility migration, category lookup, and size-token normalization.
- The simulation engine SHALL own final runtime resolution of T-shirt estimates into numeric ranges and units.
- CLI SHALL own per-run default-category override behavior.
- Exporters SHALL consume the already-defined configuration semantics rather than re-implementing independent T-shirt resolution rules.

