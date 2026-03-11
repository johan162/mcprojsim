# Formal Grammar Specification

This document provides a complete formal grammar specification for Monte Carlo Project Simulator input files in Extended Backus-Naur Form (EBNF) notation.

## Notation Conventions

- `::=` means "is defined as"
- `|` means "or" (alternation)
- `[]` means "optional" (zero or one occurrence)
- `{}` means "zero or more occurrences"
- `()` groups elements
- `""` denotes literal strings
- `<>` denotes terminal or non-terminal symbols
- Comments start with `#`

## Complete Grammar

```ebnf
# Top-Level Structure
<project_file> ::= <project_section> <tasks_section> [<project_risks_section>]

# Project Section
<project_section> ::= "project:" 
                      <project_metadata>

<project_metadata> ::= <project_name>
                       <start_date>
                       [<hours_per_day>]
                       [<confidence_levels>]
                       [<probability_thresholds>]

<project_name> ::= "name:" <string>

<start_date> ::= "start_date:" <date_string>

<date_string> ::= <year> "-" <month> "-" <day>
                # YYYY-MM-DD format

<hours_per_day> ::= "hours_per_day:" <positive_number>
                  # Default: 8.0. Controls conversion between days/weeks and hours.

<confidence_levels> ::= "confidence_levels:" "[" <percentile_list> "]"

<percentile_list> ::= <percentile> { "," <percentile> }

<percentile> ::= <integer>
               # Range: 1-99, typically: 50, 75, 80, 85, 90, 95

<probability_thresholds> ::= <red_threshold> <green_threshold>

<red_threshold> ::= "probability_red_threshold:" <probability>

<green_threshold> ::= "probability_green_threshold:" <probability>

<probability> ::= <float>
                # Range: 0.0-1.0

# Tasks Section
<tasks_section> ::= "tasks:" <task_list>

<task_list> ::= { <task> }

<task> ::= "-" <task_properties>

<task_properties> ::= <task_id>
                      <task_name>
                      <estimate>
                      <dependencies>
                      [<uncertainty_factors>]
                      [<task_risks>]

<task_id> ::= "id:" <identifier>

<task_name> ::= "name:" <string>

<identifier> ::= <letter> { <letter> | <digit> | "_" }

# Estimate Section
<estimate> ::= "estimate:" <estimate_spec>

<estimate_spec> ::= <triangular_estimate> | <lognormal_estimate> | <tshirt_estimate> | <story_point_estimate>

<triangular_estimate> ::= <min_value>
                         <most_likely_value>
                         <max_value>
                         <unit>

<lognormal_estimate> ::= "distribution:" "lognormal"
                        <most_likely_value>
                        <standard_deviation>
                        <unit>

<tshirt_estimate> ::= "t_shirt_size:" <tshirt_size>
                     # unit must NOT be specified; it comes from configuration

<tshirt_size> ::= "XS" | "S" | "M" | "L" | "XL" | "XXL"

<story_point_estimate> ::= "story_points:" <story_point_value>
                          # unit must NOT be specified; it comes from configuration

<story_point_value> ::= "1" | "2" | "3" | "5" | "8" | "13" | "21"

<min_value> ::= "min:" <positive_number>

<most_likely_value> ::= "most_likely:" <positive_number>

<max_value> ::= "max:" <positive_number>

<standard_deviation> ::= "standard_deviation:" <positive_number>

<unit> ::= "unit:" <time_unit>

<time_unit> ::= "hours" | "days" | "weeks"
               # Only valid for explicit estimates (triangular and lognormal)

# Dependencies
<dependencies> ::= "dependencies:" <dependency_list>

<dependency_list> ::= "[]" | "[" <identifier_list> "]"

<identifier_list> ::= <identifier> { "," <identifier> }

# Uncertainty Factors
<uncertainty_factors> ::= "uncertainty_factors:" <factor_list>

<factor_list> ::= { <factor> }

<factor> ::= <factor_name> ":" <factor_level>

<factor_name> ::= "team_experience" 
                | "requirements_maturity"
                | "technical_complexity"
                | "integration_complexity"
                | "team_distribution"
                | <custom_factor_name>

<factor_level> ::= "low" | "medium" | "high"

<custom_factor_name> ::= <identifier>

# Task Risks
<task_risks> ::= "risks:" <risk_list>

<risk_list> ::= { <risk> }

# Project Risks Section
<project_risks_section> ::= "project_risks:" <risk_list>

# Risk Definition
<risk> ::= "-" <risk_properties>

<risk_properties> ::= <risk_id>
                     <risk_name>
                     <risk_probability>
                     <risk_impact>

<risk_id> ::= "id:" <identifier>

<risk_name> ::= "name:" <string>

<risk_probability> ::= "probability:" <probability>

<risk_impact> ::= "impact:" <impact_spec>

<impact_spec> ::= <fixed_impact> | <percentage_impact>

<fixed_impact> ::= <positive_number>
                 # Impact in time units (days)

<percentage_impact> ::= "type:" "percentage"
                       "value:" <positive_number>
                       # Percentage value (e.g., 25 for 25%)

# Primitive Types
<string> ::= '"' { <character> } '"'

<positive_number> ::= <integer> | <float>

<integer> ::= <digit> { <digit> }

<float> ::= <integer> "." <digit> { <digit> }

<digit> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"

<letter> ::= "a".."z" | "A".."Z"

<year> ::= <digit> <digit> <digit> <digit>

<month> ::= "01" | "02" | "03" | "04" | "05" | "06" | 
            "07" | "08" | "09" | "10" | "11" | "12"

<day> ::= "01".."31"

<character> ::= any printable character except '"'
```

