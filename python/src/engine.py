from typing import Any, Optional, TextIO
from pathlib import Path
from dataclasses import dataclass

from template import Template, Status, Error, Engine, Missing
from core import Statement, Frame
from runtime import NavigationExprEngine

class JFTLEngine(Engine):

    def compile(self, source: str, where: str = "") -> Statement:
        return self._compile(source, where)
    
    def compile_from(self, source: str | Path | TextIO ) -> tuple[Template, list[Error]]: ...

    def compile_item(self, source: Any, where: str = "") -> tuple[Status, any]:
        return self._compile(source, where)

    def render(self, template: Template, input: Any, *, entry: Optional[str] = None) -> tuple[Status, Any]: ...
        
    def render_to(self, output: TextIO, template: Template, input: Any, *, entry: Optional[str]= None) -> Status: ...

    def _compile(self, source: Any, where: str = "") -> Statement:
        if isinstance(source, dict):
            entries = {k: self._compile(v, where=f"{where}.{k}") for k, v in source.items()}
            return ObjectStatement(entries)

        if isinstance(source, list):
            items = [self._compile(v, where=f"{where}[{i}]") for i, v in enumerate(source)]
            return ArrayStatement(items)

        if isinstance(source, str) and source.startswith(EXPR_PREFIX):
            path_text = source[1:]   # strip just "$", keep the "." — matches grammar directly
            engine = NavigationExprEngine(path_text, where=where)
            return PathStatement(engine)

        return Literal(source)

EXPR_PREFIX = "$."  # e.g. "$.user.name" — later: other prefixes (e.g. $cel., $^) route to other engines

@dataclass
class Literal(Statement):
    value: Any

    def eval(self, frame: Frame) -> Any | Error | Missing:
        return self.value


@dataclass
class PathStatement(Statement):
    engine: NavigationExprEngine

    def eval(self, frame: Frame) -> Any | Error | Missing:
        return self.engine.eval(frame)


@dataclass
class ObjectStatement(Statement):
    entries: dict[str, Statement]

    def eval(self, frame: Frame) -> Any | Error | Missing:
        result = {}
        for key, stmt in self.entries.items():
            value = stmt.eval(frame)
            if isinstance(value, Error):
                return value
            if isinstance(value, Missing):
                continue  # silently dropped from objects, per locked sentinel rules
            result[key] = value
        return result


@dataclass
class ArrayStatement(Statement):
    items: list[Statement]

    def eval(self, frame: Frame) -> Any | Error | Missing:
        result = []
        for stmt in self.items:
            value = stmt.eval(frame)
            if isinstance(value, Error):
                return value
            result.append(None if isinstance(value, Missing) else value)  # kept as null in arrays
        return result

