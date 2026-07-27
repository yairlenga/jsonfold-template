"""
Evaluate Expressions using
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from core import RUNTIME_DOC, Evaluator
from simpleeval import SimpleEval, DEFAULT_NAMES, EvalWithCompoundTypes

from model import COMPILE_DOC, CompilerPlugin, RuntimeContext, StatementCompiler
from template import JFTLNotice, Missing

@dataclass(kw_only=True)
class SimpleEvalEvaluator(Evaluator):
    se: SimpleEval
    source: str
    compiled: Any

    def _build_env(self, ctx: RuntimeContext) -> dict[str, Any]:
        """Walk the frame chain, closest scope wins: '_' + locals + parent vars."""
        env: dict[str, Any] = DEFAULT_NAMES.copy()
        chain: list[RuntimeContext] = []
        f: Optional[RuntimeContext] = ctx
        seen: set[int] = set()
        while f is not None and id(f) not in seen:
            chain.append(f)
            seen.add(id(f))
            if f.parent is f:
                break
            f = f.parent
        for ancestor in reversed(chain):  # farthest ancestor first, closer scopes overwrite
            env.update(ancestor.vars)
        env["_"] = ctx.current
        env["_input"] = ctx.env.input
        return env

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        se = self.se
        se.names = self._build_env(ctx)
        return se.eval(self.source, self.compiled)
    
        # Using Python rules for falsyness. Can still return Missing, Error
    def eval_cond(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
        result = self.se.eval(self.source, previously_parsed=self.compiled,)
        if isinstance(result, (Missing, JFTLNotice)):
            return result
        return bool(result)
   

@dataclass
class SimpleEvalCompiler(StatementCompiler):
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

    def compile_str(self, source: Any | str, where: str = "") -> COMPILE_DOC:
        assert isinstance(source, str)
        compiled = self._se.parse(source)
        return SimpleEvalEvaluator(se=self._se, source=source, compiled=compiled)



class SimpleEvalPlugin(CompilerPlugin):

    def createCompiler(self, DocCompiler) -> StatementCompiler:
        return SimpleEvalCompiler(DocCompiler)

