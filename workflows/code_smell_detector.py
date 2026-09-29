from pathlib import Path

from typesafe_sdk import Noul

INPUT_DIR = Path(__file__).parent.parent / "input_files" / "code_smell_detector"

CODE_SMELLS = {
    "Long function": "a function or method that does too much and runs well past what fits on one screen",
    "Duplicated code": "the same or nearly the same logic repeated in more than one place",
    "Magic numbers": "unexplained literal numbers or strings used in logic instead of named constants",
    "Poor naming": "variables, functions, or classes with vague, misleading, or single-letter names",
    "Deep nesting": "conditionals or loops nested three or more levels deep",
    "Long parameter list": "a function that takes five or more parameters",
    "God class": "a single class that holds many unrelated responsibilities",
    "Global mutable state": "module-level variables that functions read and modify",
    "Bare or swallowed exceptions": "catching all exceptions, or catching them and silently ignoring the error",
    "Dead code": "functions, variables, branches, or imports that are never used or can never run",
    "Commented-out code": "blocks of old code left in comments",
    "Hardcoded secrets or config": "passwords, API keys, file paths, or URLs written directly into the code",
    "Feature envy": "a function that mostly reads and manipulates another object's data instead of its own",
    "Primitive obsession": "passing raw strings, tuples, or dicts where a small class or type would clarify meaning",
    "Boolean flag parameter": "a boolean argument that switches a function between two different behaviors",
    "Inconsistent return types": "a function that returns different types, such as a value in one branch and None in another",
    "Mutable default argument": "a function parameter with a mutable default such as a list or dict",
    "Missing input validation": "using external or user input without checking it is present and well formed",
    "Side effects in unexpected places": "functions whose names suggest a pure calculation but which print, write files, or change state",
    "Excessive comments": "comments that restate what the code plainly does instead of explaining why",
}

THRESHOLD = 0.5


def choose_file():
    files = sorted(p for p in INPUT_DIR.iterdir() if p.is_file())
    print("\nChoose an example file:")
    for i, path in enumerate(files, 1):
        print(f"  {i}. {path.name}")

    while True:
        text = input("> ").strip()
        if text.isdigit() and 1 <= int(text) <= len(files):
            return files[int(text) - 1]
        print(f"Enter a number from 1 to {len(files)}.")


def repeatable_request(jev, input_path):
    """Ask all 20 smell questions about one file in a single request."""

    path = Path(input_path)
    return jev.system_one(
        {"filename": path.name, "code": path.read_text(encoding="utf-8")},
        {
            smell: Noul(instructions=f"Does `code` contain the code smell '{smell}', meaning {definition}?")
            for smell, definition in CODE_SMELLS.items()
        },
    )


def start_workflow(jev):
    path = choose_file()
    response = repeatable_request(jev, path)

    results = sorted(
        ((smell, response.answers[smell].noul) for smell in CODE_SMELLS),
        key=lambda item: item[1],
        reverse=True,
    )

    print(f"\nCode smells in {path.name}:\n")
    width = max(len(smell) for smell in CODE_SMELLS)
    for smell, p in results:
        verdict = "YES" if p >= THRESHOLD else "no"
        print(f"  {smell:<{width}}  {p:.2f}  {verdict}")

    found = sum(p >= THRESHOLD for _, p in results)
    print(f"\n{found} of {len(CODE_SMELLS)} smells detected.")
