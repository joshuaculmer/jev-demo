"""Interactive input and output shared by the jev_linter workflows."""

from pathlib import Path

from jev_linter.discovery import python_files
from jev_linter.findings import FilterResult
from jev_linter.report import format_text, to_json
from run_context import RunContext


def ask_for_files() -> list[Path]:
    """Ask for a file or directory and return the project's Python files under it."""

    while True:
        text = input("\nFile or directory to lint (blank for the whole project): ").strip() or "."
        path = Path(text)
        if not path.exists():
            print(f"{text} does not exist.")
            continue

        files = python_files(path)
        if files:
            return files
        print(f"No project Python files under {text}.")


def report_run(context: RunContext, results: list[FilterResult]) -> None:
    """Print the findings and save them as JSON next to the run's log."""

    print(f"\n{format_text(results)}")
    path = context.save("findings.json", to_json(results))
    print(f"\nFindings saved to {path}")
