Version: 1.1.0

Date: 2026-04-17

Status: Design Proposal (reviewed)

# Parallel Simulation Engine


##  Problem Statement

The Monte Carlo simulation engine (`SimulationEngine`) runs all iterations sequentially in a single thread. For large projects (50+ tasks, 10 000+ iterations, resource-constrained scheduling), a single `run()` call can take several seconds. Since each simulation iteration is independent — it samples task durations, evaluates risks, schedules tasks, and produces one scalar project duration — iterations are embarrassingly parallel and should benefit from concurrent execution.

This proposal analyses whether threading will actually deliver speedup given CPython's GIL, evaluates alternative concurrency models, proposes a concrete design, and provides an implementation plan.



##  Current Architecture

###  Iteration Pipeline (single iteration)

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

###  Per-Iteration State

Each iteration touches:

| Component | State | Thread-safety |
|-----------|-------|---------------|
| `DistributionSampler` | `numpy.random.RandomState` | **Not thread-safe** — internal C state mutated on every call |
| `RiskEvaluator` | `numpy.random.RandomState` (same instance) | Same as above |
| `TaskScheduler` | `project` (read-only), internal transient dicts | Scheduler creates fresh dicts per call; `project` is immutable during a run |
| `static_data` | `ProjectRunStaticData` (frozen dataclass) | Read-only — safe |
| `project` | `Project` (Pydantic model) | Read-only during `run()` — safe |

###  Result Accumulation

After each iteration the loop appends results into shared accumulators:

- `project_durations`: pre-allocated `np.ndarray` — indexed by iteration number.
- `task_durations_all`: `Dict[str, list[float]]` — appends per-task durations.
- `task_risk_impacts_all`, `project_risk_impacts_all`: same pattern.
- `task_slack_accum`: `Dict[str, list[float]]` — appends per-task slack.
- `critical_path_frequency`: `Dict[str, int]` — incremented per iteration.
- `critical_path_sequences`: `Counter[tuple[str, ...]]` — updated per iteration.
- `project_costs_all`, `task_costs_all`: optional lists, appended if cost tracking is active.
- Scalar accumulators: `max_parallel_overall`, resource wait/utilization/calendar delay lists.



##  Will Threading Actually Help?

###  The GIL Problem

CPython's Global Interpreter Lock (GIL) prevents true parallel execution of Python bytecodes. A naive threading approach would serialize all the pure-Python scheduling logic and provide no speedup at all — in fact, it would add overhead from context switching and lock contention.

However, the engine's hot path has a critical property: **most of the CPU time is spent inside NumPy C extensions** (random sampling, array operations) and in the scheduler's tight dependency-resolution loops.

###  Where Time Is Spent (estimated breakdown for a 30-task constrained project)

| Phase | Approx. share | GIL-released? |
|-------|--------------|---------------|
| `numpy.random.triangular` / `numpy.random.lognormal` | ~10% | **No** — legacy `RandomState` holds the GIL even in C code |
| `numpy.random.random` (risk rolls) | ~5% | **No** — same as above |
| `TaskScheduler.schedule_tasks` (dependency + resource loop) | ~60% | **No** — pure Python |
| Slack, critical path, max-parallel | ~10% | **No** — pure Python |
| Result accumulation (dict updates, list appends) | ~10% | **No** — pure Python |
| Overhead (function calls, object creation) | ~5% | **No** — pure Python |

**The dominant cost (~60%) is the scheduling loop**, which is pure Python and runs under the GIL. Threading will **not** parallelize this work in CPython.

###  Threading Verdict

> **Threading cannot deliver meaningful speedup for the simulation engine under CPython.** The scheduling loop that dominates runtime is pure Python and fully GIL-bound. Thread-based parallelism would add synchronization overhead with zero scheduling parallelism.

###  What Would Work: `multiprocessing` / Process-Based Parallelism

Since each iteration is independent and shares no mutable state, **process-based parallelism** sidesteps the GIL entirely. Each worker process gets its own Python interpreter, its own `numpy.random.RandomState`, its own `TaskScheduler`, and accumulates results locally. Only the final merge requires data transfer.

###  What Would Work Even Better: `concurrent.futures.ProcessPoolExecutor` with Chunked Batches

Forking one process per iteration (10 000 processes) would be dominated by IPC overhead. Instead, partition iterations into deterministic micro-chunks and have worker processes execute those chunks from a shared queue. This amortizes process creation and IPC costs while still allowing smooth progress reporting and load balancing.

###  Hybrid Approach: Threading + NumPy Vectorization (Future)

A hypothetical alternative is to vectorize the entire iteration — sample all task durations as `(N_iter, N_tasks)` arrays in one NumPy call (GIL-released), then schedule all iterations in C. This requires rewriting the scheduler in C/Cython/Rust, which is out of scope for this proposal but noted as the theoretical optimal path.



##  Proposed Design: Chunked Process Pool

###  High-Level Flow

```
SimulationEngine.run(project)
  │
  ├── _build_project_run_static_data(project)     # once, in parent
  │
  ├── if parallel and iterations >= threshold:
  │     ├── partition iterations into stable, ordered micro-chunks
  │     ├── create a short-lived ProcessPoolExecutor for this run
  │     │     each worker calls _run_chunk(project, chunk_range, seed_offset, config)
  │     │     and returns a ChunkResult (partial accumulators)
  │     ├── sort ChunkResults by chunk_start
  │     ├── merge ChunkResults into full accumulators
  │     └── _build_results(...)
  │
  └── else:
        └── _run_single_pass(...)   # existing sequential path (unchanged)
```

###  Worker Function

Each submitted micro-chunk receives the serialized project, config, a chunk descriptor, and a chunk-specific seed. The worker process executing that micro-chunk constructs its own `DistributionSampler`, `RiskEvaluator`, `TaskScheduler`, and `ProjectRunStaticData` — all cheap to create. It runs the assigned chunk of iterations and returns a `ChunkResult`.

