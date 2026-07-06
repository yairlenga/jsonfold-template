from __future__ import annotations
from typing import Any, Literal, Optional, TextIO
from pathlib import Path
from dataclasses import dataclass

from logic import LogicStatement
from py_expr import PyRunExprEngine
from template import Template, Status, Error, Engine, Missing
from core import CompileError, Condition, Environment, Evaluator, Expression, Statement, Frame, Compiler, JFTLTemplate
from runtime import NavigationExprNode

from typing import Any, Union

# --- Flat version (Any for container contents — simpler, less precise) ---

TYPE_SCALAR = Union[str, int, float, bool]
TYPE_CONTAINER = Union[dict[str, Any], list[Any]]
TYPE_SIMPLE = Union[TYPE_SCALAR, None]
TYPE_ANY = Union[TYPE_SCALAR, TYPE_CONTAINER, None]

# There is no type-level way to express "empty container" — emptiness is a
# runtime property (len(x) == 0), not something the type system can encode.
# Literal(...) only accepts hashable/immutable literal values, so
# Literal([], {}) is invalid and raises TypeError at runtime. If you need
# this concept, use a runtime helper instead:
#
def is_empty_container(x: TYPE_CONTAINER) -> bool:
    return len(x) == 0


# --- Recursive version (fully precise — containers hold TYPE_ANY_REC, not Any) ---
# Uncomment and use this instead of the flat version if you want type checkers
# to verify JSON-shape all the way down (e.g. catch a non-JSON value nested
# three levels deep inside a dict-of-lists-of-dicts).

TYPE_ANY_REC = Union[
     None, bool, int, float, str,
     list["TYPE_ANY_REC"],
     dict[str, "TYPE_ANY_REC"],
]

class JFTLEngine(Engine, Compiler):

    def compile(self, source: str | dict | list, where: str = "") -> tuple[Template, list[Error]]:
        top = self._compile(source.get("main"), where)
        return JFTLTemplate(main=top), None
    
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    def render(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]:
        body = template.main
        env = Environment(template, input)
        frame = Frame(env=env, current=env.input, level=0, parent = None)
        env.top = frame
        return Status(ok=True), self._render(body, frame)
        
    def render_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    def _compile(self, source: Any, where: str = "") -> Statement | Expression:
        if isinstance(source, dict):

            action = source.get("$", None)
            if action is True:
                return LogicStatement.compile(self, source)
            elif action is False:
                return LiteralStatement(source)
    
            entries = {k: self._compile(v, where=f"{where}.{k}") for k, v in source.items()}
            return ObjectStatement(entries)

        if isinstance(source, list):
            items = [self._compile(v, where=f"{where}[{i}]") for i, v in enumerate(source)]
            return ArrayStatement(items)

        if isinstance(source, str) and source.startswith("$"):
            if source.startswith('$$'):
                source = source[1:]
                pass
            elif source.startswith(EXPR_PREFIX):
                path_text = source[1:]   # strip just "$", keep the "." — matches grammar directly
                engine = NavigationExprNode(path_text, where=where)
                return PathStatement(engine)
            elif source.startswith(EXPR_PYTHON):
                expr = source[len(EXPR_PYTHON):].strip()
                engine = PyRunExprEngine()
                return engine.compile(expr)
            else:
                raise CompileError(Error(
                    code="INVALID_PYTHON", severity="ERROR", where=where, location=None,
                    message=f"lambda expressions are not allowed in {source!r}",
                ))

        return LiteralStatement(source)
    
    # Returning JSON friendly types
    def _render(self, source: Any | Evaluator, frame: Frame) -> tuple[TYPE_ANY_REC, list[Error] | None]:
        if isinstance(source, Evaluator):
            return source.eval(frame)

        if isinstance(source, dict):
            result = {}
            for k, v in source.items():
                eval_v, _ = self._render(v, frame)
                result[k] = eval_v
            return result
        
        if isinstance(source, list):
            result = []
            for v in source:
                eval_v, _ = self._render(v, frame)
                result.append(eval_v)
            return result, None

        if isinstance(source, Evaluator):
            eval_v, _v = source.eval(frame)
            return eval_v, None
        
        return source, None
    
    # Compiler API
    def condition(self, source: str, where: str|None) -> tuple[Condition, list[Error]]:
        return self._compile(source), None

    def expression(self, source: str | dict, where: str|None) -> tuple[Expression, list[Error]]:
        return self._compile(source), None

    def statement(self, source: dict | str, where: str|None) -> tuple[Statement, list[Error]]:
        return self._compile(source), None

EXPR_PREFIX = "$."  # e.g. "$.user.name" — later: other prefixes (e.g. $cel., $^) route to other engines
EXPR_PYTHON = "$pyrun:"

@dataclass
class LiteralStatement(Statement):
    value: Any

    def eval(self, frame: Frame) -> Any | Error | Missing:
        return self.value


@dataclass
class PathStatement(Statement):
    engine: NavigationExprNode

    def eval(self, frame: Frame) -> Any | Error | Missing:
        return self.engine.eval(frame)


@dataclass
class ObjectStatement(Statement):
    entries: dict[str, Statement]

    def eval(self, frame: Frame) -> Any | Error | Missing:
        result = {}
        for key, stmt in self.entries.items():
            value = stmt.eval(frame)
            if isinstance(value, Error):
                return value
            if isinstance(value, Missing):
                continue  # silently dropped from objects, per locked sentinel rules
            result[key] = value
        return result


@dataclass
class ArrayStatement(Statement):
    items: list[Statement]

    def eval(self, frame: Frame) -> Any | Error | Missing:
        result = []
        for stmt in self.items:
            value = stmt.eval(frame)
            if isinstance(value, Error):
                return value
            result.append(None if isinstance(value, Missing) else value)  # kept as null in arrays
        return result

