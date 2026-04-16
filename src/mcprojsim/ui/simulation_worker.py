"""Simulation worker thread (P1-13)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal  # type: ignore[import-untyped]

from mcprojsim.config import Config
from mcprojsim.parsers.yaml_parser import YAMLParser
from mcprojsim.simulation.engine import SimulationCancelled, SimulationEngine


class SimulationWorker(QThread):
    """Runs the simulation in a background thread.

    Signals
    -------
    progress(completed, total)
        Emitted during the run at each engine callback.
    finished(results_dict)
        Emitted with a serialisable summary dict on success.
    error(message)
        Emitted with an error message string on failure.
    """

    progress = Signal(int, int)
    finished = Signal(object)  # passes SimulationResults
    error = Signal(str)

    def __init__(
        self,
        project_data: dict[str, Any],
        run_config: dict[str, Any],
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._project_data = project_data
        self._run_config = run_config
        self._engine: SimulationEngine | None = None

    def cancel(self) -> None:
        if self._engine is not None:
            self._engine.cancel()

    def run(self) -> None:  # runs in worker thread
        try:
            parser = YAMLParser()
            project = parser.parse_dict(self._project_data)
            config = Config.get_default()

            iterations = int(self._run_config.get("iterations", 10_000))
            seed = self._run_config.get("random_seed")
            random_seed = int(seed) if seed is not None else None

            self._engine = SimulationEngine(
                config=config,
                iterations=iterations,
                random_seed=random_seed,
                progress_callback=lambda done, total: self.progress.emit(done, total),
            )
            results = self._engine.run(project)
            self.finished.emit(results)
        except SimulationCancelled:
            # Not an error — user requested cancel
            pass
        except Exception as exc:
            self.error.emit(str(exc))
