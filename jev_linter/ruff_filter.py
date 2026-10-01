import json
import subprocess
import sys
from pathlib import Path

from jev_linter.findings import FilterResult, Finding, Location

# Ruff exits with 1 when it finds violations and higher when it fails to run.

RUFF_FOUND_VIOLATIONS = 1


def run_ruff(*args: str) -> str:
    """Run the venv's ruff, which reads its rules from pyproject.toml, and return stdout."""

    # Arguments go to ruff as a list with no shell, so paths can't inject commands.

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode > RUFF_FOUND_VIOLATIONS:
        message = f"ruff exited with {result.returncode}: {result.stderr.strip()}"
        raise RuntimeError(message)
    return result.stdout


class RuffFilter:
    source = "ruff_filter"

    def run(self, files: list[Path]) -> FilterResult:
        if not files:
            return FilterResult.from_findings(self.source, files, [])

        output = run_ruff("check", "--output-format", "json", "--force-exclude", *map(str, files))
        findings = [self._to_finding(violation) for violation in json.loads(output)]
        return FilterResult.from_findings(self.source, files, findings)

    def _to_finding(self, violation: dict) -> Finding:
        return Finding(
            location=Location(
                Path(violation["filename"]).resolve(),
                violation["location"]["row"],
                violation["end_location"]["row"],
            ),
            rule=violation["code"] or "syntax-error",
            source=self.source,
            message=violation["message"],
        )
