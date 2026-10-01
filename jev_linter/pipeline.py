from pathlib import Path

from jev_linter.findings import Filter, FilterResult


def run_pipeline(filters: list[Filter], files: list[Path]) -> list[FilterResult]:
    """Run filters in order. Each filter sees only the files the one before it passed."""

    results = []
    for each_filter in filters:
        result = each_filter.run(files)
        results.append(result)
        files = result.passed
    return results
