# Parallel Simulation Engine

Version: 0.1.0

Date: 2026-04-17

Status: Design Proposal

---

## 1. Problem Statement

The Monte Carlo simulation engine (`SimulationEngine`) runs all iterations sequentially in a single thread. For large projects (50+ tasks, 10 000+ iterations, resource-constrained scheduling), a single `run()` call can take several seconds. Since each simulation iteration is independent — it samples task durations, evaluates risks, schedules tasks, and produces one scalar project duration — iterations are embarrassingly parallel and should benefit from concurrent execution.

This proposal analyses whether threading will actually deliver speedup given CPython's GIL, evaluates alternative concurrency models, proposes a concrete design, and provides an implementation plan.

---

## 2. Current Architecture

### 2.1 Iteration Pipeline (single iteration)

```
_run_iteration_with_sampler()
  ├── sample task durations         (DistributionSampler.sample × N tasks)
  ├── evaluate task risks           (RiskEvaluator × N tasks)
  ├── schedule tasks                (TaskScheduler.schedule_tasks)
  ├── compute peak parallelism      (TaskScheduler.max_parallel_tasks)
  ├── calculate slack               (TaskScheduler.calculate_slack)
  ├── compute project duration      (max over schedule)
  ├── evaluate project-level risks  (RiskEvaluator)
  └── identify critical paths       (TaskScheduler.get_critical_paths)
```

### 2.2 Per-Iteration State

Each iteration touches:

| Component | State | Thread-safety |
|-----------|-------|---------------|
| `DistributionSampler` | `numpy.random.RandomState` | **Not thread-safe** — internal C state mutated on every call |
| `RiskEvaluator` | `numpy.random.RandomState` (same instance) | Same as above |
| `TaskScheduler` | `project` (read-only), internal transient dicts | Scheduler creates fresh dicts per call; `project` is immutable during a run |
| `static_data` | `ProjectRunStaticData` (frozen dataclass) | Read-only — safe |
| `project` | `Project` (Pydantic model) | Read-only during `run()` — safe |

### 2.3 Result Accumulation

After each iteration the loop appends results into shared accumulators:

- `project_durations`: pre-allocated `np.ndarray` — indexed by iteration number.
- `task_durations_all`: `Dict[str, list[float]]` — appends per-task durations.
- `task_risk_impacts_all`, `project_risk_impacts_all`: same pattern.
- `task_slack_accum`: `Dict[str, list[float]]` — appends per-task slack.
- `critical_path_frequency`: `Dict[str, int]` — incremented per iteration.
- `critical_path_sequences`: `Counter[tuple[str, ...]]` — updated per iteration.
- `project_costs_all`, `task_costs_all`: optional lists, appended if cost tracking is active.
- Scalar accumulators: `max_parallel_overall`, resource wait/utilization/calendar delay lists.

---

## 3. Will Threading Actually Help?

### 3.1 The GIL Problem

CPython's Global Interpreter Lock (GIL) prevents true parallel execution of Python bytecodes. A naive threading approach would serialize all the pure-Python scheduling logic and provide no speedup at all — in fact, it would add overhead from context switching and lock contention.

However, the engine's hot path has a critical property: **most of the CPU time is spent inside NumPy C extensions** (random sampling, array operations) and in the scheduler's tight dependency-resolution loops.

### 3.2 Where Time Is Spent (estimated breakdown for a 30-task constrained project)

| Phase | Approx. share | GIL-released? |
|-------|--------------|---------------|
| `numpy.random.triangular` / `numpy.random.lognormal` | ~10% | Yes (C code, but legacy RandomState holds GIL on legacy calls) |
| `numpy.random.random` (risk rolls) | ~5% | Same as above |
| `TaskScheduler.schedule_tasks` (dependency + resource loop) | ~60% | **No** — pure Python |
| Slack, critical path, max-parallel | ~10% | **No** — pure Python |
| Result accumulation (dict updates, list appends) | ~10% | **No** — pure Python |
| Overhead (function calls, object creation) | ~5% | **No** — pure Python |

**The dominant cost (~60%) is the scheduling loop**, which is pure Python and runs under the GIL. Threading will **not** parallelize this work in CPython.

### 3.3 Threading Verdict

> **Threading cannot deliver meaningful speedup for the simulation engine under CPython.** The scheduling loop that dominates runtime is pure Python and fully GIL-bound. Thread-based parallelism would add synchronization overhead with zero scheduling parallelism.

### 3.4 What Would Work: `multiprocessing` / Process-Based Parallelism

