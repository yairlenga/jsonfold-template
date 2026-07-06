from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, TextIO
from abc import ABC, abstractmethod

from template import Template, Error, Missing
# Template Class - represent compiled templates

@dataclass(slots=True)
class JFTLTemplate(Template):
    main: Statement
#    macros: dict[str, Macro] = field(default_factory=dict)
#    functions: dict[str, Function] = field(default_factory=dict)
#    expr_engines: dict[str, ExprEngine] = field(default_factory=dict)

# Single compiled Statement 

# Runtime Objects


# Shared environment - created at the root.
@dataclass
class Environment:
    # Template in use
    template: Template
    # Original input document
    input: Any
    # Destination - for streaming mode. only relevant if level = 0.
    to: Optional[TextIO]
    # Reference to top frame.
    top: Frame

@dataclass
class Frame:

    env: Environment 
    # Aliases as '_'
    current: Any
    # Aliases as '^'
    parent: Frame
    # From parent.level + 1, root = 0
    level: int

    # User defined variables in the CURRENT frame    
    vars: dict[str, Any] = field(default_factory=dict)
    # Cached value, including inherited, calculated, ...
    _cache:  dict[str, Any] = field(default_factory=dict)

    def eval_value(self, expr: Evaluator | Any) -> Any:

        # if it can be evaluated, then use the current frame
        result = expr.eval(self) if isinstance(expr, Evaluator) else expr
        return result        
    
    def eval_bool(self, cond: Condition | Any, default_val) -> bool:
        result = cond.eval_bool(self) if isinstance(cond, Condition) else default_val
        return result

        

# Draft - NIY

class Evaluator(ABC):
    @abstractmethod
    def eval(self, frame: Frame) -> Any | Error | Missing : ...

class Condition(ABC):
    @abstractmethod
    def eval_bool(self, frame: Frame) -> bool: ...

class Statement(Evaluator): ...

class Expression(Evaluator, Condition): ...

# Draft - NYI
class Macro(Evaluator): ...

# core.py (or wherever feels like the right shared home — maybe alongside Diagnostic/Error in template.py)

class Compiler(ABC):

    @abstractmethod
    def condition(self, compiler: Compiler, source: str) -> tuple[Condition, list[Error]]: ...

    @abstractmethod
    def expression(self, compiler: Compiler, source: str | dict) -> tuple[Expression, list[Error]]: ...

    @abstractmethod
    def statement(self, compiler: Compiler, source: dict | str) -> tuple[Statement, list[Error]]: ...

class CompileError(Exception):
    """Raised for any defect discovered while compiling a template.
    Carries the actual Error to report — no separate/duplicate fields.
    Caught by the compiler and appended directly to compile()'s error list."""
    def __init__(self, error: "Error"):
        super().__init__(error.message)
        self.error = error