from __future__ import annotations
from types import NoneType
from typing import Any, Optional, TextIO, cast
from pathlib import Path
from dataclasses import dataclass, field
import re

from core import RUNTIME_DOC, Frame, JFTLConfig, JFTLTemplate
from logic import LogicStatement
from template import SKIP_VALUE, Severity, Template, RenderStatus, JFTLNotice, Engine, Missing

from model import CompileError, DocCompiler, Environment, ErrorStatement, Evaluator, Expression, RenderError, RuntimeState, Statement, StatementCompiler
from navigation import NAV_RE_STR, NavigationPlugin

from typing import Any

# --- Flat version (Any for container contents — simpler, less precise) ---

# --- Recursive version (fully precise — containers hold TYPE_ANY_REC, not Any) ---
# Uncomment and use this instead of the flat version if you want type checkers
# to verify JSON-shape all the way down (e.g. catch a non-JSON value nested
# three levels deep inside a dict-of-lists-of-dicts).



@dataclass
class JFTLCompiler(DocCompiler):
    config: JFTLConfig
    plugins: dict[str, Any] = field(default_factory=dict)

    # List of errors so far
    _fail: bool = False
    _errors: list[JFTLNotice] = field(default_factory=list)
    # Set when errors contain have severity of ERROR, or higher
    _info_count = 0
    _error_count = 0
    _warn_count = 0
    _debug_count = 0
    _max_info = 10
    _max_errors = 20
    _max_warn = 20
    _max_debug = 0

    def _add_error(self, error: JFTLNotice) -> None:
        keep_msg = False
        stop_now = False
        match error.severity:
            case Severity.ERROR:
                self._debug_count += 1
                keep_msg = self._debug_count < self._max_debug
            case Severity.INFO:
                self._info_count += 1
                keep_msg = self._info_count < self._max_info
            case Severity.WARNING:
                self._warn_count += 1
                keep_msg = self._warn_count < self._max_warn
            # Everything else is considered ERROR, including FATAL
            case _:
                self._fail = True
                self._error_count += 1
                keep_msg = self._error_count < self._max_errors
                stop_now = not keep_msg or error.severity == Severity.FATAL

        if stop_now:
            self._fail = True
            raise CompileError(error)
        if keep_msg:
            self._errors.append(error)

    def record_notice(self, error: JFTLNotice) -> JFTLNotice:
        self._add_error(error)
        return error

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

    # Compile single ex
    def _compile_simple_str(self, source: Any, where: str = "") -> Expression:

        m = self._NAV_RE.match(source)
        if m:
            expr  = self._nav_plugin.parse_nav(m, where)
            return expr

        # Consider python expression engines (hardcoded for now)

        m = self.EXPR_RE.match(source)
        if m:
            plugin_id = m.group("plugin") or self.config.default_expr_engine
            plugin = self.plugins.get(plugin_id, None)
            if isinstance(plugin, StatementCompiler):
                expr = plugin.compile_str(m.group("expr"))
                return expr

        return JFTLNotice(
            code="BAD_EXPRESSION", where=where, location=None,
            message=f"Unknown Expression {source!r}",
            )

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

    def _compile_interpolated(self, source: str, where) -> Expression:
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
                    return JFTLNotice(
                        code="BAD_INTERPOLATION", where=where,
                        message=f"nested or unclosed interpolation before position {m.start()}",
                    )
                literal += chunk

            if m.group(0) == "$${":
                literal += "${"

            else:
                inner = m.group("inner")
                if "${" in inner:
                    return JFTLNotice(
                        code="BAD_INTERPOLATION", where=where,
                        message=f"nested or unclosed interpolation: {inner!r}",
                    )
                if not self._NAV_ONLY_RE.match(inner):
                    return JFTLNotice(
                        code="BAD_INTERPOLATION", where=where,
                        message=f"interpolation only supports navigation expressions, "
                                f"got: {inner!r} (compute complex values via 'set' first)",
                    )
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
                return JFTLNotice(
                    code="BAD_INTERPOLATION", where=where,
                    message=f"nested or unclosed interpolation at end of string: {tail!r}",
                )
            segments.append(tail)

        if len(segments) == 1:
            return segments[0]

        if all(isinstance(item, str) for item in segments):
            return "".join(segments)

        return StringJoinStatement(segments)

    def _compile_str(self, source: str, where: str = "") -> Statement:
        # Check if this is potential interpolation:
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

        return self._compile_simple_str(source, where)

    def _compile(self, source: Any, where: str = "") -> Statement :

        # Simple Literal returned here
        if isinstance(source, (int, float, bool, NoneType)):
            return source
                                   
        # Handle Dictionary objects. Use '$' attribute to classify into logic, literal, macro or other.
        if isinstance(source, dict):

            action = source.get("$", None)
            if action is True:
                error_count = self._error_count
                expr = LogicStatement.compile_object(self, source)
                if self._error_count > error_count and not isinstance(expr, JFTLNotice):
                    return ErrorStatement(code="BAD-LOGIC", message="Logic Element did not compile", statement=expr)
                return expr
            
            elif action is False:
                return LiteralStatement(source)
    
            entries = {k: self._compile(v, where=f"{where}.{k}") for k, v in source.items()}            
            for err in ( e for e in entries.values() if isinstance(e, JFTLNotice)):
                self._add_error(err)
            return ObjectStatement(entries)


        if isinstance(source, list):
            items = [self._compile(v, where=f"{where}[{i}]") for i, v in enumerate(source)]
            for err in ( e for e in items if isinstance(e, JFTLNotice)):
                self._add_error(err)
            return ArrayStatement(items)

        # Scalar Cases - string
        if isinstance(source, str):
            return self._compile_str(source, where)
        
        # Non string source
        return JFTLNotice(
            code="BAD_NODE", where=where, location=None,
            message=f"Unknown node {source!r}",
            )
   
    # Compile is called from plugins that need generic compilation.
    # It also capture exceptions, and convert them to error
    def compile_str(self, source: str, where: str = "", record: bool = False) -> Statement:
        return self._compile_str(source, where)

    def compile(self, source: Any, where: str = "", record: bool = False) -> Statement:
        compiled = None
        try:
            compiled = self._compile(source, where)
            if isinstance(compiled, JFTLNotice) and record:
                self._add_error(compiled)
        except CompileError as ex:
            self._fail = True
            self._errors.append(ex.error)
            self._error_count += 1
            error = ex.error
        return compiled

    def compile_root(self, source: Any, where: str = "") -> tuple[Any, bool, list[JFTLNotice]]:
        self._fail = False
        compiled = self.compile(source, where)

        return compiled, not self._fail and self._error_count == 0, self._errors


   
