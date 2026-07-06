from typing import Any, ClassVar, Optional, TextIO, Literal
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field

@dataclass(kw_only=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    where: Optional[str] = None
    location: Optional[str] = None
    details: list["Diagnostic"] = None
    value: Any = None
    hasValue: bool = False

@dataclass
class Error(Diagnostic):
    severity: Literal["ERROR", "WARNING", "INFO"]

@dataclass
class Missing(Diagnostic):
    severity: ClassVar[Literal["MISSING"]] = "MISSING"
    
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
    error: Optional[Error] = None
    # TODO: Add statistics, runtime, ...

class Template(ABC):
    @abstractmethod
    def valid(): bool: ...


@dataclass
class Engine(ABC):
    _datasets: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def compile(self, source: str | dict, *, main_only: bool = False, **kwargs) -> tuple[Template, list[Error]]: ...

    @abstractmethod
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    @abstractmethod
    def render(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]: ...
        
    @abstractmethod
    def render_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    # Execute a simple template (not wrapped in macros) as a top level item
    def compile_and_render(self, source: dict | Any, input: Any, *, main_only: bool = False) -> tuple[Status, Any, list[Error]]:
        template, errors = self.compile(source, main_only = main_only)
        status, result = self.render(template, input) if template and template.valid else (None, None)
        return status, result, errors

    def add_dataset(self, name: str, data: Any) -> None:
        self._datasets[name] = data

def create_engine(*, strict: bool = True) -> Engine:
    """strict=False (default) treats recoverable issues (over-'^' past root,
    unsafe navigation, etc.) as WARNING-severity and continues execution —
    useful during development when many such issues may surface at once.
    strict=True escalates the same conditions to ERROR and halts.
    Global per-engine for now; per-call override may be added later if needed."""
    from engine import JFTLEngine
    return JFTLEngine()

MISSING_VALUE = Missing(code="MISSING", message="Unspecific MISSING", where=None, location=None)
