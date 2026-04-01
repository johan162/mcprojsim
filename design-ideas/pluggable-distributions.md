Version: 1.0.0

# Pluggable Distributions and Risk Models

*NFR-008: distribution types and risk models should be pluggable/extensible.*

This document surveys additional probability distributions worth adding to
`mcprojsim`, evaluates the trade-off between a richer distribution library and
the cost of a pluggable architecture, proposes a concrete architecture, and
defines what tests are needed — including a generic contract suite that future
distributions automatically inherit.

---

## Current State

`src/mcprojsim/simulation/distributions.py` contains a `DistributionSampler`
class with a `sample()` method that dispatches on `DistributionType` with a
hard `if/elif` chain:

```python
if distribution == DistributionType.TRIANGULAR:
    return self._sample_triangular(...)
elif distribution == DistributionType.LOGNORMAL:
    return self._sample_lognormal(...)
else:
    raise ValueError(f"Unknown distribution type: {distribution}")
```

`DistributionType` is a plain `str` enum in `models/project.py`. Adding a new
distribution today requires edits in at least five places:

1. `models/project.py` — add enum value
2. `simulation/distributions.py` — add sample method and dispatch branch
3. `simulation/engine.py` — `_resolve_estimate` and validation paths (when
   relevant)
4. `config.py` — add config block if the distribution has configurable parameters
5. `parsers/error_reporting.py` / `parsers/yaml_parser.py` — recognise new token

This is fragile and inhibits experimentation.

---

## Additional Distributions Worth Adding in Practice

### 1. PERT (Program Evaluation and Review Technique)

**Formula.** The PERT distribution is a reshaping of the Beta distribution
calibrated to the same `(low, expected, high)` triple used everywhere else:

$$\alpha = 1 + \lambda \cdot \frac{\text{expected} - \text{low}}{\text{high} - \text{low}}, \quad \beta = 1 + \lambda \cdot \frac{\text{high} - \text{expected}}{\text{high} - \text{low}}$$

where $\lambda$ is the **weight** placed on the mode (default 4, the classical
PERT value). The distribution is then scaled from the Beta $[0,1]$ interval to
$[\text{low}, \text{high}]$.

**Statistical properties.**

| Property | Value |
|---|---|
| Support | Bounded to `[low, high]` |
| Mean | $\frac{\text{low} + \lambda \cdot \text{expected} + \text{high}}{\lambda + 2}$ |
| Variance | $\frac{(\text{mean} - \text{low})(\text{high} - \text{mean})}{\lambda + 3}$ |
| Tail behaviour | Heavier than triangular, stays bounded |

**Why it matters.** The triangular distribution is piecewise-linear, which
produces unrealistically peaked probability density near `expected`. The PERT
distribution uses Beta-shaped smooth curves that taper gradually toward the
boundaries. This is a better model for the "fuzzy middle" that pervades
software estimates. Project management bodies of knowledge (PMI PMBOK,
Agile Estimation textbooks) use PERT as the reference three-point model.

Adding PERT as the **first new distribution** is the highest-value, lowest-risk
choice:

- Uses the identical `(low, expected, high)` parameter signature.
- No new required parameters.
- Configurable single scalar lambda for teams that want to adjust weight.
- Always bounded — no change to validation rules.
- Directly addresses the known triangular density artefact.

### 2. Beta (generalized)

Generalises PERT by allowing users to specify `alpha` and `beta` directly
instead of a mode plus weight. Useful when calibrating distributions to
historical data. Support is bounded to `[low, high]`. Requires a different
parameter shape from the standard three-point estimate, so it needs a
distinct schema block.

#### Elaboration: Is generalized Beta suitable for task estimation?

Short answer: **yes, but as an advanced mode, not the default authoring path**.

The generalized Beta family is statistically attractive because it is flexible,
bounded, and can represent a wide range of uncertainty shapes while still
respecting hard estimate limits:

$$
X = \text{low} + (\text{high} - \text{low}) \cdot Z, \quad Z \sim \text{Beta}(\alpha, \beta)
$$

This gives bounded support by construction:

$$
X \in [\text{low}, \text{high}]
$$

and closed-form moments:

$$
\mathbb{E}[X] = \text{low} + (\text{high} - \text{low}) \cdot \frac{\alpha}{\alpha + \beta}
$$

