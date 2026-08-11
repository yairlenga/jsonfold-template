from enum import StrEnum
from io import TextIOBase
from typing import Any, Callable, Final, Iterable, Optional, TextIO, Literal
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
import json

class NoticeSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    MISSING = "MISSING"
    FATAL = "FATAL"

    # required parameter: code, message wnere where (source loc).
    # Compile time: may be details (multiple errors same statement)
    # runtime: location in the data (sometimes)
    # finish: location of the bad data element.

@dataclass(frozen=True, kw_only=True)
class JFTLNotice():
    severity: NoticeSeverity = NoticeSeverity.ERROR
    phase: Optional[Literal["COMPILE", "RENDER", "FINISH"]] = None
    code: str                                    # Code: "MODULE-CODE"
    message: str
    where: str = ""                              # Location in the template
    location: Optional[str] = None               # Location in the data tree (Runtime Only)
    details: Optional[list["JFTLNotice"]] = None



ERROR_VALUE = JFTLNotice(code="GENERIC-ERROR", message="Unspecific Error")

class JFTLError(Exception):
    def __init__(self, notice: JFTLNotice):
        super().__init__(notice.message)
        self.notice = notice

@dataclass(slots=True,frozen=True)
class Missing():
    code: str = "MISSING"
    message: Optional[str] = None
    
    def __bool__(self):
        return False
    
    def __getitem__(self, key: Any) -> "Missing":
        return self
    
    def get(self, key, default=None):
        return self
    
MISSING_VALUE : Final = Missing(code="MISSING", message="Unspecific MISSING")

@dataclass
class RenderStatus:
    ok: bool
    # Most severe error (first error, or first Warning or first info)
    notice: Optional[JFTLNotice] = None
    # TODO: Add statistics, runtime, ...
    error_count: int = 0
    # Number of evaluation
    eval_count : int = 0

class Template(ABC):
    valid: bool

plugin_registry: dict[str, Callable] = {}

# Registry of default plugins. Each one will be called to get
# an instance of the plugin if/when used in an engine.
def add_default_plugin(name: str, plugin: Callable, replace: Optional[bool] = False) -> None:
    registered = name in plugin_registry
    if replace is not None and replace != registered:
        raise JFTLError( JFTLNotice(code="PLUGIN-REGISTRY", message=f"Error registering plugin {name} (registered={registered}, replace={replace}"))
    elif not isinstance(plugin, Callable): # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"Expecting callable, got {type(plugin)}")
    plugin_registry[name] = plugin

@dataclass(slots=True)
class Engine(ABC):
    _datasets: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def compile(self, source: str | dict, *, main_only: bool = False, filename: str = "", **kwargs) -> tuple[Template, list[JFTLNotice]]: ...

    def compile_from(self, source: str | Path | TextIO, **kwargs ) -> tuple[Template, list[JFTLNotice]]:
        if isinstance(source, TextIOBase):
            body = json.load(source)
        elif isinstance(source, (Path, str)):
            with open(source, "r", encoding="utf-8") as fp:
                body = json.load(fp)
        else:
            raise TypeError(f"expected string, Path of TextIO, got {type(source)}")
        return self.compile(body, **kwargs)

    @abstractmethod
    def render(self, template: Template, input: Any, *, entry: Optional[str] = None, datasets: Optional[dict[str, Any]] = None, **kwargs) -> tuple[Any, RenderStatus]: ...
        
    def render_to(self, output: TextIO | Path | str, template: Template, input: Any, **kwargs) -> RenderStatus:
        result, status = self.render(template, input, **kwargs)
        if status.ok:
            if isinstance(output, TextIOBase):
                json.dump(result, output)
            elif isinstance(output, (Path, str)):
                with open(output, "w") as fp:
                    json.dump(result, fp)
            else:
                raise TypeError(f"expected string, Path of TextIO, got {type(output)}")

        return status

    @abstractmethod
    def add_plugin(self, prefix: str, plugin: Any): ...

    # Execute a simple template (potentially, not wrapped in macros) as a top level item
    def compile_and_render(self, source: dict | Any, input: Any, *, main_only: bool = False) -> tuple[Any, RenderStatus, list[JFTLNotice]]:
        template, compile_errors = self.compile(source, main_only = main_only)
        result = None
        if template and template.valid:
            result, render_status = self.render(template, input)
        else:
            render_status = RenderStatus(False, notice=JFTLNotice(code="COMPILE_ERRORS", message="Error compiling template"))

        return result, render_status, compile_errors

    def add_dataset(self, name: str, data: Any) -> None:
        self._datasets[name] = data

def create_engine(*, plugins: Optional[bool | Iterable]= None, all_plugins: bool = False ) -> Engine:
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

    if plugins is None:
        plugins = plugin_registry.keys()

    if plugins is not False:
        import py_expr
        engine.add_plugin("py", py_expr.SimpleEvalPlugin())

        import navigation
        engine.add_plugin("nav", navigation.NavigationPlugin())
        engine.add_plugin("strict", navigation.StrictNavPlugin())

        import logic
        engine.add_plugin("logic", logic.LoginPlugin())

        import transform
        for transform_id, transform_class in transform.default_plugins.items():
            engine.add_plugin(transform_id, transform_class())

        if isinstance(plugins, Iterable):
            for plugin in plugins:
                engine.add_plugin(plugin, plugin_registry[plugin])

        if all_plugins :
            import py_run
            engine.add_plugin("pyeval", py_run.PyEvalPlugin())
            engine.add_plugin("pyrun", py_run.PyRunPlugin())


    # Those are not installed by default.

    return engine        


