from typing import Any, Optional, TextIO, Literal, Union
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
import json

JSONValue = Union[
    None, bool, int, float, str,
    list["JSONValue"],
    dict[str, "JSONValue"],
]

class _NoValueType:
    def __repr__(self) -> str:
        return "NO_VALUE"

NO_VALUE = _NoValueType()

@dataclass(kw_only=True)
class JFTLError():
    severity: Literal["ERROR", "WARNING", "INFO", "DEBUG"] = "ERROR"
    phase: Optional[Literal["COMPILE", "RENDER"]] = None
    code: str
    message: str
    where: Optional[str] = None                  # Location in the template
    location: Optional[str] = None               # Location in the data tree
    details: Optional[list["JFTLError"]] = None
    value: Any = NO_VALUE

ERROR_VALUE = JFTLError(severity='ERROR', code='GENERIC-ERROR', message="Template Error")

class JFTLException(Exception):
    def __init__(self, error: JFTLError):
        super().__init__(error.message)
        self.error = error

@dataclass
class Missing():
    code: str = "MISSING"
    message: Optional[str] = None
    
    def __bool__(self):
        return False
    
    def __getitem__(self, key: Any) -> "Missing":
        return self
    
MISSING_VALUE = Missing(code="MISSING", message="Unspecific MISSING")
SKIP_VALUE = Missing(code="SKIP", message= "Skip entry sentinel")


@dataclass
class JFTLStatus:
    ok: bool
    # Most severe error (first error, or first Warning or first info)
    errors: Optional[JFTLError] = None
    # TODO: Add statistics, runtime, ...

class Template(ABC):
    valid: bool
    error: Optional[JFTLError]

@dataclass
class Engine(ABC):
    _datasets: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def compile(self, source: str | dict, *, main_only: bool = False, **kwargs) -> tuple[Template, list[JFTLError]]: ...

    @abstractmethod
    def compile_from(self, source: str | Path | TextIO, **kwargs ) -> tuple[Template, list[JFTLError]]:
        if isinstance(source, TextIO):
            body = json.load(source)
        elif isinstance(source, (Path, str)):
            with open(source, "r") as fp:
                body = json.load(fp)
        else:
            raise TypeError(f"expected string, Path of TextIO, got {type(value).name}")
        return self.compile(body, *kwargs)

    @abstractmethod
    def render(self, template: Template, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict[str, Any]] = None) -> tuple[Any, JFTLStatus]: ...
        
    @abstractmethod
    def render_to(self, output: TextIO, template: Template, input: Any, **kwargs) -> JFTLStatus:
        result, status = self.render(template, input, **kwargs)
        if not status:
            if isinstance(output, TextIO):
                json.dump(result, output)
            elif isinstance(output, (Path, str)):
                with open(output, "w") as fp:
                    json.dump(result)
            else:
                raise TypeError(f"expected string, Path of TextIO, got {type(value).name}")

        return status

    @abstractmethod
    def add_plugin(self, prefix: str, plugin: Any): ...

    # Execute a simple template (potentially, not wrapped in macros) as a top level item
    def compile_and_render(self, source: dict | Any, input: Any, *, main_only: bool = False) -> tuple[Any, JFTLStatus, list[JFTLError]]:
        template, compile_errors = self.compile(source, main_only = main_only)
        result = None
        if template and template.valid:
            result, render_status = self.render(template, input)
        else:
            render_status = JFTLStatus(False, JFTLError(code="COMPILE_ERRORS", message="Error compiling template"))

        return result, render_status, compile_errors

    def add_dataset(self, name: str, data: Any) -> None:
        self._datasets[name] = data

def create_engine(*, no_plugins: bool = False, all_plugins: bool = False ) -> Engine:
    """Creates a JFTLEngine with default plugins registered.

    By default, registers the always-safe 'py' (simpleeval) and 'nav'
    (navigation) plugins. Pass all_plugins=True to also register the
    trusted 'pyeval'/'pyrun' tiers (full Python eval, no sandboxing —
    only enable for trusted templates). Pass no_plugins=True to skip
    even the default plugins, for callers who want to register their
    own set from scratch via add_plugin().
    """
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


