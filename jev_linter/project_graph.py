"""Static facts about a set of files that tell jev_linter_project which units to compare."""

import ast
import re
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from jev_linter.findings import Location
from jev_linter.units import Unit, extract_units, read_source

# A token is distinctive when at most this many units use it, and a knowledge pair
# needs this many distinctive tokens in common.

MAX_UNITS_PER_TOKEN = 3
MIN_SHARED_TOKENS = 2

WORD = re.compile(r"[A-Za-z]{4,}")
REPEATED_SYMBOL = re.compile(r"([^\w\s])\1{2,}")


@dataclass(frozen=True)
class CallEdge:
    caller: Unit
    callee: Unit
    site: Location


@dataclass(frozen=True)
class Construction:
    unit: Unit
    class_name: str
    site: Location


@dataclass(frozen=True)
class KnowledgePair:
    a: Unit
    b: Unit


@dataclass(frozen=True)
class ProjectGraph:
    units: list[Unit]
    edges: list[CallEdge]
    constructions: list[Construction]
    knowledge_pairs: list[KnowledgePair]

    def summary(self) -> str:
        return (
            f"{len(self.units)} units, {len(self.knowledge_pairs)} knowledge pairs, "
            f"{len(self.edges)} call edges, {len(self.constructions)} constructions"
        )


@dataclass(frozen=True)
class Module:
    name: str
    file: Path
    imports: dict[str, tuple[str, str | None]]


def build_graph(files: list[Path]) -> ProjectGraph:
    """Only the given files enter the graph, so edges to any other file are dropped."""

    modules = {file: read_module(file) for file in files}
    units = [unit for file in files for unit in extract_units(file)]
    resolver = Resolver(modules, units)
    functions = [unit for unit in units if unit.kind == "function"]

    # Repeated calls between the same two units keep only the first call site.

    edges: dict[tuple[Unit, Unit], CallEdge] = {}
    constructions: dict[tuple[Unit, str], Construction] = {}
    for unit in functions:
        for call in (node for node in ast.walk(unit.node) if isinstance(node, ast.Call)):
            site = Location(unit.file, call.lineno, call.end_lineno or call.lineno)
            edge, construction = resolver.resolve_call(unit, call, site)
            if edge:
                edges.setdefault((edge.caller, edge.callee), edge)
            if construction:
                constructions.setdefault((construction.unit, construction.class_name), construction)

    return ProjectGraph(
        units=units,
        edges=list(edges.values()),
        constructions=list(constructions.values()),
        knowledge_pairs=knowledge_pairs(functions),
    )


