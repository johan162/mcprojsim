# Formal Grammar Specification

This document specifies the accepted structure for Monte Carlo Project Simulator project and config files.

It is written in Extended Backus-Naur Form (EBNF) plus semantic constraints that are enforced by model validators.

## Notation Conventions

- `::=` means "is defined as"
- `|` means alternation
- `[]` means optional (zero or one)
- `{}` means repetition (zero or more)
- `{ ... }+` means one or more
- `()` groups elements
- `""` denotes literal strings
- `<>` denotes terminal or non-terminal symbols

## Project File Grammar

```ebnf
# Top-level project file
<project_file> ::= <project_section>
                   <tasks_section>
                   [<project_risks_section>]
                   [<resources_section>]
                   [<calendars_section>]
                   [<sprint_planning_section>]

# Project section
<project_section> ::= "project:" <project_metadata>

<project_metadata> ::= <project_name>
                       [<project_description>]
                       <start_date>
                       [<hours_per_day>]
                       [<currency>]
                       [<confidence_levels>]
                       [<probability_thresholds>]
                       [<project_distribution>]
                       [<team_size>]

<project_name> ::= "name:" <string>
<project_description> ::= "description:" <string>
<start_date> ::= "start_date:" <date_string>
<hours_per_day> ::= "hours_per_day:" <positive_number>
<currency> ::= "currency:" <string>
<confidence_levels> ::= "confidence_levels:" "[" <percentile_list> "]"
<probability_thresholds> ::= [<red_threshold>] [<green_threshold>]
<red_threshold> ::= "probability_red_threshold:" <probability>
<green_threshold> ::= "probability_green_threshold:" <probability>
<project_distribution> ::= "distribution:" <distribution_type>
<team_size> ::= "team_size:" <non_negative_integer>

<distribution_type> ::= "triangular" | "lognormal"

# Tasks
<tasks_section> ::= "tasks:" <task_list>
<task_list> ::= { <task> }+
<task> ::= "-" <task_properties>

<task_properties> ::= <task_id>
                      <task_name>
                      [<task_description>]
                      <estimate>
                      [<dependencies>]
                      [<uncertainty_factors>]
                      [<task_resources>]
                      [<task_max_resources>]
                      [<task_min_experience_level>]
                      [<task_planning_story_points>]
                      [<task_priority>]
                      [<task_spillover_probability_override>]
                      [<task_risks>]

<task_id> ::= "id:" <identifier>
<task_name> ::= "name:" <string>
<task_description> ::= "description:" <string>
<dependencies> ::= "dependencies:" <dependency_list>
<dependency_list> ::= "[]" | "[" <identifier_list> "]"

<task_resources> ::= "resources:" <identifier_list_bracketed>
<identifier_list_bracketed> ::= "[]" | "[" <identifier_list> "]"
<task_max_resources> ::= "max_resources:" <positive_integer>
<task_min_experience_level> ::= "min_experience_level:" <experience_level>
<task_planning_story_points> ::= "planning_story_points:" <positive_integer>
<task_priority> ::= "priority:" <integer>
<task_spillover_probability_override> ::= "spillover_probability_override:" <probability>

# Estimates
<estimate> ::= "estimate:" <estimate_spec>
<estimate_spec> ::= <explicit_estimate>
                  | <tshirt_estimate>
                  | <story_point_estimate>

<explicit_estimate> ::= [<estimate_distribution>]
                        <low_key>
                        <expected_key>
                        <high_key>
                        [<unit>]

<estimate_distribution> ::= "distribution:" <distribution_type>

# Accepted aliases in project files:
# low/min, expected/most_likely, high/max
<low_key> ::= ("low:" | "min:") <positive_number>
<expected_key> ::= ("expected:" | "most_likely:") <positive_number>
<high_key> ::= ("high:" | "max:") <positive_number>

<tshirt_estimate> ::= "t_shirt_size:" <tshirt_size>
<tshirt_size> ::= <bare_tshirt_size> | <qualified_tshirt_size>
<bare_tshirt_size> ::= <tshirt_size_token>
<qualified_tshirt_size> ::= <category_name> "." <tshirt_size_token>
<tshirt_size_token> ::= "XS" | "S" | "M" | "L" | "XL" | "XXL"
                      | "EXTRA_SMALL" | "SMALL" | "MEDIUM"
                      | "LARGE" | "EXTRA_LARGE" | "EXTRA_EXTRA_LARGE"

<story_point_estimate> ::= "story_points:" <story_point_value>
<story_point_value> ::= "1" | "2" | "3" | "5" | "8" | "13" | "21"

<unit> ::= "unit:" <time_unit>
<time_unit> ::= "hours" | "days" | "weeks"

# Uncertainty factors
<uncertainty_factors> ::= "uncertainty_factors:" <factor_list>
<factor_list> ::= { <factor> }
<factor> ::= <factor_name> ":" <factor_level>
<factor_name> ::= <identifier>
<factor_level> ::= <identifier>

# Risks
<task_risks> ::= "risks:" <risk_list>
<project_risks_section> ::= "project_risks:" <risk_list>
<risk_list> ::= { <risk> }
<risk> ::= "-" <risk_properties>
<risk_properties> ::= <risk_id>
                     <risk_name>
                     <risk_probability>
                     <risk_impact>
                     [<risk_description>]

<risk_id> ::= "id:" <identifier>
<risk_name> ::= "name:" <string>
<risk_probability> ::= "probability:" <probability>
<risk_description> ::= "description:" <string>

<risk_impact> ::= "impact:" <impact_spec>
<impact_spec> ::= <fixed_impact>
                | <percentage_impact>
                | <absolute_impact>

# Raw numeric risk impact is interpreted as hours
<fixed_impact> ::= <positive_number>
<percentage_impact> ::= "type:" "percentage"
                        "value:" <positive_number>
<absolute_impact> ::= "type:" "absolute"
                      "value:" <positive_number>
                      ["unit:" <time_unit>]

# Resources and calendars
<resources_section> ::= "resources:" <resource_list>
<resource_list> ::= { <resource> }
<resource> ::= "-" <resource_properties>
<resource_properties> ::= [<resource_name>]
                         [<legacy_resource_id>]
                         [<resource_availability>]
                         [<resource_calendar>]
                         [<resource_experience_level>]
                         [<resource_productivity_level>]
                         [<resource_sickness_prob>]
                         [<resource_planned_absence>]

<resource_name> ::= "name:" <identifier>
<legacy_resource_id> ::= "id:" <identifier>
<resource_availability> ::= "availability:" <probability>
<resource_calendar> ::= "calendar:" <identifier>
<resource_experience_level> ::= "experience_level:" <experience_level>
<resource_productivity_level> ::= "productivity_level:" <positive_number>
<resource_sickness_prob> ::= "sickness_prob:" <probability>
<resource_planned_absence> ::= "planned_absence:" <date_list>

<calendars_section> ::= "calendars:" <calendar_list>
<calendar_list> ::= { <calendar> }
<calendar> ::= "-" <calendar_properties>
<calendar_properties> ::= [<calendar_id>]
                         [<calendar_work_hours_per_day>]
                         [<calendar_work_days>]
                         [<calendar_holidays>]

<calendar_id> ::= "id:" <identifier>
<calendar_work_hours_per_day> ::= "work_hours_per_day:" <positive_number>
<calendar_work_days> ::= "work_days:" <weekday_int_list>
<weekday_int_list> ::= "[]" | "[" <weekday_int_values> "]"
<weekday_int_values> ::= <weekday_int> { "," <weekday_int> }
<weekday_int> ::= "1" | "2" | "3" | "4" | "5" | "6" | "7"
<calendar_holidays> ::= "holidays:" <date_list>

# Sprint planning
<sprint_planning_section> ::= "sprint_planning:" <sprint_planning_properties>

<sprint_planning_properties> ::= ["enabled:" <boolean>]
                                 "sprint_length_weeks:" <positive_integer>
                                 "capacity_mode:" <capacity_mode>
                                 ["planning_confidence_level:" <probability_exclusive>]
                                 ["removed_work_treatment:" <removed_work_treatment>]
                                 ["velocity_model:" <velocity_model>]
                                 [<history_block>]
                                 [<future_sprint_overrides_block>]
                                 [<volatility_overlay_block>]
                                 [<spillover_block>]
                                 [<sickness_block>]

<capacity_mode> ::= "story_points" | "tasks"
<removed_work_treatment> ::= "churn_only" | "reduce_backlog"
<velocity_model> ::= "empirical" | "neg_binomial"

<history_block> ::= "history:" ( <history_inline_list> | <history_external_descriptor> )
<history_inline_list> ::= { "-" <history_entry> }+
<history_external_descriptor> ::= "format:" ("json" | "csv")
                                  "path:" <string>

<history_entry> ::= "sprint_id:" <string>
                    ["sprint_length_weeks:" <positive_integer>]
                    ["completed_story_points:" <non_negative_number>]
                    ["completed_tasks:" <non_negative_integer>]
                    ["spillover_story_points:" <non_negative_number>]
                    ["spillover_tasks:" <non_negative_integer>]
                    ["added_story_points:" <non_negative_number>]
                    ["added_tasks:" <non_negative_integer>]
                    ["removed_story_points:" <non_negative_number>]
                    ["removed_tasks:" <non_negative_integer>]
                    ["holiday_factor:" <positive_number>]
                    ["end_date:" <date_string>]
                    ["team_size:" <non_negative_integer>]
                    ["notes:" <string>]

<future_sprint_overrides_block> ::= "future_sprint_overrides:" { "-" <future_override> }
<future_override> ::= ["sprint_number:" <positive_integer>]
                      ["start_date:" <date_string>]
                      ["holiday_factor:" <positive_number>]
                      ["capacity_multiplier:" <positive_number>]
                      ["notes:" <string>]

<volatility_overlay_block> ::= "volatility_overlay:"
                               ["enabled:" <boolean>]
                               ["disruption_probability:" <probability>]
                               ["disruption_multiplier_low:" <positive_number>]
                               ["disruption_multiplier_expected:" <positive_number>]
                               ["disruption_multiplier_high:" <positive_number>]

<spillover_block> ::= "spillover:"
                      ["enabled:" <boolean>]
                      ["model:" ("table" | "logistic")]
                      ["size_reference_points:" <positive_number>]
                      ["size_brackets:" <size_brackets_list>]
                      ["consumed_fraction_alpha:" <positive_number>]
                      ["consumed_fraction_beta:" <positive_number>]
                      ["logistic_slope:" <positive_number>]
                      ["logistic_intercept:" <float>]

<size_brackets_list> ::= { "-" <size_bracket> }+
<size_bracket> ::= ["max_points:" <positive_number>]
                   "probability:" <probability>

<sickness_block> ::= "sickness:"
                     ["enabled:" <boolean>]
                     ["team_size:" <positive_integer>]
                     ["probability_per_person_per_week:" <probability_exclusive>]
                     ["duration_log_mu:" <float>]
                     ["duration_log_sigma:" <positive_number>]

# Shared primitives
<identifier> ::= <letter> { <letter> | <digit> | "_" }
<identifier_list> ::= <identifier> { "," <identifier> }
<date_list> ::= "[]" | "[" <date_string_list> "]"
<date_string_list> ::= <date_string> { "," <date_string> }
<date_string> ::= <year> "-" <month> "-" <day>

<positive_number> ::= <integer_gt_zero> | <float_gt_zero>
<non_negative_number> ::= <non_negative_integer> | <non_negative_float>
<probability> ::= <float_between_0_and_1_inclusive>
<probability_exclusive> ::= <float_between_0_and_1_exclusive>

<positive_integer> ::= <integer_gt_zero>
<non_negative_integer> ::= "0" | <integer_gt_zero>

<integer> ::= <digit> { <digit> }
<integer_gt_zero> ::= <non_zero_digit> { <digit> }
<float> ::= ["-"] <integer> "." <digit> { <digit> }
<float_gt_zero> ::= <integer_gt_zero> "." <digit> { <digit> }
                 | "0." <non_zero_digit> { <digit> }
<non_negative_float> ::= <integer> "." <digit> { <digit> }

<float_between_0_and_1_inclusive> ::= "0"
                                    | "1"
                                    | "0." <digit> { <digit> }
                                    | "1.0" { "0" }

<float_between_0_and_1_exclusive> ::= "0." <non_zero_digit> { <digit> }
                                    | "0." "0" { "0" } <non_zero_digit> { <digit> }

<boolean> ::= "true" | "false"
<string> ::= '"' { <character> } '"'
<digit> ::= "0" | <non_zero_digit>
<non_zero_digit> ::= "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
<letter> ::= "a".."z" | "A".."Z"
<year> ::= <digit> <digit> <digit> <digit>
<month> ::= "01" | "02" | "03" | "04" | "05" | "06" | "07" | "08" | "09" | "10" | "11" | "12"
<day> ::= "01".."31"
<character> ::= any printable character except '"'
<experience_level> ::= "1" | "2" | "3"
```

