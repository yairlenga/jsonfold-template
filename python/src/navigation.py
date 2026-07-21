
# runtime.py
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Optional, Sequence, Union

from core import Compiler, Condition, Expression, Frame, Statement, CompileError
from template import MISSING_VALUE, JFTLError, Missing

@dataclass
class Key:
    name: str

@dataclass
class Index:
    i: int

@dataclass
class Var:
    name: str

PathSegment = Union[Key, Index | Var]

import re

_SEGMENT_RE = re.compile(r"""
    \.(?P<word>\w+)
  | \[(?P<index>-?[0-9]+)\]
  | \["(?P<dq>[^"]*)"\]
  | \['(?P<sq>[^']*)'\]
  | \[\$(?P<var>\w+)\]
""", re.VERBOSE)

class NavigationStatement(Statement, Expression):
    """Compiled 'sel:' path — parsed once at compile time, walked at eval time."""

    def __init__(self, path: str, where: str | None = None, start: Literal["_current", "_parent.current", "_input"] | str= "_current"):
        self._path = path
        self._where = where   # for diagnostics, e.g. "user.items[0].name"
        self._start = start
        self._segments = self._compile(path)

    def _compile(self, path_text: str) -> list[PathSegment]:

        segments: list[PathSegment] = []

        pos = 0

        for m in _SEGMENT_RE.finditer(path_text):
            if m.start() != pos:
                raise CompileError(JFTLError(
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
            elif m.group("var") is not None:
                segments.append(Var(m.group("var")))

        if pos != len(path_text):
            raise CompileError(JFTLError(
                code="INVALID_PATH", severity="ERROR", where=self._where, location=None,
                message=f"trailing unparsed text at position {pos} in {path_text!r}"))

        return segments

    def eval(self, frame: Frame) -> Any | JFTLError | Missing:
        value: Any = frame.current
        if self._start == "_current":
            value = frame.current
        elif self._start == "_input":
            value = frame.env.input
        elif self._start == "_parent.current":
            value = frame.parent.current
        else:
            value = frame.lookup_var(self._start)

        traveled = "_"  # builds up the "location" string as we walk, for diagnostics

        for seg in self._segments:
            if isinstance(value, (JFTLError, Missing)):
                return value  # already failed upstream — propagate, stop walking

            if isinstance(seg, Key):
                if isinstance(value, Mapping) and seg.name in value:
                    value = value[seg.name]
                else:
                    return MISSING_VALUE
                traveled += f".{seg.name}"

            elif isinstance(seg, Index):
                if isinstance(value, list) and -len(value) <= seg.i < len(value):
                    value = value[seg.i]
                else:
                    return MISSING_VALUE
                traveled += f"[{seg.i}]"

            elif isinstance(seg, Var):
                key = frame.lookup_var(seg.name)
                if isinstance(key, Missing):
                    return key
                elif isinstance(key, str) and isinstance(value, dict) and key in value:
                    value = value[key]
                elif isinstance(key, int) and isinstance(value, list) and -len(value) <= key < len(value):
                    value = value[key]
                else:
                    return MISSING_VALUE
                traveled += f".{key}"

        return value

    def eval_bool(self, frame: Frame) -> bool | JFTLError | Missing:
        result = self.eval(frame)
        if isinstance(result, (JFTLError, Missing)):
            return result
        return result not in (False, None)


import re
NAV_RE_STR = r"""
    (?P<start> \$ | \$\^ | \$< | \$(?P<vars>\w+ ) )
    (?P<segments> (\[.* | \..* )? )
"""
class NavigationPlugin(Compiler):

    _NAV_RE = re.compile("^" + NAV_RE_STR + "$", re.VERBOSE)

    def parse_nav(self, m: re.Match[str], where) -> NavigationStatement:

        start = None
        head = m.group("start")
        segments = m.group("segments")
        if head == "$":
            start = "_current"
        elif head == "$^":
            start = "_input"
        elif head == "$<":
            start = "_parent.current"
        elif (vars := m.group("vars")) != "":
            # Convert $foo.bar to .foo.bar, starting with implied "_.vars"
            start = vars

        if not start:
            return None
        
        engine = NavigationStatement(segments, start=start, where=where)
        return engine

    def parse(self, source, where):

        m = self._NAV_RE.match(source)
        if not m:
            raise CompileError(JFTLError(severity="ERROR", code="BAD-NAV-SYNTAX", message=f"Unknown navigation: '${source}", where=where))
        
        node = self.parse_nav(m, where)
        if not node:
            raise CompileError(JFTLError(severity="ERROR", code="BAD-NAV-EXPR", message=f"Unknown navigation: '${source}", where=where))      
        
        return node

    def condition(self, source: str) -> tuple[Condition, Optional[list[JFTLError]]]:
        assert isinstance(source, str)
        return self.parse(source, None), None
    
    def expression(self, source: str | dict) -> tuple[Expression, Optional[list[JFTLError]]]:
        assert isinstance(source, str)
        return self.parse(source, None), None

    def statement(self, source: dict | str) -> tuple[Statement, Optional[list[JFTLError]]]:
        assert isinstance(source, str)
        return self.parse(source, None), None