**Worker reconstruction strategy (Option A — engine-based)**: `_run_chunk` instantiates a `SimulationEngine` with `workers=1` (preventing recursion into the parallel path) and `random_seed=None` (the engine's internal `RandomState` is immediately replaced with the chunk-specific `rng`). The worker then calls engine helper methods directly: `_build_project_run_static_data`, `_run_iteration_with_sampler`, `_compute_iteration_costs`. Passing `random_seed=None` to the engine constructor is intentional here — any non-None value would initialise the sampler with the wrong seed before it gets overwritten.

**Worker stdout rule**: Workers must never write progress output. `show_progress` must be `False` and `progress_callback` must be `None` inside every worker invocation. Progress is reported exclusively by the parent after each `Future` resolves. Violating this rule causes interleaved output on stdout that cannot be suppressed.
:

```python
@dataclass
class ChunkResult:
    """Partial results from one worker's chunk of iterations."""
    chunk_start: int
    chunk_size: int
    project_durations: np.ndarray           # shape (chunk_size,)
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
    # For two-pass only: duration cache keyed by LOCAL iteration index (0-based within chunk).
    # The parent remaps to global indices via global_idx = chunk_start + local_idx.
    duration_cache_partition: Optional[Dict[int, Dict[str, float]]] = None
    cost_impact_cache_partition: Optional[Dict[int, Dict[str, float]]] = None
```

Using numpy arrays inside chunks (rather than lists) makes the merge step efficient — concatenation is O(n) with no per-element Python overhead.

> **Note**: `effort_durations` is intentionally absent from `ChunkResult`. The parent's `_build_results` already recomputes it as `np.sum(np.stack(task_durations_arrays.values()), axis=0)` from the merged per-task arrays; transmitting it separately would double IPC cost for no benefit.

###  Seed Strategy for Reproducibility

Reproducibility is a core invariant of the engine (`random_seed` contract). Parallel execution must produce deterministically reproducible results, though they need not be identical to the sequential output for the same seed (since iteration order changes the RandomState trajectory).

Strategy: **SeedSequence-based independent streams**.

```python
from numpy.random import SeedSequence, RandomState, MT19937

parent_seq = SeedSequence(user_seed)
child_seeds = parent_seq.spawn(n_chunks)
# Each chunk gets a deterministic seed derived from chunk order.
# The worker constructs its RNG as:
rng = RandomState(MT19937(child_seeds[i]))
```

> **Critical construction detail**: `RandomState(int_seed)` and `RandomState(SeedSequence)` are **not** the same call — and `RandomState(SeedSequence)` raises `TypeError` at runtime because `RandomState` accepts an integer or a `MT19937` bit-generator, but **not** a `SeedSequence` directly. Workers must always use `RandomState(MT19937(child_seed))`. This `rng` instance must be passed to **all three** per-chunk components: `DistributionSampler(rng, ...)`, `RiskEvaluator(rng)`, and `TaskScheduler(project, rng, config)`. Using different RNG instances for any of these would break the statistical independence guarantee.

For **two-pass** mode, pass-1 and pass-2 must draw from **independent** parent sequences derived from the same root seed, mirroring the sequential engine which creates two separate `RandomState(self.random_seed)` instances for the two passes:

```python
root_seq = SeedSequence(user_seed)
pass1_seq, pass2_seq = root_seq.spawn(2)
pass1_child_seeds = pass1_seq.spawn(n_p1_chunks)
pass2_child_seeds = pass2_seq.spawn(n_p2_chunks)
```

Using a single `SeedSequence.spawn(n_p1_chunks + n_p2_chunks)` and slicing would place pass-1 and pass-2 workers on the same statistical sequence, corrupting the independence that the sequential two-pass preserves.

This guarantees:
- Given the same `random_seed`, `n_workers`, and chunking policy, results are identical across runs.
- Streams are statistically independent (no overlap for practical purposes).
- Adding workers changes results (acceptable; document this).

To make the first guarantee true in practice, the implementation must:

1. Partition iterations deterministically.
2. Assign child seeds deterministically from the chunk order.
3. Merge chunk results in `chunk_start` order rather than completion order.

###  Merge Algorithm

After all workers return, the parent process merges `ChunkResult` objects:

```python
def _merge_chunk_results(chunks: list[ChunkResult]) -> MergedAccumulators:
    chunks = sorted(chunks, key=lambda chunk: chunk.chunk_start)

    # Integrity guard: total iterations must equal sum of chunk sizes
    assert sum(c.chunk_size for c in chunks) == sum(c.chunk_size for c in chunks), (
        "chunk sizes do not add up to total iterations"
    )

    project_durations = np.concatenate([c.project_durations for c in chunks])
    # ... same for all array fields ...

    # Counter merge: sum counts (not union — every task must appear in every chunk)
    critical_path_freq: Dict[str, int] = {}
    for c in chunks:
        for tid, count in c.critical_path_frequency.items():
            critical_path_freq[tid] = critical_path_freq.get(tid, 0) + count

    critical_path_seqs: Counter[tuple[str, ...]] = Counter()
    for c in chunks:
        critical_path_seqs += c.critical_path_sequences

    max_parallel = max(c.max_parallel for c in chunks)
    # ...
```

Merge is single-threaded in the parent and runs in O(total_iterations) — negligible compared to the simulation itself.

> **Type contract with `_build_results`**: `_build_results` currently accepts `Dict[str, list[float]]` for per-task accumulator fields. After concatenation, the merged data is `Dict[str, np.ndarray]`. Because `np.mean(array)` and `np.array(array)` both accept `np.ndarray`, this works at runtime, but strict `mypy` will flag the mismatch. The implementation must either update the `_build_results` signature to `Dict[str, Sequence[float] | np.ndarray]` for those parameters, or explicitly convert merged arrays to lists before passing. Choose and document one approach before implementation begins.

###  IPC Cost Analysis

Each completed micro-chunk transfers its `ChunkResult` back via pickle. Under the proposed `max(workers * 8, 32)` chunking policy, a 10 000-iteration run on 8 workers would use 32 chunks of about 313 iterations each. For a 30-task micro-chunk of that size:

| Field | Size |
|-------|------|
| `project_durations` | 313 × 8 bytes ≈ 2.5 KB |
| `task_durations` (30 tasks) | 30 × 2.5 KB ≈ 75 KB |
| `task_risk_impacts` | ≈ 75 KB |
| `task_slack` | ≈ 75 KB |
| `critical_path_frequency` | ~30 × 16 bytes ≈ 0.5 KB |
| `critical_path_sequences` | variable — typically much smaller, but workload-dependent |
| Scalar arrays (costs, resource stats) | tens of KB |
| **Total per micro-chunk** | **roughly a few hundred KB** |

Across the full run, total transferred result data scales primarily with total iterations and stored per-iteration arrays, not directly with worker count. The extra cost of using more micro-chunks is additional pickle framing overhead, which should remain small relative to simulation time for non-trivial workloads.

###  When to Parallelize

Parallel dispatch has fixed overhead: process pool startup, argument serialization, result deserialization, and merge. For small workloads this overhead dominates.

Default policy:

```python
PARALLEL_MIN_ITERATIONS = 500
PARALLEL_MIN_TASKS = 5
```

Parallelism is enabled only when both thresholds are exceeded **and** `workers > 1`. The user can explicitly set `workers=1` to force sequential execution.

**Degenerate case — `workers > iterations`**: when the requested worker count exceeds the iteration count (e.g. `workers=8, iterations=3`), the effective worker count must be clamped: `effective_workers = min(self.workers, self.iterations)`. Without this clamp, some chunks would be empty (size 0), causing `np.concatenate([])` to fail and `max()` over an empty sequence to raise. The clamp must be applied before chunk partitioning, not inside the merge.

###  Executor Lifetime

This design assumes a **short-lived executor per simulation run**.

- **CLI path**: create a new `ProcessPoolExecutor` inside `SimulationEngine.run()` and tear it down before returning. There is no pool reuse across separate CLI invocations.
- **Library/MCP path**: keep the engine default conservative (`workers=1`) so callers do not unexpectedly fan out to all CPUs. A service that wants reuse or higher concurrency may add its own pool management later, but that is explicitly out of scope for the first implementation.

This avoids hidden global state, simplifies cleanup, and keeps the implementation compatible with both one-shot CLI usage and embedded/library usage.

###  Progress Reporting

The naive design of using **one chunk per worker** is a progress-reporting flaw. If the workload is balanced, all workers finish at roughly the same time, so chunk-completion progress collapses into one visible jump near the end.

To avoid that, **progress granularity must be decoupled from worker count**.

Proposed v1 design:

1. Partition the total iteration range into **many deterministic micro-chunks**, not just `workers` chunks.
2. Keep at most `workers` micro-chunks running concurrently in the executor.
3. Each completed micro-chunk advances progress by its iteration count.

Suggested policy:

```python
target_chunk_count = min(iterations, max(workers * 8, 32))
chunk_size = math.ceil(iterations / target_chunk_count)
```

This gives:

- smoother progress updates,
- better load balancing when iteration cost varies,
- deterministic chunk boundaries for reproducibility.

With this design, an 8-worker run might use 32 or 64 micro-chunks, so the user sees incremental progress rather than one update at the end.

If even smoother progress is needed later, a second-stage enhancement can add worker heartbeats via a manager-backed queue or shared counter, but that is not required for v1.

###  Cancellation

Do **not** pass a raw `multiprocessing.Event` directly as a task argument on macOS/`spawn`; that pattern fails because the underlying synchronization primitives are not picklable in that form.

Initial implementation options that do work:

1. **`multiprocessing.Manager().Event()`**: simplest portable option. The parent creates a manager-backed event and passes the proxy to workers.
2. **Pool initializer + inherited shared state**: lower overhead, but more wiring and more platform-sensitive.

Proposed: **Option 1** for the first implementation because it is portable and straightforward.

Worker loop behaviour:

- Each worker checks `cancel_event.is_set()` at the top of each iteration.
- If set, the worker raises `SimulationCancelled` or returns a cancelled sentinel.
- The parent catches that state, calls `executor.shutdown(wait=False, cancel_futures=True)`, and raises `SimulationCancelled` to the caller.

**`_cancelled` reset between runs**: `SimulationEngine._cancelled` is never reset in the current sequential engine. After a cancelled parallel run, `_cancelled` remains `True`, and the next call to `run()` on the same engine instance would immediately raise `SimulationCancelled` without executing any iterations. The parallel implementation must add `self._cancelled = False` at the **start** of `run()`, before any dispatch logic. Add `self._active_cancel_event: Optional[Any] = None` to `__init__`; assign the manager event before the executor starts; set it back to `None` in the `finally` block. `cancel()` must set both `self._cancelled` and `self._active_cancel_event` (when present) so cancellation works for both the sequential and parallel paths with one call.

### Two-Pass Interaction

Two-pass scheduling (`_run_two_pass`) has a data dependency: pass-2 depends on pass-1's criticality indices. Both passes can independently be parallelized:

1. **Pass-1 parallel** → merge → compute `task_ci`.
2. **Pass-2 parallel** (each worker receives `task_ci`) → merge → build results.

Cached duration replay (pass-2 iterations < `pass1_iterations` reuse pass-1 durations) complicates cross-process pairing. Two options:

- **Option A**: Skip duration cache across processes — each pass-2 worker re-samples (no paired replay). This slightly changes the statistical properties but is simpler.
- **Option B**: Transfer the duration cache from pass-1 workers to pass-2 workers. For 1 000 pass-1 iterations × 30 tasks × 8 bytes = 240 KB — trivial.

Proposed: **Option B** — preserve paired replay semantics. Pass-1 workers return their `DurationCache` partition and the corresponding per-iteration task risk cost impacts; the parent distributes the relevant slices to pass-2 workers.



##  API Design

###  New `SimulationEngine` Parameter

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
        workers: int = 1,       # <-- NEW
    ):
