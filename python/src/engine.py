from __future__ import annotations
from collections.abc import Mapping
from types import NoneType
from typing import Any, ClassVar, Literal, Optional, Sequence, TextIO, cast
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

    INTERPOLATE_RE = re.compile(r"\$\$\{|\$\{([^}]*)\}")

    def _compile_str(self, source: Any, where: str = "") -> Statement | Expression:

        m = self._NAV_RE.match(source)
        if m:
            return self._nav_plugin.parse_nav(m, where)

        # Consider python expression engines (hardcoded for now)

        m = self.EXPR_RE.match(source)
        if m:
            plugin_id = m.group("plugin") or self.config.default_expr_engine
            plugin = self.plugins.get(plugin_id, None)
            if isinstance(plugin, Compiler):
                expr, _ = plugin.expression(m.group("expr"))
                return expr

        raise CompileError(JFTLError(
            code="BAD_EXPRESSION", severity="ERROR", where=where, location=None,
            message=f"Unknown Expression {source!r}",
            ))

# --- navigation grammar, mirrors Navigation.md ---
    # Interpolation only supports navigation expressions this round —
    # complex/computed values must be precomputed via `set` and
    # interpolated by variable name instead.

    _NAV_HEAD = r"""
        \^                            # top frame
      | _                             # current
      | \$ [A-Za-z_]\w*               # named variable ($foo)
      | [A-Za-z_]\w*                  # bareword variable fallback
    """

    _NAV_SEGMENT = r"""
        \. [A-Za-z_]\w*               # .foo
      | \[ -?\d+ \]                   # [123] / [-1]
      | \[ "[^"]*" \]                 # ["quoted"]
      | \[ '[^']*' \]                 # ['quoted']
      | \[ \$ [A-Za-z_]\w* \]         # [$var]
    """

    _NAV_ONLY_RE = re.compile(
        r"^(?:" + _NAV_HEAD + r")(?:" + _NAV_SEGMENT + r")*$",
        re.VERBOSE,
    )

    # --- outer scan: escape, single-brace nav ---
    # NOTE: [^}]*-style matching — a literal '}' inside a quoted nav segment
    # (e.g. ${foo["a}b"]}) is not yet supported; deferred.

    _INTERP_RE = re.compile(
        r"\$\$\{"
        r"|\$\{(?P<inner>[^}]*)\}",
    )

    def _compile_interpolated(self, source: str, where) -> Statement | str | None:
        """Splits `source` into literal and expression segments.

        Returns None if `source` contains no interpolation at all (caller
        should treat it as a plain literal). Otherwise returns a compiled
        Statement (StringJoinStatement) or a plain str if everything
        collapsed to a single literal/escaped chunk.
        """
        if "${" not in source:
            return None   # fast path — nothing to do

        segments: list = []
        pos = 0

        for m in self._INTERP_RE.finditer(source):
            literal = ""
            inner_expr = None

            if m.start() > pos:
                chunk = source[pos:m.start()]
                if "${" in chunk:
                    raise CompileError(JFTLError(
                        code="BAD_INTERPOLATION", severity="ERROR", where=where,
                        message=f"nested or unclosed interpolation before position {m.start()}",
                    ))
                literal += chunk

            if m.group(0) == "$${":
                literal += "${"

            else:
                inner = m.group("inner")
                if "${" in inner:
                    raise CompileError(JFTLError(
                        code="BAD_INTERPOLATION", severity="ERROR", where=where,
                        message=f"nested or unclosed interpolation: {inner!r}",
                    ))
                if not self._NAV_ONLY_RE.match(inner):
                    raise CompileError(JFTLError(
                        code="BAD_INTERPOLATION", severity="ERROR", where=where,
                        message=f"interpolation only supports navigation expressions, "
                                f"got: {inner!r} (compute complex values via 'set' first)",
                    ))
                inner_expr = self._compile_str("$" + inner, where)

            # Combine literal segments together to avoid re-joining at run time.
            if literal:
                if segments and isinstance(segments[-1], str):
                    segments[-1] += literal
                else:
                    segments.append(literal)
            if inner_expr:
                segments.append(inner_expr)

            pos = m.end()

        if pos < len(source):
            tail = source[pos:]
            if "${" in tail:
                raise CompileError(JFTLError(
                    code="BAD_INTERPOLATION", severity="ERROR", where=where,
                    message=f"nested or unclosed interpolation at end of string: {tail!r}",
                ))
            segments.append(tail)

        if len(segments) == 1:
            return segments[0]

        if all(isinstance(item, str) for item in segments):
            return "".join(segments)

        return StringJoinStatement(segments)

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

            if "${" in source:
                interpolated = self._compile_interpolated(source, where)
                if interpolated:
                    return interpolated

            # Anything NOT starting with '$' is literal
            if not source.startswith("$"):
                return source
            
            # Anything starting with '$$' is considered as a literal removing the first $.
            if source.startswith('$$'):
                return source[1:]

            # Check if this is potential interpolation:
            if "${" in source:
                interpolated = self._compile_interpolated(source, where)
                if interpolated:
                    return interpolated


            return self._compile_str(source, where)
        
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
class JFTLRenderer():
    template: JFTLTemplate
    _drop_null_attributes: bool = False

    def __post_init__(self):
        self._drop_null_attributes = self.template.config.drop_null_attributes

    def render(self, source: Any | Evaluator, frame: Frame) -> tuple[TYPE_ANY_REC, list[JFTLError] | None]:
        return self._render(source, frame)

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
            drop_nulls = self.template.config.drop_null_attributes
            return {
                k: mv
                for k, v in value.items()
                if ( mv := self._materialize(v)) is not None or not drop_nulls
            }

        if isinstance(value, (list, tuple)):
            return [ self._materialize(v) for v in value ]
        if isinstance(value, ( NoneType, bool, int, float, str)):
            return value
        return RenderError(JFTLError(severity = 'ERROR', code='BAD-RESULT', message=f"Result contained unknown type {type(value)}"))

