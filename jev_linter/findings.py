from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Location:
    file: Path
    start_line: int
    end_line: int


@dataclass(frozen=True)
class Finding:
    """One problem a filter found. Pair findings name the other side in related."""

    location: Location
    rule: str
    source: str
    message: str
    probability: float | None = None
    related: tuple[Location, ...] = ()

    @property
    def files(self) -> set[Path]:
        return {self.location.file, *(location.file for location in self.related)}


@dataclass(frozen=True)
class Usage:
    """Jev requests and tokens spent by one filter run."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.requests + other.requests,
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )

    def __sub__(self, other: Usage) -> Usage:
        return Usage(
            self.requests - other.requests,
            self.input_tokens - other.input_tokens,
            self.output_tokens - other.output_tokens,
        )


NO_USAGE = Usage()


@dataclass(frozen=True)
class FilterResult:
    source: str
    checked: list[Path]
    passed: list[Path]
    findings: list[Finding]
    notes: tuple[str, ...] = ()
    usage: Usage = NO_USAGE

    @classmethod
    def from_findings(
        cls,
        source: str,
        checked: list[Path],
        findings: list[Finding],
        notes: tuple[str, ...] = (),
        usage: Usage = NO_USAGE,
    ) -> FilterResult:
        """A checked file passes when no finding touches it."""

        failed = {file.resolve() for finding in findings for file in finding.files}
        passed = [file for file in checked if file.resolve() not in failed]
        return cls(source, checked, passed, findings, notes, usage)


class Filter(Protocol):
    source: str

    def run(self, files: list[Path]) -> FilterResult: ...
