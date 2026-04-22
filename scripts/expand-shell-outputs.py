#!/usr/bin/env python3
"""Expand {{!cmd:head:tail}} shell-command placeholders in markdown files.

Each placeholder is replaced with the command's stdout wrapped in triple-backtick
blocks. Files are processed in parallel. Any command failure causes an immediate
exit with a non-zero status.

Placeholder syntax
------------------
  {{!cmd}}          Full output in one ```...``` block.
  {{!cmd:N}}        First N lines of output in one ```...``` block.
  {{!cmd:N:M}}      First N lines in one ```...``` block, blank line, then
                    last M lines in a second ```...``` block.

Usage
-----
  expand-shell-outputs.py --output-dir DIR [--cwd DIR] FILE [FILE ...]

The basename of each FILE is preserved; expanded copies are written under
--output-dir.  The script exits 1 if any file or command fails.
"""

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Match {{!cmd}}, {{!cmd:N}}, or {{!cmd:N:M}}.
# Uses non-greedy .*? so it does not cross line boundaries (. does not match \n
# without re.DOTALL) and does not consume more than one placeholder per match.
_PLACEHOLDER = re.compile(r"\{\{!(.*?)(?::(\d+)(?::(\d+))?)?\}\}")


def _run_command(cmd: str, cwd: Path) -> list[str]:
    """Run *cmd* in a shell and return its stdout lines.

    Raises RuntimeError if the command exits with a non-zero status.
    """
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command exited with status {result.returncode}: {cmd!r}\n"
            f"stderr:\n{result.stderr.strip()}"
        )
    return result.stdout.splitlines()


def _fence(lines: list[str]) -> str:
    """Wrap *lines* in a fenced code block."""
    return "```\n" + "\n".join(lines) + "\n```"


def _expand_match(match: re.Match, cwd: Path) -> str:
    """Return the replacement text for a single placeholder match."""
    cmd = match.group(1).strip()
    head_str = match.group(2)
    tail_str = match.group(3)

    lines = _run_command(cmd, cwd)

    if head_str is None:
        return _fence(lines)

    head = int(head_str)
    if tail_str is None:
        return _fence(lines[:head])

    tail = int(tail_str)
    tail_lines = lines[-tail:] if tail > 0 else []
    return _fence(lines[:head]) + "\n\n" + _fence(tail_lines)


def _process_file(src: Path, out_dir: Path, cwd: Path) -> None:
    """Expand all placeholders in *src* and write the result to *out_dir/src.name*."""
    text = src.read_text(encoding="utf-8")
    expanded = _PLACEHOLDER.sub(lambda m: _expand_match(m, cwd), text)
    (out_dir / src.name).write_text(expanded, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Expand {{!cmd:head:tail}} placeholders in markdown files."
    )
    ap.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        metavar="DIR",
        help="Directory to write expanded copies into.",
    )
    ap.add_argument(
        "--cwd",
        default=".",
        type=Path,
        metavar="DIR",
        help="Working directory for shell commands (default: current directory).",
    )
    ap.add_argument("files", nargs="+", type=Path, help="Markdown files to process.")
    args = ap.parse_args()

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cwd: Path = args.cwd.resolve()

    failed = False
    with ThreadPoolExecutor() as pool:
        futures = {
            pool.submit(_process_file, Path(f), out_dir, cwd): f
            for f in args.files
        }
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                print(f"ERROR processing {futures[fut]}: {exc}", file=sys.stderr)
                failed = True

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