## Semantic Constraints

Beyond the syntactic grammar above, the following semantic constraints must be satisfied:

### Project-Level Constraints

1. **Date Format**: `start_date` must be a valid ISO 8601 date (YYYY-MM-DD)
2. **Percentiles**: Values in `confidence_levels` must be unique, sorted in ascending order, and in range [1, 99]
3. **Thresholds**: `probability_red_threshold` < `probability_green_threshold`
4. **Default Percentiles**: If not specified, defaults to `[25, 50, 75, 80, 85, 90, 95, 99]`
5. **Default Thresholds**: 
   - `probability_red_threshold`: 0.50 (50%)
   - `probability_green_threshold`: 0.90 (90%)

### Task-Level Constraints

1. **Task IDs**: Must be unique across all tasks
2. **Estimate Validity** (Triangular):
   - `min` ≤ `most_likely` ≤ `max`
   - All values must be positive
3. **Estimate Validity** (Log-Normal):
   - `most_likely` > 0
   - `standard_deviation` > 0
4. **Estimate Validity** (T-Shirt Size):
   - Must be one of: `XS`, `S`, `M`, `L`, `XL`, `XXL`
   - Values are resolved from configuration file
   - `unit` must NOT be specified in the project file; unit comes from `t_shirt_size_unit` in config (default: `"hours"`)
   - Default values (in hours):
     * `XS`: min=0.5, most_likely=1, max=2
     * `S`: min=1, most_likely=2, max=4
     * `M`: min=3, most_likely=5, max=8
     * `L`: min=5, most_likely=8, max=13
     * `XL`: min=8, most_likely=13, max=21
     * `XXL`: min=13, most_likely=21, max=34
  5. **Estimate Validity** (Story Points):
    - Must be one of: `1`, `2`, `3`, `5`, `8`, `13`, `21`
    - `unit` must NOT be specified in the project file; unit comes from `story_point_unit` in config (default: `"days"`)
    - Values are resolved from configuration file to numeric ranges
    - Default values (in days):
      * `1`: min=0.5, most_likely=1, max=3
      * `2`: min=1, most_likely=2, max=4
      * `3`: min=1.5, most_likely=3, max=5
      * `5`: min=3, most_likely=5, max=8
      * `8`: min=5, most_likely=8, max=15
      * `13`: min=8, most_likely=13, max=21
      * `21`: min=13, most_likely=21, max=34
  6. **Dependencies**: 
   - Referenced task IDs must exist
   - No circular dependencies allowed
   - Dependencies must form a Directed Acyclic Graph (DAG)
  7. **Uncertainty Factors**: Custom factor names allowed beyond predefined set

### Risk Constraints

