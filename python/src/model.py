from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import NoneType
from typing import (Any, Callable, ClassVar, Final, Optional, TextIO, TypeAlias, TypeVar,
                    cast)

from template import (FATAL_VALUE, MISSING_VALUE, JFTLError, JFTLNotice, Missing, NoticeSeverity, Template)


# Enable inlining for faster performance. Disable for troubleshooting/debug.
FAST_INLINE = True

# Create @_profile for conditional profiling. NO-OP without it.
if callable( _ := __builtins__.get("profile")):
    my_profile = cast(Callable, _)
else:
    def my_profile(func): return func


T = TypeVar("T")

Tree: TypeAlias = (
    T
    | list["Tree[T]"]
    | dict[str, "Tree[T]"]
)

class _SentialValue:
    def __init__(self, label: str):
        super().__init__()
        self._label = label

    def __repr__(self) -> str:
        return self._label
    
    def __bool__(self) -> bool | None:
        raise TypeError(f"{self._label} cannot be used as boolean")

class NoValueType(_SentialValue):

    def __bool__(self):
        return False

JSON_UNSET : Final = NoValueType("JSON_UNSET")

JFTL_RAISE : Final = _SentialValue("_RAISE_")
JFTL_NOTICE : Final = _SentialValue("_NOTICE_")

@dataclass
class ControlSignal():
    code: str = "MISSING"

JFTL_SKIP : Final = ControlSignal(code="_SKIP_")
JFTL_BREAK : Final = ControlSignal(code="_BREAK_")

JSON_LEAFS : TypeAlias = NoneType | bool | int | float | str
JSON_DOC = Tree[JSON_LEAFS]

JSON_VALUE_TYPES : Final = (bool, int, float, str, dict, list, NoneType)


#---------------------------------------------------------------------
# Template
#---------------------------------------------------------------------

@dataclass(slots=True)
class JFTLConfig:
        # Default engine to use for '$=...'
    default_expr_engine: str = ""
        # At exit will remove attributes with null/missing values
    drop_null_attributes: bool = False
        # Name of attribute that trigger actions. Default to '$'.
    action_tag :str = "$"

@dataclass(slots=True)
class JFTLTemplate(Template):

    # From Template:
    valid: bool

    # TODO: Capture frst error of a template.
    error: Optional[JFTLNotice] = None

    # Implementation
    main_entry: Optional[Evaluator] = None
    config: JFTLConfig = field(default_factory=JFTLConfig)
    datasets: dict = field(default_factory=dict)

_NULL_TEMPLATE : Final = JFTLTemplate(valid=False)

#    macros: dict[str, Macro] = field(default_factory=dict)
#    functions: dict[str, Function] = field(default_factory=dict)
#    expr_engines: dict[str, ExprEngine] = field(default_factory=dict)

#---------------------------------------------------------------------
# Runtime Support
#---------------------------------------------------------------------


RUNTIME_LEAFS : TypeAlias = JSON_LEAFS | Missing | JFTLNotice
    # Tree of RUNTIME Values, may include Missing or Notices (error nodes)
RUNTIME_DOC : TypeAlias = Tree[RUNTIME_LEAFS]
RUNTIME_BOOL : TypeAlias = bool | Missing | JFTLNotice | NoneType

RUNTIME_LIST_TYPES : Final = (list, tuple)
RUNTIME_DICT_TYPES : Final = (dict, Mapping)
RUNTIME_NULL_TYPES : Final = (NoneType, Missing)
RUNTIME_VALUE_TYPES : Final = (bool, int, float, str, dict, list, NoneType, Missing)