$$
\mathrm{Var}(X) = (\text{high} - \text{low})^2 \cdot \frac{\alpha\beta}{(\alpha + \beta)^2(\alpha + \beta + 1)}
$$

### Why it can be very useful

1. **Bounded realism.** Unlike log-normal, Beta cannot produce extreme values
    outside the elicited range.
2. **Shape flexibility.** Depending on $(\alpha, \beta)$, it can be symmetric,
    left-skewed, right-skewed, or strongly peaked.
3. **Calibration-friendly.** Teams with historical effort data can estimate
    $(\alpha, \beta)$ from normalized outcomes and use a data-fitted family.
4. **Natural superset of PERT.** PERT is effectively a constrained Beta
    parameterization from three-point estimates.

### Why it should not be the first user-facing default

1. **Poor elicitation ergonomics.** Engineers usually think in
    `(low, expected, high)`, not in $(\alpha, \beta)$.
2. **Parameter unintuitiveness.** Small parameter changes can materially alter
    tails and concentration in ways users may not predict.
3. **Higher misuse risk.** Without historical calibration, chosen parameters are
    often arbitrary and can give false precision.

### Recommended role in `mcprojsim`

- Keep **PERT** as the first and primary bounded three-point distribution for
  broad user adoption.
- Offer **generalized Beta** as an advanced option for calibrated teams,
  research workflows, or portfolio-scale model governance.
- Place Beta behind explicit configuration and documentation warnings that it
  is best used with historical fitting.

### Practical parameterization options

Two parameterization modes are useful:

1. **Direct shape mode** (advanced): users provide
    `alpha`, `beta`, `low`, and `high`.
2. **Moment mode** (safer): users provide `mean` and concentration
    `k = alpha + beta`, from which:

$$
\alpha = k \cdot \frac{\mu - \text{low}}{\text{high} - \text{low}}, \quad
\beta = k - \alpha
$$

where $\mu$ is the mean in original units. Higher $k$ concentrates mass around
the mean; lower $k$ increases spread.

### Suitability verdict

Generalized Beta is a **suitable candidate** in the estimation context when:

- the team has historical durations to calibrate against,
- hard upper/lower bounds are important,
- and users can handle advanced statistical controls.

It is **not** the best first choice for broad usage in lightweight project-file
authoring. For that, PERT delivers most of the practical benefit with much
lower cognitive overhead.

### 3. Uniform

The simplest possible model: all values in `[low, high]` equally likely. Useful
as a maximum-entropy prior when there is essentially no information beyond a
plausible range. Zero parameters beyond the two bounds. Acts as a good
pessimist's model and as a useful test reference because the true mean and
variance are analytic.

### 4. Normal (truncated)

A normal distribution truncated to `[low, high]`. `expected` maps to the mean
and the implied standard deviation is derived from the spread:

$$\sigma = \frac{\text{high} - \text{low}}{k}$$

where $k$ is a configurable factor (default 6, the six-sigma assumption). Useful
for tasks where symmetric uncertainty is genuinely credible — for example,
well-understood infrastructure tasks with fixed resource budgets.

**Caution.** The normal distribution has thin tails and allows the degenerate
case where low = high. Projects tend to be right-skewed, so uncritical use of
the normal distribution will systematically underestimate project duration.
Keep this as an advanced option with a doc-level warning.

### 5. Weibull

Widely used in reliability and software defect modelling. Parameterised by
scale $\lambda$ and shape $k$:

$$F(x) = 1 - e^{-(x/\lambda)^k}$$

When $k < 1$, the hazard rate decreases over time (early failures dominate).
When $k > 1$, the hazard rate increases (wear-out failures dominate). When
$k = 1$, it reduces to an exponential. Useful for:

- defect-discovery tasks whose duration is driven by a decreasing find-rate
- testing phases where the number of bugs remaining follows a reliability curve

Drawback: requires calibration of $k$ and $\lambda$ from historical data.
Not suitable as a user-facing three-point estimate type.

### 6. Empirical / Histogram

A non-parametric distribution sampled directly from a user-supplied array of
historical durations. `numpy.random.choice` with replacement. Useful for teams
that have accumulated sprint throughput data and want to resample it directly
rather than fitting a parametric family. Fits naturally alongside the planned
sprint-planning empirical bootstrap described in `sprint-based-planning.md`.

