
# runtime.py
from dataclasses import dataclass
from typing import Any, Union

from core import Frame, Expression, CompileError
from template import Error, Missing

@dataclass
class Key:
    name: str

@dataclass
class Index:
    i: int

@dataclass
class Up:
    pass  # one '^' step

PathSegment = Union[Key, Index, Up]

import re

_UP_RE = re.compile(r"^\^*")

_SEGMENT_RE = re.compile(r"""
    \.(?P<word>\w+)
  | \[(?P<index>-?[0-9]+)\]
  | \["(?P<dq>[^"]*)"\]
  | \['(?P<sq>[^']*)'\]
""", re.VERBOSE)

class NavigationExprEngine(Expression):
    """Compiled 'sel:' path — parsed once at compile time, walked at eval time."""

    def __init__(self, path: str, where: str | None = None):
        self._path = path
        self._where = where   # for diagnostics, e.g. "user.items[0].name"
        self._segments = self._compile(path)

    def _compile(self, path_text: str) -> list[PathSegment]:
        up_match = _UP_RE.match(path_text)
        up_count = len(up_match.group())
        rest = path_text[up_match.end():]

        segments: list[PathSegment] = [Up() for _ in range(up_count)]

        pos = 0

        for m in _SEGMENT_RE.finditer(rest):
            if m.start() != pos:
                raise CompileError(Error(
                    code="INVALID_PATH", severity="ERROR", where=self._where, location=None,
                    message=f"unexpected text at position {pos} in {rest!r}"))
            pos = m.end()

            if m.group("word") is not None:
                segments.append(Key(m.group("word")))
            elif m.group("index") is not None:
                segments.append(Index(int(m.group("index"))))
            elif m.group("dq") is not None:
                segments.append(Key(m.group("dq")))
            elif m.group("sq") is not None:
                segments.append(Key(m.group("sq")))

        if pos != len(rest):
            raise CompileError(Error(
                code="INVALID_PATH", severity="ERROR", where=self._where, location=None,
                message=f"trailing unparsed text at position {pos} in {rest!r}"))

        return segments

    def eval(self, frame: Frame) -> Any | Error | Missing:
        target = frame
        value: Any = frame.current
        traveled = "_"  # builds up the "location" string as we walk, for diagnostics

        for seg in self._segments:
            if isinstance(value, (Error, Missing)):
                return value  # already failed upstream — propagate, stop walking

            if isinstance(seg, Up):
                target = target.parent
                value = target.current
                traveled += ".^"
                continue

            if isinstance(seg, Key):
                if isinstance(value, dict) and seg.name in value:
                    value = value[seg.name]
                else:
                    return Missing(message=f"key {seg.name!r} not found",
                                    where=self._where, location=f"{traveled}.{seg.name}")
                traveled += f".{seg.name}"

            elif isinstance(seg, Index):
                if isinstance(value, list) and -len(value) <= seg.i < len(value):
                    value = value[seg.i]
                else:
                    return Missing(message=f"index {seg.i} out of range",
                                    where=self._where, location=f"{traveled}[{seg.i}]")
                traveled += f"[{seg.i}]"

        return value

    def eval_bool(self, frame: Frame) -> bool | Error | Missing:
        result = self.eval(frame)
        if isinstance(result, (Error, Missing)):
            return result
        return result not in (False, None) and not isinstance(result, Missing)