## Config File Grammar

```ebnf
<config_file> ::= { <config_top_level_entry> }

<config_top_level_entry> ::= <uncertainty_factors_config>
                           | <t_shirt_sizes_config>
                           | <t_shirt_size_default_category_config>
                           | <t_shirt_size_unit_config>
                           | <story_points_config>
                           | <story_point_unit_config>
                           | <simulation_config>
                           | <lognormal_config>
                           | <output_config>
                           | <staffing_config>
                           | <constrained_scheduling_config>
                           | <sprint_defaults_config>

<uncertainty_factors_config> ::= "uncertainty_factors:" <map>
<t_shirt_sizes_config> ::= "t_shirt_sizes:" <map>
<t_shirt_size_default_category_config> ::= "t_shirt_size_default_category:" <identifier>
<t_shirt_size_unit_config> ::= "t_shirt_size_unit:" <time_unit>
<story_points_config> ::= "story_points:" <map>
<story_point_unit_config> ::= "story_point_unit:" <time_unit>

<simulation_config> ::= "simulation:"
                        ["iterations:" <positive_integer>]

<lognormal_config> ::= "lognormal:"
                       ["high_percentile:" <integer>]

<output_config> ::= "output:"
                    ["formats:" <string_list>]
                    ["histogram_bins:" <positive_integer>]
                    ["max_stored_critical_paths:" <positive_integer>]
                    ["critical_path_report_limit:" <positive_integer>]

<staffing_config> ::= "staffing:" <map>

<constrained_scheduling_config> ::= "constrained_scheduling:"
                                    ["sickness_prob:" <probability>]
                                    ["assignment_mode:" ("greedy_single_pass" | "criticality_two_pass")]
                                    ["pass1_iterations:" <positive_integer>]

<sprint_defaults_config> ::= "sprint_defaults:"
                             ["planning_confidence_level:" <probability_exclusive>]
                             ["removed_work_treatment:" ("churn_only" | "reduce_backlog")]
                             ["velocity_model:" ("empirical" | "neg_binomial")]
                             ["volatility_disruption_probability:" <probability>]
                             ["volatility_disruption_multiplier_low:" <non_negative_number>]
                             ["volatility_disruption_multiplier_expected:" <non_negative_number>]
                             ["volatility_disruption_multiplier_high:" <non_negative_number>]
                             ["spillover_model:" ("table" | "logistic")]
                             ["spillover_size_reference_points:" <positive_number>]
                             ["spillover_size_brackets:" <list>]
                             ["spillover_consumed_fraction_alpha:" <positive_number>]
                             ["spillover_consumed_fraction_beta:" <positive_number>]
                             ["spillover_logistic_slope:" <positive_number>]
                             ["spillover_logistic_intercept:" <float>]
                             [<sprint_sickness_defaults_config>]

<sprint_sickness_defaults_config> ::= "sickness:"
                                      ["enabled:" <boolean>]
                                      ["probability_per_person_per_week:" <probability_exclusive>]
                                      ["duration_log_mu:" <float>]
                                      ["duration_log_sigma:" <positive_number>]

# Generic placeholders for map/list structures accepted by YAML/TOML.
# Their semantic content is constrained by Pydantic models.
<map> ::= mapping object
<list> ::= list/array
<string_list> ::= list/array of strings
```

