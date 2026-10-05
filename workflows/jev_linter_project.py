"""Ask Jev about design smells across files. Expects files that already pass jev_linter_files."""

from pathlib import Path

from jev_linter.console import ConsoleProgress, ask_for_files, report_run
from jev_linter.discovery import python_files
from jev_linter.findings import FilterResult
from jev_linter.project_filter import JevProjectFilter
from run_context import RunContext


def repeatable_request(context: RunContext, input_path: Path) -> FilterResult:
    return JevProjectFilter(context.jev).run(python_files(input_path))


def start_workflow(context: RunContext) -> None:
    files = ask_for_files()
    report_run(context, [JevProjectFilter(context.jev, ConsoleProgress()).run(files)])
