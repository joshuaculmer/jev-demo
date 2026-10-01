import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from jev_linter.findings import Location

type UnitKind = Literal["function", "class"]
type UnitNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef

# Calls that reach outside the program: console, files, and processes.

OUTSIDE_CALLS = {"print", "input", "open"}
OUTSIDE_METHODS = {"write", "writelines", "write_text", "write_bytes", "mkdir", "unlink", "rmdir", "rmtree", "touch"}
OUTSIDE_MODULES = ("subprocess.", "os.", "shutil.")


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

    # Source of the module-level assignments the unit reads, keyed by name.

    constants: tuple[tuple[str, str], ...] = ()

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


@dataclass(frozen=True)
class Contract:
    """What code can read off a unit: its inputs, outputs, side effects, and stated assumptions."""

    inputs: list[str]
    output: str | None
    side_effects: list[str]
    assumptions: list[str]


def contract_of(unit: Unit) -> Contract:
    node = unit.node
    if isinstance(node, ast.ClassDef):
        return Contract([], None, [], _docstring(node))

    nodes = list(ast.walk(node))
    return Contract(
        inputs=[_describe_arg(arg) for arg in _args(node) if arg.arg not in {"self", "cls"}],
        output=ast.unparse(node.returns) if node.returns else None,
        side_effects=list(dict.fromkeys(effect for child in nodes for effect in _side_effects(child, node.name))),
        assumptions=_docstring(node) + [assumption for child in nodes for assumption in _assumptions(child)],
    )


def _args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    args = node.args
    extras = [arg for arg in (args.vararg, args.kwarg) if arg]
    return [*args.posonlyargs, *args.args, *args.kwonlyargs, *extras]


def _describe_arg(arg: ast.arg) -> str:
    return f"{arg.arg}: {ast.unparse(arg.annotation)}" if arg.annotation else arg.arg


def _docstring(node: UnitNode) -> list[str]:
    docstring = ast.get_docstring(node)
    return [docstring] if docstring else []


def _side_effects(node: ast.AST, function_name: str) -> Iterator[str]:
    if isinstance(node, ast.Call):
        name = ast.unparse(node.func)
        is_outside_function = isinstance(node.func, ast.Name) and node.func.id in OUTSIDE_CALLS
        is_outside_method = isinstance(node.func, ast.Attribute) and node.func.attr in OUTSIDE_METHODS
        if is_outside_function or is_outside_method or name.startswith(OUTSIDE_MODULES):
            yield f"calls {name}"
    elif isinstance(node, ast.Global):
        yield from (f"modifies global {name}" for name in node.names)
    elif isinstance(node, ast.Assign | ast.AugAssign) and function_name != "__init__":
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        yield from (f"sets {ast.unparse(target)}" for target in targets if _is_self_attribute(target))


def _is_self_attribute(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"


def _assumptions(node: ast.AST) -> Iterator[str]:
    if isinstance(node, ast.Assert):
        yield f"asserts {ast.unparse(node.test)}"
    elif isinstance(node, ast.Raise) and node.exc:
        yield f"raises {ast.unparse(node.exc)}"


@dataclass(frozen=True)
class SourceFile:
    path: Path
    text: str
    tree: ast.Module

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()

    def constants(self) -> dict[str, str]:
        """Source of each module-level assignment, keyed by the name it assigns."""

        constants = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign | ast.AnnAssign) and node.value:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                source = ast.get_source_segment(self.text, node) or ""
                constants |= {target.id: source for target in targets if isinstance(target, ast.Name)}
        return constants


def read_source(path: Path) -> SourceFile:
    text = path.read_text(encoding="utf-8")
    return SourceFile(path, text, ast.parse(text, filename=str(path)))


def extract_units(file: Path) -> list[Unit]:
    source = read_source(file)
    return list(_walk(source, source.constants(), source.tree.body, prefix=""))


def _walk(source: SourceFile, constants: dict[str, str], body: list[ast.stmt], prefix: str) -> Iterator[Unit]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield _unit(source, constants, node, f"{prefix}{node.name}", "function")
        elif isinstance(node, ast.ClassDef):
            name = f"{prefix}{node.name}"
            yield _unit(source, constants, node, name, "class")
            yield from _walk(source, constants, node.body, prefix=f"{name}.")


def _unit(source: SourceFile, constants: dict[str, str], node: UnitNode, name: str, kind: UnitKind) -> Unit:
    start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
    end = node.end_lineno or node.lineno
    referenced = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
    return Unit(
        file=source.path,
        name=name,
        kind=kind,
        start_line=start,
        end_line=end,
        source="\n".join(source.lines[start - 1 : end]),
        node=node,
        constants=tuple((key, constants[key]) for key in sorted(referenced & constants.keys())),
    )
