import json
from pathlib import Path

from jev_linter.findings import NO_USAGE, FilterResult, Finding, Location, Usage

# TypeSafe's published rate for Jev input. Output tokens are free, and the docs say pricing can change.

DOLLARS_PER_INPUT_TOKEN = 42 / 1_000_000_000


def display_path(path: Path) -> str:
    """Path relative to the working directory when possible, with forward slashes."""

    try:
        return path.resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def summary_line(result: FilterResult) -> str:
    return f"{result.source}: {len(result.passed)} of {len(result.checked)} files passed"


def estimated_cost(usage: Usage) -> float:
    return usage.input_tokens * DOLLARS_PER_INPUT_TOKEN


def format_text(results: list[FilterResult]) -> str:
    sections = [_format_result(result) for result in results]
    return "\n\n".join([*sections, _format_cost(results)])


def to_json(results: list[FilterResult]) -> str:
    """The last filter's passed files are the ones that cleared every filter."""

    report = {
        "passed_all": [display_path(file) for file in results[-1].passed] if results else [],
        "total_usage": _usage_dict(_total_usage(results)),
        "filters": [_result_dict(result) for result in results],
    }
    return json.dumps(report, indent=2)


def _total_usage(results: list[FilterResult]) -> Usage:
    return sum((result.usage for result in results), NO_USAGE)


def _format_cost(results: list[FilterResult]) -> str:
    rows = [(result.source, result.usage) for result in results]
    rows.append(("total", _total_usage(results)))
    width = max(len(name) for name, _ in rows)

    lines = [
        "Cost (estimated from input tokens)",
        f"  {'filter':<{width}}  {'requests':>8}  {'input tokens':>12}  {'output tokens':>13}  {'est. cost':>9}",
    ]
    lines.extend(
        f"  {name:<{width}}  {usage.requests:>8,}  {usage.input_tokens:>12,}  {usage.output_tokens:>13,}"
        f"  {f'${estimated_cost(usage):.4f}':>9}"
        for name, usage in rows
    )
    return "\n".join(lines)


def _format_result(result: FilterResult) -> str:
    lines = [summary_line(result)]
    lines.extend(f"  ({note})" for note in result.notes)
    for finding in sorted(result.findings, key=_sort_key):
        lines.append(f"  {_format_location(finding.location)}  {finding.rule}{_format_probability(finding)}")
        lines.append(f"      {finding.message}")
        lines.extend(f"      related: {_format_location(location)}" for location in finding.related)
    return "\n".join(lines)


def _sort_key(finding: Finding) -> tuple[str, int]:
    return display_path(finding.location.file), finding.location.start_line


def _format_location(location: Location) -> str:
    lines = f"{location.start_line}"
    if location.end_line != location.start_line:
        lines += f"-{location.end_line}"
    return f"{display_path(location.file)}:{lines}"


def _format_probability(finding: Finding) -> str:
    return "" if finding.probability is None else f"  (p={finding.probability:.2f})"


def _result_dict(result: FilterResult) -> dict:
    return {
        "source": result.source,
        "checked": [display_path(file) for file in result.checked],
        "passed": [display_path(file) for file in result.passed],
        "notes": list(result.notes),
        "usage": _usage_dict(result.usage),
        "findings": [_finding_dict(finding) for finding in sorted(result.findings, key=_sort_key)],
    }


def _finding_dict(finding: Finding) -> dict:
    return {
        **_location_dict(finding.location),
        "rule": finding.rule,
        "source": finding.source,
        "message": finding.message,
        "probability": finding.probability,
        "related": [_location_dict(location) for location in finding.related],
    }


def _location_dict(location: Location) -> dict:
    return {"file": display_path(location.file), "start_line": location.start_line, "end_line": location.end_line}


def _usage_dict(usage: Usage) -> dict:
    return {
        "requests": usage.requests,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "estimated_cost_usd": round(estimated_cost(usage), 6),
    }