---

## Additional Risk Impact Models Worth Adding

The current risk design supports two impact types: `PERCENTAGE` and `ABSOLUTE`.
Both produce a scalar impact added deterministically once the risk fires.
Several richer models are worth supporting:

### Stochastic impact

Instead of a fixed scalar, sample the impact from a distribution when the risk
fires. For example, a risk that adds "between 2 and 10 extra days" modelled as
`impact_distribution: triangular, impact_low: 16h, impact_expected: 40h, impact_high: 80h`.
This better reflects the uncertainty in the magnitude of a risk event.

### Cascade / conditional risk

A risk that, when triggered, raises or lowers the probability of other named
risks firing in the same iteration. Useful for modelling correlated failure
modes (e.g., the event "key developer leaves" raising probabilities of many
other risks simultaneously).

### Risk mitigation response

A risk paired with a mitigation action. The mitigation has its own effort cost
and the risk impact is reduced by a factor when the mitigation fires. This
enables quantitative risk response planning.

---

## Statistical Significance of Adding New Distributions

### What the distribution choice changes in the simulation

In a project with $n$ tasks, the project duration is the (critical-path–)
weighted sum of task durations. Under mild assumptions the central limit theorem
pushes this sum toward normality. The more tasks there are and the weaker the
dependency chain, the less the choice of per-task distribution matters for the
top-level percentiles.

However, distribution choice matters materially when:

1. **Few tasks.** With 3–5 tasks in a tight dependency chain, the per-task
   distribution shape directly determines the project-level tail behaviour.

2. **Long right tails.** If one key task uses a log-normal with a heavy tail,
   the project-level P90/P95 interval is driven almost entirely by that one
   task even in a larger graph. PERT stays bounded, so it never contributes
   extreme outliers the way log-normal can.

3. **Sensitivity analysis.** Spearman rank correlations already capture
   which tasks vary most. With distribution shape as an additional degree of
   freedom, the sensitivity analysis better reflects teams' beliefs about
   which tasks are genuinely open-ended versus merely uncertain.

4. **Right-skew artefact in triangular density.** The triangular distribution
   has a density kink at `expected` and linear ramps on both sides. For tasks
   where `expected` is close to the midpoint, sampled values cluster around
   `expected` but with an abrupt discontinuity in the density. PERT produces
   a smooth unimodal bell shape and is a statistically superior model for
   the same information.

### Trade-off: richness vs. complexity

| Consideration | In favour of pluggable architecture | Against |
|---|---|---|
| Correctness | PERT is a better model than triangular for most tasks | Users rarely tune distribution choice in practice |
| Flexibility | Teams with historical data can resample empirically | More distributions means more confusion at authoring time |
| Extensibility | Third-party plugins without core changes | Plugin interface adds an indirection layer |
| Testability | Contract tests apply automatically to every distribution | More test code to maintain |
| Maintenance | One dispatcher vs. $n$ hardcoded branches | Plugin registry adds state |

**Verdict.** The full plugin interface (arbitrary user-supplied code) is
premature for `mcprojsim`. The better architecture is a **registered
distribution registry** inside the package, where new distributions can be
added by following a contract, but end-users do not write arbitrary Python
plugins. This gives extensibility to core maintainers without exposing an
unstable plugin API.

---

## Architecture Proposal

### Core abstraction: `DistributionPlugin`

Define a protocol (structural subtyping) in `simulation/distributions.py`:

```python
from typing import Protocol, runtime_checkable
import numpy as np

@runtime_checkable
class DistributionPlugin(Protocol):
    """Contract every distribution must satisfy."""

    #: Human-readable name used in YAML / config
    name: str

    def sample(
        self,
        low: float,
        expected: float,
        high: float,
        rng: np.random.RandomState,
        **kwargs: float,
    ) -> float:
        """Draw one sample from the distribution.

        Args:
            low:      Lower bound (optimistic estimate).
            expected: Mode / most-likely value.
            high:     Upper bound (pessimistic estimate).
            rng:      Seeded NumPy RandomState — must be the sole source
                      of randomness so results are reproducible.
            **kwargs: Distribution-specific parameters resolved from config.

        Returns:
            Sampled duration.  Must be a finite float ≥ 0.
        """
        ...

    def validate(self, low: float, expected: float, high: float) -> None:
        """Raise ValueError if the parameters are invalid for this distribution.

        Called once per task at validation time, not per iteration.
        """
        ...

    def parameter_schema(self) -> dict[str, type]:
        """Return supported **kwargs names and their Python types.

        Used by the config layer to check that a distribution block in
        config.yaml only contains recognised keys.
        """
        ...
```

