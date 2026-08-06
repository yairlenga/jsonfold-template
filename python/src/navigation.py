
# runtime.py
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Literal, Union, cast

from model import COMPILE_DOC, RUNTIME_DOC, RUNTIME_LIST_LIKE, RUNTIME_NULL_LIKE, CompileError, CompilerPlugin, DocCompiler, Evaluator, RuntimeContext, StatementCompiler
from template import MISSING_VALUE, JFTLNotice, Missing

if callable( _ := globals().get("profile")):
    _profile = cast(Callable, _)
else:
    def _profile(func): return func

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


@dataclass(kw_only=True)
class VariableStatement(Evaluator):
    name: str

    @_profile
    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        return ctx.lookup_var(self.name)

    # TODO: Profile, and decide if useful.
    @_profile
    def eval_inline(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        name = self.name
        if name in ctx.vars:
            return ctx.vars[name]
        return ctx.lookup_var(name)

class NavigationStatement(Evaluator):
    """Compiled 'sel:' path — parsed once at compile time, walked at eval time."""

    def __init__(self, where: str, source_code: str, *,
                 start: Literal["_data", "_frame", "_parent.data", "_input"] | str, 
                 segments: list[PathSegment],
                 strict: bool
                 ):
        super().__init__(where, source_code)
        self.where = where   # for diagnostics, e.g. "user.items[0].name"
        self._start = start
        self._segments = segments
        self._strict = strict


    
    @_profile
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
            if not ctx.parent:
                return JFTLNotice(code="NAV-NO-PARENT", message="Using '$%' is not valid at the top frame")
            value = ctx.parent.current
        else:
            value = ctx.lookup_var(self._start)

        traveled = "_"  # builds up the "location" string as we walk, for diagnostics

        for seg in self._segments:
            if isinstance(value, (JFTLNotice, Missing)):
                return value  # already failed upstream — propagate, stop walking

            if isinstance(seg, Key):
                value = (
                    value.get(seg.name, MISSING_VALUE) if isinstance(value, Mapping)
                    else JFTLNotice(code="NAV-NOT-OBJECT", message=f"string keys can only be used on objects/null, at {type(value)}") if self._strict
                    else MISSING_VALUE
                )
                traveled += f".{seg.name}"

            elif isinstance(seg, Index):
                value = (
                    value[seg.i] if isinstance(value, RUNTIME_LIST_LIKE) and -len(value) <= seg.i < len(value)
                    else JFTLNotice(code="NAV-NOT-ARRAY", message=f"integer indices can only be used on array/null, at {type(value)}") if self._strict
                    else MISSING_VALUE
                )
                traveled += f"[{seg.i}]"

            elif isinstance(seg, Var): # pyright: ignore[reportUnnecessaryIsInstance]
                key = ctx.lookup_var(seg.name)
                if isinstance(key, str):
                    value = (
                        value.get(key, MISSING_VALUE) if isinstance(value, Mapping)
                        else JFTLNotice(code="NAV-VAR-STR", message=f"string key '{str}` can only be used on objects/null, got {type(value)}") if self._strict
                        else MISSING_VALUE
                    )
                    traveled += f'.["{key}"]'
                elif isinstance(key, int) and not isinstance(key, bool) and isinstance(value, RUNTIME_LIST_LIKE) and -len(value) <= key < len(value):
                    value = (
                        value[key] if -len(value) <= key < len(value)
                        else JFTLNotice(code="NAV-NOT-ARRAY", message=f"integer index '{int}` can only be used on array/null, got {type(value)}") if self._strict
                        else MISSING_VALUE
                    )
                    traveled += f"[{key}]"
                elif not self._strict or isinstance(key, RUNTIME_NULL_LIKE):
                    value = MISSING_VALUE
                else:
                    value = JFTLNotice(code="NAV-VAR-KEY", message=f"Key type '{type(key)}' can not be used to access elements of type {type(value)}")


        return value


NAV_RE_STR = r"""
    (?P<start> \$ | \$\^ | \$< | \$% | \$(?P<vars>\w+ ) )
    (?P<segments> (\[.* | \..* )? )
"""

@dataclass
class NavigationCompiler(StatementCompiler):

    strict: bool = False
    _NAV_RE = re.compile("^" + NAV_RE_STR + "$", re.VERBOSE)

    @staticmethod
    def _parse_segments(where: str, path_text: str) -> list[PathSegment]:

        segments: list[PathSegment] = []

        pos = 0

        for m in _SEGMENT_RE.finditer(path_text):
            if m.start() != pos:
                raise CompileError(JFTLNotice(
                    code="INVALID_PATH", where=where, location=None,
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
                code="INVALID_PATH",where=where, location=None,
                message=f"trailing unparsed text at position {pos} in {path_text!r}"))

        return segments    

    @classmethod
    def parse_nav(cls, m: re.Match[str], where, *, strict: bool = False) -> NavigationStatement | VariableStatement | JFTLNotice:

        start_part = m.group("start")
        segments_part = m.group("segments")
        start = ""
        if start_part == "$":
            start = "_data"
        elif start_part == "$^":
            start = "_input"
        elif start_part == "$%":
            start = "_frame"
        elif start_part == "$<":
            start = "_parent._data"
        elif (vars := m.group("vars")):
            # Convert $foo.bar to .foo.bar, starting with implied "_.vars"
            start : str = vars
            if not segments_part:
                return VariableStatement(name=vars)                

        if not start:
            return JFTLNotice(code="BAD-NAV-SYNTAX", message=f"Unknown start: '${start_part}", where=where)
        
        segments = cls._parse_segments(where, segments_part)
        source_code : str = m[0]
        expr = NavigationStatement(where, source_code, start=start, segments=segments, strict=strict)
        return expr

    def _parse(self, source, where):

        m = self._NAV_RE.match(source)
        if not m:
            return JFTLNotice(code="BAD-NAV-SYNTAX", message=f"Unknown navigation: '${source}", where=where)
        
        expr = self.parse_nav(m, where, strict = self.strict)
        if not expr:
            return JFTLNotice(code="BAD-NAV-EXPR", message=f"Unknown navigation: '${source}", where=where)
        
        return expr

    def compile_str(self, source: Any | str, where: str = "") -> COMPILE_DOC:
        assert isinstance(source, str)
        expr = self._parse(source, where)
        return expr
    

class NavigationPlugin(CompilerPlugin):
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler:
        return NavigationCompiler(docCompiler, strict=False)

class StrictNavPlugin(CompilerPlugin):
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler:
        return NavigationCompiler(docCompiler, strict=True)
