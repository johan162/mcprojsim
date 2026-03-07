"""Monte Carlo Project Simulator - A probabilistic project estimation tool."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

from mcprojsim.models.project import Project, Task, Risk
from mcprojsim.simulation.engine import SimulationEngine


def _resolve_version() -> str:
    try:
        return version("mcprojsim")
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        try:
            with pyproject_path.open("rb") as pyproject_file:
                return tomllib.load(pyproject_file)["tool"]["poetry"]["version"]
        except FileNotFoundError, KeyError, tomllib.TOMLDecodeError:
            return "0.0.0+unknown"


__version__ = _resolve_version()
__all__ = ["Project", "Task", "Risk", "SimulationEngine"]
