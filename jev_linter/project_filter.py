"""Asks Jev about design smells between the units that project_graph links."""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import Noul, Question

from jev_client import JevClient
from jev_linter.findings import FilterResult, Finding
from jev_linter.progress import SILENT_PROGRESS, Progress, UsageCounter
from jev_linter.project_graph import CallEdge, Construction, KnowledgePair, build_graph
from jev_linter.questions import (
    THRESHOLD,
    read_span,
    span_lines,
    span_questions,
    unit_state,
)
from jev_linter.units import Unit

DUPLICATED_KNOWLEDGE = "Duplicated knowledge"
DRIFT = "Drift"
SHOTGUN_SURGERY = "Shotgun surgery"
FEATURE_ENVY = "Feature envy"
REDUNDANT_VALIDATION = "Redundant validation"
MISSING_VALIDATION = "Missing validation"
MISSING_INJECTION = "Missing dependency injection"

# Shotgun surgery needs at least this many units that encode the same knowledge.

MIN_SHOTGUN_UNITS = 3

MESSAGES = {
    DUPLICATED_KNOWLEDGE: "both encode the same knowledge, so changing it means editing both",
    DRIFT: "both encode the same knowledge, and the copies already disagree",
    SHOTGUN_SURGERY: "these units encode the same knowledge, so one change touches all of them",
    FEATURE_ENVY: "the caller mostly works with the callee's object, so its logic may belong in that class",
    REDUNDANT_VALIDATION: "the caller and callee check the same condition",
    MISSING_VALIDATION: "outside input reaches the callee without either function checking it",
    MISSING_INJECTION: "the collaborator should be passed in so callers can substitute it",
}

SAME_KNOWLEDGE = "Assume `a` and `b` encode the same piece of knowledge."

PAIR_QUESTIONS = {
    DUPLICATED_KNOWLEDGE: (
        "Count each unit's `code` together with the `module_constants` it reads. Do `a` and `b` each encode the "
        "same piece of knowledge, such as a text format, file layout, naming convention, or business rule, so "
        "that changing that knowledge would mean editing both? Code that looks alike but serves different "
        "concerns doesn't count, and one simply calling the other doesn't count."
    ),
    DRIFT: (
        f"{SAME_KNOWLEDGE} Do the two copies already state it differently, so that one would accept or produce "
        "something the other wouldn't?"
    ),
}

EDGE_QUESTIONS = {
    FEATURE_ENVY: (
        "Does `caller.code` mostly read or change the data of the object that `callee` belongs to, so that its "
        "logic would sit better as a method of that object's class?"
    ),
    REDUNDANT_VALIDATION: (
        "Do `caller.code` and `callee.code` both check the same condition on the same value, so that one of "
        "the checks is redundant?"
    ),
}

# Missing validation combines two separate judgments: outside data crosses the call,
# and nothing checks it.

PASSES_OUTSIDE_DATA = "Passes outside data"
CHECKS_OUTSIDE_DATA = "Checks outside data"
OUTSIDE_DATA = (
    "data that came from outside the program, such as user input, file contents, command-line arguments, "
    "environment variables, or a network response"
)

VALIDATION_QUESTIONS = {
    PASSES_OUTSIDE_DATA: (
        f"Does `caller.code` pass `callee` {OUTSIDE_DATA}? Values the program built or computed itself don't count."
    ),
    CHECKS_OUTSIDE_DATA: (
        f"Assume `caller.code` passes `callee` {OUTSIDE_DATA}. Does `caller.code` or `callee.code` check that "
        "this data is present and well formed before relying on it?"
    ),
}


def injection_question(class_name: str) -> str:
    return (
        f"`code` constructs `{class_name}` itself. Is `{class_name}` a collaborator with its own behavior or "
        "external resources, such as a client, logger, or service, that the caller of `code` should pass in so "
        "it can be substituted? Constructing plain data or value objects doesn't count, and neither does a "
        "program's entry point wiring its parts together."
    )


@dataclass(frozen=True)
class Duplicate:
    a: Unit
    b: Unit
    probability: float
    findings: list[Finding]


