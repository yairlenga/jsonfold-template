from __future__ import annotations
from collections.abc import Mapping
from types import NoneType
from typing import Any, Literal, Optional, Sequence, TextIO, cast
from pathlib import Path
from dataclasses import dataclass, field
import re

from logic import LogicStatement
from template import Template, Status, JFTLError, Engine, Missing
from core import SKIP_VALUE, CompileError, Condition, Environment, Evaluator, Expression, JFTLConfig, RenderError, Statement, Frame, Compiler, JFTLTemplate
from navigation import NAV_RE_STR, NavigationPlugin

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
class JFTLCompiler(Compiler):
    config: JFTLConfig
    plugins: dict[str, Any] = field(default_factory=dict)

    # Call to natigation: 
    _NAV_RE = re.compile('^' + NAV_RE_STR + "$", re.VERBOSE)
    _nav_plugin : NavigationPlugin = field(default_factory=NavigationPlugin)

    # Call to expression engine: $prefix=expression
    EXPR_RE = re.compile(r"""
        \$
        (?P<plugin> \w+ )?
        =
        \s *
        (?P<expr> (?s:.*))
        $            
    """, re.VERBOSE)

    def _compile(self, source: Any, where: str = "") -> Statement | Expression | str | int | float | bool | NoneType :

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

            # Anything NOT starting with '$' is literal
            if not source.startswith("$"):
                return source
            
            # Anything starting with '$$' is considered as a literal removing the first $.
            if source.startswith('$$'):
                return source[1:]

            m = self._NAV_RE.match(source)
            if m:
                return self._nav_plugin.parse_nav(m, where)

            # Consider python expression engines (hardcoded for now)

            m = self.EXPR_RE.match(source)
            if m:
                plugin_id = m.group("plugin") or self.config.default_engine
                plugin = self.plugins.get(plugin_id, None)
                if isinstance(plugin, Compiler):
                    expr, _ = plugin.expression(m.group("expr"))
                    return expr

            raise CompileError(JFTLError(
                code="BAD_EXPRESSION", severity="ERROR", where=where, location=None,
                message=f"Unknown Expression {source!r}",
                ))
        
        # Non string source
        raise CompileError(JFTLError(
            code="BAD_NODE", severity="ERROR", where=where, location=None,
            message=f"Unknown node {source!r}",
            ))

    # Compiler API
    def condition(self, source: str, where: str|None) -> tuple[Condition, list[JFTLError]]:
        return self._compile(source), None

    def expression(self, source: str | dict, where: str|None) -> tuple[Expression, list[JFTLError]]:
        return self._compile(source), None

    def statement(self, source: dict | str, where: str|None) -> tuple[Statement, list[JFTLError]]:
        return self._compile(source), None
    
    def compile(self, source: dict | str, where: str|None) -> tuple[Statement, list[JFTLError]]:
        return self._compile(source), None

    


@dataclass
class JFTLEngine(Engine):

    _plugins: dict[str, Any] = field(default_factory=dict)

    def add_plugin(self, prefix: str, plugin: Any) -> None:
        self._plugins[prefix] = plugin

    def compile(self, source: str | dict | list, where: str = "", *, main_only: bool = False) -> tuple[JFTLTemplate, list[JFTLError]]:
        top = cast(dict, { "main": source } if main_only else source)
        config = JFTLConfig(**top.get("config", {}))
        compiler = JFTLCompiler(config, self._plugins)
        compiled = compiler._compile(top["main"], where)

        return JFTLTemplate(main_entry=compiled, config=config), None
    
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[JFTLError]]: ...

    def render_raw(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None, globals: Optional[dict] = None) -> tuple[Status, Any]:
        body = template.main_entry
        env = Environment(template, input, datasets=self._datasets)
        frame = Frame.top_frame(env)
        result, _ = self._render(body, frame)
        frame.reset()
        if isinstance(result, JFTLError):
            status = Status(False, result)
        else:
            status = Status(ok=True)
        return status, result

    def render(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]:
        result = None
        try:
            status, result = self.render_raw(template, input, entry = entry)
            result = self._materialize(result)
        except RenderError as re:
            status = Status(False, re.error)
        return status, result
        
    def render_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...


    # Returning JSON friendly types
    def _render(self, source: Any | Evaluator, frame: Frame) -> tuple[TYPE_ANY_REC, list[JFTLError] | None]:
        if isinstance(source, Evaluator):
            return source.eval(frame), None

        if isinstance(source, dict):
            result = {}
            for k, v in source.items():
                eval_v, _ = self._render(v, frame)
                if isinstance(eval_v, JFTLError):
                    return eval_v, None
                elif eval_v == SKIP_VALUE:
                    continue  # silently dropped from objects, per locked sentinel rules
                result[k] = eval_v
            return result, None
        
        if isinstance(source, list):
            result = []
            for v in source:
                eval_v, _ = self._render(v, frame)
                if isinstance(eval_v, JFTLError):
                    return eval_v, None
                elif eval_v == SKIP_VALUE:
                    continue
                result.append(eval_v)
            return result, None
       
        return source, None

    def materialize(self, result: Any) -> Any:
        return self._materialize(result)

    def _materialize(self, value: Any) -> Any:
        if isinstance(value, (Missing, Frame)):
            return None
        if isinstance(value, dict):
            return { k: self._materialize(v) for k, v in value.items() }
        if isinstance(value, (list, tuple)):
            return [ self._materialize(v) for v in value ]
        if isinstance(value, ( NoneType, bool, int, float, str)):
            return value
        return RenderError(JFTLError(severity = 'ERROR', code='BAD-RESULT', message=f"Result contained unknown type {type(value)}"))
           

@dataclass
class LiteralStatement(Statement):
    value: Any

    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        return self.value

@dataclass
class ObjectStatement(Statement):
    entries: dict[str, Statement]

    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        result = {}
        for key, item in self.entries.items():
            value = item.eval(frame) if isinstance(item, Evaluator) else item
            if isinstance(value, JFTLError):
                return value
            if value == SKIP_VALUE:
                continue  # silently dropped from objects, per locked sentinel rules
            result[key] = value
        return result


@dataclass
class ArrayStatement(Statement):
    items: list[Statement]

    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        result = []
        for item in self.items:
            value = item.eval(frame) if isinstance(item, Evaluator) else item
            if isinstance(value, JFTLError):
                return value
            elif value == SKIP_VALUE:
                continue
            result.append(value)
        return result