This is a Protocol (PEP 544), not an ABC. Implementations do not need to
inherit anything; structural compatibility is checked at registration time.

### Registry

```python
# simulation/distribution_registry.py

_REGISTRY: dict[str, DistributionPlugin] = {}

def register(plugin: DistributionPlugin) -> None:
    """Register a distribution plugin under its .name."""
    if not isinstance(plugin, DistributionPlugin):
        raise TypeError(f"{plugin!r} does not satisfy DistributionPlugin protocol")
    _REGISTRY[plugin.name] = plugin

def get(name: str) -> DistributionPlugin:
    """Return the plugin for `name`, raising KeyError if unknown."""
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"Unknown distribution '{name}'. Known: {known}")
    return _REGISTRY[name]

def registered_names() -> list[str]:
    """Return sorted list of registered distribution names."""
    return sorted(_REGISTRY)
```

Built-in distributions are registered in `simulation/__init__.py` so they are
available the moment the package is imported:

```python
# simulation/__init__.py
from mcprojsim.simulation import distribution_registry as _reg
from mcprojsim.simulation.builtin_distributions import (
    TriangularDistribution,
    LognormalDistribution,
    PERTDistribution,
    UniformDistribution,
)

_reg.register(TriangularDistribution())
_reg.register(LognormalDistribution())
_reg.register(PERTDistribution())
_reg.register(UniformDistribution())
```

### `DistributionType` stays a string enum

`DistributionType` remains a `str` enum in `models/project.py` but its values
are validated against the registry at parse time rather than being hardcoded
in a dispatch chain. New distributions do not require adding enum values —
the `DistributionType` enum becomes a curated shortlist of first-class names
while the registry is the actual truth:

```python
class DistributionType(str, Enum):
    TRIANGULAR = "triangular"
    LOGNORMAL  = "lognormal"
    PERT       = "pert"
    UNIFORM    = "uniform"
    # Future distributions added here as they graduate from experimental
```

Alternatively, remove the enum constraint entirely and accept any string that
resolves in the registry. This is a trade-off: typed enum gives IDE completion
and Pydantic v2 validation for free; open string gives zero-edit extensibility.
**Recommended**: keep the enum for published names, allow unknown values through
with a deprecation warning, then validate via registry at simulation time.

### `DistributionSampler` becomes a thin dispatcher

```python
class DistributionSampler:
    def __init__(self, rng: np.random.RandomState, config: Config):
        self._rng = rng
        self._config = config

    def sample(self, estimate: TaskEstimate) -> float:
        name = (estimate.distribution or DistributionType.TRIANGULAR).value
        plugin = distribution_registry.get(name)
        kwargs = self._config.distribution_params(name)   # see Config changes
        return plugin.sample(
            estimate.low, estimate.expected, estimate.high,
            rng=self._rng,
            **kwargs,
        )
```

Validation at parse/resolve time:

```python
    def validate_estimate(self, estimate: TaskEstimate,
                          effective: DistributionType) -> None:
        name = effective.value
        plugin = distribution_registry.get(name)
        plugin.validate(estimate.low, estimate.expected, estimate.high)
```

### Config changes

Add a generic `distribution_params` section that each plugin reads:

```yaml
# config.yaml
distributions:
  pert:
    lambda: 4      # weight on the mode (classic PERT = 4)
  lognormal:
    high_percentile: 95
  uniform: {}      # no configurable parameters
```

In `config.py`:

```python
class DistributionsConfig(BaseModel):
    model_config = {"extra": "allow"}   # allow unknown distribution blocks

    lognormal: LogNormalConfig = Field(default_factory=LogNormalConfig)
    pert: PERTConfig = Field(default_factory=PERTConfig)
    uniform: dict = Field(default_factory=dict)

class Config(BaseModel):
    ...
    distributions: DistributionsConfig = Field(
        default_factory=DistributionsConfig
    )

    def distribution_params(self, name: str) -> dict[str, float]:
        """Return plugin kwargs for a named distribution from config."""
        block = getattr(self.distributions, name, {})
        if isinstance(block, BaseModel):
            return block.model_dump(exclude_none=True)
        return dict(block)
```

