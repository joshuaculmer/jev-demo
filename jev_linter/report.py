import json
from pathlib import Path

from jev_linter.findings import FilterResult, Finding, Location


def display_path(path: Path) -> str:
    """Path relative to the working directory when possible, with forward slashes."""

    try:
        return path.resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def format_text(results: list[FilterResult]) -> str:
    sections = [_format_result(result) for result in results]
    return "\n\n".join(sections)


def to_json(results: list[FilterResult]) -> str:
    return json.dumps({"filters": [_result_dict(result) for result in results]}, indent=2)


def _format_result(result: FilterResult) -> str:
    lines = [f"{result.source}: {len(result.passed)} of {len(result.checked)} files passed"]
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