class JevProjectFilter:
    """Compares units across the given files. Expects files that already pass jev_linter_files."""

    source = "jev_linter_project"

    def __init__(self, jev: JevClient, progress: Progress = SILENT_PROGRESS) -> None:
        self.jev = UsageCounter(jev)
        self.progress = progress

    def run(self, files: list[Path]) -> FilterResult:
        usage_before = self.jev.usage
        graph = build_graph(files)
        constructions = group_by_unit(graph.constructions)
        self.progress.start(self.source, len(graph.knowledge_pairs) + len(graph.edges) + len(constructions))
        self.progress.note(graph.summary())

        duplicates = [duplicate for pair in graph.knowledge_pairs if (duplicate := self.check_pair(pair))]
        findings = [finding for duplicate in duplicates for finding in duplicate.findings]
        findings += shotgun_surgery(duplicates, self.source)
        findings += [finding for edge in graph.edges for finding in self.check_edge(edge)]
        findings += [
            finding
            for unit, unit_constructions in constructions.items()
            for finding in self.check_constructions(unit, unit_constructions)
        ]

        result = FilterResult.from_findings(
            self.source,
            files,
            findings,
            notes=(graph.summary(),),
            usage=self.jev.usage - usage_before,
        )
        self.progress.finish(result)
        return result

    def check_pair(self, pair: KnowledgePair) -> Duplicate | None:
        a, b = pair.a, pair.b
        self.progress.step(f"pair  {a.name} <> {b.name}")
        questions: dict[str, Question] = {smell: Noul(instructions=text) for smell, text in PAIR_QUESTIONS.items()}
        questions |= span_questions(f"{DUPLICATED_KNOWLEDGE} in a", SAME_KNOWLEDGE, "`a.code`", span_lines(a))
        questions |= span_questions(f"{DUPLICATED_KNOWLEDGE} in b", SAME_KNOWLEDGE, "`b.code`", span_lines(b))

        response = self.jev.system_one(
            {"a": unit_state(a, with_contract=True), "b": unit_state(b, with_contract=True)},
            questions,
        )
        probability = response.answers[DUPLICATED_KNOWLEDGE].noul
        if probability < THRESHOLD:
            return None

        location = read_span(response, f"{DUPLICATED_KNOWLEDGE} in a", a)
        related = (read_span(response, f"{DUPLICATED_KNOWLEDGE} in b", b),)
        drift = response.answers[DRIFT].noul
        smells = {DUPLICATED_KNOWLEDGE: probability} | ({DRIFT: drift} if drift >= THRESHOLD else {})
        findings = [
            Finding(location, smell, self.source, f"`{a.name}` and `{b.name}`: {MESSAGES[smell]}", p, related)
            for smell, p in smells.items()
        ]
        return Duplicate(a, b, probability, findings)

    def check_edge(self, edge: CallEdge) -> list[Finding]:
        caller, callee = edge.caller, edge.callee
        self.progress.step(f"edge  {caller.name} -> {callee.name}")
        smells =[smell for smell in EDGE_QUESTIONS if smell != FEATURE_ENVY or calls_other_class(edge)]
        questions = {smell: EDGE_QUESTIONS[smell] for smell in smells} | VALIDATION_QUESTIONS
        response = self.jev.system_one(
            {"caller": unit_state(caller, with_contract=True), "callee": unit_state(callee, with_contract=True)},
            {question_id: Noul(instructions=text) for question_id, text in questions.items()},
        )

        answers = {question_id: response.answers[question_id].noul for question_id in questions}
        probabilities = {smell: answers[smell] for smell in smells}
        probabilities[MISSING_VALIDATION] = answers[PASSES_OUTSIDE_DATA] * (1 - answers[CHECKS_OUTSIDE_DATA])
        return [
            Finding(
                location=edge.site,
                rule=smell,
                source=self.source,
                message=f"`{caller.name}` calls `{callee.name}`: {MESSAGES[smell]}",
                probability=probability,
                related=(callee.location,),
            )
            for smell, probability in probabilities.items()
            if probability >= THRESHOLD
        ]

    def check_constructions(self, unit: Unit, constructions: list[Construction]) -> list[Finding]:
        self.progress.step(f"constructions  {unit.name}")
        question_ids = {construction: f"{MISSING_INJECTION}: {construction.class_name}" for construction in constructions}
        response = self.jev.system_one(
            unit_state(unit, with_contract=True),
            {
                question_id: Noul(instructions=injection_question(construction.class_name))
                for construction, question_id in question_ids.items()
            },
        )
        return [
            Finding(
                location=construction.site,
                rule=MISSING_INJECTION,
                source=self.source,
                message=f"`{unit.name}` constructs `{construction.class_name}`: {MESSAGES[MISSING_INJECTION]}",
                probability=response.answers[question_id].noul,
            )
            for construction, question_id in question_ids.items()
            if response.answers[question_id].noul >= THRESHOLD
        ]


def calls_other_class(edge: CallEdge) -> bool:
    """Feature envy only applies when the callee is a method of a class the caller doesn't belong to."""

    callee_class, _, method = edge.callee.name.rpartition(".")
    caller_class = edge.caller.name.rpartition(".")[0]
    return bool(callee_class) and callee_class != caller_class and method != "__init__"


def group_by_unit(constructions: list[Construction]) -> dict[Unit, list[Construction]]:
    groups: dict[Unit, list[Construction]] = defaultdict(list)
    for construction in constructions:
        groups[construction.unit].append(construction)
    return groups


def shotgun_surgery(duplicates: list[Duplicate], source: str) -> list[Finding]:
    """Groups of units joined by duplicated knowledge. The weakest link sets the probability."""

    neighbors: dict[Unit, set[Unit]] = defaultdict(set)
    for duplicate in duplicates:
        neighbors[duplicate.a].add(duplicate.b)
        neighbors[duplicate.b].add(duplicate.a)

    findings, seen = [], set()
    for start in neighbors:
        if start in seen:
            continue
        group = connected_units(start, neighbors)
        seen |= group
        if len(group) < MIN_SHOTGUN_UNITS:
            continue

        units = sorted(group, key=lambda unit: (str(unit.file), unit.start_line))
        probability = min(d.probability for d in duplicates if d.a in group)
        findings.append(
            Finding(
                location=units[0].location,
                rule=SHOTGUN_SURGERY,
                source=source,
                message=f"{', '.join(f'`{unit.name}`' for unit in units)}: {MESSAGES[SHOTGUN_SURGERY]}",
                probability=probability,
                related=tuple(unit.location for unit in units[1:]),
            )
        )
    return findings


def connected_units(start: Unit, neighbors: dict[Unit, set[Unit]]) -> set[Unit]:
    group, frontier = {start}, [start]
    while frontier:
        for neighbor in neighbors[frontier.pop()] - group:
            group.add(neighbor)
            frontier.append(neighbor)
    return group