@dataclass
class JFTLRenderer():
    template: JFTLTemplate
    _drop_null_attributes: bool = False

    def __post_init__(self):
        self._drop_null_attributes = self.template.config.drop_null_attributes

    def render(self, source: Any | Evaluator, frame: Frame) -> tuple[Any, Optional[JFTLNotice]]:
        result, error = self._render(source, frame)
        # Possible that the document itself is an (unhandled) error
        if not error and isinstance(result, JFTLNotice):
            error = result
            result = None
        return result, error

    def _render(self, source: Any | Evaluator, frame: Frame) -> tuple[Any, Optional[JFTLNotice]]:
        if isinstance(source, Evaluator):
            return source.eval(frame), None

        if isinstance(source, dict):
            result = {}
            for k, v in source.items():
                eval_v, _ = self._render(v, frame)
                if isinstance(eval_v, JFTLNotice):
                    return eval_v, None
                elif eval_v == SKIP_VALUE:
                    continue  # silently dropped from objects, per locked sentinel rules
                result[k] = eval_v
            return result, None
        
        if isinstance(source, list):
            result = []
            for v in source:
                eval_v, _ = self._render(v, frame)
                if isinstance(eval_v, JFTLNotice):
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
        return JFTLNotice(code='BAD-RESULT', message=f"Result contained unknown type {type(value)}")

