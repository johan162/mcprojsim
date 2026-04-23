# Monetary Cost Estimation

Monte Carlo simulation gives you a probabilistic view of *when* a project finishes.
`mcprojsim` can extend that same probabilistic reasoning to *how much* it will cost — 
turning every iteration's sampled schedule into a cost estimate and surfacing a full
cost distribution alongside the duration distribution.

## Activating cost estimation

Cost estimation is opt-in: it activates automatically as soon as any cost-related
field is present in your project file.  Specifically, cost is computed when **at least
one** of the following is set:

| Field | Where | Activates because… |
|---|---|---|
| `default_hourly_rate > 0` | `project:` section | Labor cost is non-zero |
| `hourly_rate` (any value) | a `resources:` entry | Resource has an explicit rate |
| `fixed_cost` | a task | Task has a fixed fee regardless of duration |
| `cost_impact` | a risk | Risk has a monetary consequence |

A `default_hourly_rate: 0` alone does **not** activate cost — zero rate produces zero
labor cost, so there is nothing to report.  But `hourly_rate: 0` on a named resource
*does* activate it (an explicit zero is different from "not set").

---

## Project-level cost fields

Add these to the `project:` metadata block in your YAML file.

```yaml
project:
  name: My Project
  start_date: "2026-03-01"
  default_hourly_rate: 150     # fallback rate (per hour) for any task with no resource
  overhead_rate: 0.15          # 15% markup applied to total labor cost
  currency: EUR                # currency code displayed in output (default: EUR)
```

### `default_hourly_rate`

The hourly rate (in whatever currency you choose) applied to every task that has no
named resource, or whose resource has no explicit `hourly_rate`.

- Must be `≥ 0`
- If omitted, defaults to `0` (no labor cost for unrated tasks)

### `overhead_rate`

A fractional multiplier added on top of total labour cost to represent management
overhead, tooling, office, etc.

```
overhead = labor_cost × overhead_rate
total_cost = labor_cost + overhead + fixed_costs + risk_cost_impacts
```

- Range: `0.0` – `3.0` (i.e., up to 300 % markup)
- Overhead is applied to **labor only** — fixed costs and risk cost impacts are
  not marked up again

### `currency`

An arbitrary string label (e.g. `EUR`, `USD`, `GBP`, `SEK`) displayed next to all
cost figures.  It is **not** used for conversion — it is purely cosmetic.

- If omitted, falls back to the `currency` setting in your [configuration file](14_configuration.md)
  (default: `EUR`)

---

## Per-resource hourly rates

When you have named resources, you can assign each a specific rate:

```yaml
resources:
  - name: alice
    hourly_rate: 240    # senior engineer — overrides the project default
  - name: bob
    hourly_rate: 160    # mid-level engineer
  - name: carol         # no hourly_rate → uses project default_hourly_rate
    experience_level: 1
```

