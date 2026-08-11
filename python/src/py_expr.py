"""
Evaluate Expressions using
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from simpleeval import SimpleEval, DEFAULT_NAMES, EvalWithCompoundTypes, InvalidExpression

from model import COMPILE_DOC, RUNTIME_DOC, CompileContext, CompileNotice, CompilerPlugin, DocCompiler, Evaluator, RuntimeContext, StatementCompiler
from template import JFTLNotice, Missing

def _create_simple_eval() -> SimpleEval:
    STRING_ATTRS = [
        "join",
        "lower",
        "upper",
        "strip",
        "lstrip",
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


@dataclass(slots=True, frozen=True, kw_only=True)
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

        key = id(self)
        se = ctx.env.cache.get(key)
        # Clone on first call
        if se is None:
            se = _create_simple_eval()
            ctx.env.cache[key] = se
        se.names = self._build_env(ctx)
        # TODO: Propograte exception to the user, with ability to covert them to "soft" JFTLNotice.
        try:
            return se.eval(self.source, self.compiled)
        except Exception as e:
            return JFTLNotice(
                code="PYEXPR_RUNTIME_ERROR",
                where=self.where,
                message=f"{e}",
                source=self.source
            )
    
        # Using Python rules for falsyness. Can still return Missing, Error
    def eval_cond(self, ctx: RuntimeContext) -> Any | JFTLNotice | Missing:
        result = self.eval(ctx)
        if isinstance(result, (Missing, JFTLNotice)):
            return result
        return bool(result)
   

@dataclass
class SimpleEvalCompiler(StatementCompiler):
    simple_eval : SimpleEval | None= None
    _se : SimpleEval = field(init=False)

    def __post_init__(self) -> None:
        self._se = self.simple_eval if self.simple_eval else _create_simple_eval()


    def compile_str(self, source: Any | str, cc: CompileContext) -> COMPILE_DOC:
        assert isinstance(source, str)
        try:
            compiled = self._se.parse(source)
        except SyntaxError as e:
            return CompileNotice(cc, "PYEXPR-SYNTAX",
                f"error evaluating {source!r}: {e}",
                source = source
            )            

        except InvalidExpression as e:
            return CompileNotice(cc, "PYEXPR-INVALID",
                                 f"error evaluating {source!r}: {e}",
                                 source = source
            )            
        return SimpleEvalEvaluator(cc, se=self._se, source=source, compiled=compiled)




class SimpleEvalPlugin(CompilerPlugin):

    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler :
        return SimpleEvalCompiler(docCompiler)

