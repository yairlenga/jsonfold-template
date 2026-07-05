from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, TextIO
from abc import ABC, abstractmethod

from template import Template, Error
# Template Class - represent compiled templates

@dataclass(slots=True)
class JFTLTemplate(Template):
    main: Statement
#    macros: dict[str, Macro] = field(default_factory=dict)
#    functions: dict[str, Function] = field(default_factory=dict)
#    expr_engines: dict[str, ExprEngine] = field(default_factory=dict)

# Single compiled Statement 

class Statement(ABC):
    @abstractmethod
    def eval(self, frame: Frame) -> Any | Error : ...

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

# Draft - NIY
class ExprEngine:
    def eval(self, frame: Frame) -> Any | Error: ...
    def eval_bool(self, frame: Frame) -> Any | Error: ...

# Draft - NYI
class Macro(ABC):
    @abstractmethod
    def eval(self, frame: Frame, args: dict[str, Any]) -> Any | Error: ...