@dataclass
class JFTLEngine(Engine):
    
    _plugins: dict[str, Any] = field(default_factory=dict)

    def add_plugin(self, prefix: str, plugin: Any) -> None:
        self._plugins[prefix] = plugin

    def compile(self, source: str | dict | list, where: str = "", *, main_only: bool = False) -> tuple[JFTLTemplate, list[JFTLNotice]]:
        top = cast(dict, { "main": source } if main_only else source)
        config = JFTLConfig(**top.get("config", {}))


        compiler = JFTLCompiler(config, self._plugins)
        compiled, valid, errors = compiler.compile_root(top["main"], where)

        if not isinstance((datasets := top.get("datasets", {}) or {}) , dict):
            raise CompileError(
                JFTLNotice(code='BAD-DATASET', message=f"Dataset must be dictionary, got {type(datasets)}")
                )
        return JFTLTemplate(main_entry=compiled, config=config, datasets=datasets, valid=valid ), errors
    
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[JFTLNotice]]: ...

    def _render_top(self, renderer: JFTLRenderer, input: Any, body: Optional[Evaluator], datasets: Optional[dict] = None) -> tuple[Any, RenderStatus]:
        if not body:
            return None, RenderStatus(False, JFTLNotice(code="NO-MAIN", message="Template does not have main"))
       
        datasets = { **(renderer.template.datasets), **(self._datasets), **(datasets or {})}

        env = Environment(renderer.template, input, datasets=datasets)
        frame = Frame.root_state(env)
        result, render_error = renderer.render(body, frame)
        frame.reset()
        if render_error:
            status = RenderStatus(False, render_error)
        else:
            status = RenderStatus(ok=True)
        return result, status

    def render_raw(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict] = None) -> tuple[Any, RenderStatus]:
        renderer = JFTLRenderer(template)
        result, status = self._render_top(renderer, input, template.main_entry, datasets)       
        return result, status

    def render(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None,  datasets: Optional[dict] = None) -> tuple[Any, RenderStatus]:
        result = None
        try:
            renderer = JFTLRenderer(template)
            result, status = self._render_top(renderer, input, template.main_entry, datasets=datasets)
            result = renderer.materialize(result)

        except RenderError as re:
            status = RenderStatus(False, re.notice)
        return result, status
        
    def render_to(self, output: TextIO | Path | str, template: Template, input: Any, *, entry: Optional[str]= None) -> RenderStatus: ...

    def materialize(self, result: Any, template: Optional[Template] = None) -> Any:
        if not template:
            template = JFTLTemplate(main_entry=None, config=JFTLConfig(), valid=True)

        renderer = JFTLRenderer(cast(JFTLTemplate, template))
        return renderer.materialize(result)

           

@dataclass
class LiteralStatement(Evaluator):
    value: Any

    def eval(self, frame: Frame) -> Any | JFTLNotice | Missing:
        return self.value

@dataclass
class ObjectStatement(Evaluator):
    entries: dict[str, Expression]

    def eval(self, frame: Frame) -> Any | JFTLNotice | Missing:
        result = {}
        for key, item in self.entries.items():
            value = item.eval(frame) if isinstance(item, Evaluator) else item
            if isinstance(value, JFTLNotice):
                return value
            if value == SKIP_VALUE:
                continue  # silently dropped from objects, per locked sentinel rules
            result[key] = value
        return result


@dataclass
class ArrayStatement(Evaluator):
    items: list[Expression | Any]

    def eval(self, frame: Frame) -> Any | JFTLNotice | Missing:
        result = []
        for item in self.items:
            value = item.eval(frame) if isinstance(item, Evaluator) else item
            if isinstance(value, JFTLNotice):
                return value
            elif value == SKIP_VALUE:
                continue
            result.append(value)
        return result

@dataclass
class ValueFormatStatement(Evaluator):
    expr: Any
    format_spec: Optional[str]

    def eval(self, state: RuntimeState) -> RUNTIME_DOC:
        item = self.expr
        value = state.eval_value(self.expr)
        if isinstance(value, JFTLEngine):
            return value
        if isinstance(value, Missing):
            return "null"
        if not isinstance(value, (NoneType, bool, int, float, str)):
            return JFTLNotice(code='CANT-STRINGIFY', message=f"Result contained unknown type {type(value)}")
        formatted = format(value, self.format_spec) if self.format_spec else str(value)
        return formatted

@dataclass
class StringJoinStatement(Evaluator):
    items: list[Expression]
    separator: str = ""

    def eval(self, frame: Frame) -> RUNTIME_DOC:
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
                return JFTLNotice(code='JOIN-STR-VALUE', message=f"Expecting string got {type(value)}")

            result.append(value)
        return "".join(result)

