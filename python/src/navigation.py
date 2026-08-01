
# runtime.py
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Union, cast

from model import COMPILE_DOC, RUNTIME_LIST_LIKE, CompileError, CompilerPlugin, Evaluator, RuntimeContext, StatementCompiler
from template import MISSING_VALUE, JFTLNotice, Missing

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

class NavigationStatement(Evaluator):
    """Compiled 'sel:' path — parsed once at compile time, walked at eval time."""

    def __init__(self, path: str, start: Literal["_data", "_parent.data", "_input"] | str= "_data", where: str = "" ):
        super().__init__(where, path)
        self._path = path
        self.where = where   # for diagnostics, e.g. "user.items[0].name"
        self._start = start
        self._segments = self._compile(path)

    def _compile(self, path_text: str) -> list[PathSegment]:

        segments: list[PathSegment] = []

        pos = 0

        for m in _SEGMENT_RE.finditer(path_text):
            if m.start() != pos:
                raise CompileError(JFTLNotice(
                    code="INVALID_PATH", where=self.where, location=None,
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
            raise CompileError(JFTLNotice(
                code="INVALID_PATH",where=self.where, location=None,
                message=f"trailing unparsed text at position {pos} in {path_text!r}"))

        return segments

    def eval(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
        value = None
        start = self._start
        if start == "_data":
            value = ctx.current
        elif start == "_frame":
            value = ctx
        elif self._start == "_input":
            value = ctx.env.input
        elif self._start == "_parent._data":
            value = cast(RuntimeContext, ctx.parent).current
        else:
            value = ctx.lookup_var(self._start)

        traveled = "_"  # builds up the "location" string as we walk, for diagnostics

        for seg in self._segments:
            if isinstance(value, (JFTLNotice, Missing)):
                return value  # already failed upstream — propagate, stop walking

            if isinstance(seg, Key):
                if isinstance(value, Mapping) and seg.name in value:
                    value = value[seg.name]
                else:
                    return MISSING_VALUE
                traveled += f".{seg.name}"

            elif isinstance(seg, Index):
                if isinstance(value, RUNTIME_LIST_LIKE) and -len(value) <= seg.i < len(value):
                    value = value[seg.i]
                else:
                    return MISSING_VALUE
                traveled += f"[{seg.i}]"

            elif isinstance(seg, Var): # pyright: ignore[reportUnnecessaryIsInstance]
                key = ctx.lookup_var(seg.name)
                if isinstance(key, Missing):
                    return key
                elif isinstance(key, str) and isinstance(value, dict) and key in value:
                    value = value[key]
                elif isinstance(key, int) and isinstance(value, RUNTIME_LIST_LIKE) and -len(value) <= key < len(value):
                    value = value[key]
                else:
                    return MISSING_VALUE
                traveled += f".{key}"

        return value


NAV_RE_STR = r"""
    (?P<start> \$ | \$\^ | \$< | \$% | \$(?P<vars>\w+ ) )
    (?P<segments> (\[.* | \..* )? )
"""
class NavigationCompiler(StatementCompiler):

    _NAV_RE = re.compile("^" + NAV_RE_STR + "$", re.VERBOSE)

    def parse_nav(self, m: re.Match[str], where) -> NavigationStatement | JFTLNotice:

        start = None
        head = m.group("start")
        segments = m.group("segments")
        if head == "$":
            start = "_data"
        elif head == "$^":
            start = "_input"
        elif head == "$%":
            start = "_frame"
        elif head == "$<":
            start = "_parent._data"
        elif (vars := m.group("vars")) != "":
            # Convert $foo.bar to .foo.bar, starting with implied "_.vars"
            start = vars

        if not start:
            return JFTLNotice(code="BAD-NAV-SYNTAX", message=f"Unknown start: '${head}", where=where)
        
        expr = NavigationStatement(segments, start=start, where=where)
        return expr

    def parse(self, source, where):

        m = self._NAV_RE.match(source)
        if not m:
            return JFTLNotice(code="BAD-NAV-SYNTAX", message=f"Unknown navigation: '${source}", where=where)
        
        expr = self.parse_nav(m, where)
        if not expr:
            return JFTLNotice(code="BAD-NAV-EXPR", message=f"Unknown navigation: '${source}", where=where)
        
        return expr

    def compile_str(self, source: Any | str, where: str = "") -> COMPILE_DOC:
        assert isinstance(source, str)
        expr = self.parse(source, where)
        return expr
    

class NavigationPlugin(CompilerPlugin):
    def createCompiler(self, DocCompiler) -> StatementCompiler:
        return NavigationCompiler(DocCompiler)
