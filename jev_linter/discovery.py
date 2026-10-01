from pathlib import Path

from jev_linter.ruff_filter import run_ruff


def python_files(path: Path) -> list[Path]:
    """The Python files under path that ruff's exclude settings count as part of the project."""

    output = run_ruff("check", "--show-files", "--force-exclude", str(path))
    return sorted(Path(line).resolve() for line in output.splitlines() if line.endswith(".py"))