## Semantic Constraints

### Project-level

1. `start_date` must be a valid ISO date in `YYYY-MM-DD` format.
2. `probability_red_threshold` must be strictly less than `probability_green_threshold`.
3. Default confidence levels are `[10, 25, 50, 75, 80, 85, 90, 95, 99]`.
4. Default thresholds are:
   - `probability_red_threshold`: `0.50`
   - `probability_green_threshold`: `0.90`
5. If `team_size` is omitted or `0`, only explicitly listed resources are used.
6. If `team_size > explicit_resources`, unnamed default resources are generated up to `team_size`.
7. If `team_size < explicit_resources`, validation fails.

### Tasks and estimates

1. Task IDs must be unique.
2. At least one task is required.
3. Dependency IDs must reference existing tasks.
4. Circular dependencies are not allowed.
5. For explicit estimates:
   - `low <= expected <= high`
   - if effective distribution is `lognormal`, then `low < expected < high`
   - `unit` is optional; when omitted it defaults to `hours`
6. Accepted explicit estimate aliases are:
   - `low` or `min`
   - `expected` or `most_likely`
   - `high` or `max`
7. Symbolic estimate rules:
   - exactly one of `t_shirt_size` or `story_points` may be set
   - `unit` must not be set when using symbolic estimates
8. `max_resources >= 1`.
9. `min_experience_level` must be `1`, `2`, or `3`.
10. `spillover_probability_override` must be in `[0.0, 1.0]`.

