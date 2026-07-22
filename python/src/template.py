from typing import Any, ClassVar, Optional, TextIO, Literal
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field

@dataclass(kw_only=True)
class JFTLError(Exception):
    severity: Literal["ERROR", "WARNING", "INFO"]
    code: str
    message: str
    where: Optional[str] = None
    location: Optional[str] = None
    details: list["Exception"] = None
    value: Any = None
    hasValue: bool = False

@dataclass
class Missing():
    code: str = "MISSING"
    message: Optional[str] = None
    
    def __bool__(self):
        return False
    
    def __getattr__(self, name: str) -> "Missing":
        return self
    
    def __getitem__(self, key: Any) -> "Missing":
        return self

@dataclass
class Status:
    ok: bool
    # Most severe error (first error, or first Warning or first info)
    error: Optional[JFTLError] = None
    # TODO: Add statistics, runtime, ...

class Template(ABC):
    @abstractmethod
    def valid(): bool: ...

@dataclass
class Engine(ABC):
    _datasets: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def compile(self, source: str | dict, *, main_only: bool = False, **kwargs) -> tuple[Template, list[JFTLError]]: ...

    @abstractmethod
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[JFTLError]]: ...

    @abstractmethod
    def render(self, template: Template, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict[str, Any]] = None) -> tuple[Status, Any]: ...
        
    @abstractmethod
    def render_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    @abstractmethod
    def add_plugin(self, prefix: str, plugin: Any): ...

    # Execute a simple template (not wrapped in macros) as a top level item
    def compile_and_render(self, source: dict | Any, input: Any, *, main_only: bool = False) -> tuple[Status, Any, list[JFTLError]]:
        template, errors = self.compile(source, main_only = main_only)
        status, result = self.render(template, input) if template and template.valid else (None, None)
        return status, result, errors

    def add_dataset(self, name: str, data: Any) -> None:
        self._datasets[name] = data

def create_engine(*, no_plugins: bool = False, all_plugins: bool = False ) -> Engine:
    """strict=False (default) treats recoverable issues (over-'^' past root,
    unsafe navigation, etc.) as WARNING-severity and continues execution —
    useful during development when many such issues may surface at once.
    strict=True escalates the same conditions to ERROR and halts.
    Global per-engine for now; per-call override may be added later if needed."""
    from engine import JFTLEngine
    engine = JFTLEngine()

    if not no_plugins:
        import py_expr
        engine.add_plugin("py", py_expr.SimpleEvalPlugin())

        import navigation
        engine.add_plugin("nav", navigation.NavigationPlugin())

        if all_plugins :
            import py_run
            engine.add_plugin("pyeval", py_run.PyEvalPlugin())
            engine.add_plugin("pyrun", py_run.PyRunPlugin())
    
    # Those are not installed by default.

    return engine        


MISSING_VALUE = Missing(code="MISSING", message="Unspecific MISSING")
ERROR_VALUE = JFTLError(severity='ERROR', code='GENERIC-ERROR', message="Template Error")
