import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from jev_linter.findings import Location

type UnitKind = Literal["function", "class"]
type UnitNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


@dataclass(frozen=True)
class Unit:
    """A function, method, or class. Nested functions belong to the unit that defines them."""

    file: Path
    name: str
    kind: UnitKind
    start_line: int
    end_line: int
    source: str
    node: UnitNode = field(compare=False, repr=False)

    @property
    def location(self) -> Location:
        return Location(self.file, self.start_line, self.end_line)

    def numbered_lines(self) -> dict[str, str]:
        """Non-blank lines keyed by their line number in the file."""

        return {
            str(number): line.rstrip()
            for number, line in enumerate(self.source.splitlines(), self.start_line)
            if line.strip()
        }


def extract_units(file: Path) -> list[Unit]:
    source_lines = file.read_text(encoding="utf-8").splitlines()
    tree = ast.parse("\n".join(source_lines), filename=str(file))
    return list(_walk(file, source_lines, tree.body, prefix=""))


def _walk(file: Path, source_lines: list[str], body: list[ast.stmt], prefix: str) -> Iterator[Unit]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield _unit(file, source_lines, node, f"{prefix}{node.name}", "function")
        elif isinstance(node, ast.ClassDef):
            name = f"{prefix}{node.name}"
            yield _unit(file, source_lines, node, name, "class")
            yield from _walk(file, source_lines, node.body, prefix=f"{name}.")


def _unit(file: Path, source_lines: list[str], node: UnitNode, name: str, kind: UnitKind) -> Unit:
    start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
    end = node.end_lineno or node.lineno
    source = "\n".join(source_lines[start - 1 : end])
    return Unit(file, name, kind, start, end, source, node)
