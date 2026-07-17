from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Any, Optional, TextIO
from abc import ABC, abstractmethod

from template import MISSING_VALUE, Template, Error, Missing
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
class Frame:

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

    def eval_value(self, expr: Evaluator | Any, default_val=None) -> Any:
        if expr is None:
            return default_val

        # if it can be evaluated, then use the current frame
        result = expr.eval(self) if isinstance(expr, Evaluator) else expr
        return result        
    
    def eval_bool(self, cond: Condition | Any, default_val=None) -> bool:
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
            "_error": Error(severity='ERROR', code='TEMPLATE-ERROR', message="Template Error"),
            "_skip" : SKIP_VALUE,
        }
        frame = cls(env=env, current=env.input, level=0, parent=None, vars=top_vars)
        env.top = frame
        return frame

    def child_frame(self, vars: dict[str, Any] = {} ) -> Frame:
        return replace(
            self,
            parent = self,
            level = self.level+1,
            vars = vars,
            _cache = {},
        )
    
    def lookup_var(self, name: str) -> Any:
        """Search this frame, then parent, then parent's parent, ...
        for `name` in `vars`. Caches the result (or MISSING) at every
        frame walked through, so a repeated lookup from the same frame
        is O(1) afterward."""
        if name in self._cache:
            return self._cache[name]

        frame = self
#        chain = []
        while frame is not None:
            if name in frame.vars:
                value = frame.vars[name]
#                for f in chain:
#                    f._cache[name] = value
                if frame != self:
                    self._cache[name] = value
                return value
#            chain.append(frame)
            frame = frame.parent

#        for f in chain:
#            f._cache[name] = MISSING_VALUE
        return MISSING_VALUE
    

 

# Draft - NIY

class Evaluator(ABC):
    @abstractmethod
    def eval(self, frame: Frame) -> Any | Error | Missing : ...

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
    def condition(self, source: str) -> tuple[Condition, Optional[list[Error]]]: ...

    @abstractmethod
    def expression(self, source: str | dict) -> tuple[Expression, Optional[list[Error]]]: ...

    @abstractmethod
    def statement(self, source: dict | str) -> tuple[Statement, Optional[list[Error]]]: ...

class CompileError(Exception):
    """Raised for any defect discovered while compiling a template.
    Carries the actual Error to report — no separate/duplicate fields.
    Caught by the compiler and appended directly to compile()'s error list."""
    def __init__(self, error: Error):
        super().__init__(error.message)
        self.error = error



class RenderError(Exception):
    def __init__(self, error: Error):
        super().__init__(error.message)
        self.error = error