@dataclass(slots=True)
class Environment:

    # Template in use
    template: Template
    # Original input document
    input: Any
    # Destination - for streaming mode. only relevant if level = 0.
    to: Optional[TextIO] = None
    # Run time Data Sets, mapped via _datasets
    datasets: dict[str, Any] = field(default_factory=dict)

    # Reference to top frame. Set later, as top frame and top environment point to each other.
    top: RuntimeContext | None = None

    # Runtime statistics
    eval_count : int = 0

    # Runtime Data,
    cache: dict[Any, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeContext (Mapping, ABC):

    _NULL_ENVIRONMENT : ClassVar = Environment(_NULL_TEMPLATE, None)

    env: Environment 
    # Aliases as '_'
    current: Any

    # Location of current element, relative to parent
    part_path: str

    # Aliases as '^'
    parent: Optional[RuntimeContext]
    
    # Global Frame, top frame with user variables
    global_ctx: Optional[RuntimeContext] = None
    # From parent.level + 1, root = 0
    level: int = 0

    # User defined variables in the CURRENT frame    
    vars: dict[str, Any] = field(default_factory=dict)
    # Cached value, including inherited, calculated, ...

    def where(self, where: Optional[str] = None) -> str:
        paths = [ where ] if where else []
        ctx = self
        while ctx:
            paths.append(ctx.part_path)
            ctx = ctx.parent if ctx.level > 0 else None
        return " ".join(reversed(paths))


    def _set_current(self, current: Any):
        pass
        self.current = current
        return

    set_current = _set_current

    def set_state_data(self, current: Any) -> None: ...

    def _resolve(self, notice: JFTLNotice, on: Any) -> Any:
        if on is JFTL_RAISE or notice.severity is NoticeSeverity.FATAL:
            raise JFTLError(notice)
        if on is JFTL_NOTICE:
            return notice
        return on

    _good_result = ()

    def stop_on_fatal(self, notice: JFTLNotice, expr: Any) -> None:
        if notice.severity is NoticeSeverity.FATAL:
            if isinstance(expr, Evaluator):
                notice = replace(notice, source = expr.source_code, where = expr.cc.where)
            raise RenderError(notice)
        return


    @my_profile
    def eval_value(
        self,
        stmt : Statement,
        *,
        context: Optional[str] = None,
        on_missing: Any = JSON_UNSET,
        on_error: Any = JFTL_NOTICE,
        on_unset: Any = JFTL_RAISE,
    ) -> RUNTIME_DOC:
        
        if isinstance(stmt, Evaluator):
            self.env.eval_count += 1
            result = stmt.eval(self)

        elif isinstance(stmt, NoValueType):
            if on_unset is JFTL_RAISE or on_unset is JFTL_NOTICE:
                error = JFTLNotice(
                    code="UNSET_STATEMENT",
                    where=self.where(context),
                    message="Value not specified",
                )
                return self._resolve(error, on_unset)
            return on_unset

        else:
            result = cast(RUNTIME_DOC, stmt)
        
        if isinstance(result, JSON_VALUE_TYPES):
            return result

        elif isinstance(result, JFTLNotice):
            if result.severity == NoticeSeverity.FATAL:
                self.stop_on_fatal(result, stmt)

            return self._resolve(result, on_error)

        elif isinstance(result, Missing): # pyright: ignore[reportUnnecessaryIsInstance]
            if on_missing is JFTL_RAISE or on_missing is JFTL_NOTICE:
                error = JFTLNotice(
                    code="MISSING_VALUE",
                    where=self.where(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_missing)
            return result if on_missing is JSON_UNSET else on_missing

        return result        

    @my_profile
    def eval_bool(
        self,
        cond : Condition,
        *,
        context: Optional[str] = None,
        on_null: Any = False,
        on_error: Any = JFTL_NOTICE,
        on_unset: Any = JFTL_RAISE,
    ) -> RUNTIME_BOOL:
        """Default: JFTL's strict falsiness — False | null | Missing are
        falsy, everything else truthy. Pass on_null=_RAISE (or _ERROR)
        to instead treat a missing/null result as a failure in this
        context. Override for engine-specific truthiness."""

        self.env.eval_count += 1
        if isinstance(cond, bool):
            return cond

        if isinstance(cond, Evaluator):
            result = cond.eval_bool(self)
            if isinstance(result, bool):
                return result

        elif isinstance(cond, NoValueType):
            if on_unset is JFTL_RAISE or on_unset is JFTL_NOTICE:
                error = JFTLNotice(
                    code="UNSET_CONDITION",
                    where=self.where(context),
                    message="Condition not specified",
                )
                return self._resolve(error, on_unset)
            return on_unset
        
            # Very unlikely that we will even get there. This compiler
            # should resolve constants to boolean/error at compile time.
        else:
            result = cond

        if isinstance(result, JFTLNotice):
            return self._resolve(result, on_error)

        elif isinstance(result, RUNTIME_NULL_TYPES):
            if on_null is JFTL_RAISE or on_null is JFTL_NOTICE:
                error = JFTLNotice(
                    code="MISSING_VALUE",
                    where=self.where(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_null)
            return on_null

        if result is False:
            return False
        return True
 
    def reset(self) -> None:
        self.env = self._NULL_ENVIRONMENT
        self.current = None
        self.parent = None
        self.level = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reset()

    @classmethod
    @abstractmethod
    def root_context(cls, env: Environment) -> RuntimeContext: ...

    @abstractmethod
    def child_state(self, name: str) -> RuntimeContext: ...
    
    def  __getitem__(self, key):
        return self.lookup_var(key)
    
    def __iter__(self):
        return self.vars.__iter__()

    def __len__(self):
        return self.vars.__len__()

    def __contains__(self, key: object) -> bool:
        return key in self.vars

    def lookup_var(self, name: str, *, cache_mode: Optional[bool] = None) -> Any:
        """Search this frame, then parent, then parent's parent, ...
        for `name` in `vars`. Caches the result (or MISSING) at every
        frame walked through, so a repeated lookup from the same frame
        is O(1) afterward."""
        ctx = self
        while ctx is not None:
            if name in ctx.vars:
                # Found a value - cache at all levels
                value = ctx.vars[name]
                return value
            ctx = ctx.parent if ctx.level > 0 else None

        # May want to cache missing at some time, but not use too much memory
#        for f in chain:
#            f._cache[name] = MISSING_VALUE
        return MISSING_VALUE
    
from abc import ABC, abstractmethod
from typing import Any, Optional

@dataclass(slots=True, frozen=True)
class Evaluator(ABC):
    cc: CompileContext
    source_code: Optional[str] = None           # Source code, if known

    @abstractmethod
    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        ...

    def eval_bool(
        self,
        ctx: RuntimeContext,
    ) -> RUNTIME_BOOL :
        """Default: JFTL's strict falsiness — False | null | Missing are
        falsy, everything else truthy. Pass on_null=_RAISE (or _ERROR)
        to instead treat a missing/null result as a failure in this
        context. Override for engine-specific truthiness."""
        result = self.eval(ctx)
        return result if isinstance(result, (bool, Missing, JFTLNotice, NoneType)) else True
    
    @property
    def where(self)->str:
        return self.cc.where
    

def RuntimeNotice(
        expr: Evaluator,
        code: str,
        message: str,
        *,
        severity: NoticeSeverity = NoticeSeverity.ERROR,
        item_expr: Any = None
    ):
    if isinstance(item_expr, Evaluator):
        expr = item_expr
    return JFTLNotice(
        severity=severity,
        phase= 'RENDER',
        code=code,
        message = message,
        source = expr.source_code,
        where = expr.cc.where
    )



#---------------------------------------------------------------------
# Compilation Support
#---------------------------------------------------------------------


COMPILE_LEAFS : TypeAlias = Evaluator | JSON_LEAFS | Missing | JFTLNotice | Missing
    # Tree of compiled object, may include values, Missing nodes, to-bd-evaluated nodes, and error notice nodes.
COMPILE_DOC = Tree[COMPILE_LEAFS]

Expression = COMPILE_DOC | NoValueType        # Expressoin returning any value
Condition = COMPILE_DOC | NoValueType         # Expression yielding boolean
Statement = COMPILE_DOC | NoValueType         # Statement, returning any value

# core.py (or wherever feels like the right shared home — maybe alongside Diagnostic/Error in template.py)

@dataclass(slots=True, frozen=True, kw_only=True)
class ErrorStatement(Evaluator):
    statement: COMPILE_DOC = None
    notice: JFTLNotice

    def eval(self, ctx: RuntimeContext) -> JFTLNotice:
        return self.notice
    
@dataclass(frozen=True, slots=True)
class SegmentTag:
    name: str

CompilePathSegment: TypeAlias = str | int | SegmentTag   # str = object key, int = array index, Tag = grammar keyword


@dataclass(frozen=True, slots=True)
class CompileContext:
    segment: CompilePathSegment
    parent: Optional[CompileContext] = None
    where: str = ""

    ROOT: ClassVar[CompileContext]

    def child(self, segment: CompilePathSegment) -> CompileContext:
        return CompileContext(segment, self)
    
    @staticmethod
    def root(name: str = ""):
        return CompileContext(name, None)

    def _segment_label(self) -> str:
        seg = self.segment
        return (
            f"[{seg}]" if isinstance(seg, int)
            else f":{seg.name}" if isinstance(seg, SegmentTag)
            else f'["{seg}"]' if isinstance(seg, str) and not seg.isidentifier() # pyright: ignore[reportUnnecessaryIsInstance]
            else f".{seg}" if self.parent
            else seg
        )

    def notice(self, code: str, message: str, *,
        severity: NoticeSeverity = NoticeSeverity.ERROR,
        source: Optional[str] = None,
        details: Optional[list["JFTLNotice"]] = None
    ):
        return JFTLNotice(
            severity=severity,
            phase= 'COMPILE',
            code=code,
            message = message,
            source = source,
            where = self.where,
            details = details,
        )        


    def _where(self) -> str:
        label = self._segment_label()
        full_name = (self.parent.where if self.parent else "") + label
        return full_name

    def __post_init__(self):
        if not self.where:
            object.__setattr__(self, "where", self._where())
        return self.where

    def __str__(self) -> str:
        return self.where



CompileContext.ROOT = CompileContext(segment="")

class BaseCompiler(ABC):

    @abstractmethod
    def compile_str(self, source: str, cc: CompileContext ) -> COMPILE_DOC : ...

    def compile(self, source: JSON_DOC, cc: CompileContext) -> COMPILE_DOC:
        if isinstance(source, str):
            return self.compile_str(source, cc)
        return cc.notice("UNEXPECTED-BODY", f"Plugin {type(self)} expecting str, but got '{type(source)}'")


@dataclass
class StatementCompiler(BaseCompiler):

    compiler: DocCompiler


class DocCompiler(BaseCompiler):

    @abstractmethod
    def compile(self, source: JSON_DOC, cc: CompileContext) -> COMPILE_DOC: ...

    # evaluated via the eval_condition
    def condition(self, source: JSON_DOC, where: CompileContext) -> Condition:
        return self.compile(source, where)

    # Evaluated via eval
    def statement(self, source: JSON_DOC, where: CompileContext) -> Statement:
        return self.compile(source, where)

    # Evaluated via eval
    def expression(self, source: str, where: CompileContext) -> Expression:
        return self.compile(source, where)
    
    # Lookup plugin
    @abstractmethod
    def plugin(self, name: str) -> Any: ...

    # Record error (or warning/info) during compilation 
    def record_notice(self, error: JFTLNotice) -> JFTLNotice: ...

def CompileNotice(
        cc: CompileContext,
        code: str,
        message: str,
        *,
        severity: NoticeSeverity = NoticeSeverity.ERROR,
        source: Optional[str] = None,
        details: Optional[list["JFTLNotice"]] = None
):
    return JFTLNotice(
        severity=severity,
        phase= 'COMPILE',
        code=code,
        message = message,
        source = source,
        where = cc.where,
        details = details,
    )

 
class CompileError(JFTLError):
    """Raised for any defect discovered while compiling a template.
    Carries the actual Error to report — no separate/duplicate fields.
    Caught by the compiler and appended directly to compile()'s error list."""

class RenderError(JFTLError):
    """Raised for any defect discovered while Rendering a template.
    Carries the actual Error to report — no separate/duplicate fields.
    Caught by the compiler and appended directly to compile()'s error list."""

           
# Helper to transform Literal values
@dataclass(slots=True, frozen=True, kw_only=True)
class LiteralStatement(Evaluator):
    value: Any

    def eval(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
        return self.value


# Plugin Management

class Transformer(ABC):

    @abstractmethod
    def transform(self, input: RUNTIME_DOC) -> RUNTIME_DOC: ...

class CompilerPlugin(ABC):

    @abstractmethod
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler : ...