def module_name(file: Path) -> str:
    """Dotted import name relative to the working directory, which is the project root."""

    try:
        relative = file.resolve().relative_to(Path.cwd())
    except ValueError:
        relative = Path(file.name)
    parts = list(relative.with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def read_module(file: Path) -> Module:
    name = module_name(file)
    imports: dict[str, tuple[str, str | None]] = {}
    for node in read_source(file).tree.body:
        if isinstance(node, ast.Import):
            imports |= {alias.asname or alias.name: (alias.name, None) for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            source = _absolute_module(name, file, node)
            imports |= {alias.asname or alias.name: (source, alias.name) for alias in node.names}
    return Module(name, file, imports)


def _absolute_module(name: str, file: Path, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    package = name.split(".") if file.stem == "__init__" else name.split(".")[:-1]
    base = package[: len(package) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


class Resolver:
    """Finds the project unit a call reaches, when static analysis can tell."""

    def __init__(self, modules: dict[Path, Module], units: list[Unit]) -> None:
        self.modules = modules
        self.module_names = {module.name for module in modules.values()}
        self.units = {(modules[unit.file].name, unit.name): unit for unit in units}

    def resolve_call(self, unit: Unit, call: ast.Call, site: Location) -> tuple[CallEdge | None, Construction | None]:
        module = self.modules[unit.file]
        target = self._target(module, unit, call.func)

        if target is None:
            name = call.func.id if isinstance(call.func, ast.Name) else None
            is_external_class = name is not None and self._is_external_class(module, name)
            return None, Construction(unit, name, site) if is_external_class else None

        if target.kind == "function":
            return CallEdge(unit, target, site), None

        constructor = self.units.get((self.modules[target.file].name, f"{target.name}.__init__"))
        edge = CallEdge(unit, constructor, site) if constructor else None
        construction = None if _is_dataclass(target) else Construction(unit, target.name, site)
        return edge, construction

    def _target(self, module: Module, unit: Unit, func: ast.expr) -> Unit | None:
        if isinstance(func, ast.Name):
            return self._lookup(module, func.id)
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
            return None

        owner = func.value.id
        if owner in {"self", "cls"} and "." in unit.name:
            class_name = unit.name.rsplit(".", 1)[0]
            return self.units.get((module.name, f"{class_name}.{func.attr}"))
        if module.imports.get(owner, ("", ""))[1] is None:
            return self.units.get((module.imports[owner][0], func.attr))

        owner_class = self._parameter_class(module, unit, owner)
        if owner_class is None:
            return None
        return self.units.get((self.modules[owner_class.file].name, f"{owner_class.name}.{func.attr}"))

    def _lookup(self, module: Module, name: str) -> Unit | None:
        if (module.name, name) in self.units:
            return self.units[(module.name, name)]
        source, imported = module.imports.get(name, ("", None))
        return self.units.get((source, imported)) if imported else None

    def _parameter_class(self, module: Module, unit: Unit, parameter: str) -> Unit | None:
        """The project class a parameter is annotated with, such as `jev: JevClient`."""

        node = unit.node
        if isinstance(node, ast.ClassDef):
            return None
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            if arg.arg == parameter and isinstance(arg.annotation, ast.Name):
                found = self._lookup(module, arg.annotation.id)
                return found if found and found.kind == "class" else None
        return None

    def _is_external_class(self, module: Module, name: str) -> bool:
        """A class imported from a third-party package. Standard library classes are left out."""

        source, imported = module.imports.get(name, ("", None))
        top_package = source.split(".")[0]
        return (
            imported is not None
            and name[0].isupper()
            and source not in self.module_names
            and top_package not in sys.stdlib_module_names
        )


def _is_dataclass(unit: Unit) -> bool:
    """Dataclasses hold plain values, so constructing one directly is never a missing injection."""

    decorators = unit.node.decorator_list
    return any("dataclass" in ast.unparse(decorator) for decorator in decorators)


def knowledge_pairs(functions: list[Unit]) -> list[KnowledgePair]:
    """Pairs of functions that share distinctive string tokens or have overlapping signatures."""

    tokens = {unit: _knowledge_tokens(unit) for unit in functions}
    usage = Counter(token for unit_tokens in tokens.values() for token in unit_tokens)
    distinctive = {
        unit: {token for token in unit_tokens if usage[token] <= MAX_UNITS_PER_TOKEN}
        for unit, unit_tokens in tokens.items()
    }

    return [
        KnowledgePair(a, b)
        for a, b in combinations(functions, 2)
        if len(distinctive[a] & distinctive[b]) >= MIN_SHARED_TOKENS or _signatures_overlap(a, b)
    ]


def _knowledge_tokens(unit: Unit) -> set[str]:
    """Tokens from the unit's string literals and from the module constants it reads."""

    texts = list(_strings_in(unit.node, skip_docstrings=True))
    texts.extend(text for _, source in unit.constants for text in _strings_in(ast.parse(source)))

    words = {word.lower() for text in texts for word in WORD.findall(text)}
    symbols = {match.group(0) for text in texts for match in REPEATED_SYMBOL.finditer(text)}
    return words | symbols


def _strings_in(node: ast.AST, *, skip_docstrings: bool = False) -> Iterator[str]:
    docstrings = set(map(id, _docstring_nodes(node))) if skip_docstrings else set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and id(child) not in docstrings:
            yield child.value


def _docstring_nodes(node: ast.AST) -> Iterator[ast.Constant]:
    for child in ast.walk(node):
        body = getattr(child, "body", None)
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                yield first.value


def _signatures_overlap(a: Unit, b: Unit) -> bool:
    """Same declared return type and at least one shared parameter type."""

    returns_a, parameters_a = _signature_types(a)
    returns_b, parameters_b = _signature_types(b)
    return returns_a is not None and returns_a == returns_b and bool(parameters_a & parameters_b)


def _signature_types(unit: Unit) -> tuple[str | None, set[str]]:
    node = unit.node
    if isinstance(node, ast.ClassDef):
        return None, set()
    returns = ast.unparse(node.returns) if node.returns else None
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    return returns, {ast.unparse(arg.annotation) for arg in arguments if arg.annotation}