Since each iteration is independent and shares no mutable state, **process-based parallelism** sidesteps the GIL entirely. Each worker process gets its own Python interpreter, its own `numpy.random.RandomState`, its own `TaskScheduler`, and accumulates results locally. Only the final merge requires data transfer.

### 3.5 What Would Work Even Better: `concurrent.futures.ProcessPoolExecutor` with Chunked Batches

Forking one process per iteration (10 000 processes) would be dominated by IPC overhead. Instead, partition iterations into **chunks** (e.g., 10 000 iterations / 8 workers = 1 250 per chunk) and have each worker run a mini-loop that returns aggregated partial results. This amortizes process creation and IPC costs.

### 3.6 Hybrid Approach: Threading + NumPy Vectorization (Future)

A hypothetical alternative is to vectorize the entire iteration — sample all task durations as `(N_iter, N_tasks)` arrays in one NumPy call (GIL-released), then schedule all iterations in C. This requires rewriting the scheduler in C/Cython/Rust, which is out of scope for this proposal but noted as the theoretical optimal path.

---

## 4. Proposed Design: Chunked Process Pool

### 4.1 High-Level Flow

```
SimulationEngine.run(project)
  │
  ├── _build_project_run_static_data(project)     # once, in parent
  │
  ├── if parallel and iterations >= threshold:
  │     ├── partition iterations into N chunks
  │     ├── spawn N worker processes via ProcessPoolExecutor
  │     │     each worker calls _run_chunk(project, chunk_range, seed_offset, config)
  │     │     and returns a ChunkResult (partial accumulators)
  │     ├── merge ChunkResults into full accumulators
  │     └── _build_results(...)
  │
  └── else:
        └── _run_single_pass(...)   # existing sequential path (unchanged)
```

### 4.2 Worker Function

Each worker receives the serialized project, config, and a seed offset. It constructs its own `DistributionSampler`, `RiskEvaluator`, `TaskScheduler`, and `ProjectRunStaticData` — all cheap to create. It runs its assigned chunk of iterations and returns a `ChunkResult`:

```python
@dataclass
class ChunkResult:
    """Partial results from one worker's chunk of iterations."""
    project_durations: np.ndarray           # shape (chunk_size,)
    effort_durations: np.ndarray            # shape (chunk_size,)
    task_durations: Dict[str, np.ndarray]   # per-task, shape (chunk_size,)
    task_risk_impacts: Dict[str, np.ndarray]
    project_risk_impacts: np.ndarray
    task_slack: Dict[str, np.ndarray]
    critical_path_frequency: Dict[str, int]
    critical_path_sequences: Counter[tuple[str, ...]]
    max_parallel: int
    resource_wait_times: np.ndarray
    resource_utilizations: np.ndarray
    calendar_delay_times: np.ndarray
    project_costs: Optional[np.ndarray]
    task_costs: Optional[Dict[str, np.ndarray]]
```

Using numpy arrays inside chunks (rather than lists) makes the merge step efficient — concatenation is O(n) with no per-element Python overhead.

### 4.3 Seed Strategy for Reproducibility

Reproducibility is a core invariant of the engine (`random_seed` contract). Parallel execution must produce deterministically reproducible results, though they need not be identical to the sequential output for the same seed (since iteration order changes the RandomState trajectory).

Strategy: **SeedSequence-based independent streams**.

```python
from numpy.random import SeedSequence, RandomState, MT19937

parent_seq = SeedSequence(user_seed)
child_seeds = parent_seq.spawn(n_workers)
# Each worker: RandomState(MT19937(child_seeds[i]))
```

This guarantees:
- Given the same `random_seed` and `n_workers`, results are identical across runs.
- Streams are statistically independent (no overlap for practical purposes).
- Adding workers changes results (acceptable; document this).

### 4.4 Merge Algorithm

After all workers return, the parent process merges `ChunkResult` objects:

```python
def _merge_chunk_results(chunks: list[ChunkResult]) -> MergedAccumulators:
    project_durations = np.concatenate([c.project_durations for c in chunks])
    # ... same for all array fields ...

    # Counter merge: sum counts
    critical_path_freq = Counter()
    for c in chunks:
        for tid, count in c.critical_path_frequency.items():
            critical_path_freq[tid] += count

    critical_path_seqs = Counter()
    for c in chunks:
        critical_path_seqs += c.critical_path_sequences

    max_parallel = max(c.max_parallel for c in chunks)
    # ...
```

Merge is single-threaded in the parent and runs in O(total_iterations) — negligible compared to the simulation itself.

### 4.5 IPC Cost Analysis

Each worker transfers its `ChunkResult` back via pickle. For a 30-task, 1 250-iteration chunk:

