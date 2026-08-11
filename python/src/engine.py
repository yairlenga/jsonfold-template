from __future__ import annotations
from types import NoneType
from typing import Any, Optional, cast
from dataclasses import dataclass, field
import re

from core import Frame
from logic import LogicCompiler
from navigation import NAV_RE_STR, NavigationCompiler
from template import NoticeSeverity, Template, RenderStatus, JFTLNotice, Engine, Missing

from model import COMPILE_DOC, JFTL_BREAK, JFTL_SKIP, JSON_DOC, JSON_VALUE_TYPES, JSON_UNSET, RUNTIME_DOC, RUNTIME_LIST_TYPES, RUNTIME_NULL_TYPES, RUNTIME_VALUE_TYPES, CompileError, CompileContext, CompileNotice, CompilerPlugin, DocCompiler, Environment, ErrorStatement, Evaluator, Expression, JFTLConfig, JFTLTemplate, LiteralStatement, RenderError, RuntimeContext, StatementCompiler, my_profile

from typing import Any

# --- Flat version (Any for container contents — simpler, less precise) ---

# --- Recursive version (fully precise — containers hold TYPE_ANY_REC, not Any) ---
# Uncomment and use this instead of the flat version if you want type checkers
# to verify JSON-shape all the way down (e.g. catch a non-JSON value nested
# three levels deep inside a dict-of-lists-of-dicts).

@dataclass
class JFTLCompiler(DocCompiler):
    config: JFTLConfig
    _plugins: dict[str, Any] = field(default_factory=dict)

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

    def plugin(self, name:str) -> Any:
        return self._plugins.get(name)

    def _add_error(self, error: JFTLNotice) -> None:
        keep_msg = False
        stop_now = False
        match error.severity:
            case NoticeSeverity.DEBUG:
                self._debug_count += 1
                keep_msg = self._debug_count < self._max_debug
            case NoticeSeverity.INFO:
                self._info_count += 1
                keep_msg = self._info_count < self._max_info
            case NoticeSeverity.WARNING:
                self._warn_count += 1
                keep_msg = self._warn_count < self._max_warn
            # Everything else is considered ERROR, including FATAL
            case _:
                self._fail = True
                self._error_count += 1
                keep_msg = self._error_count < self._max_errors
                stop_now = not keep_msg or error.severity == NoticeSeverity.FATAL

        if stop_now:
            self._fail = True
            raise CompileError(error)
        if keep_msg:
            self._errors.append(error)

    def record_notice(self, error: JFTLNotice) -> JFTLNotice:
        self._add_error(error)
        return error

    # Call to natigation: 
    _NAV_RE = re.compile("^" + NAV_RE_STR + "$", re.VERBOSE)

    # Call to expression engine: $prefix=expression
    EXPR_RE = re.compile(r"""
        \$
        (?P<plugin> \w+ )?
        =
        \s *
        (?P<expr> (?s:.*))
        $            
    """, re.VERBOSE)

    _nav_compiler : Optional[NavigationCompiler] = None
    _expr_compilers: dict[str, Optional[StatementCompiler]] = field(default_factory=dict)

    # Compile single ex
    def _compile_simple_str(self, source: Any, cc: CompileContext) -> COMPILE_DOC:

        m = self._NAV_RE.match(source)
        if m:
            if self._nav_compiler is None:
                self._nav_compiler = NavigationCompiler(self)
            expr  = self._nav_compiler.parse_nav(m, cc)
            return expr

        # Consider python expression engines (hardcoded for now)

        m = self.EXPR_RE.match(source)
        if m:
            plugin_id = m.group("plugin") or self.config.default_expr_engine
            expr_compiler = self._expr_compilers.get(plugin_id, None)
            if not expr_compiler:
                plugin = self._plugins.get(plugin_id, None)
                if isinstance(plugin, CompilerPlugin):
                    expr_compiler = self._expr_compilers[plugin_id] = plugin.createCompiler(self)

            if isinstance(expr_compiler, StatementCompiler):
                expr = expr_compiler.compile_str(m.group("expr"), cc)
                return expr

        return CompileNotice(code="BAD_EXPRESSION", cc=cc,
            message=f"Unknown Expression {source!r}" )

