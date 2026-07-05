from typing import Any, Optional, TextIO, Literal
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Error:
    severity: Literal["ERROR", "WARNING", "INFO"]
    code: str
    message: str
    location: Optional[str]


@dataclass
class Status:
    ok: bool
    # Most severe error (first error, or first Warning or first info)
    error: Optional[Error] = None
    # TODO: Add statistics, runtime, ...

@dataclass
class Template(ABC):
    valid: bool



@dataclass
class Engine(ABC):
    _datasets: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def compile(self, source: dict) -> tuple[Template, list[Error]]: ...

    @abstractmethod
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    @abstractmethod
    def eval(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]: ...
        
    @abstractmethod
    def eval_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    def add_dataset(self, name: str, data: Any) -> None:
        self._datasets[name] = data
    

