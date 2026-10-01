"""Ask Jev about code smells in each function and class. Expects files that already pass ruff_filter."""

from pathlib import Path

from jev_linter.console import ask_for_files, report_run
from jev_linter.files_filter import JevFilesFilter
from jev_linter.findings import FilterResult
from run_context import RunContext


def repeatable_request(context: RunContext, input_path: Path) -> FilterResult:
    return JevFilesFilter(context.jev).run([input_path])


def start_workflow(context: RunContext) -> None:
    files = ask_for_files()
    report_run(context, [JevFilesFilter(context.jev).run(files)])
