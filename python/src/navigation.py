
# runtime.py
from abc import ABC
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from typing import Any

from model import COMPILE_DOC, RUNTIME_DICT_TYPES, RUNTIME_DOC, RUNTIME_LIST_TYPES, RUNTIME_NULL_TYPES, CompileError, CompileContext, CompileNotice, CompilerPlugin, DocCompiler, Evaluator, RuntimeContext, RuntimeNotice, StatementCompiler, my_profile
from template import MISSING_VALUE, JFTLNotice, Missing


class NavType(Enum):
    KEY = auto()
    INDEX = auto()
    VAR = auto()

@dataclass(frozen=True, slots=True)
class PathSegment:
    type: NavType
    name: str
    index: int

import re

_SEGMENT_RE = re.compile(r"""
    \.(?P<word>\w+)
  | \[(?P<index>-?[0-9]+)\]
  | \["(?P<dq>[^"]*)"\]
  | \['(?P<sq>[^']*)'\]
  | \[\$(?P<var>\w+)\]
""", re.VERBOSE)


@dataclass(slots=True, frozen=True, kw_only=True)
class VariableStatement(Evaluator):
    name: str

    @my_profile
    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        return ctx.lookup_var(self.name)

    # TODO: Profile, and decide if useful.
    @my_profile
    def eval_inline(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        name = self.name
        if name in ctx.vars:
            return ctx.vars[name]
        return ctx.lookup_var(name)

class _NavStart(StrEnum):
    VARS = "_vars"
    DATA = "_data"
    FRAME = "_frame"
    PARENT_DATA = "_parent._data"
    INPUT = "_input"

@dataclass(slots=True, frozen=True, kw_only=True)
class NavigationEvaluator(Evaluator, ABC):
    """Compiled 'sel:' path — parsed once at compile time, walked at eval time."""

    start: _NavStart
    start_var: str
    segments: list[PathSegment]
    strict: bool

    NAV_STOP_TYPES = (Missing, JFTLNotice)

    @my_profile
    def _find_start(self, ctx: RuntimeContext) -> Any | RuntimeContext:

        start = self.start
        value = None
        # Start from one of the predefined locations:        
        if start == _NavStart.DATA:
            value = ctx.current
        elif start == _NavStart.VARS:
            return ctx.lookup_var(self.start_var)
        elif start == _NavStart.FRAME:
            value = ctx
        elif start == _NavStart.INPUT:
            value = ctx.env.input
        elif start == _NavStart.PARENT_DATA:
            if not ctx.parent:
                return RuntimeNotice(self, "NAV-NO-PARENT", "Using '$%' is not valid at the top frame")
            value = ctx.parent.current
        else:
            return RuntimeNotice(self, "NAV-BAD-START", message= f"Unexpected navigation start location: {start}")
    
        return value


class _GenericNavEvaluator(NavigationEvaluator):
    
    @my_profile
    def _eval_nav(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:

#        value = self._find_head(ctx, self._start)
        value = self._find_start(ctx)

        traveled = "$"  # builds up the "location" string as we walk, for diagnostics
        nav_stop_types = (Missing, JFTLNotice)

        for seg in self.segments:
            if isinstance(value, nav_stop_types):
                return value  # already failed upstream — propagate, stop walking

            match seg.type:
                case NavType.KEY:
                    value = (
                        value.get(seg.name, MISSING_VALUE) if isinstance(value, RUNTIME_DICT_TYPES)
                        else RuntimeNotice(self, "NAV-NOT-OBJECT", f"string keys can only be used on objects, found {type(value)} path {'traveled'}") if self.strict
                        else MISSING_VALUE
                    )
                    traveled += f".{seg.name}"

                case NavType.INDEX:
                    value = (
                        value[seg.index] if isinstance(value, RUNTIME_LIST_TYPES) and -len(value) <= seg.index < len(value)
                        else RuntimeNotice(self, "NAV-NOT-ARRAY", f"integer indices can only be used on array/null, at {type(value)}") if self.strict
                        else MISSING_VALUE
                    )
                    traveled += f"[{seg.index}]"

                case NavType.VAR:
                    key = ctx.lookup_var(seg.name)
                    if isinstance(key, str) and isinstance(value, RUNTIME_DICT_TYPES):
                        value = value.get(key, MISSING_VALUE)                        
                        traveled += f'.["{key}"]'

                    elif isinstance(key, int) and not isinstance(key, bool) and isinstance(value, RUNTIME_LIST_TYPES):
                        value = value[key] if -len(value) <= key < len(value) else MISSING_VALUE
                        traveled += f"[[key]]"

                    elif not self.strict or isinstance(key, RUNTIME_NULL_TYPES):
                        value = MISSING_VALUE
                    else:
                        value = RuntimeNotice(self, "NAV-VAR-KEY", f"Key type '{type(key)}' can not be used to access elements of type {type(value)}")

        return value

    eval = _eval_nav

_DICT_OR_MISSING = (*RUNTIME_DICT_TYPES, Missing)

class _KeyNavEvaluator(NavigationEvaluator):

    # Evaluate $.key in non-strict mode.
    @my_profile
    def eval_k(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
        value = self._find_start(ctx)

        result = (
            value.get(self.segments[0].name, MISSING_VALUE) if isinstance(value, _DICT_OR_MISSING)
            else value if isinstance(value, JFTLNotice)
            else MISSING_VALUE
        )
        return result

    eval = eval_k


    
class _IndexNavEvalulator(NavigationEvaluator):

    @my_profile
    # Evaluate $[123] in non-strict mode.
    def eval_n(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
#        value = self._find_head(ctx, self._start)
        value = self._find_start(ctx)
        index1 = self.segments[0].index

        result = (
            value[index1] if isinstance(value, RUNTIME_LIST_TYPES) and -len(value) <= index1 < len(value)
            else value if isinstance(value, JFTLNotice)
            else MISSING_VALUE
        )

        return result
    
    eval = eval_n


class _KeyKeyNavEvaluator(NavigationEvaluator):

    @my_profile
    # Evaluate $.key1.keys in non-strict mode.

    def eval_kk(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
#        value = self._find_head(ctx, self._start)
        value = self._find_start(ctx)
        if isinstance(value, self.NAV_STOP_TYPES):
            return value

        value = (
            v1.get(self.segments[1].name, MISSING_VALUE)
            if isinstance((
                v1:=value.get(self.segments[0].name, MISSING_VALUE)
                ), RUNTIME_DICT_TYPES)
            else MISSING_VALUE
        )

        return value


    eval = eval_kk


class _KeyIndexNavEvaluator(NavigationEvaluator):

    @my_profile
    # Evaluate $.key1[123] in non-strict mode.
    def eval_kn(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
#        value = self._find_head(ctx, self._start)
        value = self._find_start(ctx)
        if isinstance(value, self.NAV_STOP_TYPES):
            return value

        segments = self.segments
        result = (
            v1[index2]
            if(
                isinstance( value, RUNTIME_DICT_TYPES)
                and isinstance( (v1:=value.get(segments[0].name, MISSING_VALUE)), RUNTIME_LIST_TYPES)
                and -len(value) <= (index2:=segments[1].index) < len(v1)
            )
            else MISSING_VALUE
        )

        return result
    
    eval = eval_kn

NAV_RE_STR = r"""
    (?P<start> \$ | \$\^ | \$< | \$% | \$(?P<vars>\w+ ) )
    (?P<segments> (\[.* | \..* )? )
"""

@dataclass
class NavigationCompiler(StatementCompiler):

    strict: bool = False
    _NAV_RE = re.compile("^" + NAV_RE_STR + "$", re.VERBOSE)

    @staticmethod
    def _parse_segments(cc: CompileContext, path_text: str) -> list[PathSegment]:

        segments: list[PathSegment] = []
        pos = 0

        for m in _SEGMENT_RE.finditer(path_text):
            if m.start() != pos:
                raise CompileError(CompileNotice(cc, "INVALID_PATH",
                    message=f"unexpected text at position {pos} in {path_text!r}"))
            pos = m.end()

            if m.group("word") is not None:
                seg = PathSegment(NavType.KEY, m.group("word"), 0)
            elif m.group("index") is not None:
                seg = PathSegment(NavType.INDEX, "", int(m.group("index")))
            elif m.group("dq") is not None:
                seg = PathSegment(NavType.KEY, m.group("dq"), 0)
            elif m.group("sq") is not None:
                seg = PathSegment(NavType.KEY, m.group("sq"), 0)
            elif m.group("var") is not None:
                seg = PathSegment(NavType.VAR, m.group("var"), 0)
            else:
                raise CompileError(CompileNotice(cc, "INVALID_PATH",
                    message=f"Unknown navigation segment position {pos} in {path_text!r}"))

            segments.append(seg)

        if pos != len(path_text):
            raise CompileError(CompileNotice(cc, "INVALID_PATH",
                message=f"trailing unparsed text at position {pos} in {path_text!r}"))

        return segments    

    @classmethod
    def parse_nav(cls, m: re.Match[str], cc: CompileContext, *, strict: bool = False) -> NavigationEvaluator | VariableStatement | JFTLNotice:

        source_code : str = m[0]
        start_part = m.group("start")
        segments_part = m.group("segments")
        start_name = start_part
        nav_start = None
        if start_part == "$":
            nav_start = _NavStart.DATA
        elif start_part == "$^":
            nav_start = _NavStart.INPUT
        elif start_part == "$%":
            nav_start = _NavStart.FRAME
        elif start_part == "$<":
            nav_start = _NavStart.PARENT_DATA
        elif (start_name := m.group("vars")):
            # Convert $foo.bar to .foo.bar, starting with implied "_.vars"
            if not segments_part:
                return VariableStatement(cc, name=start_name)
            nav_start = _NavStart.VARS
        else:
            return CompileNotice(cc, "BAD-NAV-SYNTAX", f"Unknown nav: name='{source_code}'", source = source_code)
            
        segments = cls._parse_segments(cc, segments_part)
        source_code : str = m[0]

        if len(segments) == 1 and segments[0].type == NavType.KEY and not strict:
            return _KeyNavEvaluator(cc, source_code, start=nav_start, start_var=start_name, segments=segments, strict=strict)
        elif len(segments) == 1 and segments[0].type == NavType.INDEX and not strict:
            return _IndexNavEvalulator(cc, source_code, start=nav_start, start_var=start_name, segments=segments, strict=strict)
        elif len(segments) == 2 and segments[0].type == NavType.KEY and segments[1].type == NavType.KEY and not strict:
            return _KeyKeyNavEvaluator(cc, source_code, start=nav_start, start_var=start_name, segments=segments, strict=strict)
        elif len(segments) == 2 and segments[0].type == NavType.KEY and segments[1].type == NavType.INDEX and not strict:
            return _KeyIndexNavEvaluator(cc, source_code, start=nav_start, start_var=start_name, segments=segments, strict=strict)
#        elif len(segments) == 3 and segments[0].type == NavType.KEY and segments[1].type == NavType.KEY and segments[2].type == NavType.KEY and not strict:
#            return _KeyKeyKeyNavEvaluator(where, source_code, start=start, segments=segments, strict=strict)
#        elif len(segments) == 2 and segments[0].type == NavType.KEY and segments[1].type == NavType.INDEX and not strict:
#            return _KeyKeyIndexNavEvaluator(where, source_code, start=start, segments=segments, strict=strict)
           
        # Fallback - does not match any existinng pattern
        expr = _GenericNavEvaluator(cc, source_code, start=nav_start, start_var=start_name, segments=segments, strict=strict)
        return expr

    def _parse(self, source, cc: CompileContext):

        m = self._NAV_RE.match(source)
        if not m:
            return CompileNotice(cc, "BAD-NAV-PATTERN", f"Unknown navigation:", source=source)
        
        expr = self.parse_nav(m, cc, strict = self.strict)
        if not expr:
            return CompileNotice(cc, "BAD-NAV-EXPR", f"Unknown navigation", source=source)
        
        return expr

    def compile_str(self, source: Any | str, cc: CompileContext) -> COMPILE_DOC:
        assert isinstance(source, str)
        expr = self._parse(source, cc)
        return expr
    

class NavigationPlugin(CompilerPlugin):
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler:
        return NavigationCompiler(docCompiler, strict=False)

class StrictNavPlugin(CompilerPlugin):
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler:
        return NavigationCompiler(docCompiler, strict=True)
