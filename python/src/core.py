from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import NoneType
from typing import Any, Optional, TextIO
from abc import ABC, abstractmethod

from template import SKIP_VALUE, Engine, JFTLException, Template, JFTLError, Missing, ERROR_VALUE, MISSING_VALUE
# Template Class - represent compiled templates

# Sentinal value to ignore a value in a collection



# Runtime Objects

@dataclass
class JFTLConfig:
    # Default engine to use for '$=...'
    default_expr_engine: str = ""
    drop_null_attributes: bool = False

    plugins: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class JFTLTemplate(Template):

    main_entry: Optional[Evaluator] = None
    config: JFTLConfig = field(default_factory=JFTLConfig)
    datasets: dict = field(default_factory=dict)

    def valid(self) -> bool:
        return True

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
    top: Frame | None = None

_NULL_TEMPLATE = JFTLTemplate()
_NULL_ENVIRONMENT = Environment(_NULL_TEMPLATE, None)

@dataclass
class Frame (Mapping):

    env: Environment 
    # Aliases as '_'
    current: Any
    # Aliases as '^'
    parent: Frame | None
    # Global Frame, top frame with user variables
    global_frame: Optional[Frame] = None
    # From parent.level + 1, root = 0
    level: int = 0

    # User defined variables in the CURRENT frame    
    vars: dict[str, Any] = field(default_factory=dict)
    # Cached value, including inherited, calculated, ...
    _cache:  dict[str, Any] = field(default_factory=dict)

    # Sync the exposed var '_' with the current attribute
    def _update_current(self):
        self.vars["_"] = self.current

    def set_current(self, current: Any):
        self.current = current
        self._update_current()

    def eval_value(self, expr: Evaluator | Any, default_val=None) -> Any:
        if expr is None:
            return default_val

        # if it can be evaluated, then use the current frame
        result = expr.eval(self) if isinstance(expr, Evaluator) else expr
        return result        
    
    def eval_bool(self, cond: Evaluator | Any, default_val=None) -> bool | None:
        if cond is None:
            return default_val
        result = cond.eval_bool(self)        
        return result
    
    def reset(self) -> None:
        self.env = _NULL_ENVIRONMENT
        self.current = None
        self.parent = None
        self.level = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reset()

    @classmethod
    def top_frame(cls, env: Environment) -> Frame:
        top_vars = {
            "_missing": MISSING_VALUE,
            "_error": ERROR_VALUE,
            "_skip" : SKIP_VALUE,
            "_input" : env.input,
            "_level" : 0,
            "_datasets": env.datasets,
            "_": env.input,
        }
        frame = cls(env=env, current=env.input, level=0, parent=None, vars=top_vars)
        # Must "Patch" the environment to point back to the root frame.
        # May want one day to point each frame direct to the top, to avoid circular
        env.top = frame
        top_vars["_top"] = frame
        top_vars["_external"] = top_vars
        top_vars["_local"] = top_vars
        frame._update_current()
        return frame

    def child_frame(self) -> Frame:
        child_vars : dict[str, Any] = {
            "_parent" : self,
        }
        frame = replace(
            self,
            parent = self,
            level = self.level+1,
            vars = child_vars,
            _cache = {},
        )
        frame._update_current()
        child_vars["_local"] = child_vars
        return frame
    
    def  __getitem__(self, key):
        if key in self._cache:
            return self._cache[key]

        return self.lookup_var(key)
    
    def __iter__(self):
        return self.vars.__iter__()

    def __len__(self):
        return self.vars.__len__()

    def __contains__(self, key: object) -> bool:
        return key in self.vars

    def lookup_var(self, name: str, cache_value: bool = False) -> Any:
        """Search this frame, then parent, then parent's parent, ...
        for `name` in `vars`. Caches the result (or MISSING) at every
        frame walked through, so a repeated lookup from the same frame
        is O(1) afterward."""
        frame = self
        chain = []
        while frame is not None:
            if name in frame.vars:
                # Found a value - cache at all levels
                value = frame.vars[name]
                if cache_value:
                    for f in chain[1:]:
                        f._cache[name] = value
                return value
            chain.append(frame)
            frame = frame.parent

        # May want to cache missing at some time, but not use too much memory
#        for f in chain:
#            f._cache[name] = MISSING_VALUE
        return MISSING_VALUE
    
from abc import ABC, abstractmethod
from typing import Any, Optional

_RAISE = object()   # default — raise a JFTLException on failure
_ERROR = object()   # return the JFTLError object itself, don't raise


class Evaluator(ABC):
    where: str = ""
    source_code: Optional[str] = None           # Source code, if known

    @abstractmethod
    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        ...

    def _location(self, context: Optional[str]) -> str:
        return f"{self.where} ({context})" if context else self.where

    def _resolve(self, error: JFTLError, on: Any) -> Any:
        if on is _RAISE:
            raise JFTLException(error)
        if on is _ERROR:
            return error
        return on

    def eval_bool(
        self,
        frame: Frame,
        *,
        context: Optional[str] = None,
        on_null: Any = False,
        on_error: Any = _RAISE,
    ) -> bool:
        """Default: JFTL's strict falsiness — False | null | Missing are
        falsy, everything else truthy. Pass on_null=_RAISE (or _ERROR)
        to instead treat a missing/null result as a failure in this
        context. Override for engine-specific truthiness."""
        result = self.eval(frame)

        if isinstance(result, JFTLError):
            return self._resolve(result, on_error)

        if isinstance(result, (NoneType, Missing)):
            if on_null is _RAISE or on_null is _ERROR:
                error = JFTLError(
                    severity="ERROR", code="MISSING_VALUE",
                    where=self._location(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_null)
            return on_null

        if result is False:
            return False
        return True

    def eval_str(
        self,
        frame: Frame,
        *,
        context: Optional[str] = None,
        on_null: Any = "",
        on_error: Any = _RAISE,
    ) -> str:
        """Stringify this node's value."""
        result = self.eval(frame)

        if isinstance(result, (NoneType, Missing)):
            if on_null is _RAISE or on_null is _ERROR:
                error = JFTLError(
                    severity="ERROR", code="MISSING_VALUE",
                    where=self._location(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_null)
            return on_null

        if isinstance(result, JFTLError):
            return self._resolve(result, on_error)

        if isinstance(result, bool):
            return "true" if result else "false"
        if isinstance(result, (int, float, str)):
            return str(result)

        error = JFTLError(
            severity="ERROR", code="NON_SCALAR_VALUE",
            where=self._location(context),
            message=f"cannot stringify {type(result).__name__} value",
        )
        return self._resolve(error, on_error)
    
Condition = Evaluator
Stringifier = Evaluator
Expression = Evaluator

# core.py (or wherever feels like the right shared home — maybe alongside Diagnostic/Error in template.py)

class Compiler(ABC):

    @abstractmethod
    def compile(self, source: str) -> tuple[Evaluator, Optional[list[JFTLError]]]: ...

    def condition(self, source: str) -> tuple[Condition, Optional[list[JFTLError]]]:
        return self.compile(source)

    def expression(self, source: str) -> tuple[expression, Optional[list[JFTLError]]]:
        return self.compile(source)

class CompileError(Exception):
    """Raised for any defect discovered while compiling a template.
    Carries the actual Error to report — no separate/duplicate fields.
    Caught by the compiler and appended directly to compile()'s error list."""
    def __init__(self, error: JFTLError):
        super().__init__(error.message)
        self.error = error

class RenderError(Exception):
    def __init__(self, error: JFTLError):
        super().__init__(error.message)
        self.error = error