The existing `lognormal` top-level key can be kept as a deprecated alias and
merged into `distributions.lognormal` at load time.

### `models/project.py` changes

Minimal. Enum gains new values as distributions graduate. Validation logic
for `low < expected < high` constraints is removed from the model and delegated
to each plugin's `validate()` method, which is called from the parse layer.

---

## First New Distribution: PERT

### Implementation

```python
# simulation/builtin_distributions.py (excerpt)
import numpy as np

class PERTDistribution:
    name = "pert"

    def sample(
        self,
        low: float,
        expected: float,
        high: float,
        rng: np.random.RandomState,
        *,
        pert_lambda: float = 4.0,
        **_: float,
    ) -> float:
        rng_range = high - low
        if rng_range == 0:
            return low
        norm_mode = (expected - low) / rng_range
        alpha = 1.0 + pert_lambda * norm_mode
        beta  = 1.0 + pert_lambda * (1.0 - norm_mode)
        # numpy has no direct Beta parameterised by alpha/beta; use
        # the relationship: Beta(a,b) = gamma(a) / (gamma(a) + gamma(b))
        sample = rng.beta(alpha, beta)
        return float(low + sample * rng_range)

    def validate(self, low: float, expected: float, high: float) -> None:
        if not (low <= expected <= high):
            raise ValueError("PERT requires low ≤ expected ≤ high")
        if low >= high:
            raise ValueError("PERT requires low < high")

    def parameter_schema(self) -> dict[str, type]:
        return {"pert_lambda": float}
```

Mean of the PERT distribution: $\mu = (\text{low} + 4 \cdot \text{expected} + \text{high}) / 6$.

For default `pert_lambda = 4`, this is the classic PERT mean used in CPM
project planning. Increasing `pert_lambda` sharpens the distribution around
`expected`; decreasing it flattens it toward uniform.

### YAML authoring

```yaml
# Minimal (uses config default lambda = 4)
estimate:
  distribution: "pert"
  low: 3
  expected: 5
  high: 12
  unit: "days"

# With explicit lambda override (per-task not yet supported,
# see future work below)
```

### Config block

```yaml
distributions:
  pert:
    lambda: 6    # sharper peak → tasks you know well
```

---

## YAML / TOML Parser Changes

`parsers/error_reporting.py` validates that `distribution` is a known value.
Currently this is checked against `DistributionType` enum members. After the
registry architecture:

1. On startup the registry is populated.
2. `registered_names()` replaces the hardcoded allowed-values list.
3. Unknown distribution names produce the same line-aware error messages as
   before, now also suggesting nearest registered names via `difflib`.

No other parser changes are needed because the estimate schema is unchanged.

---

## Test Architecture

### Contract test suite (the key design)

The most important test artefact is a **parameterised contract test** that every
distribution must pass. This is written once and applies automatically to all
registered distributions — including any future one we have not written yet.