| Field | Size |
|-------|------|
| `project_durations` | 1 250 × 8 bytes = 10 KB |
| `task_durations` (30 tasks) | 30 × 10 KB = 300 KB |
| `task_risk_impacts` | 300 KB |
| `task_slack` | 300 KB |
| `critical_path_frequency` | ~30 × 16 bytes ≈ 0.5 KB |
| `critical_path_sequences` | variable — up to ~50 KB for diverse paths |
| Scalar arrays (costs, resource stats) | ~60 KB |
| **Total per worker** | **~1 MB** |

With 8 workers: ~8 MB total transfer. Pickle deserialization of 8 MB takes <10 ms. This is well under the simulation time for any non-trivial project.

### 4.6 When to Parallelize

Parallel dispatch has fixed overhead: process pool startup (~50–200 ms on first use, near-zero on reuse), argument serialization, result deserialization, merge. For small workloads this overhead dominates.

Default policy:

```python
PARALLEL_MIN_ITERATIONS = 500
PARALLEL_MIN_TASKS = 5
```

Parallelism is enabled only when both thresholds are exceeded **and** `workers > 1`. The user can explicitly set `workers=1` to force sequential execution.

### 4.7 Progress Reporting

With process-based parallelism, workers cannot directly call the parent's `progress_callback`. Options:

1. **No per-iteration progress in parallel mode** — report only chunk completion. With 8 workers, the user sees 8 progress jumps. Acceptable for typical runtimes (<5 seconds).
2. **Shared `multiprocessing.Value` counter** — each worker atomically increments after each iteration; parent polls on a timer. Adds complexity but granular progress.

Proposed: **Option 1 for initial implementation.** Each chunk completion triggers a progress update. The existing `progress_callback(completed, total)` contract is honoured by summing completed chunks. Option 2 can be added later if users report poor UX on large runs.

### 4.8 Cancellation

The parent holds a `multiprocessing.Event` (`cancel_event`). Each worker checks `cancel_event.is_set()` at the top of its inner loop (same position as the current `self._cancelled` check). On cancellation, the parent calls `executor.shutdown(wait=False, cancel_futures=True)` and raises `SimulationCancelled`.

### 4.9 Two-Pass Interaction

Two-pass scheduling (`_run_two_pass`) has a data dependency: pass-2 depends on pass-1's criticality indices. Both passes can independently be parallelized:

1. **Pass-1 parallel** → merge → compute `task_ci`.
2. **Pass-2 parallel** (each worker receives `task_ci`) → merge → build results.

Cached duration replay (pass-2 iterations < `pass1_iterations` reuse pass-1 durations) complicates cross-process pairing. Two options:

- **Option A**: Skip duration cache across processes — each pass-2 worker re-samples (no paired replay). This slightly changes the statistical properties but is simpler.
- **Option B**: Transfer the duration cache from pass-1 workers to pass-2 workers. For 1 000 pass-1 iterations × 30 tasks × 8 bytes = 240 KB — trivial.

Proposed: **Option B** — preserve paired replay semantics. Pass-1 workers return their `DurationCache` partition; parent distributes relevant slices to pass-2 workers.

---

## 5. API Design

### 5.1 New `SimulationEngine` Parameter

```python
class SimulationEngine:
    def __init__(
        self,
        iterations: int = DEFAULT_SIMULATION_ITERATIONS,
        random_seed: Optional[int] = None,
        config: Optional[Config] = None,
        show_progress: bool = True,
        two_pass: bool = False,
        pass1_iterations: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        workers: Optional[int] = None,       # <-- NEW
    ):
```

- `workers=None` (default): auto-detect using `os.cpu_count()` (hyperthreads). Falls back to 1 if detection fails or the platform prohibits `fork`/`spawn`.
- `workers=1`: force sequential execution (existing code path, no process pool).
- `workers=N` (N > 1): use N worker processes.

### 5.2 CLI Flag

```
mcprojsim simulate project.yaml --workers 4
mcprojsim simulate project.yaml --workers 1    # force sequential
mcprojsim simulate project.yaml                # auto (cpu_count)
```

### 5.3 Reproducibility Contract

The docstring and user guide will state:

> When `workers > 1`, results are deterministic for a given `(random_seed, workers)` pair. Changing the number of workers changes the random stream partitioning and therefore the exact results. To reproduce results from a parallel run, use the same `random_seed` **and** `workers` value. Setting `workers=1` reproduces legacy sequential behaviour exactly.

---

## 6. Expected Speedup

### 6.1 Amdahl's Law Analysis