`hourly_rate` on a resource **overrides** `default_hourly_rate` for tasks assigned to
that resource.  If a task is assigned to multiple resources the engine uses the
**mean** of their rates as a Phase 1 simplifying assumption (see
[Known limitations](#known-limitations) below).

---

## Per-task fixed costs

Some tasks carry a cost regardless of how long they take — a software license,
a cloud-infrastructure setup fee, a hardware purchase:

```yaml
tasks:
  - id: cloud_setup
    name: Cloud Infrastructure Setup
    estimate:
      low: 8
      expected: 16
      high: 30
    fixed_cost: 3500    # flat €3,500 added every iteration, regardless of duration
```

- `fixed_cost` is an unrestricted float — **negative values represent credits or
  rebates** (e.g. a committed-spend discount or an early-delivery bonus)
- Fixed costs are included in total cost but are **not** subject to `overhead_rate`

---

## Risk cost impacts

Risks can carry a monetary consequence in addition to (or instead of) a schedule
impact.  When a risk triggers in an iteration, its `cost_impact` is added to that
iteration's total cost.

```yaml
risks:
  - name: Vendor support escalation
    probability: 0.25
    impact: 5           # +5 hours schedule impact when triggered
    cost_impact: 4000   # +€4,000 cost impact when triggered

  - name: Early sign-off bonus
    probability: 0.20
    impact: -8          # saves 8 hours
    cost_impact: -1500  # saves €1,500

  - name: Compliance audit fee
    probability: 0.10
    impact: 0           # no schedule impact
    cost_impact: 8000   # pure cost event — affects cost distribution only
```

Both task-level and project-level risks support `cost_impact`.

### Project-level risks

Project-level risks are defined in a separate `project_risks:` section at the
top level of the YAML file (not nested under `project:` or `tasks:`).  They
apply globally to the whole project:

```yaml
project_risks:
  - id: funding_delay
    name: Funding approval delay
    probability: 0.15
    impact:
      type: absolute
      value: 80
      unit: hours
    cost_impact: 25000    # resubmission fees + additional consultant time

  - id: vendor_bankruptcy
    name: Key vendor goes bankrupt
    probability: 0.05
    impact: 0              # no schedule impact — cost-only
    cost_impact: 50000     # emergency vendor replacement
```

---

## Full project example

```yaml
project:
  name: API Platform
  start_date: "2026-06-01"
  default_hourly_rate: 120
  overhead_rate: 0.18
  currency: EUR

resources:
  - name: alice
    hourly_rate: 200
    experience_level: 3
  - name: bob
    hourly_rate: 140
    experience_level: 2

tasks:
  - id: design
    name: API Design
    estimate: { low: 16, expected: 24, high: 40 }
    resources: [alice]
    risks:
      - name: Scope creep
        probability: 0.30
        impact: 8
        cost_impact: 1500

  - id: backend
    name: Backend Implementation
    estimate: { low: 60, expected: 100, high: 160 }
    dependencies: [design]
    resources: [alice, bob]
    fixed_cost: -2000   # tooling credit

  - id: deploy
    name: Deployment
    estimate: { low: 8, expected: 12, high: 24 }
    dependencies: [backend]
    fixed_cost: 500     # cloud provisioning fee
```

---

## Running a simulation with cost

```bash
# Standard run — cost output appears automatically when cost fields are present
mcprojsim simulate project.yaml

# Set a budget target to see the probability of staying within it
mcprojsim simulate project.yaml --target-budget 40000

# Include full per-task cost breakdown in JSON export
mcprojsim simulate project.yaml -f json --full-cost-detail
```

---

## Reading cost output

### Table mode (default)

```
┌─────────────────────────────────────────────────────────────┐
│ Cost Distribution (EUR)                                     │
├────────────┬────────────┬────────────┬──────────────────────┤
│ P50        │ P80        │ P90        │ P95                  │
│ €34,200    │ €41,800    │ €46,500    │ €50,100              │
└────────────┴────────────┴────────────┴──────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ Budget Analysis                                                   │
├─────────────────────────────────────────────────────────────────── │
│ Target budget:     €40,000                                        │
│ Probability within budget: 74.3%                                  │
│ 80% confidence interval:   €29,800 – €41,800                      │
└───────────────────────────────────────────────────────────────────┘
```

### Plain CLI mode

When no `--table` flag is used, the cost section is printed in plain text after the
standard duration summary, showing the same percentile breakdown plus a brief
sensitivity note.

### Cost sensitivity

When cost estimation is active, `mcprojsim` computes a **Spearman rank correlation**
between each task's cost contribution and the total project cost.  High-correlation
tasks are the biggest cost drivers.

---

## Budget confidence analysis

### `--target-budget`

Pass `--target-budget <amount>` to see:

- The probability that total cost stays within the budget
- The 80 % confidence interval for total cost

```bash
mcprojsim simulate project.yaml --target-budget 45000
```

### Programmatic access (Python API)

```python
results = engine.run()

# Probability of finishing within €45,000
p = results.probability_within_budget(45000)

# Budget needed for 90% confidence
budget_90 = results.budget_for_confidence(0.90)

# Confidence interval (point estimate, lower, upper)
point, lo, hi = results.budget_confidence_interval(45000, confidence_level=0.80)
```

---

## Cost in exported reports

### JSON (`-f json`)

The cost section appears under `"cost"` in the JSON output:

```json
"cost": {
  "currency": "EUR",
  "mean": 36450.0,
  "std_dev": 6200.0,
  "percentiles": { "50": 35800.0, "80": 41900.0, "90": 46200.0, "95": 49800.0 },
  "overhead_rate": 0.18,
  "task_costs": {
    "design": { "mean": 4200.0, "p50": 4050.0, "p90": 5800.0 },
    "backend": { "mean": 28100.0, "p50": 27500.0, "p90": 34200.0 },
    "deploy": { "mean": 3600.0, "p50": 3400.0, "p90": 4800.0 }
  },
  "sensitivity": { "backend": 0.82, "design": 0.35, "deploy": 0.18 },
  "duration_correlation": 0.97
}
```

Use `--full-cost-detail` to include the complete per-task breakdown.

### CSV (`-f csv`)

A `cost_statistics` section is appended at the end of the CSV with one row per
percentile plus rows for mean and standard deviation.

### HTML (`-f html`)

The HTML report gains:

- A **Cost Summary** card showing mean, median, std dev, and the percentile table
- A **Cost Histogram** visualising the cost distribution across iterations
- A **Cost Sensitivity Tornado Chart** showing which tasks drive cost variance
  (Spearman rank correlation, top 15 tasks)
- A **Cost Breakdown by Task** table listing each task's mean cost, std dev,
  min, max, and percentage of total project cost
- A **Budget Confidence** card (if `--target-budget` was provided) with a
  probability gauge, percentile table, and cost CDF S-curve chart
- A **Cost Sensitivity** table ranking tasks by their cost correlation

---

## Configuration defaults

Override cost defaults in a [config file](14_configuration.md) so you don't have to
repeat them in every project file:

```yaml
cost:
  default_hourly_rate: 130   # applied when project omits default_hourly_rate
  overhead_rate: 0.10        # default 10% overhead
  currency: EUR              # default currency label
  include_in_output: true    # set false to suppress cost sections globally
```

`include_in_output: false` suppresses cost output in all reports and console
output, but does **not** suppress the underlying computation — budget methods
on `SimulationResults` still return values.

---

## Natural-language input

The `generate` command understands cost fields in plain-text project descriptions.
Supported cost-related patterns:

| Input pattern | Maps to |
|---|---|
| `Default rate: €120/hour`, `Hourly rate: 150` | `default_hourly_rate` |
| `Overhead: 15%`, `Overhead rate: 0.15` | `overhead_rate` |
| `Currency: EUR` | `currency` |
| `Rate: €200/hour` (under a resource) | resource `hourly_rate` |
| `Fixed cost: $5000`, `One-time cost: 5000` | task `fixed_cost` |
| `Risks:` header + structured bullets | task `risks` (see below) |
| Prose risk sentences | task `risks` with `cost_impact` |

### Structured risk format

Indent a `Risks:` header under a task, then list the risk name, probability,
impact, and optional cost impact as sub-bullets:

```
Task 3: Data Transformation
- Estimate: 40/80/140 hours
- Depends on Task 2
- Risks:
  - Third-Party API Changes
  - Probability: 0.25
  - Impact: 3/5 days
  - Cost impact: 8000
```

### Prose risk format

The parser recognises risk sentences that include a probability and at least
one consequence (schedule delay or cost impact). Keywords like *penalty*,
*fee*, or *surcharge* produce a positive `cost_impact`; keywords like *bonus*,
*reward*, *saving*, or *credit* produce a negative `cost_impact`:

```
Task 6: Go-Live
- Estimate: 10/20/35 hours
- There is a 25% probability of a deployment rollback penalty of $5000 and 2 days delay
- There is a 15% chance the client rewards early delivery with a $4000 bonus
```

### Full example

```
Project name: My API
Start date: 2026-06-01
Default rate: €120/hour
Overhead: 15%
Currency: EUR

Resource 1: Alice
- Experience: 3
- Rate: €200/hour

Task 1:
- API Design
- Size: M
- Resources: Alice
- Fixed cost: 1000

Task 2:
- Backend
- Size: XL
- Depends on Task 1
- There is a 20% risk of integration delays costing a $3000 fee and adding 2 days
```

```bash
mcprojsim generate project_description.txt > project.yaml
mcprojsim simulate project.yaml --target-budget 50000
```

See `examples/cost_nl_prose_example.txt`, `examples/cost_nl_example.txt`, and
`examples/cost_nl_risk_example.txt` for full natural-language examples with cost
and risk definitions.

---

## Secondary currencies and FX conversion

When your team spans multiple countries, or when you report costs to a client in a
different currency, `mcprojsim` can automatically convert every cost distribution to
one or more **secondary currencies** and include the results in all outputs.

### How it works

1. You nominate up to **5 secondary currencies** in the project file.
2. At simulation time, `mcprojsim` fetches the current mid-market exchange rate from
   [Frankfurter](https://frankfurter.dev/) — a free, key-less service backed by
   official sources.
3. Rates are **cached on disk** for 24 hours so that repeated runs do not hit the
   network (see [Rate caching](#rate-caching) below).
4. You can optionally mark up the official rate by a **conversion cost** and an
   **overhead rate** to model the real cost of buying foreign currency.
5. The adjusted rate is applied element-wise to the entire cost distribution —
   every simulation iteration is converted — so the output is a proper
   probabilistic distribution in the target currency.

### Adjusted-rate formula

```
r_adj = (1 + fx_conversion_cost + fx_overhead_rate) × r_official
```

| Term | Meaning |
|---|---|
| `r_official` | Mid-market rate fetched from Frankfurter (e.g. 1 EUR = 11.20 SEK) |
| `fx_conversion_cost` | Bank bid-ask spread as a fraction, e.g. `0.015` = 1.5 % |
| `fx_overhead_rate` | Additional overhead (hedging, admin) as a fraction, e.g. `0.005` = 0.5 % |
| `r_adj` | Effective rate actually paid, used for all conversions |

**Example:**  EUR → SEK with a 2 % bank spread and 0.5 % admin fee:

```
r_official = 11.20        # live mid-market
r_adj = (1 + 0.02 + 0.005) × 11.20 = 1.025 × 11.20 = 11.48 SEK/EUR
```

A project with a P80 cost of €42,000 would show **SEK 482,160** at P80.

### Project file fields

Add the following to your `project:` section:

```yaml
project:
  name: API Platform
  currency: EUR               # primary (base) currency
  default_hourly_rate: 150
  overhead_rate: 0.15

  secondary_currencies: [SEK, USD, GBP]   # up to 5 ISO 4217 codes
  fx_conversion_cost: 0.015               # 1.5% bank spread
  fx_overhead_rate: 0.005                 # 0.5% internal overhead
```

| Field | Type | Range | Default | Description |
|---|---|---|---|---|
| `secondary_currencies` | list of strings | up to 5 entries | `[]` | ISO 4217 codes to convert to |
| `fx_conversion_cost` | float | 0 – 0.50 | `0.0` | Bank spread fraction |
| `fx_overhead_rate` | float | 0 – 1.0 | `0.0` | Additional overhead fraction |
| `fx_rates` | mapping | any positive float | `{}` | Manual rate overrides (bypass live fetch) |

All four fields are optional. If `secondary_currencies` is empty (the default),
no FX fetching or conversion is performed.

### Manual rate overrides

If you have a contractually locked exchange rate, or simply want reproducible
results without a network dependency, set `fx_rates` to bypass the live fetch:

```yaml
project:
  currency: EUR
  secondary_currencies: [SEK, USD]
  fx_rates:
    SEK: 11.50    # use this fixed rate — no markups applied
    USD: 1.08     # manual rates are always used as-is
```

Manual rates take precedence over anything fetched from Frankfurter.
**No markups are applied to manual rates** — they are used exactly as specified.

### Suppressing FX at run time

Pass `--no-fx` to any `simulate` call to skip secondary-currency output even if
the project file defines `secondary_currencies`:

```bash
mcprojsim simulate project.yaml --no-fx
```

This is useful for quick local runs where network access is unavailable or
undesired.

### Console output

When secondary currencies are configured, a **Cost in Secondary Currencies**
section is appended after the primary cost table.  For each currency it shows:

- The effective exchange rate used (official and adjusted, if markups were applied)
- The same confidence-level percentiles as the primary cost table

```
Cost in Secondary Currencies:
  SEK  1 EUR = 11.48 SEK  (official: 11.20, bank: +1.5%, overhead: +0.5%)
       P50: SEK 391,360  |  P80: SEK 481,160  |  P90: SEK 527,100  |  P95: SEK 563,400

  USD  1 EUR = 1.09 USD  (official: 1.068, bank: +1.5%, overhead: +0.5%)
       P50: $37,200  |  P80: $45,700  |  P90: $50,100  |  P95: $53,500
```

If the rate source is a manual override, `(manual)` appears instead of the
markup breakdown.  If a rate is unavailable (network failure, unknown currency),
that currency is silently skipped and a warning is emitted.

### FX data in exported reports

#### JSON (`-f json`)

A `secondary_currencies` array is added inside the `"cost"` section:

```json
"cost": {
  "currency": "EUR",
  "mean": 36450.0,
  "percentiles": { "50": 34200, "80": 41800, "90": 46500, "95": 50100 },
  "secondary_currencies": [
    {
      "currency": "SEK",
      "official_rate": 11.2,
      "adjusted_rate": 11.48,
      "fx_conversion_cost": 0.015,
      "fx_overhead_rate": 0.005,
      "source": "live",
      "fetched_at": "2026-06-01T09:14:33+00:00",
      "mean": 418000.0,
      "percentiles": { "50": 392400, "80": 479700, "90": 533700, "95": 575100 }
    }
  ]
}
```

The `source` field is one of `"live"`, `"disk_cache"`, or `"manual_override"`,
allowing you to audit which data source was used.

#### CSV and HTML

Both exporters receive the same `fx_provider` and include secondary-currency
data alongside the primary cost section — extra rows in the CSV cost block and
an additional card in the HTML report.

### Rate caching

Fetching live rates for every simulation run would be wasteful and fragile.
`mcprojsim` maintains a disk cache at:

```
~/.mcprojsim/fx_rates_cache.json
```

**Cache behaviour:**

| Property | Value |
|---|---|
| Location | `~/.mcprojsim/fx_rates_cache.json` |
| TTL | 24 hours per entry |
| Granularity | Per base-currency / target-currency pair |
| Format | JSON: `{ "EUR": { "SEK": { "rate": 11.2, "fetched_at": "..." } } }` |

Entries from different base currencies coexist in the same file.  On startup,
`ExchangeRateProvider` loads all fresh entries for the current base currency into
memory.  Stale entries (older than 24 h) are skipped and re-fetched on next use.

All disk I/O errors (permissions, corrupt file, etc.) are silently swallowed —
the cache is best-effort.  If the cache cannot be read or written, live rates are
still fetched and used for the current run; they just will not be persisted.

### Full example with secondary currencies

```yaml
project:
  name: International API Platform
  start_date: "2026-06-01"
  default_hourly_rate: 150
  overhead_rate: 0.15
  currency: EUR

  # Show costs in Swedish kronor and US dollars as well
  secondary_currencies: [SEK, USD]
  fx_conversion_cost: 0.015   # 1.5% bank spread
  fx_overhead_rate: 0.005     # 0.5% internal admin

resources:
  - name: alice
    hourly_rate: 200
    experience_level: 3
  - name: bob
    hourly_rate: 140
    experience_level: 2

tasks:
  - id: design
    name: API Design
    estimate: { low: 16, expected: 24, high: 40 }
    resources: [alice]

  - id: backend
    name: Backend Implementation
    estimate: { low: 60, expected: 100, high: 160 }
    dependencies: [design]
    resources: [alice, bob]
    fixed_cost: -2000   # tooling credit

  - id: deploy
    name: Deployment
    estimate: { low: 8, expected: 12, high: 24 }
    dependencies: [backend]
    fixed_cost: 500
```

```bash
mcprojsim simulate project.yaml --target-budget 45000
```

---

## Known limitations

**Multi-resource equal-effort-split (Phase 1 simplification)**

When a task is assigned to multiple resources, the engine uses the **mean** of
their hourly rates multiplied by the sampled elapsed duration.  This assumes each
resource contributes an equal share of the effort.  If resources truly work in
parallel for the full elapsed duration, the actual cost is higher than what the
simulation reports.

Example: two resources at €100/hr and €200/hr on a 32-hour task.
The engine computes `32 × mean(100, 200) = 32 × 150 = €4,800`, which equals the
true cost only when each person works 16 hours (equal split).  If both work the
full 32 hours in parallel the true cost is `32×100 + 32×200 = €9,600`.

This limitation will be addressed in a future release with explicit effort
tracking per resource.

---

## Example files

| File | Description |
|---|---|
| `examples/cost_simple.yaml` | `default_hourly_rate` + `overhead_rate` + one `fixed_cost` + risk `cost_impact` |
| `examples/cost_constrained.yaml` | Per-resource rates with resource-constrained scheduling |
| `examples/cost_advanced.yaml` | Full feature set: per-resource rates, multiple fixed costs and credits, risks with cost-only impacts |
| `examples/cost_nl_example.txt` | Structured natural-language input with cost fields |
| `examples/cost_nl_prose_example.txt` | Prose-style natural-language project brief |
