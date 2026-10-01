"""Run ruff_filter, jev_linter_files, and jev_linter_project in order on the chosen files."""

from jev_linter.console import ask_for_files, report_run
from jev_linter.files_filter import JevFilesFilter
from jev_linter.pipeline import run_pipeline
from jev_linter.project_filter import JevProjectFilter
from jev_linter.ruff_filter import RuffFilter
from run_context import RunContext


def start_workflow(context: RunContext) -> None:
    files = ask_for_files()
    filters = [RuffFilter(), JevFilesFilter(context.jev), JevProjectFilter(context.jev)]
    report_run(context, run_pipeline(filters, files))
