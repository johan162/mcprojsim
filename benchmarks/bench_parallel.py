"""Benchmark: parallel simulation speedup across worker counts and project sizes.

Run with:
    poetry run python benchmarks/bench_parallel.py

Results are printed to stdout and can be captured for documentation.
Do NOT import this file from tests; it spawns worker processes when executed.
"""

from __future__ import annotations

if __name__ == "__main__":
    import os
    import time
    from pathlib import Path

    from mcprojsim.config import Config, ConstrainedSchedulingAssignmentMode
    from mcprojsim.parsers.yaml_parser import YAMLParser
    from mcprojsim.simulation.parallel import partition_chunks
    from mcprojsim.simulation.engine import SimulationEngine

    REPO_ROOT = Path(__file__).parent.parent
    FIXTURES = {
        "abundant_resources": REPO_ROOT
        / "tests/fixtures/test_fixture_abundant_resources.yaml",
        "contention": REPO_ROOT / "tests/fixtures/test_fixture_contention.yaml",
        "large_100_tasks": REPO_ROOT / "examples/large_project_100_tasks.yaml",
    }
    WORKER_COUNTS: list[int | str] = [1, 2, 4, 8, "auto"]
    ITERATION_COUNTS = [20_000, 50_000, 80_000, 200_000]
    RUN_MODES = ["single_pass", "two_pass"]
    COST_MODES = [False, True]
    SEED = 42

    def bench(
        project_path: Path,
        workers: int | str,
        iterations: int,
        cost_active: bool,
        run_mode: str,
    ) -> tuple[float, int, int, bool]:
        parser = YAMLParser()
        project = parser.parse_file(str(project_path))
        if cost_active:
            project.project.default_hourly_rate = 100.0

        config = Config.get_default()
        two_pass = run_mode == "two_pass" and len(project.resources) > 0
        if two_pass:
            config.constrained_scheduling.assignment_mode = (
                ConstrainedSchedulingAssignmentMode.CRITICALITY_TWO_PASS
            )

        resolved_workers = os.cpu_count() or 1 if workers == "auto" else int(workers)
        effective_workers = min(resolved_workers, iterations)
        chunk_count = len(partition_chunks(iterations, effective_workers))
        engine = SimulationEngine(
            iterations=iterations,
            random_seed=SEED,
            config=config,
            show_progress=False,
            workers=resolved_workers,
        )
        t0 = time.perf_counter()
        engine.run(project)
        return time.perf_counter() - t0, resolved_workers, chunk_count, two_pass

    for iteration_count in ITERATION_COUNTS:
        print()
        print(f"Iterations: {iteration_count}")
        print(
            f"{'fixture':<24} {'mode':<11} {'workers':>7} {'cost':>6} {'chunks':>7} {'elapsed_s':>10} {'speedup':>8}"
        )
        print("-" * 86)

        for fixture_label, fixture_path in FIXTURES.items():
            if not fixture_path.exists():
                print(f"  [SKIP] {fixture_label}: file not found at {fixture_path}")
                continue

            for run_mode in RUN_MODES:
                for cost_active in COST_MODES:
                    baseline: float | None = None
                    for w in WORKER_COUNTS:
                        elapsed, resolved_workers, chunk_count, two_pass_active = bench(
                            fixture_path,
                            w,
                            iteration_count,
                            cost_active=cost_active,
                            run_mode=run_mode,
                        )
                        if w == 1:
                            baseline = elapsed
                        speedup = baseline / elapsed if baseline else 1.0
                        mode_label = run_mode if two_pass_active else "single_pass"
                        print(
                            f"{fixture_label:<24} {mode_label:<11} {str(resolved_workers):>7} {'on' if cost_active else 'off':>6} {chunk_count:>7} {elapsed:>10.3f} {speedup:>8.2f}x"
                        )
                    print()
