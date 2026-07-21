from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Optional, TextIO
from abc import ABC, abstractmethod

from template import MISSING_VALUE, Template, JFTLError, Missing
# Template Class - represent compiled templates

# Sentinal value to ignore a value in a collection

SKIP_VALUE = object()
@dataclass(slots=True)
class JFTLTemplate(Template):

    main_entry: Evaluator
    config: JFTLConfig    

    def valid(self) -> bool:
        return True

#    macros: dict[str, Macro] = field(default_factory=dict)
#    functions: dict[str, Function] = field(default_factory=dict)
#    expr_engines: dict[str, ExprEngine] = field(default_factory=dict)

# Single compiled Statement 

# Runtime Objects

@dataclass
class JFTLConfig:
    # Default engine to use for '$=...'
    default_engine: str = ""

    plugins: dict[str, Any] = field(default_factory=dict)


# Shared environment - created at the root.
@dataclass
class Environment:

    # Template in use
    template: Template
    # Original input document
    input: Any
    # Destination - for streaming mode. only relevant if level = 0.
    to: Optional[TextIO] = None
    # Reference to top frame. Set later, as top frame and top environment point to each other.
    top: Frame | None = None

@dataclass
class Frame (Mapping):

    env: Environment 
    # Aliases as '_'
    current: Any
    # Aliases as '^'
    parent: Frame | None
    # From parent.level + 1, root = 0
    level: int

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
    
    def eval_bool(self, cond: Condition | Any, default_val=None) -> bool | None:
        if cond is None:
            return default_val
        result = cond.eval_bool(self)        
        return result
    
    def reset(self) -> None:
        self.env = None
        self.current = None
        self.parent = None
        self.level = None

    def __enter__(self):
        return self

    def __exit__(self):
        self.reset(self)

    @classmethod
    def top_frame(cls, template: Template, input: Any) -> Frame:
        env = Environment(template, input)
        top_vars = {
            "_missing": MISSING_VALUE,
            "_error": JFTLError(severity='ERROR', code='TEMPLATE-ERROR', message="Template Error"),
            "_skip" : SKIP_VALUE,
            "_input" : input,
            "_level" : 0,
            "_": input,
        }
        frame = cls(env=env, current=env.input, level=0, parent=None, vars=top_vars)
        env.top = frame
        top_vars["_top"] = frame
        top_vars["_global"] = top_vars
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
    
class Evaluator(ABC):
    @abstractmethod
    def eval(self, frame: Frame) -> Any | JFTLError | Missing : ...

class Condition(ABC):
    def eval_bool(self, frame: Frame) -> bool:
        result = self.eval(frame)
        if result is False or result is None or isinstance(result, Missing):
            return False
        return True

class Statement(Evaluator, Condition): ...

class Expression(Evaluator, Condition): ...

# Draft - NYI
class Macro(Evaluator, Condition): ...

# core.py (or wherever feels like the right shared home — maybe alongside Diagnostic/Error in template.py)

class Compiler(ABC):

    @abstractmethod
    def condition(self, source: str) -> tuple[Condition, Optional[list[JFTLError]]]: ...

    @abstractmethod
    def expression(self, source: str | dict) -> tuple[Expression, Optional[list[JFTLError]]]: ...

    @abstractmethod
    def statement(self, source: dict | str) -> tuple[Statement, Optional[list[JFTLError]]]: ...

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
