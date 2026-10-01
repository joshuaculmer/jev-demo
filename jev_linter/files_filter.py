from pathlib import Path

from typesafe_sdk import Choice, Noul, Question, SystemOneResponse

from jev_client import JevClient
from jev_linter.findings import FilterResult, Finding, Location
from jev_linter.units import Unit, extract_units

THRESHOLD = 0.5

# Choice accepts at most 255 options, so longer units are reported whole.

MAX_SPAN_OPTIONS = 255

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

    def __init__(self, jev: JevClient) -> None:
        self.jev = jev

    def run(self, files: list[Path]) -> FilterResult:
        findings = [finding for file in files for unit in extract_units(file) for finding in self.check(unit)]
        return FilterResult.from_findings(self.source, files, findings)

    def check(self, unit: Unit) -> list[Finding]:
        smells = CLASS_SMELLS if unit.kind == "class" else FUNCTION_SMELLS
        lines = unit.numbered_lines()
        ask_span = unit.kind == "function" and len(lines) <= MAX_SPAN_OPTIONS

        response = self.jev.system_one(
            {"filename": unit.file.name, "unit": unit.name, "code": unit.source},
            smell_questions(unit, smells, lines if ask_span else None),
        )
        return [
            Finding(
                location=span(response, smell, unit) if ask_span else unit.location,
                rule=smell,
                source=self.source,
                message=f"`{unit.name}`: {definition}",
                probability=response.answers[smell].noul,
            )
            for smell, definition in smells.items()
            if response.answers[smell].noul >= THRESHOLD
        ]


def smell_questions(unit: Unit, smells: dict[str, str], lines: dict[str, str] | None) -> dict[str, Question]:
    """One Noul per smell, plus speculative start and end lines when lines are given."""

    questions: dict[str, Question] = {}
    for smell, definition in smells.items():
        meaning = f"the code smell '{smell}', meaning {definition}"
        questions[smell] = Noul(instructions=f"Does `code`, the {unit.kind} `unit`, have {meaning}?")
        if lines:
            assumption = f"Assume `code` has {meaning}."
            questions[f"{smell}: start"] = Choice(
                instructions=f"{assumption} On which line does the clearest instance start?",
                criteria=lines,
            )
            questions[f"{smell}: end"] = Choice(
                instructions=f"{assumption} On which line does that same instance end?",
                criteria=lines,
            )
    return questions


def span(response: SystemOneResponse, smell: str, unit: Unit) -> Location:
    """The span Jev chose, or the whole unit when the span is inverted."""

    start = int(response.answers[f"{smell}: start"].choice)
    end = int(response.answers[f"{smell}: end"].choice)
    return Location(unit.file, start, end) if start <= end else unit.location
