from pathlib import Path

from typesafe_sdk import Noul, Question

from jev_client import JevClient
from jev_linter.findings import FilterResult, Finding
from jev_linter.progress import SILENT_PROGRESS, Progress, UsageCounter
from jev_linter.questions import (
    THRESHOLD,
    read_span,
    span_lines,
    span_questions,
    unit_state,
)
from jev_linter.units import Unit, extract_units

FUNCTION_SMELLS = {
    "Poor naming": "the function, its parameters, or its variables have vague, misleading, or single-letter names",
    "Side effects in unexpected places": (
        "its name suggests a pure calculation or query, but it prints, writes files, or changes state"
    ),
    "Excessive comments": "its comments restate what the code plainly does instead of explaining why",
    "Magic numbers": "it uses literal numbers or strings whose meaning a reader can't tell without a named constant",
    "Primitive obsession": (
        "it passes raw strings, tuples, or dicts where a small class or type would make the meaning clear"
    ),
    "Law of Demeter": (
        "it calls behavior through a collaborator's collaborator, such as `order.customer.wallet.charge()`, "
        "instead of asking its direct collaborators. Reading data the function needs from a returned object "
        "is not a violation"
    ),
}

CLASS_SMELLS = {
    "God class": "the class holds many unrelated responsibilities",
}


class JevFilesFilter:
    """Asks Jev about code smells in each function, method, and class, one request per unit."""

    source = "jev_linter_files"

    def __init__(self, jev: JevClient, progress: Progress = SILENT_PROGRESS) -> None:
        self.jev = UsageCounter(jev)
        self.progress = progress

    def run(self, files: list[Path]) -> FilterResult:
        usage_before = self.jev.usage
        units = [unit for file in files for unit in extract_units(file)]
        self.progress.start(self.source, len(units))

        findings = [finding for unit in units for finding in self.check(unit)]
        result = FilterResult.from_findings(self.source, files, findings, usage=self.jev.usage - usage_before)
        self.progress.finish(result)
        return result

    def check(self, unit: Unit) -> list[Finding]:
        self.progress.step(f"{unit.file.name}  {unit.name}")
        smells = CLASS_SMELLS if unit.kind == "class" else FUNCTION_SMELLS
        response = self.jev.system_one(unit_state(unit), smell_questions(unit, smells))
        return [
            Finding(
                location=read_span(response, smell, unit),
                rule=smell,
                source=self.source,
                message=f"`{unit.name}`: {definition}",
                probability=response.answers[smell].noul,
            )
            for smell, definition in smells.items()
            if response.answers[smell].noul >= THRESHOLD
        ]


def smell_questions(unit: Unit, smells: dict[str, str]) -> dict[str, Question]:
    """One Noul per smell, plus speculative span questions for functions."""

    lines = span_lines(unit)
    questions: dict[str, Question] = {}
    for smell, definition in smells.items():
        meaning = f"the code smell '{smell}', meaning {definition}"
        questions[smell] = Noul(instructions=f"Does `code`, the {unit.kind} `unit`, have {meaning}?")
        questions |= span_questions(smell, f"Assume `code` has {meaning}.", "`code`", lines)
    return questions
