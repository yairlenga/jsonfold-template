from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Any, Callable, Optional, TextIO
import typing

# Template Class - represent compiled templates

@dataclass(slots=True)
class Template:
    main: Statement
    macros: dict[str, Macro] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    valid: bool = False

# Single compiled Statement 
@dataclass
class Statement:
    def execute(self, env: Environment) -> Optional[Any]: ...

# Execution environment
class Engine:
    # Additional functions.
    functions: dict[str, Callable]

    # Available expression engines (in addition to default CEL)
    expr_engines: dict[str, ExprEngine]

    # provided globals, merged into data context
    data: dict[str, Any]

    def compile(self, source: dict) -> tuple[Template, list[Error]]: ...

    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    def eval(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]: ...
        
    def eval_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    # Execution result
@dataclass
class Status:
    ok: bool
    # Most severe error (first error, or first Warning or first info)
    error: Optional[Error] = None
    # TODO: Add statistics, runtime, ...


class ExprEngine:
    def eval(self, env: Environment) -> Any | Error: ...
    def eval_bool(self, env: Environment) -> Any | Error: ...

class Macro:
    def eval(self, args: dict[str, Any]) -> Any | Error: ...

@dataclass
class Error:
    severity: Literal["ERROR", "WARNING", "INFO"]
    code: str
    message: str
    location: Optional[str]

@dataclass
class Context:
    # Aliases as '_'
    current: Any
    # Aliases as '^'
    parent: Context
    # From parent.level + 1, root = 0
    level: int

    # Copied from parent
    template: Template
    input: Any
    top: Context
    data: dict[str, Any] 
    # Destination - for streaming mode. only relevant if level = 0.
    to: Optional[TextIO]

@dataclass
class Environment:
    state: Context
    # User defined variables in the CURRENT frame    
    vars: dict[str, Any] = field(default_factory=dict)
    # Cached value, including inherited, calculated, ...
    cache:  dict[str, Any] = field(default_factory=dict)

list(typing.get_type_hints(obj)
     for obj in globals().values()
     if isinstance(obj, type) and obj.__module__ == __name__)