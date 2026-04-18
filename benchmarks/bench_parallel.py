"""Benchmark: parallel simulation speedup across worker counts and project sizes.

Run with:
    poetry run python benchmarks/bench_parallel.py

Results are printed to stdout and can be captured for documentation.
Do NOT import this file from tests; it spawns worker processes when executed.
"""

from __future__ import annotations

if __name__ == "__main__":
    import time
    from pathlib import Path

    from mcprojsim.parsers.yaml_parser import YAMLParser
    from mcprojsim.simulation.engine import SimulationEngine

    REPO_ROOT = Path(__file__).parent.parent
    FIXTURES = {
        "abundant_resources": REPO_ROOT
        / "tests/fixtures/test_fixture_abundant_resources.yaml",
        "contention": REPO_ROOT / "tests/fixtures/test_fixture_contention.yaml",
        "large_100_tasks": REPO_ROOT / "examples/large_project_100_tasks.yaml",
    }
    WORKER_COUNTS = [1, 2, 4, 8]
    ITERATION_COUNTS = [20_000, 50_000, 80_000, 200_000]
    SEED = 42

    def bench(
        project_path: Path,
        workers: int,
        iterations: int,
        cost_active: bool,
    ) -> float:
        parser = YAMLParser()
        project = parser.parse_file(str(project_path))
        engine = SimulationEngine(
            iterations=iterations,
            random_seed=SEED,
            show_progress=False,
            workers=workers,
        )
        t0 = time.perf_counter()
        engine.run(project)
        return time.perf_counter() - t0

    for iteration_count in ITERATION_COUNTS:
        print()
        print(f"Iterations: {iteration_count}")
        print(
            f"{'fixture':<24} {'workers':>7} {'cost':>6} {'elapsed_s':>10} {'speedup':>8}"
        )
        print("-" * 60)

        for fixture_label, fixture_path in FIXTURES.items():
            if not fixture_path.exists():
                print(f"  [SKIP] {fixture_label}: file not found at {fixture_path}")
                continue

            baseline: float | None = None
            for w in WORKER_COUNTS:
                elapsed = bench(
                    fixture_path,
                    w,
                    iteration_count,
                    cost_active=False,
                )
                if w == 1:
                    baseline = elapsed
                speedup = baseline / elapsed if baseline else 1.0
                print(
                    f"{fixture_label:<24} {w:>7} {'off':>6} {elapsed:>10.3f} {speedup:>8.2f}x"
                )
            print()