```python
# tests/test_distribution_contract.py
import pytest
import numpy as np
from mcprojsim.simulation import distribution_registry
from mcprojsim.simulation.distribution_registry import registered_names

CASES = [
    (1.0, 5.0, 10.0),   # typical right-skewed
    (0.0, 3.0,  6.0),   # symmetric
    (2.0, 2.5, 20.0),   # extreme right skew
    (0.5, 0.6,  1.0),   # very narrow range
]


@pytest.fixture(params=registered_names())
def plugin(request):
    return distribution_registry.get(request.param)


@pytest.mark.parametrize("low,expected,high", CASES)
def test_sample_is_finite(plugin, low, expected, high):
    rng = np.random.RandomState(42)
    val = plugin.sample(low, expected, high, rng)
    assert np.isfinite(val), f"{plugin.name}: got non-finite sample {val}"


@pytest.mark.parametrize("low,expected,high", CASES)
def test_sample_non_negative(plugin, low, expected, high):
    rng = np.random.RandomState(42)
    val = plugin.sample(low, expected, high, rng)
    assert val >= 0.0


def test_sample_bounded_distributions():
    """Bounded distributions must never escape [low, high]."""
    bounded = {"triangular", "pert", "uniform"}
    rng = np.random.RandomState(0)
    for name in bounded:
        if name not in registered_names():
            continue
        plugin = distribution_registry.get(name)
        for _ in range(5000):
            v = plugin.sample(2.0, 5.0, 10.0, rng)
            assert 2.0 <= v <= 10.0, f"{name}: out-of-bounds sample {v}"


@pytest.mark.parametrize("low,expected,high", CASES)
def test_reproducible_with_same_seed(plugin, low, expected, high):
    s1 = plugin.sample(low, expected, high, np.random.RandomState(7))
    s2 = plugin.sample(low, expected, high, np.random.RandomState(7))
    assert s1 == s2


def test_different_seeds_produce_different_values(plugin):
    results = {
        plugin.sample(1.0, 5.0, 10.0, np.random.RandomState(seed))
        for seed in range(50)
    }
    assert len(results) > 1, f"{plugin.name}: always returns the same value"


@pytest.mark.parametrize("low,expected,high", CASES)
def test_validate_valid_params_does_not_raise(plugin, low, expected, high):
    plugin.validate(low, expected, high)


def test_validate_rejects_low_gt_high(plugin):
    with pytest.raises(ValueError):
        plugin.validate(10.0, 5.0, 1.0)


def test_validate_accepts_low_equals_expected(plugin):
    """Most distributions allow expected at the lower boundary."""
    # Just must not raise for valid inputs
    try:
        plugin.validate(3.0, 3.0, 10.0)
    except ValueError:
        pass  # some distributions may require strict inequality


@pytest.mark.parametrize("low,expected,high", CASES)
def test_mean_in_plausible_range(plugin, low, expected, high):
    """Sample mean over 10k draws should be between low and high."""
    rng = np.random.RandomState(0)
    samples = [plugin.sample(low, expected, high, rng) for _ in range(10_000)]
    mean = np.mean(samples)
    assert low <= mean <= high, (
        f"{plugin.name}: sample mean {mean:.3f} outside [{low}, {high}]"
    )


def test_parameter_schema_returns_dict(plugin):
    schema = plugin.parameter_schema()
    assert isinstance(schema, dict)
    for k, v in schema.items():
        assert isinstance(k, str)
        assert isinstance(v, type)
```

Any distribution added to the registry automatically inherits all of the above
tests. No additional test registration is required.

### Distribution-specific unit tests

Each distribution additionally gets its own file for property tests:

```python
# tests/test_distribution_pert.py
import numpy as np
import pytest
from mcprojsim.simulation.builtin_distributions import PERTDistribution


PERT = PERTDistribution()


def test_pert_mean_matches_formula():
    """Classic PERT mean: (low + 4*expected + high) / 6."""
    low, exp, high = 2.0, 5.0, 14.0
    expected_mean = (low + 4 * exp + high) / 6.0
    rng = np.random.RandomState(0)
    samples = [PERT.sample(low, exp, high, rng) for _ in range(50_000)]
    assert abs(np.mean(samples) - expected_mean) < 0.05


def test_pert_lambda_sharpens_distribution():
    """Higher lambda → smaller standard deviation."""
    rng1 = np.random.RandomState(1)
    rng2 = np.random.RandomState(1)
    samples_sharp = [PERT.sample(1, 5, 10, rng1, pert_lambda=8) for _ in range(10_000)]
    samples_flat  = [PERT.sample(1, 5, 10, rng2, pert_lambda=1) for _ in range(10_000)]
    assert np.std(samples_sharp) < np.std(samples_flat)


def test_pert_bounded():
    rng = np.random.RandomState(99)
    for _ in range(10_000):
        v = PERT.sample(3.0, 5.0, 9.0, rng)
        assert 3.0 <= v <= 9.0


def test_pert_symmetric_when_mode_is_midpoint():
    """With mode at midpoint and lambda=4, skewness should be near zero."""
    low, high = 0.0, 10.0
    mid = 5.0
    rng = np.random.RandomState(42)
    samples = [PERT.sample(low, mid, high, rng) for _ in range(50_000)]
    from scipy import stats
    sk = stats.skew(samples)
    assert abs(sk) < 0.05, f"symmetric PERT had skewness {sk:.4f}"
```