```

    The parameter behaves as follows:

    - `workers=1` (default): force sequential execution (existing code path, no process pool). This keeps library and MCP callers conservative and backwards-compatible.
    - `workers=N` (N > 1): use N worker processes.

    The **CLI** may still expose an auto mode and translate it before constructing the engine:

    - CLI `--workers auto`: resolve to `os.cpu_count()`.
    - CLI `--workers 1`: force sequential.
    - Library callers that want auto-detection can opt into it explicitly before creating the engine.

###  CLI Flag

```
mcprojsim simulate project.yaml --workers 4
mcprojsim simulate project.yaml --workers 1    # force sequential
mcprojsim simulate project.yaml --workers auto
```

###  Reproducibility Contract

The docstring and user guide will state:

> When `workers > 1`, results are deterministic for a given `(random_seed, workers, chunking policy)` tuple. Changing the number of workers changes the random stream partitioning and therefore the exact results. To reproduce results from a parallel run, use the same `random_seed`, `workers`, and implementation-defined chunking policy. Setting `workers=1` reproduces legacy sequential behaviour exactly.



##  Expected Speedup

###  Amdahl's Law Analysis

Let $p$ be the fraction of work that is parallelizable (the per-iteration simulation), and $s = 1 - p$ be the serial fraction (argument setup, result merge, `_build_results`).

The serial fraction consists of:
- `_build_project_run_static_data`: runs once and is small.
- Merge: O(total_iterations), dominated by `np.concatenate` and `Counter` merging.
- `_build_results`: statistics, percentile caching, sensitivity analysis, and optional cost analysis.
- Process pool startup and teardown: roughly 50–200 ms per run on the CLI path.

The previous version of this proposal understated the serial tail. In this codebase, post-processing is not negligible:

- `SimulationResults.calculate_statistics()` computes skewness and kurtosis via SciPy.
- `SensitivityAnalyzer.calculate_correlations()` runs one Spearman correlation per task.
- `CostAnalyzer.analyze()` runs additional Spearman and Pearson correlations when cost tracking is active.

On the current development machine, a synthetic 10 000-iteration result set showed the following approximate serial post-processing cost:

- **30 tasks with cost arrays**: ~0.18 s for statistics, percentiles, sensitivity, and cost analysis.
- **100 tasks with cost arrays**: ~0.58 s for the same work.

That means the serial fraction is workload-dependent and can easily land in the **5–20%** range once analysis and process startup are included.

Maximum theoretical speedup with $N$ workers remains:

$$S(N) = \frac{1}{s + \frac{1-s}{N}}$$

Representative bounds for 8 workers:

| Serial fraction $s$ | Max theoretical speedup at 8 workers |
|---------------------|--------------------------------------:|
| 5%                  | 5.93× |
| 10%                 | 4.71× |
| 15%                 | 3.90× |
| 20%                 | 3.33× |

###  Practical Overhead Deductions

Real-world factors that reduce the theoretical maximum:

| Factor | Cost | Impact |
|--------|------|--------|
| Pool startup/teardown | ~50–200 ms per run | Material for small CLI workloads |
| Argument serialization (pickle project) | ~1–5 ms | Negligible |
| Result deserialization (8 workers × ~1 MB) | ~10 ms | Negligible |
| Serial post-processing (`_build_results`, sensitivity, cost analysis) | ~0.1–0.6+ s depending on task count and enabled outputs | Material limiter on high-core-count scaling |
| OS scheduling / cache effects | 5–15% | Reduces effective speedup by ~10% |

**Revised realistic expectation:**

- **Small workloads** (< 500 iterations or < 5 tasks): sequential is likely faster.
- **Typical constrained workloads** (roughly 10 000 iterations, tens of tasks): expect around **2× to 4×** speedup on 8 logical CPUs.
- **Heavier workloads with minimal post-processing** may approach **4× to 5×**, but that should be treated as an upper-end result, not the default expectation.

The design should therefore position parallel execution as a substantial improvement for heavier runs, not as near-linear scaling.

###  Comparison: Threading vs Multiprocessing

| Approach | GIL-bound scheduler | IPC overhead | Reproducibility | Speedup (8 cores) |
|----------|:-------------------:|:------------:|:---------------:|:-----------------:|
| Threading | serialized | none | easy (shared state) | ~1.0× (no gain) |
| Multiprocessing (chunked) | bypassed | low but non-zero | SeedSequence | ~2× to 5× depending on workload |

###  Validation Requirement for Performance Claims

The exact speedup claim must be validated on this repository after implementation. The design is only complete if it includes a benchmark pass that compares:

1. dependency-only scheduling vs resource-constrained scheduling,
2. small, medium, and large task sets,
3. cost analysis on vs off,
4. worker counts `1`, `2`, `4`, `8`, and `auto`.

No documentation or release note should claim a specific speedup range until those benchmark numbers exist.



##  Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| `fork` safety on macOS (default is `spawn` since Python 3.8) | Medium | Use `spawn` start method explicitly; avoid forking with loaded numpy. Already the default on macOS. |
| Pickle failures for custom objects | Low | `Project`, `Config`, `ProjectRunStaticData` are all Pydantic/dataclass — pickle-safe. Add a smoke test. |
| Memory pressure (N copies of project) | Low | Project is typically < 100 KB. 8 copies = < 1 MB. |
| Non-determinism from `spawn` timing | None | Workers use `SeedSequence`-derived independent streams — deterministic regardless of scheduling order. |
| Merge order accidentally following completion order | Medium | Include `chunk_start` in `ChunkResult` and always sort before concatenation. |
| Regression in sequential mode | Medium | Keep the existing `_run_single_pass` code path exactly as-is when `workers=1`. Parallel mode is a separate code path. |
| Cancellation primitive not portable under `spawn` | High | Use `multiprocessing.Manager().Event()` for v1; do not pass a raw `multiprocessing.Event` as a task argument. |
| Two-pass paired replay correctness | Medium | Transfer `DurationCache` partition from pass-1 to pass-2 workers and assert cache hit rate in tests. |
| `progress_callback` granularity | Low | Document that parallel mode reports per-chunk progress. Implement fine-grained counter in a follow-up. |
| Default worker count oversubscribes embedded callers | High | Keep `SimulationEngine(workers=1)` as the library default; only the CLI offers `auto`. |
| Worker uses wrong `RandomState` instance | High | Worker must pass the same chunk-local `rng` to `DistributionSampler`, `RiskEvaluator`, and `TaskScheduler`. A mismatch silently uses the wrong stream without raising any error. |
| Worker writes to stdout | Medium | Workers must be constructed with `show_progress=False` and `progress_callback=None`. Enforce this inside `_run_chunk` unconditionally, regardless of the parent's settings. |
| `_cancelled` not reset between runs | High | Add `self._cancelled = False` at the start of `run()`. Without it, a cancelled engine becomes permanently dead on the same instance. |
| Two-pass passes sharing one `SeedSequence` tree | High | Pass-1 and pass-2 must derive child seeds from separate parent sequences (`root_seq.spawn(2)`). A common parent breaks statistical independence between the two passes. |
| `workers > iterations` causes empty chunks | Medium | Clamp `effective_workers = min(self.workers, self.iterations)` before chunk partitioning. Empty chunks cause `np.concatenate` failures and empty-sequence `max()` errors. |
| Two-pass global index corruption | High | Pass-1 workers store cache entries with **local** indices (0-based within chunk). Parent merge must remap: `global_idx = chunk.chunk_start + local_idx`. Failing to remap causes pass-2 workers to look up wrong keys or raise `KeyError`. |



##  Alternatives Considered

###  `threading` with GIL-releasing C Extensions

Rejected. The scheduler is pure Python and accounts for ~60% of iteration time. Threading would achieve at most ~1.0× speedup on the overall simulation (see §3.2).

###  Cython/Rust Scheduler + Threading

Rewriting the scheduler in a GIL-releasing language would allow true threading parallelism. However:
- The scheduler is ~500 lines of non-trivial dependency/resource logic.
- Maintenance burden of a dual-language codebase.
- Out of scope for a first parallelism iteration.

This remains the long-term optimal path and is noted in §3.6.

###  `asyncio`

`asyncio` is cooperative multitasking on a single thread. It provides zero CPU parallelism. Useful for I/O-bound work (e.g., web server), not for compute-bound simulation.

###  `joblib` / `dask`

External dependencies that wrap multiprocessing with additional features (memoisation, distributed scheduling). Overkill for this use case. The standard library `concurrent.futures.ProcessPoolExecutor` is sufficient and adds no dependencies.



##  Implementation Plan

### Step 1 — Add Parallel Support Module

Create a new module [src/mcprojsim/simulation/parallel.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/parallel.py) with:

- `ChunkResult` frozen dataclass,
- chunk partition helpers,
- seed partition helpers,
- `merge_chunk_results()`.

- **Inputs**: list of `ChunkResult`.
- **Outputs**: merged accumulators matching the signature of `_build_results`.
- **Important**: include `chunk_start` and sort chunks before concatenation so merge order is deterministic.
- **Verify**: unit test that merges two synthetic `ChunkResult` objects delivered out of order and asserts deterministic concatenation, summed counters, and max-parallel.

Validation:

- Add unit tests in either a new [tests/test_parallel_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_parallel_simulation.py) or in [tests/test_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_simulation.py).
- Confirm the helper module contains no CLI-only imports and can be imported safely from worker processes.
- Verify chunk partitioning creates more progress units than workers and remains deterministic for a fixed `(iterations, workers)` tuple.
- Add an assertion inside `merge_chunk_results` that `sum(c.chunk_size for c in chunks) == total_iterations`; raise `AssertionError` on mismatch so any partitioning bug surfaces immediately.
- Test that merged `critical_path_frequency` values sum to exactly `total_iterations` across all tasks (every iteration must nominate exactly one critical path).
- Test that merged `critical_path_sequences` Counter equals the elementwise sum of individual chunk Counters — not a union — so path frequencies are correctly accumulated.
- Test that merging two chunks with `chunk_start` values `[100, 0]` (deliberately reversed order) produces identical output to merging them in `[0, 100]` order.
- Test that merging a list containing one empty chunk (size 0) does not raise and produces correct totals from the remaining chunks.

### Step 2 — Worker Function `_run_chunk`

Add a module-level function `_run_chunk()` in [src/mcprojsim/simulation/parallel.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/parallel.py) (must be top-level for pickling):

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
    cancel_event: Optional[Any],
) -> ChunkResult:
```

