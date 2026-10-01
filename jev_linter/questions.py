"""Question pieces shared by the Jev filters."""

from dataclasses import asdict

from typesafe_sdk import Choice, SystemOneResponse

from jev_linter.findings import Location
from jev_linter.units import Unit, contract_of

THRESHOLD = 0.5

# Choice accepts at most 255 options, so longer units are reported whole.

MAX_SPAN_OPTIONS = 255


def unit_state(unit: Unit, *, with_contract: bool = False) -> dict:
    state = {"filename": unit.file.name, "unit": unit.name, "code": unit.source}
    if unit.constants:
        state["module_constants"] = dict(unit.constants)
    if with_contract:
        state["contract"] = asdict(contract_of(unit))
    return state


def span_lines(unit: Unit) -> dict[str, str] | None:
    """Line options for a function short enough to ask about. Classes are always reported whole."""

    lines = unit.numbered_lines()
    return lines if unit.kind == "function" and len(lines) <= MAX_SPAN_OPTIONS else None


def span_questions(question_id: str, assumption: str, code_path: str, lines: dict[str, str] | None) -> dict:
    """Speculative start and end lines of the clearest instance, read later by read_span."""

    if lines is None:
        return {}
    return {
        f"{question_id}: start": Choice(
            instructions=f"{assumption} On which line of {code_path} does the clearest instance start?",
            criteria=lines,
        ),
        f"{question_id}: end": Choice(
            instructions=f"{assumption} On which line of {code_path} does that same instance end?",
            criteria=lines,
        ),
    }


def read_span(response: SystemOneResponse, question_id: str, unit: Unit) -> Location:
    """The span Jev chose, or the whole unit when no span was asked or Jev inverted it."""

    start_id, end_id = f"{question_id}: start", f"{question_id}: end"
    if start_id not in response.answers:
        return unit.location

    start, end = int(response.answers[start_id].choice), int(response.answers[end_id].choice)
    return Location(unit.file, start, end) if start <= end else unit.location