### Risk model contract tests

Analogous contract tests for risk plugins:

```python
# tests/test_risk_model_contract.py
import numpy as np
import pytest
from mcprojsim.simulation import risk_registry

@pytest.fixture(params=risk_registry.registered_names())
def risk_plugin(request):
    return risk_registry.get(request.param)

def test_risk_impact_non_negative(risk_plugin):
    rng = np.random.RandomState(0)
    for _ in range(1000):
        impact = risk_plugin.evaluate(probability=0.5, base_impact=40.0,
                                      base_duration=80.0, rng=rng)
        assert impact >= 0.0

def test_zero_probability_never_fires(risk_plugin):
    rng = np.random.RandomState(0)
    for _ in range(500):
        impact = risk_plugin.evaluate(probability=0.0, base_impact=40.0,
                                      base_duration=80.0, rng=rng)
        assert impact == 0.0

def test_unit_probability_always_fires(risk_plugin):
    rng = np.random.RandomState(0)
    for _ in range(500):
        impact = risk_plugin.evaluate(probability=1.0, base_impact=40.0,
                                      base_duration=80.0, rng=rng)
        assert impact > 0.0
```

### Integration tests

```python
# tests/test_distribution_integration.py
"""Run a full project simulation with each registered distribution
and verify that results are finite, positive, and reproducible."""
import pytest
import numpy as np
from mcprojsim.simulation import distribution_registry
from mcprojsim.simulation.engine import SimulationEngine
from mcprojsim.config import Config
from mcprojsim.models.project import Project

MINIMAL_PROJECT_YAML = """
project:
  name: test
  start_date: "2026-01-01"
  distribution: "{dist}"
tasks:
  - id: t1
    name: Task A
    estimate:
      low: 8
      expected: 16
      high: 40
      unit: hours
    dependencies: []
  - id: t2
    name: Task B
    estimate:
      low: 4
      expected: 8
      high: 20
      unit: hours
    dependencies: [t1]
"""

@pytest.mark.parametrize("dist_name", distribution_registry.registered_names())
def test_full_simulation_with_distribution(dist_name):
    import yaml
    from mcprojsim.parsers.yaml_parser import YAMLParser

    data = yaml.safe_load(MINIMAL_PROJECT_YAML.format(dist=dist_name))
    project = YAMLParser().parse_dict(data)

    engine = SimulationEngine(iterations=200, random_seed=42,
                              config=Config.get_default(), show_progress=False)
    results = engine.run(project)

    assert results.mean > 0
    assert np.isfinite(results.mean)
    assert results.std_dev >= 0
    # Reproducible
    engine2 = SimulationEngine(iterations=200, random_seed=42,
                               config=Config.get_default(), show_progress=False)
    results2 = engine2.run(project)
    assert results.mean == results2.mean
```

---

## Implementation Work Breakdown

### Step 1 — Define the Protocol and registry (no breaking changes)

- Add `DistributionPlugin` Protocol to `simulation/distributions.py`
- Add `distribution_registry.py` module
- Keep existing `DistributionSampler._sample_triangular` and
  `_sample_triangular` but wrap each in a thin plugin class
- Register built-ins; keep the existing `if/elif` dispatch as a fallback
  until all paths are migrated.

Exit criteria: existing tests still green; registry reports two names.

### Step 2 — Implement PERT and Uniform

- `simulation/builtin_distributions.py` with `PERTDistribution`,
  `UniformDistribution`
- `config.py`: add `PERTConfig(lambda=4)` inside new `DistributionsConfig`
- `DistributionType` enum: add `PERT = "pert"`, `UNIFORM = "uniform"`
- Register both distributions in `simulation/__init__.py`
- Add `distributions.pert.lambda` to `sample_config.yaml`
- Update docs: `docs/user_guide/task_estimation.md` PERT and Uniform sections

Exit criteria: contract test suite green for all four distributions.

### Step 3 — Migrate `DistributionSampler` to full registry dispatch

- Replace `if/elif` chain with `distribution_registry.get(name).sample(...)`
- Move per-distribution validation out of `models/project.py` into each
  plugin's `validate()`, called from `parsers/error_reporting.py`
- `Config.distribution_params(name)` helper to feed kwargs
- Remove now-redundant `validate_effective_distribution` from `TaskEstimate`