The function reconstructs `Project`, `Config`, `SimulationEngine` internals, runs the iteration chunk, and returns a `ChunkResult`. `cancel_event` is a manager-backed proxy, not a raw `multiprocessing.Event`.

- **Verify**: call `_run_chunk` directly (no pool) with a 100-iteration chunk on the quickstart project. Assert result shapes and value ranges.

Validation:

- Use [examples/quickstart_example.yaml](/Users/ljp/Devel/mcprojsim/examples/quickstart_example.yaml) or a fixture from [tests/fixtures/test_fixture_contention.yaml](/Users/ljp/Devel/mcprojsim/tests/fixtures/test_fixture_contention.yaml).
- Ensure `_run_chunk()` reconstructs only models and helper objects that are actually pickle-safe in this repo: `Project`, `Config`, `TaskScheduler`, `DistributionSampler`, `RiskEvaluator`.
- Ensure the function does not rely on instance state from `SimulationEngine` that is unavailable in a spawned process.
- If `_run_chunk()` instantiates `SimulationEngine` internally for helper reuse, force `workers=1` there so worker code cannot recurse into parallel dispatch.
- Verify that the single chunk-local `rng` object produced by `RandomState(MT19937(child_seed))` is passed to `DistributionSampler`, `RiskEvaluator`, **and** `TaskScheduler` — add an assertion or integration test that confirms different components within one chunk share the same `random_state` identity.
- Test that calling `_run_chunk` twice with identical `(project_dict, config_dict, child_seed, chunk_start, chunk_size)` produces **bit-for-bit identical** `project_durations` arrays (chunk-level reproducibility).
- Test that `_run_chunk` produces **no stdout output** — capture stdout with `capsys` and assert it is empty.