### Uncertainty factors

1. Factor names are open-ended strings.
2. Factor levels are open-ended strings.
3. Missing factors or levels fall back to multiplier `1.0` at runtime.

### Resources and calendars

1. Resource names must be unique after normalization.
2. If a resource omits `name` but provides legacy `id`, `id` becomes `name`.
3. If both `name` and `id` are omitted, generated names `resource_001`, `resource_002`, ... are assigned.
4. Resource bounds:
   - `availability` in `(0.0, 1.0]`
   - `experience_level` in `{1, 2, 3}`
   - `productivity_level` in `[0.1, 2.0]`
   - `sickness_prob` in `[0.0, 1.0]`
5. Calendar IDs must be unique.
6. `work_days` values must be in `1..7`.
7. Resource `calendar` references must exist; when no calendars are defined, `default` is valid.
8. Task `resources` entries must reference existing resources.
9. If a task references named resources, each referenced resource must satisfy that task's `min_experience_level`.

### Sprint planning

1. When `sprint_planning.enabled` is true, at least two usable historical rows with positive delivery signal are required.
2. History rows must include exactly one of `completed_story_points` or `completed_tasks`.
3. Unit-family fields in each row must match the completed field family.
4. `sprint_id` values must be unique.
5. In `story_points` capacity mode, every task must have resolvable planning story points.
6. If `spillover.enabled` is true, every task must have resolvable planning story points.
7. Future overrides:
   - at least one locator (`sprint_number` or `start_date`) is required
   - `start_date` must align to sprint boundaries
   - if both locators are present, they must resolve to the same sprint
   - two overrides may not resolve to the same sprint