Let $p$ be the fraction of work that is parallelizable (the per-iteration simulation), and $s = 1 - p$ be the serial fraction (argument setup, result merge, `_build_results`).

The serial fraction consists of:
- `_build_project_run_static_data`: runs once, ~0.1 ms.
- Merge: O(total_iterations), dominated by `np.concatenate`. For 10 000 iterations × 30 tasks ≈ 5 ms.
- `_build_results`: statistics, sensitivity analysis, cost analysis. ~10 ms.
- Process pool overhead: ~5 ms (reused pool) to ~200 ms (cold start).

For a typical 10 000-iteration, 30-task constrained project that takes ~4 seconds sequentially:

$$s \approx \frac{0.015 + 0.005}{4.0} \approx 0.5\%$$

Maximum theoretical speedup with $N$ workers:

$$S(N) = \frac{1}{s + \frac{1-s}{N}} = \frac{1}{0.005 + \frac{0.995}{N}}$$

| Workers | Theoretical speedup | Estimated wall time |
|---------|--------------------:|--------------------:|
| 1       | 1.0×               | 4.0 s               |
| 2       | 1.97×              | 2.0 s               |
| 4       | 3.86×              | 1.04 s              |
| 8       | 7.28×              | 0.55 s              |
| 16      | 13.0×              | 0.31 s              |

### 6.2 Practical Overhead Deductions

Real-world factors that reduce the theoretical maximum:

| Factor | Cost | Impact |
|--------|------|--------|
| Cold pool startup | ~200 ms (first run only) | Amortized in CLI runs with `--workers` |
| Argument serialization (pickle project) | ~1–5 ms | Negligible |
| Result deserialization (8 workers × ~1 MB) | ~10 ms | Negligible |
| OS scheduling / cache effects | 5–15% | Reduces effective speedup by ~10% |

**Realistic expected speedup: ~5–6× on 8 cores** for the typical workload (10 000 iterations, 30 tasks, constrained scheduling). For small workloads (< 500 iterations or < 5 tasks), sequential execution is faster due to pool overhead.

### 6.3 Comparison: Threading vs Multiprocessing

| Approach | GIL-bound scheduler | IPC overhead | Reproducibility | Speedup (8 cores) |
|----------|:-------------------:|:------------:|:---------------:|:-----------------:|
| Threading | serialized | none | easy (shared state) | ~1.0× (no gain) |
| Multiprocessing (chunked) | bypassed | ~10 ms | SeedSequence | ~5–6× |

---

## 7. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| `fork` safety on macOS (default is `spawn` since Python 3.8) | Medium | Use `spawn` start method explicitly; avoid forking with loaded numpy. Already the default on macOS. |
| Pickle failures for custom objects | Low | `Project`, `Config`, `ProjectRunStaticData` are all Pydantic/dataclass — pickle-safe. Add a smoke test. |
| Memory pressure (N copies of project) | Low | Project is typically < 100 KB. 8 copies = < 1 MB. |
| Non-determinism from `spawn` timing | None | Workers use `SeedSequence`-derived independent streams — deterministic regardless of scheduling order. |
| Regression in sequential mode | Medium | Keep the existing `_run_single_pass` code path exactly as-is when `workers=1`. Parallel mode is a separate code path. |
| Two-pass paired replay correctness | Medium | Transfer `DurationCache` partition from pass-1 to pass-2 workers and assert cache hit rate in tests. |
| `progress_callback` granularity | Low | Document that parallel mode reports per-chunk progress. Implement fine-grained counter in a follow-up. |

---

## 8. Alternatives Considered

### 8.1 `threading` with GIL-releasing C Extensions

Rejected. The scheduler is pure Python and accounts for ~60% of iteration time. Threading would achieve at most ~1.0× speedup on the overall simulation (see §3.2).

### 8.2 Cython/Rust Scheduler + Threading

Rewriting the scheduler in a GIL-releasing language would allow true threading parallelism. However:
- The scheduler is ~500 lines of non-trivial dependency/resource logic.
- Maintenance burden of a dual-language codebase.
- Out of scope for a first parallelism iteration.

This remains the long-term optimal path and is noted in §3.6.

### 8.3 `asyncio`

`asyncio` is cooperative multitasking on a single thread. It provides zero CPU parallelism. Useful for I/O-bound work (e.g., web server), not for compute-bound simulation.

### 8.4 `joblib` / `dask`

External dependencies that wrap multiprocessing with additional features (memoisation, distributed scheduling). Overkill for this use case. The standard library `concurrent.futures.ProcessPoolExecutor` is sufficient and adds no dependencies.

---

## 9. Implementation Plan

