from typing import Any, Callable, Optional, TextIO
from pathlib import Path

from template import Template, Status, Error, Engine



class JFTLEngine(Engine):

    def compile(self, source: dict) -> tuple[Template, list[Error]]: ...

    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    def eval(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]: ...
        
    def eval_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...