8. Volatility multipliers must satisfy `low <= expected <= high`.
9. Sprint sickness constraints:
   - `probability_per_person_per_week` in `(0.0, 1.0)`
   - `duration_log_sigma > 0`

### Risks

1. `probability` must be in `[0.0, 1.0]`.
2. Numeric `impact` is interpreted as hours.
3. Absolute structured impact supports `type: absolute`, `value`, and optional `unit` (`hours`, `days`, `weeks`).
4. Percentage impact supports `type: percentage` and `value`.
5. A global uniqueness constraint for risk IDs is not currently enforced by a dedicated validator.

### Config

1. `constrained_scheduling.sickness_prob` must be in `[0.0, 1.0]`.
2. `constrained_scheduling.assignment_mode` must be `greedy_single_pass` or `criticality_two_pass`.
3. `constrained_scheduling.pass1_iterations` must be `> 0`.
4. `sprint_defaults.sickness.probability_per_person_per_week` must be in `(0.0, 1.0)`.
5. `sprint_defaults.sickness.duration_log_sigma` must be `> 0`.
6. `sprint_defaults.sickness.duration_log_mu` is any real number.

## Example Validation

### Valid Core Project

```yaml
project:
  name: "Valid Project"
  description: "Core simulation"
  start_date: "2025-11-01"
  distribution: "triangular"
  confidence_levels: [50, 80, 90, 95]
  probability_red_threshold: 0.50
  probability_green_threshold: 0.90

tasks:
  - id: "task_001"
    name: "Backend Development"
    estimate:
      min: 5
      most_likely: 8
      max: 15
    risks:
      - id: "tech_debt"
        name: "Technical debt discovered"
        probability: 0.30
        impact:
          type: "absolute"
          value: 2
          unit: "days"

  - id: "task_002"
    name: "Integration"
    estimate:
      distribution: "lognormal"
      low: 1
      expected: 3
      high: 8
      unit: "days"
    dependencies: ["task_001"]
```