### Step 1 — `ChunkResult` Data Class

Create `src/mcprojsim/simulation/parallel.py` with the `ChunkResult` frozen dataclass and a `merge_chunk_results()` function.

- **Inputs**: list of `ChunkResult`.
- **Outputs**: merged accumulators matching the signature of `_build_results`.
- **Verify**: unit test that merges two synthetic `ChunkResult` objects and asserts concatenated arrays, summed counters, and max-parallel.

### Step 2 — Worker Function `_run_chunk`

Add a module-level function `_run_chunk()` in `parallel.py` (must be top-level for pickling):

```python
def _run_chunk(
    project_dict: dict,
    config_dict: dict,
    chunk_start: int,
    chunk_size: int,
    child_seed: np.random.SeedSequence,
    task_priority: Optional[Dict[str, float]],
    cached_durations_slice: Optional[Dict[int, Dict[str, float]]],
    cached_cost_impacts_slice: Optional[Dict[int, Dict[str, float]]],
    cancel_event: Optional[multiprocessing.Event],
) -> ChunkResult:
```

The function reconstructs `Project`, `Config`, `SimulationEngine` internals, runs the iteration chunk, and returns a `ChunkResult`.

- **Verify**: call `_run_chunk` directly (no pool) with a 100-iteration chunk on the quickstart project. Assert result shapes and value ranges.

### Step 3 — Seed Partitioning

Add a helper `partition_seeds(random_seed, n_workers)` that returns a list of `SeedSequence` children.

- **Verify**: call twice with the same seed and worker count — assert identical child entropy. Call with different worker counts — assert different entropy.

### Step 4 — Parallel Dispatch in Single-Pass

Add `_run_single_pass_parallel()` to `SimulationEngine`:

1. Partition iterations into `n_workers` chunks.
2. Serialize `project` and `config` as dicts (`.model_dump()`).
3. Submit chunks to `ProcessPoolExecutor`.
4. Collect results, merge, call `_build_results`.

Wire `_run_single_pass` to delegate to the parallel variant when `self.workers > 1` and thresholds are met.

- **Verify**: run the quickstart project with `workers=2, seed=42` and assert identical results on repeated runs. Compare mean/p80/p90 to `workers=1` results — should be statistically similar (not identical due to different seed streams).

### Step 5 — Cancellation

Pass a `multiprocessing.Event` to each worker. On `cancel()`, set the event. Workers check `cancel_event.is_set()` each iteration.

- **Verify**: start a 100 000-iteration simulation in a background thread, call `cancel()` after 100 ms, assert `SimulationCancelled` is raised.

### Step 6 — Progress Reporting

After each `Future` completes, update the progress counter and invoke `progress_callback`.

- **Verify**: run with `progress_callback` capturing calls. Assert monotonically increasing completed counts.

### Step 7 — Two-Pass Parallel

Extend `_run_two_pass` with parallel dispatch:

1. Pass-1: parallel chunks → merge → compute `task_ci` + collect `DurationCache` partitions.
2. Pass-2: parallel chunks, each receiving `task_ci` and relevant `cached_durations_slice`.

- **Verify**: run a constrained project with `two_pass=True, workers=2, seed=42` and assert `TwoPassDelta` is populated. Compare to `workers=1` — delta direction should agree.

### Step 8 — CLI Integration

Add `--workers` option to the `simulate` command:

```python
@click.option("--workers", type=int, default=None,
              help="Worker processes for parallel simulation (default: auto-detect CPU count).")
```

Pass through to `SimulationEngine(workers=workers)`.

- **Verify**: `mcprojsim simulate examples/quickstart_example.yaml --workers 2 --seed 42` produces valid output. `--workers 1` matches legacy output exactly.

### Step 9 — Documentation and Tests

- Add a section to the user guide explaining the `--workers` flag and reproducibility guarantees.
- Add `tests/test_parallel_sim.py` with:
  - Determinism: same seed + workers → same results.
  - Correctness: parallel mean within 2% of sequential mean (statistical similarity test with enough iterations).
  - Cancellation: parallel cancel raises `SimulationCancelled`.
  - Edge cases: `workers > iterations` (degenerate chunks).
  - Two-pass: parallel two-pass produces valid `TwoPassDelta`.

### Step 10 — Performance Benchmark

Add `benchmarks/bench_parallel.py` (not in test suite) that times sequential vs parallel at 1/2/4/8 workers on a 30-task constrained project with 10 000 iterations. Record and report speedup ratios.

- **Verify**: 4-worker speedup is ≥ 2.5× and 8-worker speedup is ≥ 4× on a multi-core machine.
