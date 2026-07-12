"""
Evaluate Expressions using
"""

from dataclasses import InitVar, dataclass, field
from typing import Any, Optional

from core import Compiler, Condition, Evaluator, Expression, Frame, Statement
from simpleeval import SimpleEval, DEFAULT_NAMES, EvalWithCompoundTypes

from template import Error, Missing

@dataclass
class SimpleEvalEvaluator(Statement, Expression, Condition):
    se: SimpleEval
    source: str
    compiled: Any

    def _build_env(self, frame: Frame) -> dict[str, Any]:
        """Walk the frame chain, closest scope wins: '_' + locals + parent vars."""
        env: dict[str, Any] = DEFAULT_NAMES.copy()
        chain: list[Frame] = []
        f: Optional[Frame] = frame
        seen: set[int] = set()
        while f is not None and id(f) not in seen:
            chain.append(f)
            seen.add(id(f))
            if f.parent is f:
                break
            f = f.parent
        for ancestor in reversed(chain):  # farthest ancestor first, closer scopes overwrite
            env.update(ancestor.vars)
        env["_"] = frame.current
        env["_input"] = frame.env.input
        return env

    def eval(self, frame: Frame) -> Any | Error | Missing:
        se = self.se
        se.names = self._build_env(frame)
        return se.eval(self.source, self.compiled)
    
        # Using Python rules for falsyness. Can still return Missing, Error
    def eval_cond(self, frame: Frame) -> Any | Error | Missing:
        result = self.se.eval(self.source, previously_parsed=self.compiled,)
        result = self.se.eval(self.source, previously_parsed=self.compiled,)
        if isinstance(result, (Missing, Error)):
            return result
        return bool(result)
   

@dataclass
class SimpleEvalPlugin(Compiler):
    simple_eval : SimpleEval | None= None
    _se : SimpleEval = field(init=False)

    def __post_init__(self) -> None:
        self._se = self.simple_eval if self.simple_eval else self._default_simple_eval()

    def _default_simple_eval(self) -> SimpleEval:
        STRING_ATTRS = [
            "join",
            "lower",
            "upper",
            "strip",
            "rstrip",
            "startswith",
            "endswith",
            "replace",
            "split"
        ]
        # Was SimpleEval, but it does not support comprehension 
        se = EvalWithCompoundTypes(
            allowed_attrs= { str: STRING_ATTRS }
        )
        se.functions = {
            "abs": abs,
            "len": len,
            "min": min,
            "max": max,
            "sum": sum,
            "round": round,
            "range": range,
            "sorted": sorted,
            "any": any,
            "all": all,
            "int": int,
            "float": float,
            "bool": bool,
            "str": str,
            "ord": ord,
            "chr": chr,
        }
        return se

    def condition(self, source: str) -> tuple[Condition, Optional[list[Error]]]:
        assert isinstance(source, str)
        compiled = self._se.parse(source)
        return SimpleEvalEvaluator(self._se, source, compiled), None

    def expression(self, source: str | dict) -> tuple[Expression, Optional[list[Error]]]:
        assert isinstance(source, str)
        compiled = self._se.parse(source)
        return SimpleEvalEvaluator(self._se, source, compiled), None

    def statement(self, source: dict | str) -> tuple[Statement, Optional[list[Error]]]:
        assert isinstance(source, str)
        compiled = self._se.parse(source)
        return SimpleEvalEvaluator(self._se, source, compiled), None