1. **Risk IDs**: Must be unique within their scope (task-level or project-level)
2. **Probability Range**: 0.0 ≤ probability ≤ 1.0
3. **Impact Values**:
   - Fixed impact: positive number; plain numbers are treated as hours
   - Structured absolute impact: `type: "absolute"`, `value`, and `unit` (`"hours"`, `"days"`, or `"weeks"`)
   - Percentage impact: positive number (percentage of task/project duration)
4. **Impact Type**: If `type: percentage` is specified, `value` must be present

## Example Validation

### Valid Example

```yaml
project:
  name: "Valid Project"
  start_date: "2025-11-01"
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
      unit: "days"
    dependencies: []
    uncertainty_factors:
      team_experience: "medium"
      technical_complexity: "high"
    risks:
      - id: "tech_debt"
        name: "Technical debt discovered"
        probability: 0.30
        impact: 5

  - id: "task_002"
    name: "Integration"
    estimate:
      distribution: "lognormal"
      most_likely: 3
      standard_deviation: 1.5
      unit: "days"
    dependencies: ["task_001"]

  - id: "task_003"
    name: "Quick Fix"
    estimate:
      t_shirt_size: "S"
    dependencies: []

  - id: "task_004"
    name: "Backlog Item"
    estimate:
      story_points: 5
    dependencies: []

project_risks:
  - id: "resource_loss"
    name: "Team member leaves"
    probability: 0.20
    impact:
      type: "percentage"
      value: 25
```

### Invalid Examples

```yaml
# INVALID: min > most_likely
estimate:
  min: 10
  most_likely: 5  # ERROR: must be >= min
  max: 15
  unit: "days"

# INVALID: circular dependency
tasks:
  - id: "task_a"
    dependencies: ["task_b"]
  - id: "task_b"
    dependencies: ["task_a"]  # ERROR: circular reference

# INVALID: probability out of range
risks:
  - id: "risk_001"
    probability: 1.5  # ERROR: must be 0.0-1.0
    impact: 10

# INVALID: threshold inconsistency
project:
  probability_red_threshold: 0.90
  probability_green_threshold: 0.50  # ERROR: must be > red_threshold

# INVALID: unknown T-shirt size
estimate:
  t_shirt_size: "XXXL"  # ERROR: not a valid size (XS, S, M, L, XL, XXL)

# INVALID: unit specified on T-shirt size estimate
estimate:
  t_shirt_size: "M"
  unit: "days"  # ERROR: T-shirt size estimates must not specify 'unit'

# INVALID: unsupported Story Point value
estimate:
  story_points: 4  # ERROR: must be one of 1, 2, 3, 5, 8, 13, 21

# INVALID: unit specified on Story Point estimate
estimate:
  story_points: 5
  unit: "days"  # ERROR: Story Point estimates must not specify 'unit'
```

## Format Support

This grammar is implemented in both YAML and TOML formats:

- **YAML**: Primary format (`.yaml` or `.yml` files)
- **TOML**: Alternative format (`.toml` files)

Both formats support the same semantic structure defined by this grammar.

## Parser Implementation

The grammar is implemented using:

- **Pydantic 2.0**: For schema validation and type checking
- **PyYAML**: For YAML parsing
- **tomli/tomli-w**: For TOML parsing

See `src/mcprojsim/models/` for the complete Pydantic model definitions that enforce this grammar.

## T-Shirt Size Configuration

T-shirt sizes can be customized via a configuration file. The default values (listed in the [Semantic Constraints](#semantic-constraints) section above) follow a Fibonacci-like progression. See [Task Estimation — T-Shirt Size Estimates](user_guide/task_estimation.md#t-shirt-size-estimates) for the full default mapping table and customization guidance, and [Configuration](configuration.md) for the configuration file format.

## Story Point Configuration

Story Point mappings can be customized via a configuration file in the same way. The default values are listed in the [Semantic Constraints](#semantic-constraints) section above. See [Task Estimation — Story Point Estimates](user_guide/task_estimation.md#story-point-estimates) for the full default mapping table and customization guidance.

To view the current configuration including T-shirt sizes and Story Point mappings, use:

```bash
mcprojsim config show
```

## Related Documentation

- [Getting Started](user_guide/getting_started.md) - Install and run your first simulation
- [Examples](examples.md) - Complete working examples
- [API Reference](api_reference.md) - Detailed API documentation
- [Configuration](configuration.md) - Configuration options