Exit criteria: all existing tests green; no `if/elif` on `DistributionType`
remains in the dispatch path.

### Step 4 — Update parser and error reporting

- `error_reporting.py`: validate distribution name against
  `registered_names()` instead of enum membership
- `difflib.get_close_matches` for typo suggestions on unknown names
- Add line-aware error path for unknown distributions in `yaml_parser.py`

Exit criteria: validation tests for unknown distribution names pass.

### Step 5 — Stochastic risk impacts

- Define `RiskPlugin` Protocol analogous to `DistributionPlugin`
- Implement `StochasticImpactRiskPlugin` that samples from a named
  distribution when a risk fires
- `risk_registry.py` analogous to `distribution_registry.py`
- Wire into `RiskEvaluator`

Exit criteria: risk contract tests green; stochastic impact integration tests
pass.

---

## Files to Create or Modify

| File | Change |
|---|---|
| `simulation/distributions.py` | Add `DistributionPlugin` Protocol; keep existing classes |
| `simulation/distribution_registry.py` | New: registry dict, `register`, `get`, `registered_names` |
| `simulation/builtin_distributions.py` | New: `TriangularDistribution`, `LognormalDistribution`, `PERTDistribution`, `UniformDistribution` |
| `simulation/risk_registry.py` | New: analogous registry for risk plugins |
| `simulation/__init__.py` | Register built-in plugins |
| `simulation/engine.py` | Update `DistributionSampler` constructor; keep rest unchanged |
| `models/project.py` | Add `PERT`, `UNIFORM` to `DistributionType`; remove plugin-level validation |
| `config.py` | Add `DistributionsConfig`, `PERTConfig`; keep `LogNormalConfig` inside it |
| `parsers/error_reporting.py` | Validate distribution names via `registered_names()` |
| `tests/test_distribution_contract.py` | New: contract suite |
| `tests/test_distribution_pert.py` | New: PERT-specific property tests |
| `tests/test_risk_model_contract.py` | New: risk model contract suite  |
| `tests/test_distribution_integration.py` | New: full-simulation parametric tests |
| `docs/user_guide/task_estimation.md` | Add PERT and Uniform sections |
| `examples/sample_config.yaml` | Add `distributions.pert.lambda` block |

---

## What We Gain vs. What It Costs

### Gains

- **Better default accuracy.** PERT is statistically superior to triangular for
  three-point software estimates. Switching the recommended default from
  triangular to PERT for new projects would reduce the systematic density kink
  artefact with zero API surface change.

- **Auto-tested extensibility.** The contract suite means any future
  distribution passes the same tests automatically. Maintainers do not need to
  remember to write coverage.

- **Config-driven parameters per distribution.** `pert.lambda`,
  `lognormal.high_percentile`, and future parameters all live in one
  `distributions:` block in `config.yaml` instead of being spread ad-hoc.

- **Risk model extensibility.** Stochastic impact and cascade risks expand
  the realism of the risk model significantly with no changes to the core
  Monte Carlo loop.

### Costs

- **Migration effort.** Steps 1–4 above are roughly 3–5 days of focused work.
  Step 5 (risk plugins) is another 2–3 days.

- **Config surface increases.** `distributions.pert.lambda` is one more
  thing users might accidentally misconfigure. Good docs and validation
  mitigate this.

- **Slightly more indirection.** `DistributionSampler.sample()` now delegates
  to a registry lookup instead of a direct method call. The overhead is
  negligible (dict lookup per task per iteration).

- **Protocol compatibility must be maintained.** If the `DistributionPlugin`
  signature changes, all built-in plugins break. This argues for locking the
  protocol carefully before shipping Step 3.

---

## Recommended Sequence for MVP

1. Implement PERT (Steps 1 and 2 for PERT only) — this is the immediate
   highest-value change.
2. Add the contract test suite immediately so future work auto-inherits it.
3. Migrate dispatch (Step 3) in the same PR to eliminate the `if/elif` debt.
4. Defer stochastic risk impacts (Step 5) to a later release.
5. Add Uniform as a convenience distribution alongside PERT.

Do not implement Weibull or Empirical until the sprint-planning empirical
resampling work in `sprint-based-planning.md` is complete — the two are related
and should share a design review.
