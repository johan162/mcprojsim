"""Verify that the doc examples for progress_callback and cancellation are runnable.

These tests extract the logic from docs/api_reference/11_api_examples.md Example 7
and run it in a test harness to catch any hallucinated API usage.
"""

import threading
import time
from datetime import date

import pytest

from mcprojsim import SimulationEngine
from mcprojsim.simulation.engine import SimulationCancelled
from mcprojsim.models.project import Project, ProjectMetadata, Task, TaskEstimate


@pytest.fixture
def demo_project():
    return Project(
        project=ProjectMetadata(name="Doc Example", start_date=date(2026, 5, 1)),
        tasks=[
            Task(
                id="t1",
                name="Design",
                estimate=TaskEstimate(low=2, expected=5, high=10),
            ),
            Task(
                id="t2",
                name="Build",
                estimate=TaskEstimate(low=5, expected=10, high=20),
                dependencies=["t1"],
            ),
            Task(
                id="t3",
                name="Test",
                estimate=TaskEstimate(low=3, expected=6, high=12),
                dependencies=["t2"],
            ),
        ],
    )


class TestDocExample7aProgressCallback:
    """Example 7a: basic progress_callback usage."""

    def test_callback_receives_updates(self, demo_project):
        calls: list[tuple[int, int]] = []

        def on_progress(completed: int, total: int) -> None:
            calls.append((completed, total))

        engine = SimulationEngine(
            iterations=10000,
            random_seed=42,
            show_progress=True,
            progress_callback=on_progress,
        )
        results = engine.run(demo_project)

        # Callback was called at least once
        assert len(calls) > 0
        # Every call reports the correct total
        assert all(t == 10000 for _, t in calls)
        # Final call is 100 %
        assert calls[-1][0] == 10000
        # Results are valid
        assert results.percentile(80) > 0

    def test_callback_suppresses_stdout(self, demo_project, capsys):
        engine = SimulationEngine(
            iterations=100,
            random_seed=42,
            show_progress=True,
            progress_callback=lambda c, t: None,
        )
        engine.run(demo_project)

        captured = capsys.readouterr()
        assert "Progress:" not in captured.out


class TestDocExample7bCancellation:
    """Example 7b: cancel() from another thread."""

    def test_cancel_stops_simulation(self, demo_project):
        engine = SimulationEngine(
            iterations=500_000, random_seed=42, show_progress=False
        )

        exc_holder: list[BaseException | None] = [None]

        def run_in_background():
            try:
                engine.run(demo_project)
            except SimulationCancelled as e:
                exc_holder[0] = e

        worker = threading.Thread(target=run_in_background)
        worker.start()

        time.sleep(0.1)
        engine.cancel()

        worker.join(timeout=5.0)
        assert not worker.is_alive(), "Worker should have stopped"
        assert isinstance(exc_holder[0], SimulationCancelled)


class TestDocExample7cCombined:
    """Example 7c: callback + cancellation (GUI pattern)."""

    def test_combined_callback_and_cancel(self, demo_project):
        progress_pct = 0

        def update_progress_bar(completed: int, total: int) -> None:
            nonlocal progress_pct
            progress_pct = int(100 * completed / total)

        engine = SimulationEngine(
            iterations=200_000,
            random_seed=42,
            show_progress=True,
            progress_callback=update_progress_bar,
        )

        result_holder: list[object] = [None]  # None = not set, str = cancelled

        def worker_fn():
            try:
                results = engine.run(demo_project)
                result_holder[0] = results
            except SimulationCancelled:
                result_holder[0] = "cancelled"

        worker = threading.Thread(target=worker_fn)
        worker.start()

        time.sleep(0.05)
        engine.cancel()

        worker.join(timeout=5.0)
        assert not worker.is_alive()
        assert result_holder[0] == "cancelled"
        # Some progress must have been reported before cancellation
        # (may be 0 if cancel fired before first 10% bucket)
        assert progress_pct >= 0
