#!/usr/bin/env python3
"""Expand {{!cmd:head:tail}} shell-command placeholders in markdown files.

Each placeholder is replaced with the command's stdout wrapped in triple-backtick
blocks. Files are processed in parallel. Any command failure causes an immediate
exit with a non-zero status.

Placeholder syntax
------------------
  {{!cmd}}                Full output in one ```...``` block.
  {{!cmd:N}}              First N lines of output in one ```...``` block.
  {{!cmd:N:M}}            First N lines in one ```...``` block, blank line, then
                          last M lines in a second ```...``` block.
  {{!cmd@A4:25:25,B5:20:20}}  Format-specific truncation. When --format a4 is
                              passed, use A4 spec (25:25); when --format b5,
                              use B5 spec (20:20). If format not present in
                              specs, use full output for that format.
  {{!cmd@B5:20:20}}       Only B5 format has a spec; other formats use full output.

Usage
-----
  expand-shell-outputs.py --output-dir DIR [--cwd DIR] [--format FORMAT] FILE [FILE ...]

The basename of each FILE is preserved; expanded copies are written under
--output-dir. The script exits 1 if any file or command fails.
"""

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Match {{!...content...}} where content may include @ for format specs.
# Uses non-greedy .*? so it does not cross line boundaries and does not
# consume more than one placeholder per match.
_PLACEHOLDER = re.compile(r"\{\{!(.*?)\}\}")


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


def _parse_format_specs(
    spec_str: str,
) -> dict[str, tuple[int | None, int | None]]:
    """Parse format specification string like 'A4:25:25,B5:20:20'.

    Returns dict like {'a4': (25, 25), 'b5': (20, 20), ...}
    where tuples are (head, tail). Either head or tail can be None.
    """
    specs: dict[str, tuple[int | None, int | None]] = {}
    for part in spec_str.split(","):
        part = part.strip()
        if not part:
            continue
        pieces = part.split(":")
        if len(pieces) < 1:
            continue
        fmt = pieces[0].strip().lower()
        head = int(pieces[1]) if len(pieces) > 1 and pieces[1].strip() else None
        tail = int(pieces[2]) if len(pieces) > 2 and pieces[2].strip() else None
        specs[fmt] = (head, tail)
    return specs


def _expand_match(
    match: re.Match, cwd: Path, target_format: str | None = None  # type: ignore
) -> str:
    """Return the replacement text for a single placeholder match.

    Args:
        match: The regex match object
        cwd: Working directory for commands
        target_format: The target format (e.g. 'a4', 'b5'), or None for full output
    """
    content = match.group(1).strip()

    # Split on @ to separate command+inline_specs from format_specs
    if "@" in content:
        cmd_part, format_specs_str = content.split("@", 1)
    else:
        cmd_part = content
        format_specs_str = None

    # Parse inline head:tail from cmd_part (backward compatibility).
    # Look for :N or :N:M at the very end where N, M are digits.
    inline_match = re.search(r":(\d+)(?::(\d+))?$", cmd_part)
    inline_head: int | None = None
    inline_tail: int | None = None
    if inline_match:
        inline_head = int(inline_match.group(1))
        inline_tail = (
            int(inline_match.group(2)) if inline_match.group(2) else None
        )
        cmd = cmd_part[: inline_match.start()].strip()
    else:
        cmd = cmd_part.strip()

    # Parse format-specific specs if present
    format_specs: dict[str, tuple[int | None, int | None]] = {}
    if format_specs_str:
        format_specs = _parse_format_specs(format_specs_str)

    # Determine which head/tail to use based on target_format
    head: int | None = None
    tail: int | None = None
    if target_format and target_format.lower() in format_specs:
        head, tail = format_specs[target_format.lower()]
    else:
        # Use inline specs if available (backward compat), else full output
        head = inline_head
        tail = inline_tail

    lines = _run_command(cmd, cwd)

    if head is None:
        return _fence(lines)

    if tail is None:
        return _fence(lines[:head])

    tail_lines = lines[-tail:] if tail > 0 else []
    return _fence(lines[:head]) + "\n\n" + _fence(tail_lines)


def _process_file(src: Path, out_dir: Path, cwd: Path, target_format: str | None) -> None:
    """Expand all placeholders in *src* and write the result to *out_dir/src.name*."""
    text = src.read_text(encoding="utf-8")
    expanded = _PLACEHOLDER.sub(
        lambda m: _expand_match(m, cwd, target_format), text
    )
    (out_dir / src.name).write_text(expanded, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Expand {{!cmd:head:tail}} and format-aware placeholders in markdown files."
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
    ap.add_argument(
        "--format",
        default=None,
        metavar="FORMAT",
        help="Target format (e.g. 'a4', 'b5'). When specified, format-specific "
        "truncation rules are applied if present in placeholders (e.g. @A4:25:25). "
        "If the format is not specified in a placeholder, full output is used.",
    )
    ap.add_argument("files", nargs="+", type=Path, help="Markdown files to process.")
    args = ap.parse_args()

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cwd: Path = args.cwd.resolve()

    failed = False
    with ThreadPoolExecutor() as pool:
        futures = {
            pool.submit(_process_file, Path(f), out_dir, cwd, args.format): f
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
    