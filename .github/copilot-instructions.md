# Copilot instructions for `mcprojsim`

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.


## Build, test, and lint commands

The canonical workflow is Poetry-first. Use `Makefile` targets as convenience wrappers, but when exact behavior matters, prefer the Poetry/CI commands below.

```bash
# install the local dev environment
poetry config virtualenvs.in-project true
poetry install --with dev,docs

# include MCP dependencies when touching mcp_server.py or MCP tests
poetry install --with dev,docs,mcp

# full test suite (matches CI closely)
poetry run pytest tests/ -n auto --cov=src/mcprojsim --cov-report=term-missing --cov-report=html --cov-report=xml --cov-fail-under=80

# run a single test or test class
poetry run pytest tests/test_simulation.py::TestDistributionSampler::test_sample_triangular --no-cov
poetry run pytest tests/test_cli.py::TestCli --no-cov -v

# keyword-filtered test run
poetry run pytest tests/ -k "critical_path" --no-cov

# formatting, linting, and type-checking
poetry run black --check src tests
poetry run flake8 src tests
poetry run mypy src tests

# docs
poetry run mkdocs build
poetry run mkdocs serve

# packaging
poetry build
poetry run twine check dist/*

# higher-level wrapper used by the repo
./scripts/mkbld.sh
```

Useful wrappers that exist in this repo:

```bash
make install
make check
make test
make test-short
make docs
make docs-serve
make build
```

## High-level architecture

`src/mcprojsim/cli.py` is the main entrypoint. The top-level Click commands are `simulate`, `validate`, `config show`, and `generate`.

The core flow is:

`CLI / MCP` -> `parser` -> `Pydantic models` -> `SimulationEngine` -> `analysis` -> `exporters`

Important boundaries:

- `config.py` is the single source of truth for default uncertainty multipliers, symbolic estimate mappings, output settings, and staffing profiles. YAML config overrides are merged onto defaults instead of replacing the whole structure.
- `parsers/yaml_parser.py` and `parsers/toml_parser.py` handle structured project files. They rely on `parsers/error_reporting.py` so validation errors keep file/line context.
- `nl_parser.py` is separate from the YAML/TOML parsers. It turns semi-structured plain text into project data and is reused by both the CLI `generate` command and the MCP server.
- `models/project.py` defines the project/task/risk/resource/calendar schema with Pydantic v2 validators. This layer enforces dependency integrity, symbolic estimate rules, threshold validation, and resource/calendar constraints.
- `simulation/engine.py` runs the Monte Carlo loop. It samples task durations, applies risks, delegates scheduling to `TaskScheduler`, stores per-iteration arrays, and aggregates full critical-path sequences.
- `simulation/scheduler.py` has two modes: dependency-only scheduling and resource/calendar-constrained scheduling. If a change touches scheduling semantics, assume both modes matter.
- `models/simulation.py` stores results as numpy-backed arrays and distinguishes elapsed project duration from total effort (`effort_durations`). It also stores constrained-scheduling diagnostics like resource wait time and utilization.
- `analysis/` adds post-processing such as statistics, critical-path analysis, sensitivity correlations, and staffing recommendations.
- `exporters/` turns `SimulationResults` into JSON, CSV, and HTML output. HTML export depends on both results and config.
- `mcp_server.py` exposes MCP tools for generating YAML, validating descriptions, and simulating directly from natural-language input. The MCP dependency is optional.

## Key conventions

- Use strict typing in `src/`. The repo is configured for Python 3.13, strict `mypy`, and Pydantic v2 validators. Tests are still type-checked, but with looser rules than source files.
- Reuse `Config` defaults instead of hardcoding T-shirt sizes, story-point mappings, thresholds, output limits, or staffing constants in new code.
- Symbolic estimates are config-driven. If a task uses `t_shirt_size` or `story_points`, do not add `unit` in the project file; the unit comes from config and is enforced by model validation.
- Explicit estimates are normalized to canonical hours during simulation. Be careful to preserve the distinction between elapsed duration and total effort when changing results, analysis, or exporters.
- Keep parser/model responsibilities separate: parsers should produce good, location-aware validation errors; schema rules belong in the Pydantic models.
- Preserve reproducibility. Randomness flows through `SimulationEngine(random_seed=...)` and its `numpy.random.RandomState`.
- Critical-path data exists in two forms: per-task criticality frequency and full ordered path sequences. Do not collapse one into the other when editing analysis or exports.
- CLI tests use `click.testing.CliRunner`; MCP tests call tool functions directly and use `pytest.importorskip("mcp")` because MCP support is optional.
- If you touch scheduling, resource assignment, calendars, or staffing, read both `tests/test_simulation.py` and `tests/test_staffing.py`; they cover behavior that is easy to regress.
- Version resolution in `src/mcprojsim/__init__.py` falls back to `pyproject.toml` when the package is not installed, so source-checkout behavior should keep working.
- For docs work, `docs.yml` creates a `docs/CHANGELOG.md` symlink before building. If a docs build fails around the changelog page, use the repo script or replicate that symlink step.