### Valid Sprint-Planning Project

```yaml
project:
  name: "Sprint Forecast"
  start_date: "2026-05-04"

tasks:
  - id: "task_001"
    name: "Discovery"
    estimate:
      story_points: 3
    dependencies: []
  - id: "task_002"
    name: "Build"
    estimate:
      story_points: 5
    dependencies: ["task_001"]

sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    - sprint_id: "SPR-001"
      completed_story_points: 10
      spillover_story_points: 1
    - sprint_id: "SPR-002"
      completed_story_points: 9
      spillover_story_points: 2
```

### Valid Config Snippet

```yaml
constrained_scheduling:
  sickness_prob: 0.05
  assignment_mode: criticality_two_pass
  pass1_iterations: 500

sprint_defaults:
  planning_confidence_level: 0.85
  velocity_model: neg_binomial
  sickness:
    enabled: true
    probability_per_person_per_week: 0.06
    duration_log_mu: 0.693
    duration_log_sigma: 0.75
```

### Invalid Examples

```yaml
# INVALID: min > expected
estimate:
  low: 10
  expected: 5
  high: 15

# INVALID: circular dependency
tasks:
  - id: "task_a"
    dependencies: ["task_b"]
  - id: "task_b"
    dependencies: ["task_a"]

# INVALID: unsupported story point
estimate:
  story_points: 4

# INVALID: symbolic estimate must not set unit
estimate:
  t_shirt_size: "M"
  unit: "days"

# INVALID: sprint planning needs at least two usable history rows
sprint_planning:
  enabled: true
  sprint_length_weeks: 2
  capacity_mode: story_points
  history:
    - sprint_id: "S1"
      completed_story_points: 0
```

## Format Support

This grammar is implemented for both YAML and TOML:

- YAML (`.yaml`, `.yml`)
- TOML (`.toml`)

## Parser Implementation

Core implementation components:

- Pydantic v2 model validation
- PyYAML parsing
- tomli/tomli-w TOML parsing and writing

See [src/mcprojsim/models/project.py](../src/mcprojsim/models/project.py) and [src/mcprojsim/config.py](../src/mcprojsim/config.py).