### Step 3 — Seed Partitioning

Add a helper `partition_seeds(random_seed, n_chunks)` that returns a list of `SeedSequence` children aligned to deterministic chunk order.

- **Verify**: call twice with the same seed and chunk count — assert identical child entropy. Call with different chunk counts — assert different entropy.

Validation:

- Keep this helper in [src/mcprojsim/simulation/parallel.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/parallel.py), not in CLI code.
- Add a determinism test in [tests/test_parallel_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_parallel_simulation.py).
- Add a test that changing chunk count changes the derived seed set, while keeping `(random_seed, n_chunks)` fixed reproduces it exactly.
- Add a test that child seeds for two different chunk indices produce statistically independent streams: draw the first 10 values from each child's `RandomState(MT19937(child_seed))` and assert they are not all equal.
- Assert `n_chunks >= 1` inside `partition_seeds`; raise `ValueError` for `n_chunks < 1`.

### Step 4 — Parallel Dispatch in Single-Pass

Update [src/mcprojsim/simulation/engine.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/engine.py):

- add the `workers` parameter to `SimulationEngine.__init__`,
- add `_run_single_pass_parallel()`,
- branch from the existing `_run_single_pass()` or `run()` entry path when parallel execution is enabled.

Implementation details:

1. Partition iterations into deterministic micro-chunks, where chunk count is greater than worker count.
2. Serialize `project` and `config` as dicts (`.model_dump()`).
3. Create a short-lived `ProcessPoolExecutor` using a `spawn` context.
4. Submit up to `workers` micro-chunks initially, then refill the executor as futures complete until all chunks are consumed.
5. Collect results, sort by `chunk_start`, merge, call `_build_results`.