@dataclass
class JFTLEngine(Engine):

    _null_template: ClassVar[JFTLTemplate] = JFTLTemplate(main_entry=None, config=JFTLConfig())

    _plugins: dict[str, Any] = field(default_factory=dict)

    def add_plugin(self, prefix: str, plugin: Any) -> None:
        self._plugins[prefix] = plugin

    def compile(self, source: str | dict | list, where: str = "", *, main_only: bool = False) -> tuple[JFTLTemplate, list[JFTLError]]:
        top = cast(dict, { "main": source } if main_only else source)
        config = JFTLConfig(**top.get("config", {}))
        compiler = JFTLCompiler(config, self._plugins)
        compiled = compiler._compile(top["main"], where)
        if not isinstance((datasets := top.get("datasets", {}) or {}) , dict):
            raise CompileError(
                JFTLError(severity = 'ERROR', code='BAD-DATASET', message=f"Dataset must be dictionary, got {type(datasets)}")
                )
        return JFTLTemplate(main_entry=compiled, config=config, datasets=datasets), None
    
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[JFTLError]]: ...

    def _render_top(self, renderer: JFTLRenderer, input: Any, body: Optional[Evaluator], datasets: Optional[dict] = None) -> tuple[Status, Any]:
        if not body:
            return Status(False, JFTLError(severity='ERROR', code="NO-MAIN", message="Template does not have main")), None
       
        datasets = { **(renderer.template.datasets), **(self._datasets), **(datasets or {})}

        env = Environment(renderer.template, input, datasets=datasets)
        frame = Frame.top_frame(env)
        result, _ = renderer._render(body, frame)
        frame.reset()
        if isinstance(result, JFTLError):
            status = Status(False, result)
        else:
            status = Status(ok=True)
        return status, result

    def render_raw(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict] = None) -> tuple[Status, Any]:
        renderer = JFTLRenderer(template)
        return self._render_top(renderer, input, template.main_entry, datasets)       

    def render(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None,  datasets: Optional[dict] = None) -> tuple[Status, Any]:
        result = None
        try:
            renderer = JFTLRenderer(template)
            status, result = self._render_top(renderer, input, template.main_entry, datasets=datasets)
            result = renderer.materialize(result)

        except RenderError as re:
            status = Status(False, re.error)
        return status, result
        
    def render_to(self, output: TextIO | Path | str, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    def materialize(self, result: Any, template: Optional[Template] = None) -> Any:
        template = cast(JFTLTemplate, template) if template else self._null_template
        renderer = JFTLRenderer(template)
        return renderer.materialize(result)

           

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

@dataclass
class ValueFormatStatement(Statement):
    expr: Any
    format_spec: Optional[str]

    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        item = self.expr
        value = frame.eval_value(self.expr)
        if isinstance(value, JFTLEngine):
            return value
        if isinstance(value, Missing):
            return "null"
        if not isinstance(value, (NoneType, bool, int, float, str)):
            return RenderError(JFTLError(severity = 'ERROR', code='CANT-STRINGIFY', message=f"Result contained unknown type {type(value)}"))
        formatted = format(value, self.format_spec) if self.format_spec else str(value)
        return formatted

@dataclass
class StringJoinStatement(Statement):
    items: list[Statement]
    separator: str = ""

    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        result = []
        for item in self.items:
            value = item.eval(frame) if isinstance(item, Evaluator) else item
            if isinstance(value, str):
                pass
            elif isinstance(value, (NoneType, Missing)):
                value = "null"
            elif isinstance(value, (int, float)):
                value = str(value)
            elif isinstance(value, bool):
                value = ["false", "true"][value]

            if not isinstance(value, str):
                return RenderError(JFTLError(severity = 'ERROR', code='JOIN-STR-VALUE', message=f"Expecting string got {type(value)}"))

            result.append(value)
        return "".join(result)

