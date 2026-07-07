
# runtime.py
from dataclasses import dataclass
from typing import Any, Literal, Union

from core import Expression, Frame, Statement, CompileError
from template import Error, Missing

@dataclass
class Key:
    name: str

@dataclass
class Index:
    i: int

PathSegment = Union[Key, Index]

import re

_SEGMENT_RE = re.compile(r"""
    \.(?P<word>\w+)
  | \[(?P<index>-?[0-9]+)\]
  | \["(?P<dq>[^"]*)"\]
  | \['(?P<sq>[^']*)'\]
""", re.VERBOSE)

class NavigationExprNode(Statement, Expression):
    """Compiled 'sel:' path — parsed once at compile time, walked at eval time."""

    def __init__(self, path: str, where: str | None = None, start: Literal["current", "parent", "root", "vars"] = "current"):
        self._path = path
        self._where = where   # for diagnostics, e.g. "user.items[0].name"
        self._start = start
        self._segments = self._compile(path)

    def _compile(self, path_text: str) -> list[PathSegment]:

        segments: list[PathSegment] = []

        pos = 0

        for m in _SEGMENT_RE.finditer(path_text):
            if m.start() != pos:
                raise CompileError(Error(
                    code="INVALID_PATH", severity="ERROR", where=self._where, location=None,
                    message=f"unexpected text at position {pos} in {path_text!r}"))
            pos = m.end()

            if m.group("word") is not None:
                segments.append(Key(m.group("word")))
            elif m.group("index") is not None:
                segments.append(Index(int(m.group("index"))))
            elif m.group("dq") is not None:
                segments.append(Key(m.group("dq")))
            elif m.group("sq") is not None:
                segments.append(Key(m.group("sq")))

        if pos != len(path_text):
            raise CompileError(Error(
                code="INVALID_PATH", severity="ERROR", where=self._where, location=None,
                message=f"trailing unparsed text at position {pos} in {path_text!r}"))

        return segments

    def eval(self, frame: Frame) -> Any | Error | Missing:
        target = frame
        value: Any = frame.current
        if self._start == "root":
            value = frame.env.input
        elif self._start == "parent":
            value = frame.parent.current
        elif self._start == "vars":
            value = frame.vars

        traveled = "_"  # builds up the "location" string as we walk, for diagnostics

        for seg in self._segments:
            if isinstance(value, (Error, Missing)):
                return value  # already failed upstream — propagate, stop walking

            if isinstance(seg, Key):
                if isinstance(value, dict) and seg.name in value:
                    value = value[seg.name]
                else:
                    return Missing(code="MISSING", message=f"key {seg.name!r} not found",
                                    where=self._where, location=f"{traveled}.{seg.name}")
                traveled += f".{seg.name}"

            elif isinstance(seg, Index):
                if isinstance(value, list) and -len(value) <= seg.i < len(value):
                    value = value[seg.i]
                else:
                    return Missing(code="MISSING", message=f"index {seg.i} out of range",
                                    where=self._where, location=f"{traveled}[{seg.i}]")
                traveled += f"[{seg.i}]"

        return value

    def eval_bool(self, frame: Frame) -> bool | Error | Missing:
        result = self.eval(frame)
        if isinstance(result, (Error, Missing)):
            return result
        return result not in (False, None)