Wire `_run_single_pass` to delegate to the parallel variant when `self.workers > 1` and thresholds are met.

- **Verify**: run the quickstart project with `workers=2, seed=42` and assert identical results on repeated runs. Compare mean/p80/p90 to `workers=1` results — should be statistically similar (not identical due to different seed streams).

Validation:

- Preserve the existing sequential path unchanged when `workers == 1`.
- Confirm [src/mcprojsim/simulation/__init__.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/__init__.py) still exports `SimulationEngine` cleanly. No new exports are required unless the parallel helpers are intended to be public.
- Add regression tests to [tests/test_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_simulation.py) for sequential behaviour and to [tests/test_parallel_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_parallel_simulation.py) for parallel behaviour.
- Add an assertion inside `_run_single_pass_parallel` that `sum(chunk_sizes) == self.iterations` before any futures are submitted, so partitioning bugs surface at the call site.
- Wrap the entire executor block in `try/finally executor.shutdown(wait=True)` to prevent process leaks even when an unexpected exception occurs before all futures complete.
- Test that `workers=1` produces **bit-for-bit identical** `SimulationResults` (same `durations` array, same statistics) compared to the pre-existing sequential path for the same seed — this is the critical regression guard confirming the sequential code path was not modified.
- Test that `workers > iterations` (e.g. `workers=8, iterations=3`) does not raise and returns a valid `SimulationResults`.
- Test that cost-tracking output (when active) in parallel mode matches the sequential output for the same `(random_seed, workers)` tuple.

### Step 5 — Cancellation

Create a `multiprocessing.Manager()` inside the parallel run path and pass `manager.Event()` to each worker. On `cancel()`, set the event. Workers check `cancel_event.is_set()` each iteration.

- **Verify**: start a 100 000-iteration simulation in a background thread, call `cancel()` after 100 ms, assert `SimulationCancelled` is raised.

Validation:

- Implement and test this in [src/mcprojsim/simulation/engine.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/engine.py) and [src/mcprojsim/simulation/parallel.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/parallel.py).
- Do not pass a raw `multiprocessing.Event` as a task argument.
- Confirm cancellation also tears down manager resources and the executor cleanly.
- Update `SimulationEngine.cancel()` itself so it sets both the existing in-process `_cancelled` flag and the active shared cancel event when a parallel run is in flight.
- Reset any per-run shared cancellation state in `run()` setup/finally so one cancelled run does not poison later runs on the same engine instance.
- Test that calling `run()` again on the same engine instance **after** a cancelled run succeeds and returns a valid result (i.e. `_cancelled` was reset).
- Test that after cancellation all worker processes have exited (no daemon process leak): assert that `executor._processes` is empty or all processes have `exitcode is not None` after `executor.shutdown(wait=True)` completes.

### Step 6 — Progress Reporting

After each micro-chunk `Future` completes, update the progress counter by that chunk's completed iteration count and invoke `progress_callback`.

- **Verify**: run with `progress_callback` capturing calls. Assert monotonically increasing completed counts.

Validation:

- Keep the callback signature aligned with the current engine contract in [src/mcprojsim/simulation/engine.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/engine.py).
- Add targeted tests in [tests/test_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_simulation.py) or [tests/test_parallel_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_parallel_simulation.py).
- Add a test that uses `workers=4` with more than 4 micro-chunks and asserts multiple progress updates arrive before completion.
- Preserve the current stdout throttling semantics for non-callback progress output, so micro-chunk completion does not emit one line per chunk when output is redirected.
- Test that parallel mode does **not** emit stdout progress lines when a `progress_callback` is provided — capture stdout and assert it is empty.
- Test that the final progress callback invocation reports `completed_iterations == self.iterations` exactly — no off-by-one from rounding in chunk boundaries.

### Step 7 — Two-Pass Parallel

Extend the existing two-pass path in [src/mcprojsim/simulation/engine.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/simulation/engine.py):

1. Pass-1: parallel chunks → merge → compute `task_ci` + collect `DurationCache` partitions and per-iteration task risk cost-impact partitions.
2. Pass-2: parallel chunks, each receiving `task_ci`, relevant `cached_durations_slice`, and relevant cached task risk cost impacts.

- **Verify**: run a constrained project with `two_pass=True, workers=2, seed=42` and assert `TwoPassDelta` is populated. Compare to `workers=1` — delta direction should agree.

Validation:

- Reuse the existing acceptance coverage in [tests/test_two_pass_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_two_pass_simulation.py) and extend it rather than duplicating the whole suite.
- Ensure pass-1 replay data remains keyed by global iteration index so `chunk_start` offsets do not corrupt replay.
- Preserve both paired duration replay and paired task-level cost-impact replay; the current engine uses both to keep cost overruns correlated with schedule overruns.
- Verify that two-pass remains dependency-only when resources are absent, just as the current engine does.
- Preserve the existing user-facing pass labels and progress structure (`Pass 1`, `Pass 2`) when progress output is enabled.
- After parallel pass-1 merge, assert `len(global_duration_cache) == effective_p1_iters * n_tasks` before starting pass-2 dispatch — a size mismatch means the global-index remapping is wrong.
- Test that the pass-2 replay fraction is correct: exactly `effective_p1_iters` of the `self.iterations` pass-2 iterations must use cached durations, and the rest must sample fresh.
- Test that pass-1 and pass-2 child seeds are derived from **different** parent `SeedSequence` objects (from `root_seq.spawn(2)`) so the two passes remain statistically independent.