# --- navigation grammar, mirrors Navigation.md ---
    # Interpolation only supports navigation expressions this round —
    # complex/computed values must be precomputed via `set` and
    # interpolated by variable name instead.

    _NAV_HEAD = r"""
                                      # start at current data
      | \^                            # top frame
      | <                             # prev frame data
      | %                             # frame
      | [A-Za-z_]\w*                  # named variable ($foo)
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

    _INTERP_RE = re.compile(r"""
    \$\$\{                        # literal "$${" — escaped/literal placeholder marker
    | \$\{ (?P<inner>[^}]*) \}      # "${...}" — captures the inner expression
    """, re.VERBOSE)

    def _compile_interpolated(self, source: str, cc: CompileContext) -> COMPILE_DOC:
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
                    return CompileNotice(cc, "BAD_INTERPOLATION",
                        f"nested or unclosed interpolation before position {m.start()}",
                    )
                literal += chunk

            if m.group(0) == "$${":
                literal += "${"

            else:
                inner = m.group("inner")
                if "${" in inner:
                    return CompileNotice(cc, "BAD_INTERPOLATION",
                        message=f"nested or unclosed interpolation: '{inner!r}'",
                    )
                if not self._NAV_ONLY_RE.match(inner):
                    return CompileNotice(cc, "BAD_INTERPOLATION",
                        message=f"Unrecognized interpolation '{inner!r}'",
                    )
                inner_expr = self._compile_str("$" + inner, cc)

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
                return CompileNotice(cc, "BAD_INTERPOLATION",
                    f"nested or unclosed interpolation at end of string: {tail!r}",
                )
            segments.append(tail)

        if len(segments) == 1:
            return segments[0]

        if all(isinstance(item, str) for item in segments):
            return "".join(segments)

        return StringJoinStatement(cc, items=segments)

    def _compile_str(self, source: str, where: CompileContext) -> COMPILE_DOC:

        # Check if this is potential interpolation:
        int_pos = source.find("${")
        if int_pos == 0 or int_pos > 0 and not source.startswith("$"):
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

    @staticmethod
    def _unliteral(x):
        return x.value if isinstance(x, LiteralStatement) else x
    
    _logicCompiler : Optional[LogicCompiler] = None

    def _parse_object_statement(self, source: dict, cc: CompileContext, action: dict) -> dict | JFTLNotice:

        # Validate object constructor
        # 1. no foreach
        # 2. len(source) > 1
        # 3. no out,
        # 4. last element of cases (if any) does not have "else"
        cases = action.get("cases")
        if len(source) == 1:
            return CompileNotice(cc, "BAD-OBJECT-LOGIC",
                                 f'Object Statement must have additional attributes, not just {{ "$": {{ ... }}')

        if ( "foreach" in action
            or "transform" in action
            or "out" in action
            or (isinstance(cases, list) and cases and cases[-1].get("else") is not None)
        ):
            return CompileNotice(cc, "BAD-OBJECT-STATEMENT",
                                 f"Object logic can not have 'foreach', 'transform', 'output', or 'cases' with 'else')")

        # Rebuild the logic statement, setting out/cases
        stmt = dict(action)
        stmt[self.config.action_tag] = True
        new_out = dict(source)
        new_out.pop(self.config.action_tag)
        if isinstance(cases, list):
            stmt["cases"] = cases + [{ "else": new_out }]
        else:
            stmt["out"]  = new_out
        return stmt

    def _parse_array_statement(self, source: list, cc: CompileContext, action: dict, out: Any) -> dict | JFTLNotice:
        foreach = action.get("foreach")
        if not isinstance(foreach, dict):
            return CompileNotice(cc, "BAD-ARRAY-FOREACH", f"Must have 'foreach' when using building arrays)")
        
        cases = foreach.get("cases")
        if ( "transform" in action
            or "out" in action
            or (isinstance(cases, list) and cases and cases[-1].get("else") is not None)
        ):
            return CompileNotice(cc, "BAD-ARRAY-STATEMENT", f"Object logic can not have 'foreach', 'transform', 'output', or 'cases' with 'else')")

        stmt = dict(action)
        new_foreach = dict(foreach)
        stmt[self.config.action_tag] = True
        stmt["foreach"] = new_foreach
        if isinstance(cases, list):
            new_foreach["cases"] = cases  +[{ "else": out }]
        else:
            new_foreach["out"] = out
        return stmt


    def _compile_action(self, source: dict, cc: CompileContext) -> COMPILE_DOC:

#        where = cc.where

        action = source.get(self.config.action_tag, JSON_UNSET)
        if isinstance(action, dict):
            new_source = self._parse_object_statement(source, cc, action)
            if isinstance(new_source, JFTLNotice):
                return new_source
            source = new_source            
            action = source.get(self.config.action_tag, JSON_UNSET)

        if action is True:
            error_count = self._error_count
            if self._logicCompiler is None:  
                self._logicCompiler = LogicCompiler(self)

            logic_elem = dict(source)
            logic_elem.pop(self.config.action_tag)
            expr = self._logicCompiler.compile(logic_elem, cc)
            if self._error_count > error_count and not isinstance(expr, JFTLNotice):
                # If the error_count was breached, we convert the dictionary to 'ErrorStatement'
                # which will result in runtime error, should the template be executed, with
                # the original template available as attribute.
                notice = CompileNotice(cc, "BAD-LOGIC",
                    message="Logic Element did not compile")
                return ErrorStatement(cc, notice = notice, statement=expr)

            return expr
        
        if action is False:
            if not "out" in source:
                return CompileNotice(cc, "MISSING-VALUE",
                    "Missing 'out' in Literal statements ('$' = False), value must be provided")
            return LiteralStatement(cc, value=source.get("out"))
                                    
        else:
            action_name = f"'{action}'" if isinstance(action, str) else f"type={type(action)}"
            return CompileNotice(cc, "LOGIC-ACTION",
                f"The action must be a string or boolean, got '$=:{action_name}'")


    def _compile(self, source: Any, cc: CompileContext) -> COMPILE_DOC :

        # Simple Literal returned here
        if isinstance(source, (int, float, bool, NoneType)):
            return source

        # Special case - array constructor
        if (isinstance(source, list)
            and len(source) == 2
            and isinstance((first := source[0]), dict)
            and len(first) == 1
            and isinstance(action := first.get(self.config.action_tag), dict)
        ):
            new_source = self._parse_array_statement(source, cc, action, source[1])
            source = new_source

        # Handle Dictionary objects. Use '$' attribute to classify into logic, literal, macro or other.
        if isinstance(source, dict):

            # If there is '$', this is action/call
            if self.config.action_tag in source:
                return self._compile_action(source, cc)
    
            # If the all dict is constant, just use the original
            if all(isinstance(x, (NoneType, bool, int, float)) for x in source.values()):
                return LiteralStatement(cc, value=source)

            entries = {k: self._compile(v, cc.child(k)) for k, v in source.items()}            
            for err in ( e for e in entries.values() if isinstance(e, JFTLNotice)):
                self._add_error(err)

            # If it's all literals, unwrap and return a new literal.
            if all(isinstance(x, (NoneType, bool, int, float, str, LiteralStatement)) for x in entries.values()):
                return LiteralStatement(cc, value= dict({ k: self._unliteral(v) for k,v in source.items() }) )

            return ObjectEvaluator(cc, entries=dict(entries))


        if isinstance(source, list):

            # Unnested tree can be converted to literal quickly
            if all(isinstance(x, (NoneType, bool, int, float)) for x in source):
                return LiteralStatement(cc, value=source)



            items = [self._compile(v, cc.child(i)) for i, v in enumerate(source)]
            for err in ( e for e in items if isinstance(e, JFTLNotice)):
                self._add_error(err)

            # If it's all literals, unwrap and return a new literal.
            if all(isinstance(x, (NoneType, bool, int, float, str, LiteralStatement)) for x in items):
                return LiteralStatement(cc, value=list(self._unliteral(x) for x in items))

            return ArrayEvaluator(cc, items=items)

        # Scalar Cases - string
        if isinstance(source, str):
            return self._compile_str(source, cc)
        
        # Non string source
        return CompileNotice(cc, "BAD_NODE",
            message=f"Unknown node {source!r}",
            )
   
    # Compile is called from plugins that need generic compilation.
    # It also capture exceptions, and convert them to error
    def compile_str(self, source: str, cc: CompileContext) -> COMPILE_DOC:
        return self._compile_str(source, cc)

    def compile(self, source: Any, cc: CompileContext, record: bool = False) -> COMPILE_DOC:
        try:
            compiled = self._compile(source, cc)
            if isinstance(compiled, JFTLNotice) and record:
                self._add_error(compiled)
            return compiled
        except CompileError as ex:
            self._fail = True
            self._errors.append(ex.notice)
            self._error_count += 1

    def compile_root(self, source: Any, where: CompileContext) -> tuple[Any, bool, list[JFTLNotice]]:
        self._fail = False
        compiled = self.compile(source, where)
        ok = not self._fail and self._error_count == 0
        # Make sure compiled is non-false, if template is valid, wrap it inside a literal,
        # If compilation failed, make it JFTLNotice.
        if not compiled:
            if ok:
                compiled = LiteralStatement(where, None, value=compiled)
            else:
                compiled = JFTLNotice(code="COMPILE-ERROR", message="Compile Error")

        return compiled, not self._fail and self._error_count == 0 and not isinstance(compiled, JFTLNotice), self._errors
   
@dataclass
class JFTLRenderer():
    template: Template
    _drop_null_attributes: bool = False

    def __post_init__(self):
        if isinstance(self.template, JFTLTemplate) and (config := self.template.config):
            self._drop_null_attributes = config.drop_null_attributes

    def render(self, source: COMPILE_DOC, frame: Frame) -> tuple[RUNTIME_DOC, Optional[JFTLNotice]]:
        result= self._render(source, frame)
        error = None
        # Possible that the document itself is an (unhandled) error
        if not error and isinstance(result, JFTLNotice):
            error = result
            result = None
        return result, error

    def _render(self, source: COMPILE_DOC, frame: Frame) -> RUNTIME_DOC:
        if isinstance(source, Evaluator):
            return source.eval(frame)

        # Most likely, below not used, as objects are either "All-Literal" (converted into LiteralStatement),
        # or "mixed" literal/statement, which get converted to ObjectStatement. This is kept in case the
        # compiler will decide to keep a dictionary in "unknown" state.
        if isinstance(source, dict):
            return ObjectEvaluator.eval_object(frame, source)

        # Most liekly, below not used, and arrays are either "all-lieteral" (converted into LiteralStatement),
        # or "mixed" literal/statement, which get converted to ArrayStatement. This is kept in case the
        # compiler will decide to keep array ni "unknown" state.
        if isinstance(source, RUNTIME_LIST_TYPES):
            return ArrayEvaluator.eval_array(frame, source)
       
        return source
    
    def materialize(self, result: RUNTIME_DOC) -> JSON_DOC:
        return self._materialize(result)

    def _materialize(self, value: RUNTIME_DOC) -> JSON_DOC:
        if isinstance(value, (Missing, RuntimeContext)):
            return None
        if isinstance(value, dict):
            drop_nulls = self._drop_null_attributes
            return {
                k: mv
                for k, v in value.items()
                if ( mv := self._materialize(v)) is not None or not drop_nulls
            }

        if isinstance(value, RUNTIME_LIST_TYPES):
            return [ self._materialize(v) for v in value ]
        if isinstance(value, ( NoneType, bool, int, float, str)):
            return value

        raise RenderError(
            JFTLNotice(code="BAD-RESULT", message=f"Result contained unknown type {type(value)}"))

@dataclass(slots=True)
class JFTLEngine(Engine):
    
    _plugins: dict[str, Any] = field(default_factory=dict)

    def add_plugin(self, prefix: str, plugin: object) -> None:
        if prefix in self._plugins:
            raise RenderError(notice=JFTLNotice(code="DUP-PLUGIN", message=f"Plugin '$(prefix)' already registed"))
        
        self._plugins[prefix] = plugin

    def compile(self, source: str | dict | list, *, main_only: bool = False, filename: str = "",  **kwargs) -> tuple[JFTLTemplate, list[JFTLNotice]]:
        MAIN_ENTRY = "main"
        top = cast(dict, { MAIN_ENTRY: source } if main_only else source)
        config = JFTLConfig(**top.get("config", {}))
        root_name = filename if filename else "root" if main_only else MAIN_ENTRY

        compiler = JFTLCompiler(config, self._plugins)
        compiled, valid, errors = compiler.compile_root(top[MAIN_ENTRY], CompileContext.root(root_name))
        first_error = next((e for e in errors if e.severity in (NoticeSeverity.FATAL, NoticeSeverity.ERROR)), None) 

        if not isinstance((datasets := top.get("datasets", {}) or {}) , dict):
            raise CompileError(
                JFTLNotice(code="BAD-DATASET", message=f"Dataset must be dictionary, got {type(datasets)}")
                )

        return JFTLTemplate(main_entry=compiled, config=config, datasets=datasets, valid=valid, error=first_error ), errors
    
    def _render_top(self, renderer: JFTLRenderer, input: Any, body: Optional[Evaluator], datasets: Optional[dict] = None) -> tuple[Any, RenderStatus]:
        if not body:
            return None, RenderStatus(False, JFTLNotice(code="NO-MAIN", message="Template does not have main"))
       
        template_datasets = renderer.template.datasets if isinstance(renderer.template, JFTLTemplate) else None
        datasets = { **(template_datasets or {}), **(self._datasets), **(datasets or {})}

        env = Environment(renderer.template, input, datasets=datasets)
        frame = Frame.root_context(env)
        result, render_error = renderer.render(body, frame)
        frame.reset()
        if render_error:
            status = RenderStatus(False, render_error, eval_count = env.eval_count)
        else:
            status = RenderStatus(ok=True, eval_count=env.eval_count)
        return result, status

    def render_raw(self, template: JFTLTemplate, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict] = None) -> tuple[Any, RenderStatus]:
        renderer = JFTLRenderer(template)
        result, status = self._render_top(renderer, input, template.main_entry, datasets)       
        return result, status

    def render(self, template: Template | JFTLTemplate, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict[str, Any]] = None, **kwargs) -> tuple[Any, RenderStatus]:

        result = None
        try:
            renderer = JFTLRenderer(template)
            main_entry = None if entry else template.main_entry if isinstance(template, JFTLTemplate) else None
            result, status = self._render_top(renderer, input, main_entry, datasets=datasets)
            result = renderer.materialize(result)

        except RenderError as re:
            status = RenderStatus(False, re.notice)
        return result, status
        
    def materialize(self, result: Any, template: Optional[Template] = None) -> tuple[Any, Optional[JFTLNotice]]:
        try:
            if isinstance(result, JFTLNotice):
                return None, result

            if not template:
                template = JFTLTemplate(main_entry=None, config=JFTLConfig(), valid=True)

            renderer = JFTLRenderer(cast(JFTLTemplate, template))
            result = renderer.materialize(result)
            return result, None
        except RenderError as re:
            status = re.notice

        return result, status



_RUNTIME_EXTRA_TYPES = (RuntimeContext, Missing)

@dataclass(slots=True, frozen=True, kw_only=True)
class ObjectEvaluator(Evaluator):

    # Each item capture the attribute of the expression
    # True - dynamic expression (isinstance(v, Evaluator)
    # False - constant - valid JSON (int, str, ...)
    # False - constant - special value (SKIP, BREAK, ...)

    ITEM_LIST = list[tuple[str, COMPILE_DOC, Optional[bool]]]

    entries: dict[str, COMPILE_DOC]
    _items: ITEM_LIST = field(default_factory=list)

    @staticmethod
    def _dict_to_items( entries: dict[str, COMPILE_DOC] ) -> ITEM_LIST :
       return [
            (k, v, True if isinstance(v, Evaluator) else False if isinstance(v, JSON_VALUE_TYPES) else None)
            for k, v in entries.items()
        ]

    @staticmethod
    @my_profile
    def _eval_items(ctx:RuntimeContext, items: ITEM_LIST) -> RUNTIME_DOC:
        kv_list = []
        for key, doc, dynamic in items:
            value = cast(Evaluator, doc).eval(ctx) if dynamic else cast(RUNTIME_DOC, doc)

            # Constant potentially, with magic value
            if dynamic is not False:
                # Validate Expression.
                if isinstance(value, RUNTIME_VALUE_TYPES):
                    pass
                # There are 2 magical values: JFTL_SKIP, JFTL_BREAK, that can be emitted and require special handling
                elif value is JFTL_SKIP:
                    continue  # silently dropped from objects, per locked sentinel rules
                elif value is JFTL_BREAK:
                    break
                # Also, there are few runtime types that are OK, may be we need to connect this with strict/safe mode ?
                elif isinstance(value, JFTLNotice): # pyright: ignore[reportUnnecessaryIsInstance]
                    return value
                elif not isinstance(value, _RUNTIME_EXTRA_TYPES): # pyright: ignore[reportUnnecessaryIsInstance]
                    # TODO: Add position indicator for bad item, may be display it.
                    return JFTLNotice(code="ITEM-UNKNOWN-TYPE", message=f"Got unexpected value type {type(value)}")
            kv_list.append((key, value))

        result = dict(kv_list)
        return result

    def __post_init__(self):
        self._items.clear()
        self._items.extend(self._dict_to_items(self.entries))

    @classmethod
    def eval_object(cls, ctx: RuntimeContext, doc: dict[str, COMPILE_DOC]) -> RUNTIME_DOC:
        return cls._eval_items(ctx, cls._dict_to_items(doc))

    @my_profile
    def eval(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
        return self._eval_items(ctx, self._items)

@dataclass(slots=True, frozen=True, kw_only=True)
class ArrayEvaluator(Evaluator):
    items: list[COMPILE_DOC]

    @staticmethod
    def eval_array(ctx: RuntimeContext, items: list[COMPILE_DOC]) -> RUNTIME_DOC:
        result = []
        for item in items:
            value = item.eval(ctx) if isinstance(item, Evaluator) else item
            if isinstance(value, JFTLNotice):
                return value
            elif value is JFTL_SKIP:
                continue
            elif value is JFTL_BREAK:
                break
            result.append(value)
        return result

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        return self.eval_array(ctx, self.items)

@dataclass(slots=True, frozen=True, kw_only=True)
class ValueFormatStatement(Evaluator):
    expr: Any
    format_spec: Optional[str]

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        value = ctx.eval_value(self.expr)
        if isinstance(value, JFTLNotice):
            return value
        if isinstance(value, Missing):
            return "null"
        if not isinstance(value, (NoneType, bool, int, float, str)):
            return JFTLNotice(code="CANT-STRINGIFY", message=f"Result contained unknown type {type(value)}")
        formatted = format(value, self.format_spec) if self.format_spec else str(value)
        return formatted

@dataclass(slots=True, frozen=True, kw_only=True)
class StringJoinStatement(Evaluator):
    items: list[Expression]
    separator: str = ""

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        result = []
        for item in self.items:
            value = item.eval(ctx) if isinstance(item, Evaluator) else item
            if isinstance(value, str):
                pass
            elif isinstance(value, RUNTIME_NULL_TYPES):
                value = "null"
            elif isinstance(value, bool):
                value = ["false", "true"][value]
            elif isinstance(value, (int, float)):
                value = str(value)

            if not isinstance(value, str):
                return JFTLNotice(code="JOIN-STR-VALUE", message=f"Expecting string got {type(value)}")

            result.append(value)
        return "".join(result)

