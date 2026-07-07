"""
$pyrun: — arbitrary, fully-trusted Python expression evaluation.

Protocol:
  - ExprEngine is registered ONCE (e.g. engine.add_expr_engine("pyrun", PyRunExprEngine())).
  - ExprEngine.compile(source_text, where) is called ONCE PER EXPRESSION, at
    template compile time. It returns an Evaluator.
  - Evaluator.eval(frame) / Evaluator.eval_bool(frame) are called at RUNTIME,
    potentially many times (once per render, once per foreach iteration, etc.).

No sandboxing, no AST filtering — this is the deliberate 'shell escape' mode,
opt-in only via explicit registration. Input data still cannot become code on
its own (it's only ever placed into the evaluation namespace as values), but
if input objects carry real Python methods, those ARE callable from here.
"""
import ast
from abc import ABC, abstractmethod
from typing import Any, Optional

from core import Evaluator, Frame, CompileError
from template import Error, Missing

def _build_env(frame: Frame) -> dict[str, Any]:
    """Walk the frame chain, closest scope wins: '_' + locals + parent vars."""
    env: dict[str, Any] = {}
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


class PyRunEvaluator(Evaluator):
    """One compiled '$pyrun:' expression."""

    def __init__(self, code: Any, source_text: str, where: Optional[str]):
        self._code = code
        self._source = source_text
        self._where = where

    def eval(self, frame: Frame) -> Any | Error | Missing:
        env = _build_env(frame)
        try:
            return eval(self._code, {"__builtins__": __builtins__}, env)
        except Exception as e:
            return Error(
                code="PYRUN_RUNTIME_ERROR", severity="ERROR",
                where=self._where, location=None,
                message=f"error evaluating {self._source!r}: {e}",
            )

    def eval_bool(self, frame: Frame) -> bool | Error | Missing:
        result = self.eval(frame)
        if isinstance(result, (Error, Missing)):
            return result
        return bool(result)  # native Python truthiness — not JFTL's falsy rule


class PyRunExprEngine:
    """Registered once (e.g. via engine.add_expr_engine('pyrun', PyRunExprEngine())).
    Stateless — compile() is called once per '$pyrun:' expression found during
    template compilation, and returns a PyRunEvaluator."""

    def compile(self, source_text: str, where: Optional[str] = None) -> Evaluator:
        try:
            tree = ast.parse(source_text, mode="eval")
        except SyntaxError as e:
            raise CompileError(Error(
                code="INVALID_PYTHON", severity="ERROR", where=where, location=None,
                message=f"invalid Python expression {source_text!r}: {e}",
            ))

        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                raise CompileError(Error(
                    code="INVALID_PYTHON", severity="ERROR", where=where, location=None,
                    message=f"lambda expressions are not allowed in {source_text!r}",
                ))

        code = compile(tree, filename="<jftl-pyrun-expr>", mode="eval")
        return PyRunEvaluator(code, source_text, where)