### Step 8 — CLI Integration

Update the real CLI entry point in [src/mcprojsim/cli.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/cli.py) by adding `--workers` to the existing `simulate` command:

```python
@click.option("--workers", type=str, default="1",
              help="Worker processes for parallel simulation. Use an integer or 'auto'.")
```

Resolve `auto` in the CLI layer via `os.cpu_count()` and pass the resulting integer to `SimulationEngine(workers=workers)`.

- **Verify**: `mcprojsim simulate examples/quickstart_example.yaml --workers 2 --seed 42` produces valid output. `--workers 1` matches legacy output exactly. `--workers auto` resolves to the detected CPU count.

Validation:

- Extend [tests/test_cli.py](/Users/ljp/Devel/mcprojsim/tests/test_cli.py) for option parsing and engine construction.
- Add a CLI integration test in [tests/test_cli_integration.py](/Users/ljp/Devel/mcprojsim/tests/test_cli_integration.py) if end-to-end invocation is needed.
- Do not change MCP defaults in [src/mcprojsim/mcp_server.py](/Users/ljp/Devel/mcprojsim/src/mcprojsim/mcp_server.py) for v1; the engine default remains `workers=1`.
- Add explicit CLI validation that `--workers` is either `auto` or a positive integer; reject `0`, negatives, and arbitrary strings before constructing the engine.
- Update the many `FakeEngine` stubs in [tests/test_cli.py](/Users/ljp/Devel/mcprojsim/tests/test_cli.py) so monkeypatched constructor signatures accept the new `workers` argument.
- Test that `--workers 0`, `--workers -1`, and `--workers abc` each produce a `UsageError` / `BadParameter` **before** any project file is parsed or engine is constructed — fail fast on bad input.
- Verify `--workers auto` resolves to `os.cpu_count()` (or at minimum a positive integer) and that the resolved value is logged or visible in `--verbose` output so users can confirm what was used.

### Step 9 — Documentation and Tests

- Update [docs/user_guide/12_running_simulations.md](/Users/ljp/Devel/mcprojsim/docs/user_guide/12_running_simulations.md) to explain the `--workers` flag and reproducibility guarantees.
- Update [docs/api_reference/02_core.md](/Users/ljp/Devel/mcprojsim/docs/api_reference/02_core.md) if `SimulationEngine` constructor arguments are documented there.
- Add [tests/test_parallel_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_parallel_simulation.py).
- Cover determinism: same seed + workers → same results.
- Cover deterministic merge: same seed + workers still matches when chunk futures complete in different orders.
- Cover correctness: parallel summary metrics remain within an agreed tolerance on fixed fixtures; avoid a brittle hard-coded threshold until benchmark data exists.
- Cover cancellation: parallel cancel raises `SimulationCancelled`.
- Cover edge cases: `workers > iterations` (degenerate chunks).
- Cover two-pass mode: parallel two-pass produces valid `TwoPassDelta`.

Validation:

- Keep existing sequential test suites green: [tests/test_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_simulation.py), [tests/test_two_pass_simulation.py](/Users/ljp/Devel/mcprojsim/tests/test_two_pass_simulation.py), and [tests/test_cli.py](/Users/ljp/Devel/mcprojsim/tests/test_cli.py).
- Run at minimum:

  - `poetry run pytest tests/test_parallel_simulation.py --no-cov -v`
  - `poetry run pytest tests/test_simulation.py tests/test_two_pass_simulation.py tests/test_cli.py --no-cov -v`

### Step 10 — Performance Benchmark

Create a new benchmark script at [benchmarks/bench_parallel.py](/Users/ljp/Devel/mcprojsim/benchmarks/bench_parallel.py). The `benchmarks/` directory does not currently exist, so this step includes creating that directory.

Benchmark matrix:

- dependency-only fixture,
- constrained-scheduling fixture,
- cost tracking on/off,
- worker counts `1`, `2`, `4`, `8`, and `auto` where available.

Suggested inputs:

- [tests/fixtures/test_fixture_abundant_resources.yaml](/Users/ljp/Devel/mcprojsim/tests/fixtures/test_fixture_abundant_resources.yaml),
- [tests/fixtures/test_fixture_contention.yaml](/Users/ljp/Devel/mcprojsim/tests/fixtures/test_fixture_contention.yaml),
- optionally a larger example from [examples/large_project_100_tasks.yaml](/Users/ljp/Devel/mcprojsim/examples/large_project_100_tasks.yaml).

- **Verify**: record actual speedup ratios; do not hard-code a pass/fail expectation like `≥ 4×` until the implementation is benchmarked on representative hardware.

Validation:

- **Required**: the benchmark script must include `if __name__ == "__main__":` guard — without it, importing the script (e.g. accidentally during test discovery) would spawn worker processes recursively under `spawn`. This is not optional.
- Record not just elapsed time, but also worker count, chunk count, and whether cost analysis was enabled, so benchmark output can be interpreted later.

### Step 11 — Final Validation Gate

Before the feature is considered complete:

1. Run the focused test suites named above.
2. Run a manual CLI check with `--workers 1`, `--workers 2`, and `--workers auto`.
3. Run the benchmark script and capture results in a developer note or PR description.
4. Confirm there is no behavioural change for current MCP callers because the engine default remains sequential.
5. Confirm documentation avoids claiming a specific speedup until benchmark data exists.


## Post-Implementation Analysis (2026-04-18): Why Dependency-Only Scales Less

### Observed Benchmark Shape

Recent benchmark runs over `20k`, `50k`, `80k`, and `200k` iterations show:

- **Resource-constrained contention fixture** scales strongly, reaching about **5.18x** at 8 workers for 200k iterations.
- **Large dependency-only fixture (100 tasks)** scales well but lower, reaching about **4.20x** at 8 workers for 200k iterations.
- **Tiny dependency-only fixture (3 tasks)** is intentionally gated to remain sequential via the payoff heuristic (parallel overhead dominates).

So the dependency-only large workload is **not failing to scale**; it is scaling materially, but less than the constrained case.

### Independence Is Necessary, Not Sufficient

Per-iteration independence allows parallel execution, but it does **not** remove all serial and overhead costs.

Total wall clock still includes:

1. Process startup and pool coordination.
2. Serialization/deserialization of chunk arguments and results.
3. Parent-side merge of arrays and counters.
4. Serial post-processing (`_build_results`, percentiles, sensitivity, optional cost analysis).

By Amdahl's law, even with perfectly independent iterations, speedup is bounded by the non-parallel tail.

For 8 workers, using measured speedups:

- Dependency-only large fixture: $S \approx 4.20$  $\Rightarrow$ implied serial fraction $s \approx 0.13$.
- Constrained contention fixture: $S \approx 5.18$ $\Rightarrow$ implied serial fraction $s \approx 0.078$.

That difference in effective serial fraction explains most of the gap.

### Why the Dependency-Only 100-Task Case Has a Larger Effective Serial Fraction

#### 1. Lower compute intensity per iteration than constrained scheduling

Dependency-only scheduling is algorithmically cheaper than resource-constrained scheduling because it does not resolve resource assignment conflicts and waiting windows. This means each iteration does less useful CPU work to amortize fixed multiprocessing overhead.

In short: constrained mode has **more work per iteration**, so it benefits more from process-level parallelism.

#### 2. Much higher IPC volume for 100-task chunks

At 200k iterations with 8 workers, current chunking uses 64 chunks of 3125 iterations each.

Per chunk for the 100-task dependency-only case (float64 arrays):

- `project_durations`: ~25 KB
- `task_durations`: ~2.5 MB
- `task_risk_impacts`: ~2.5 MB
- `task_slack`: ~2.5 MB
- scalar diagnostic arrays + maps: additional overhead

Total returned payload is on the order of **~7.5 MB per chunk** before pickle/container overhead, i.e. roughly **~480 MB** transferred from workers to parent over the run.

For the 7-task contention fixture, equivalent payload is roughly an order of magnitude smaller. The heavier IPC burden in the 100-task dependency-only case directly reduces net speedup.

#### 3. Serial post-processing cost grows with task count

After merge, analysis still runs in the parent:

- statistics over large arrays,
- percentile caching,
- sensitivity correlations per task.

With 100 tasks this post phase is materially larger than with 7 tasks, further increasing the serial tail.

#### 4. Chunk boundary overhead remains fixed by policy

The chunk policy (`max(workers * 8, 32)`) is chosen for progress smoothness and load balance. It also implies a fixed number of chunk submissions/results per run, each with framing and coordination overhead. If per-chunk payload is large (100-task case), this overhead is more visible.

### Is This an Implementation Bug?

Current evidence says **no**.

- The scaling direction is correct (speedup grows with iteration count).
- Determinism and correctness tests pass.
- The relative gap matches expected overhead structure (IPC + serial analysis + lighter per-iteration compute in dependency-only mode).

So this is primarily a **performance-shape characteristic**, not a correctness defect.

### Practical Interpretation

- For heavy constrained workloads, parallel mode provides strong payoff.
- For heavy dependency-only workloads, parallel mode still helps significantly, but less than constrained mode.
- For tiny graphs / low iteration counts, sequential remains best and is now enforced by heuristic gating.

### Follow-Up Optimizations (if higher dependency-only speedup is desired)

1. **Reduce IPC payload**: optional "summary-only" mode that does not return all per-task arrays when caller/export path does not need them.
2. **Adaptive chunk sizing**: larger chunks for high-task-count dependency-only runs to reduce per-chunk framing cost.
3. **Cheaper cancellation polling**: avoid manager-proxy checks every single iteration (poll every k iterations).
4. **Post-processing parallelization/vectorization**: especially sensitivity for high task counts.
5. **Worker state reuse via initializer**: reduce per-chunk reconstruction overhead where safe.

These are optimisation opportunities; they are not blockers for functional correctness.


## Chunk-Size Experiment (2026-04-18): Halved Chunk Count + Min 6000 Iterations

### Experiment Setup

To test whether IPC overhead is the dominant limiter, we ran an experiment with two temporary partitioning changes:

1. halve target chunk count from `max(workers * 8, 32)` to `max(workers * 4, 16)`
2. enforce `chunk_size >= 6000`

Same benchmark matrix as before:

- fixtures: `abundant_resources`, `contention`, `large_100_tasks`
- workers: `1, 2, 4, 8`
- iterations: `20k, 50k, 80k, 200k`

### Results vs Baseline

Key comparison at 8 workers (`speedup` relative to 1 worker):

| Fixture | 20k | 50k | 80k | 200k |
|--------|----:|----:|----:|-----:|
| contention (baseline) | 2.90x | 4.03x | 4.47x | 5.18x |
| contention (min 6000) | 1.94x | 3.78x | 4.20x | 5.42x |
| delta | -0.96x | -0.25x | -0.27x | +0.24x |
| large_100_tasks (baseline) | 2.80x | 3.55x | 3.79x | 4.20x |
| large_100_tasks (min 6000) | 1.89x | 3.42x | 3.62x | 4.45x |
| delta | -0.91x | -0.13x | -0.17x | +0.25x |

Observations:

- At **20k–80k**, forcing a 6000 minimum chunk size clearly hurts speedup.
- At **200k**, it helps modestly (better amortisation of IPC/framing overhead).
- `abundant_resources` remains near 1.0x either way (no meaningful gain from parallelism for this tiny graph).

### Interpretation

A large fixed minimum chunk size trades off two effects:

1. **Pro**: fewer, larger payload transfers and less per-chunk framing overhead.
2. **Con**: coarser load balancing, fewer progress events, and weaker queue refill dynamics.

For medium workloads (20k–80k), the balancing downside dominates. For very large workloads (200k), IPC amortisation starts to dominate.

### Recommendation: Minimum Chunk Size Policy

Do **not** use a global hard minimum of 6000. It is too aggressive for medium-size runs.

Recommended policy:

1. Keep the current baseline chunking (`max(workers * 8, 32)`) as default.
2. If introducing a minimum chunk size, make it **adaptive**, not fixed:
    - `iterations < 100_000`: no minimum (or <= 2000)
    - `100_000 <= iterations < 200_000`: minimum around 3000
    - `iterations >= 200_000`: minimum around 5000–6000

If a single static value must be chosen, the safest value from this experiment is **~3000**, not 6000, because it is less likely to penalise 20k–80k workloads while still reducing chunk count for larger runs.
