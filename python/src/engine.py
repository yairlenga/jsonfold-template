from __future__ import annotations
from typing import Any, Literal, Optional, TextIO
from pathlib import Path
from dataclasses import dataclass, field
import re

from logic import LogicStatement
from template import Template, Status, Error, Engine, Missing
from core import CompileError, Condition, Environment, Evaluator, Expression, RenderError, Statement, Frame, Compiler, JFTLTemplate
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

@dataclass
class JFTLEngine(Engine, Compiler):

    _plugins: dict[str, Any] = field(default_factory=dict)

    def add_plugin(self, prefix: str, plugin: Any) -> None:
        self._plugins[prefix] = plugin

    def compile(self, source: str | dict | list, where: str = "", *, main_only: bool = False) -> tuple[Template, list[Error]]:
        top = source if main_only else source.get("main")
        compiled = self._compile(top, where)
        return JFTLTemplate(main=compiled), None
    
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    def render(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]:
        try:
            body = template.main
            frame = Frame.top_frame(template, input)
            result, _ = self._render(body, frame)
            status = Status(ok=True)
        except RenderError as re:
            status = re.error
        finally:
            frame.reset()
        return status, result
        
    def render_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    # Call to natigation: $anchor... or $ancho[...]
    NAV_RE = re.compile(r"""
        \$
        (?P<head> | \^ | < | (?P<vars>\w+ ) )
        (?P<segments> $ | \[.* | \..* )
        $
    """, re.VERBOSE)

    # Call to expression engine: $prefix=expression
    EXPR_RE = re.compile(r"""
        \$
        (?P<plugin> \w+ )
        =
        \s *
        (?P<expr> .*)
        $            
    """, re.VERBOSE)

    def _compile(self, source: Any, where: str = "") -> Statement | Expression:

        # Simple Literal returned here
        if isinstance(source, (int, float, bool, type(None))):
            return source
                                   
        # Handle Dictionary objects. Use '$' attribute to classify into logic, literal, macro or other.
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

        # Scalar Cases - string
        if isinstance(source, str):

            # Anything starting with '$$' is considered as a literal removing the first $.
            if not source.startswith("$"):
                return source
            
            if source.startswith('$$'):
                return source[1:]

            m = self.NAV_RE.match(source) if source != "$" else None
            if m:
                start = None
                head = m.group("head")
                segments = m.group("segments")
                if head == "":
                    start = "_current"
                    # Special case '$.' implied start with current, NO segments
                    if segments == ".":
                        segments = "" 
                elif head == "^":
                    start = "_input"
                elif head == "<":
                    start = "_parent.current"
                elif (vars := m.group("vars")) != "":
                    # Convert $foo.bar to .foo.bar, starting with implied "_.vars"
                    start = vars

                if start:
                    engine = NavigationExprNode(segments, where=where, start=start)
                    return PathStatement(engine)

            # Consider python expression engines (hardcoded for now)

            m = self.EXPR_RE.match(source)
            if m:
                plugin_id = m.group("plugin")
                plugin = self._plugins.get(plugin_id, None)
                if isinstance(plugin, Compiler):
                    expr, _ = plugin.expression(m.group("expr"))
                    return expr

            raise CompileError(Error(
                code="BAD_EXPRESSION", severity="ERROR", where=where, location=None,
                message=f"Unknown Expression {source!r}",
                ))
        
        # Non string source
        raise CompileError(Error(
            code="BAD_NODE", severity="ERROR", where=where, location=None,
            message=f"Unknown node {source!r}",
            ))


    # Returning JSON friendly types
    def _render(self, source: Any | Evaluator, frame: Frame) -> tuple[TYPE_ANY_REC, list[Error] | None]:
        if isinstance(source, Evaluator):
            return source.eval(frame), None

        if isinstance(source, dict):
            result = {}
            for k, v in source.items():
                eval_v, _ = self._render(v, frame)
                if isinstance(eval_v, Error):
                    return Error, None
                if isinstance(eval_v, Missing):
                    continue  # silently dropped from objects, per locked sentinel rules
                result[k] = eval_v
            return result, None
        
        if isinstance(source, list):
            result = []
            for v in source:
                eval_v, _ = self._render(v, frame)
                if isinstance(eval_v, Error):
                    return Error
                if isinstance(eval_v, Missing):
                    eval_v = None
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
        for key, item in self.entries.items():
            value = item.eval(frame) if isinstance(item, Evaluator) else item
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
        for item in self.items:
            value = item.eval(frame) if isinstance(item, Evaluator) else item
            if isinstance(value, Error):
                return value
            result.append(None if isinstance(value, Missing) else value)  # kept as null in arrays
        return result

