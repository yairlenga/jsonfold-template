from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import NoneType
from typing import Any, ClassVar, Final, Optional, TextIO, TypeAlias, Union, cast
from abc import ABC, abstractmethod

from template import SKIP_VALUE, JFTLException, Template, JFTLNotice, Missing, ERROR_VALUE, MISSING_VALUE

from typing import TypeAlias, TypeVar

T = TypeVar("T")

Tree: TypeAlias = (
    T
    | list["Tree[T]"]
    | dict[str, "Tree[T]"]
)

class _NoValueType:
    def __init__(self, label: str):
        self._label = label

    def __repr__(self) -> str:
        return self._label

JFTL_UNDEF : Final = _NoValueType("UNDEFINED")
_RAISE : Final = _NoValueType("_RAISE")
_ERROR : Final = _NoValueType("_ERROR")

JSON_LEAFS : TypeAlias = NoneType | bool | int | float | str
    # Tree of JSON Values.
JSON_DOC = Tree[JSON_LEAFS]

RUNTIME_LEAFS : TypeAlias = JSON_LEAFS | Missing | JFTLNotice
    # Tree of RUNTIME Values, may include Missing or Notices (error nodes)
RUNTIME_DOC = Tree[RUNTIME_LEAFS]

# Template Class - represent compiled templates

# Runtime Objects

@dataclass
class JFTLConfig:
    # Default engine to use for '$=...'
    default_expr_engine: str = ""
    drop_null_attributes: bool = False

@dataclass(slots=True)
class JFTLTemplate(Template):

    # From Template:
    valid: bool
    error: Optional[JFTLNotice] = None

    # Implementation
    main_entry: Optional[Evaluator] = None
    config: JFTLConfig = field(default_factory=JFTLConfig)
    datasets: dict = field(default_factory=dict)

_NULL_TEMPLATE : Final = JFTLTemplate(valid=False)

#    macros: dict[str, Macro] = field(default_factory=dict)
#    functions: dict[str, Function] = field(default_factory=dict)
#    expr_engines: dict[str, ExprEngine] = field(default_factory=dict)


# Shared environment - created at the root.
@dataclass
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
    top: RuntimeState | None = None


