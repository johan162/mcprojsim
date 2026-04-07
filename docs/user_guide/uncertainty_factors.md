# Uncertainty Factors

**Uncertainty factors** are persistent conditions that systematically stretch or compress estimated effort. An inexperienced team, poorly defined requirements, or high technical complexity are uncertainty factors. They are not random events; they are known characteristics of the working environment that affect how long tasks are likely to take.

Understanding both **risks** and **uncertainty factors** — and when to use each — is essential for building realistic project models.

Every task can specify its own set of uncertainty factors. The simulator reads these labels, looks up the corresponding numeric multipliers from the configuration file, and multiplies them together to produce a single adjustment that scales the sampled base duration.

In the task pipeline, uncertainty factors are applied **after estimate sampling** and **before risk impacts** are added.

## Supported Uncertainty Factors

`mcprojsim` supports five uncertainty factors out of the box. Each factor maps qualitative labels to numeric multipliers defined in the configuration file.

### Team Experience

Reflects how familiar the team is with the technology and domain.

| Level    | Default Multiplier | Effect                        |
|----------|--------------------|-------------------------------|
| `high`   | 0.90               | 10% faster than baseline      |
| `medium` | 1.00               | No adjustment (baseline)      |
| `low`    | 1.30               | 30% slower than baseline      |

An experienced team working in a familiar domain is likely to move faster. An inexperienced team facing unfamiliar technology needs more time for learning, mistakes, and rework.

### Requirements Maturity

Captures how well-defined and stable the requirements are.

| Level    | Default Multiplier | Effect                        |
|----------|--------------------|-------------------------------|
| `high`   | 1.00               | Clear, stable requirements    |
| `medium` | 1.15               | Some ambiguity or gaps        |
| `low`    | 1.40               | High ambiguity, likely changes|

Poorly defined requirements lead to rework, misunderstandings, and scope changes. Even a skilled team slows down when the target keeps moving.

### Technical Complexity

Indicates how technically challenging the work is.

| Level    | Default Multiplier | Effect                        |
|----------|--------------------|-------------------------------|
| `low`    | 1.00               | Well-understood technology    |
| `medium` | 1.20               | Moderate complexity           |
| `high`   | 1.50               | Novel or cutting-edge work    |

Work involving unfamiliar architectures, new frameworks, or complex algorithms takes longer than routine development even for experienced teams.

### Team Distribution

Reflects whether the team is colocated or distributed.

| Level         | Default Multiplier | Effect                                |
|---------------|--------------------|---------------------------------------|
| `colocated`   | 1.00               | Same location, easy communication     |
| `distributed` | 1.25               | Remote/distributed, overhead applies  |

Distributed teams face communication delays, timezone differences, and coordination overhead. This factor accounts for that systematic slowdown.

### Integration Complexity

Measures how much integration work is involved with other systems.

| Level    | Default Multiplier | Effect                        |
|----------|--------------------|-------------------------------|
| `low`    | 1.00               | Minimal integration needed    |
| `medium` | 1.15               | Moderate integration effort   |
| `high`   | 1.35               | Complex multi-system integration |

Tasks that require coordination with external APIs, databases, or third-party services carry additional overhead from interface changes, testing environments, and compatibility issues.

## How the Combined Multiplier Is Calculated

When a task specifies multiple uncertainty factors, their multipliers are multiplied together to produce a single combined adjustment. The sampled base duration is then scaled by this combined multiplier.

**Formula:**

$$\text{adjusted\_duration} = \text{base\_duration} \times \prod_{i=1}^{n} \text{multiplier}_i$$

**Example calculation:**

Consider a task with the following uncertainty factors:

| Factor                  | Level        | Multiplier |
|-------------------------|--------------|------------|
| `team_experience`       | `medium`     | 1.00       |
| `requirements_maturity` | `low`        | 1.40       |
| `technical_complexity`  | `high`       | 1.50       |
| `team_distribution`     | `distributed`| 1.25       |
| `integration_complexity`| `medium`     | 1.15       |

Combined multiplier: $1.00 \times 1.40 \times 1.50 \times 1.25 \times 1.15 = 3.0188$

If the sampled base duration is 5 days, the adjusted duration becomes $5 \times 3.0188 \approx 15.1$ days.

This illustrates why multiple adverse factors compound quickly. Even moderate individual adjustments can produce a significant overall effect when multiplied together.

\newpage

## Validation and Fallback Behavior

The current implementation distinguishes between project-file schema validation and runtime multiplier lookup:

- The task model defines five named uncertainty fields: `team_experience`, `requirements_maturity`, `technical_complexity`, `team_distribution`, `integration_complexity`.
- When these labels are looked up at runtime, missing factor names or unknown levels in the active configuration fall back to multiplier `1.0`.

Practical implications:

- If a configured factor name is missing entirely, that factor contributes no scaling (`1.0`).
- If a level string is not present under a configured factor, that factor also contributes `1.0`.
- In other words, unknown or unmatched labels do not raise an error in multiplier lookup; they behave like neutral multipliers.

For predictable behavior, keep project-file labels aligned with your configured level names.

## Default Values

If a task does not specify a particular uncertainty factor, the default level is applied. The defaults are:

| Factor                  | Default Level |
|-------------------------|---------------|
| `team_experience`       | `medium`      |
| `requirements_maturity` | `medium`      |
| `technical_complexity`  | `medium`      |
| `team_distribution`     | `colocated`   |
| `integration_complexity`| `medium`      |

A task that omits the `uncertainty_factors` block entirely still receives these defaults, resulting in a combined multiplier based on the default levels. In the default configuration, `medium` maps to `1.00` for `team_experience` but `1.15` for `requirements_maturity`, `1.20` for `technical_complexity`, and `1.15` for `integration_complexity`, so the default combined multiplier is not simply `1.0`:

$$1.00 \times 1.15 \times 1.20 \times 1.00 \times 1.15 \approx 1.587$$

This means a task with no explicit uncertainty factors will still have its sampled base duration stretched by roughly 59% before any risks are applied. If your project results look longer than your estimates, this default compounding is a likely contributor. Setting `requirements_maturity`, `technical_complexity`, and `integration_complexity` to `"high"`, `"low"`, and `"low"` respectively, or calibrating their multipliers in your configuration file, are common ways to bring the baseline back toward `1.0`.

\newpage

## Defining Uncertainty Factors in the Project File

Uncertainty factors are specified per task. You only need to include the factors you want to set explicitly; any omitted factors use their default level.

```yaml
tasks:
  - id: "task_001"
    name: "Database schema design"
    estimate:
      low: 3
      expected: 5
      high: 10
      unit: "days"
    uncertainty_factors:
      team_experience: "high"
      requirements_maturity: "medium"
      technical_complexity: "low"
      team_distribution: "colocated"
      integration_complexity: "low"
```

You may also specify only the factors that differ from the defaults:

```yaml
tasks:
  - id: "task_010"
    name: "Prototype ML pipeline"
    estimate:
      low: 8
      expected: 14
      high: 25
      unit: "days"
    uncertainty_factors:
      team_experience: "low"
      technical_complexity: "high"
```

Here, `requirements_maturity`, `team_distribution`, and `integration_complexity` all take their default values.

\newpage

## Configuring Uncertainty Factor Multipliers

The numeric multipliers for each factor and level are defined in the configuration file (`config.yaml`), not in the project file. This separation means the project file describes the project conditions, while the configuration file defines how the organization interprets those conditions.

### Default Configuration

```yaml
uncertainty_factors:
  team_experience:
    high: 0.90      # Experienced team is 10% faster
    medium: 1.0     # Baseline
    low: 1.30       # Inexperienced team is 30% slower
  requirements_maturity:
    high: 1.0       # Well-defined requirements
    medium: 1.15    # Some ambiguity
    low: 1.40       # High ambiguity
  technical_complexity:
    low: 1.0        # Simple, well-understood technology
    medium: 1.20    # Moderate complexity
    high: 1.50      # High complexity, cutting-edge tech
  team_distribution:
    colocated: 1.0  # Team in same location
    distributed: 1.25  # Distributed team with communication overhead

  integration_complexity:
    low: 1.0        # Minimal integration
    medium: 1.15    # Moderate integration
    high: 1.35      # Complex integration with multiple systems
```

## Customizing Multipliers

You can adjust the multipliers to match your organization's experience. For example, if your organization has found that distributed teams incur a higher overhead than the default 25%, you might change that value:

```yaml
uncertainty_factors:
  team_distribution:
    colocated: 1.0
    distributed: 1.40  # 40% overhead for distributed work
```

Any values you specify in your configuration file are merged with the defaults. You only need to include the factors or levels you want to override.

If you provide a factor with only some levels (for example only `distributed` under `team_distribution`), unspecified levels continue to use defaults.

If you add additional factor names in configuration that are not referenced by the project task schema, they are effectively unused by the current simulation pipeline.

## Recommended Authoring Pattern

- Keep task files focused on the five supported factor fields.
- Keep organization-specific multiplier calibration in `config.yaml`.
- Override only the factor levels that differ from defaults.
- Recheck combined multiplier magnitude for heavily adverse combinations to avoid unintentionally extreme schedules.



## Summary

| Concept                | What It Models                              | When It Applies         | How It Affects Duration           |
|------------------------|---------------------------------------------|-------------------------|-----------------------------------|
| **Uncertainty factor** | A persistent working condition              | Per task, every iteration| Multiplies the sampled duration   |

- Uncertainty factors are **multiplicative**: they scale the sampled base duration before risks are evaluated.
- Multiple uncertainty factors **compound**: their multipliers are multiplied together, which can produce significant combined effects.

\newpage

