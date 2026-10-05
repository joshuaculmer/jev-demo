"""Interactive input and output shared by the jev_linter workflows."""

import shutil
from pathlib import Path

from jev_linter.discovery import python_files
from jev_linter.findings import FilterResult
from jev_linter.report import format_text, summary_line, to_json
from run_context import RunContext


class ConsoleProgress:
    """Shows each filter's current step on one line that rewrites itself in place."""

    def __init__(self) -> None:
        self.source = ""
        self.total = 0
        self.done = 0
        self.line_length = 0

    def start(self, source: str, total: int) -> None:
        self.source, self.total, self.done = source, total, 0

    def note(self, text: str) -> None:
        self._print(f"{self.source}  {text}")

    def step(self, label: str) -> None:
        self.done += 1
        counter = f"[{self.done:>{len(str(self.total))}}/{self.total}]"
        self._rewrite(f"{self.source}  {counter}  {label}")

    def finish(self, result: FilterResult) -> None:
        self._print(summary_line(result))

    def _rewrite(self, text: str) -> None:
        # A line that wraps can't be rewritten, so it is cut to the terminal width.

        text = text[: shutil.get_terminal_size().columns - 1]
        print(f"\r{text:<{self.line_length}}", end="", flush=True)
        self.line_length = len(text)

    def _print(self, text: str) -> None:
        self._rewrite("")
        print(f"\r{text}")
        self.line_length = 0


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