@dataclass
class RuntimeState (Mapping):

    _NULL_ENVIRONMENT : ClassVar = Environment(_NULL_TEMPLATE, None)

    env: Environment 
    # Aliases as '_'
    current: Any   

    # Location of current element, relative to parent
    part_path: str

    # Aliases as '^'
    parent: Optional[RuntimeState]
    
    # Global Frame, top frame with user variables
    global_frame: Optional[RuntimeState] = None
    # From parent.level + 1, root = 0
    level: int = 0
    # Number of errors reported against self/childrens
    error_count : int = 0

    # User defined variables in the CURRENT frame    
    vars: dict[str, Any] = field(default_factory=dict)
    # Cached value, including inherited, calculated, ...

    def where(self, where: Optional[str] = None):
        paths = [ where ] if where else []
        state = self
        while state:
            paths.append(state.part_path)
            state = state.parent if state.level > 0 else None
        return " ".join(reversed(paths))

    def set_current(self, current: Any):
        self.current = current

    def _resolve(self, error: JFTLNotice, on: Any) -> Any:
        if on is _RAISE:
            raise JFTLException(error)
        if on is _ERROR:
            return error
        return on


    def eval_value(
        self,
        stmt : Statement,
        *,
        context: Optional[str] = None,
        on_null: Any = JFTL_UNDEF,
        on_error: Any = _ERROR,
        on_unset: Any = _RAISE,
    ) -> RUNTIME_DOC:
        
        result = stmt.eval(self) if isinstance(stmt, Evaluator) else cast(RUNTIME_DOC, stmt)

        if isinstance(result, JFTLNotice):
            return self._resolve(result, on_error)

        elif isinstance(result, _NoValueType):
            if on_unset is _RAISE or on_unset is _ERROR:
                error = JFTLNotice(
                    code="UNSET_STATEMENT",
                    where=self.where(context),
                    message="Condition not specified",
                )
                return self._resolve(error, on_unset)
            return on_unset

        elif isinstance(result, (NoneType, Missing)):
            if on_null is _RAISE or on_null is _ERROR:
                error = JFTLNotice(
                    code="MISSING_VALUE",
                    where=self.where(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_null)
            return result if on_null is JFTL_UNDEF else on_null

        return result        

    def eval_bool(
        self,
        cond : Condition,
        *,
        context: Optional[str] = None,
        on_null: Any = False,
        on_error: Any = _ERROR,
        on_unset: Any = _RAISE,
    ) -> bool:
        """Default: JFTL's strict falsiness — False | null | Missing are
        falsy, everything else truthy. Pass on_null=_RAISE (or _ERROR)
        to instead treat a missing/null result as a failure in this
        context. Override for engine-specific truthiness."""

        result = cond.eval(self) if isinstance(cond, Evaluator) else cond

        if isinstance(result, JFTLNotice):
            return self._resolve(result, on_error)

        elif result == JFTL_UNDEF:
            if on_unset is _RAISE or on_unset is _ERROR:
                error = JFTLNotice(
                    code="UNSET_CONDITION",
                    where=self.where(context),
                    message="Condition not specified",
                )
                return self._resolve(error, on_unset)
            return on_unset

        elif isinstance(result, (NoneType, Missing)):
            if on_null is _RAISE or on_null is _ERROR:
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
    def root_state(cls, env: Environment) -> RuntimeState: ...

    def child_state(self) -> RuntimeState: ...
    
    def  __getitem__(self, key):
        return self.lookup_var(key)
    
    def __iter__(self):
        return self.vars.__iter__()

    def __len__(self):
        return self.vars.__len__()

    def __contains__(self, key: object) -> bool:
        return key in self.vars

    def lookup_var(self, name: str, *, cache_value: bool = False) -> Any:
        """Search this frame, then parent, then parent's parent, ...
        for `name` in `vars`. Caches the result (or MISSING) at every
        frame walked through, so a repeated lookup from the same frame
        is O(1) afterward."""
        state = self
        while state is not None:
            if name in state.vars:
                # Found a value - cache at all levels
                value = state.vars[name]
                return value
            state = state.parent if state.level > 0 else None

        # May want to cache missing at some time, but not use too much memory
#        for f in chain:
#            f._cache[name] = MISSING_VALUE
        return MISSING_VALUE
    
from abc import ABC, abstractmethod
from typing import Any, Optional

class Evaluator(ABC):
    where: str = ""
    source_code: Optional[str] = None           # Source code, if known

    @abstractmethod
    def eval(self, state: RuntimeState) -> RUNTIME_DOC:
        ...

    def eval_bool(
        self,
        state: RuntimeState,
        *,
        on_null: bool | None = False ,
    ) -> bool | None :
        """Default: JFTL's strict falsiness — False | null | Missing are
        falsy, everything else truthy. Pass on_null=_RAISE (or _ERROR)
        to instead treat a missing/null result as a failure in this
        context. Override for engine-specific truthiness."""
        result = self.eval(state)
        return on_null if isinstance(result, (NoneType, Missing)) else True if result else False

class Transformer(ABC):

    @abstractmethod
    def transform(self, value: RUNTIME_DOC) -> RUNTIME_DOC: ...


COMPILE_LEAFS : TypeAlias = Evaluator | JSON_LEAFS | Missing | JFTLNotice | Missing
    # Tree of compiled object, may include values, Missing nodes, to-bd-evaluated nodes, and error notice nodes.
COMPILE_DOC = Tree[COMPILE_LEAFS]

Expression = COMPILE_DOC | _NoValueType        # Expression returning any value
Condition = COMPILE_DOC | _NoValueType         # Expression yielding boolean
Statement = COMPILE_DOC | _NoValueType         # Statement, returning any value

# core.py (or wherever feels like the right shared home — maybe alongside Diagnostic/Error in template.py)
@dataclass
class ErrorStatement(JFTLNotice, Evaluator):
    statement: COMPILE_DOC = None

    def eval(self, state: RuntimeState) -> JFTLNotice:
        return self

class StatementCompiler(ABC):

    @abstractmethod
    def compile_str(self, source: str, where: str = "" ) -> COMPILE_DOC : ...

    def compile(self, source: JSON_DOC, where: str = "") -> COMPILE_DOC:
        if isinstance(source, str):
            return self.compile_str(source, where)
        return JFTLNotice(code="UNEXPECTED-BODY", message=f"Plugin {type(self)} expecting str, but got '{type(source)}'")


class DocCompiler(StatementCompiler):

    @abstractmethod
    def compile(self, source: JSON_DOC, where: str = "") -> COMPILE_DOC: ...

    # evaluated via the eval_condition
    def condition(self, source: JSON_DOC, where: str = "") -> Condition:
        return self.compile(source, where)

    # Evaluated via eval
    def statement(self, source: JSON_DOC, where: str = "") -> Statement:
        return self.compile(source, where)

    # Evaluated via eval
    def expression(self, source: str, where: str = "") -> Expression:
        return self.compile(source, where)
    
    def record_notice(self, error: JFTLNotice) -> JFTLNotice: ...

    
class CompileError(Exception):
    """Raised for any defect discovered while compiling a template.
    Carries the actual Error to report — no separate/duplicate fields.
    Caught by the compiler and appended directly to compile()'s error list."""
    def __init__(self, error: JFTLNotice):
        super().__init__(error.message)
        self.error = error

class RenderError(Exception):
    def __init__(self, notice: JFTLNotice):
        super().__init__(notice.message)
        self.notice = notice
