# Lark POC: Grammar-Driven Parser/Validator

This proof of concept demonstrates a path to replace hand-wired shape validation with a grammar-driven parser using Lark.

## Goal

Use one formal grammar as the structural source of truth for both:

1. project files (`YAML` / `TOML`)
2. config files (`YAML`)

without manually writing a parser for the grammar itself.

## Current POC Architecture

1. Load source file (`YAML`/`TOML`) to a Python mapping.
2. Normalize into a canonical text form with deterministic field ordering.
3. Parse canonical text with Lark using [mcprojsim_schema.lark](mcprojsim_schema.lark).

This gives grammar-level structure validation while keeping source-format concerns (YAML/TOML syntax) separate.

## Files

- [mcprojsim_schema.lark](mcprojsim_schema.lark): Lark grammar for project + config schema.
- [lark_poc.py](lark_poc.py): CLI that loads payloads, canonicalizes, and parses with Lark.

## Run

Install dependency (POC-local):

```bash
poetry run pip install lark
```

Validate a project file:

```bash
poetry run python design-ideas/POCs/lark/lark_poc.py examples/quickstart_project.yaml --mode project
```

Validate in auto mode (project/config inferred):

```bash
poetry run python design-ideas/POCs/lark/lark_poc.py examples/sample_config.yaml --mode auto
```

Inspect canonical representation:

```bash
poetry run python design-ideas/POCs/lark/lark_poc.py examples/sample_project.yaml --show-canonical
```

## Why this is a viable replacement direction

- Grammar-first structural validation moves allowable shape into one declarative artifact.
- Reduces drift between docs grammar and parser behavior.
- Enables parser error handling to move toward grammar-originated diagnostics.

## Migration path toward production replacement

1. Make canonical representation a stable internal IR contract.
2. Replace raw unknown-field checks with grammar parse + targeted semantic checks.
3. Keep Pydantic for semantic/value validation initially.
4. Incrementally move semantic constraints into dedicated post-parse validator passes.
5. Add golden test corpus comparing current parser vs Lark parser acceptance/rejection.

## Known POC limitations

- This POC parses a canonical IR, not YAML/TOML directly.
- Some map-shaped sections are intentionally generic in grammar to keep iteration speed high.
- Semantic constraints (e.g. cross-reference integrity, threshold relationships) are not fully encoded in grammar and still require validator passes.

## Intended next steps

- Tighten grammar for currently generic map sections.
- Add structured parse-tree to domain object transformation.
- Add test matrix against `examples/` and selected invalid fixtures.
