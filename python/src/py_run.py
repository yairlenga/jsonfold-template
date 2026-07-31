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
from dataclasses import dataclass
from typing import Any, Callable, Optional, cast

from model import COMPILE_DOC, RUNTIME_BOOL, RUNTIME_DOC, CompilerPlugin, Evaluator, RuntimeContext, StatementCompiler
from template import JFTLNotice, Missing, MISSING_VALUE

def _build_env(ctx: RuntimeContext) -> dict[str, Any]:
    """Walk the frame chain, closest scope wins: '_' + locals + parent vars."""
    env: dict[str, Any] = {}
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


class PyEvalEvaluator(Evaluator):
    """One compiled '$pyrun:' expression."""

    def __init__(self, code: Any, source_text: str, where: str = ""):
        super().__init__()
        self._code = code
        self._source = source_text
        self._where = where

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        env = _build_env(ctx)
        try:
            return eval(self._code, env)
        except Exception as e:
            return JFTLNotice(
                code="PYRUN_RUNTIME_ERROR",
                where=self._where, location=None,
                message=f"error evaluating {self._source!r}: {e}",
            )

    def eval_bool(self, ctx: RuntimeContext) -> RUNTIME_BOOL:
        result = self.eval(ctx)
        if isinstance(result, (bool, JFTLNotice, Missing)):
            return result
        return bool(result)  # native Python truthiness — not JFTL's falsy rule


class PyEvalCompiler(StatementCompiler):
    """Registered once (e.g. via engine.add_expr_engine('pyrun', PyRunExprEngine())).
    Stateless — compile() is called once per '$pyrun:' expression found during
    template compilation, and returns a PyRunEvaluator."""


    def _compile(self, source_text: str, where: str = "") -> COMPILE_DOC:
        try:
            tree = ast.parse(source_text, mode="eval")
        except SyntaxError as e:
            return JFTLNotice(
                code="INVALID_PYTHON", where=where, location=None,
                message=f"invalid Python expression {source_text!r}: {e}",
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                return JFTLNotice(
                    code="INVALID_PYTHON",where=where, location=None,
                    message=f"lambda expressions are not allowed in {source_text!r}",
                )

        code = compile(tree, filename="<jftl-pyrun-expr>", mode="eval")
        return PyEvalEvaluator(code, source_text, where)

    def compile_str(self, source: str, where: str = "") -> COMPILE_DOC:
        return self._compile(source)


class PyEvalPlugin(CompilerPlugin):
    def createCompiler(self, DocCompiler) -> StatementCompiler:
        return PyEvalCompiler(DocCompiler)

from types import CodeType
from typing import Any


@dataclass(kw_only=True)
class PyRunEvaluator(Evaluator):
    func_call: CodeType
    func_def: Callable | Any
    glob_env: dict[str, Any]
    source: Optional[str] = None

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        names = _build_env(ctx)

        # Global Object
        g = self.func_def.__globals__
        g.clear()
        g.update(self.glob_env)
        g.update(names)

        try:
            return eval(self.func_call, g)
        except Exception as e:
            return JFTLNotice(
                code="PYRUN_RUNTIME_ERROR",
                where=self.where, location=None,
                message=f"error evaluating {self.source!r}: {e}",
            )

    def eval_bool(self, ctx: RuntimeContext) -> RUNTIME_BOOL:
        result = self.eval(ctx)
        if isinstance(result, (bool, JFTLNotice, Missing)):
            return result
        return bool(result)  # native Python truthiness — not JFTL's falsy rule


class PyRunCompiler(StatementCompiler):
    """Registered once (e.g. via engine.add_expr_engine('pyrun', PyRunExprEngine())).
    Stateless — compile() is called once per '$pyrun:' expression found during
    template compilation, and returns a PyRunEvaluator."""

    def _compile(self, source_text: str, where:str = "") -> PyRunEvaluator:
        # Parse the user's text as ordinary Python statements.
        filename = where if where else "<pyrun>"
        FUNC_NAME = "pyrun_func"
        MISSING_VAR = "_MISSING"

        parsed = ast.parse(
            source_text,
            filename=filename,
            mode="exec",
            )

        # Add implied return _MISSING to the end of the statement list
        parsed.body.append(ast.Return(
            value=ast.Name(
                id=MISSING_VAR,
                ctx=ast.Load(),
            )
        ))

        # Wrap in a function
        function_definition = ast.FunctionDef(
            name=FUNC_NAME,
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=parsed.body,
            decorator_list=[],
            returns=None,
            type_comment=None,
            type_params=[],
        )

        wrapper_module = ast.Module(
            body=[function_definition],
            type_ignores=[],
        )

        ast.fix_missing_locations(wrapper_module)

        wrapper_code = compile(
            wrapper_module,
            filename=filename,
            mode="exec",
            )

        # Execute the wrapper once to obtain the generated function's code object.
        eval_globals: dict[str, Any] = {
            MISSING_VAR: MISSING_VALUE,
        }

        build_locals = {}
        exec(wrapper_code, eval_globals, build_locals)

        func_call = compile(FUNC_NAME + "()", filename, "eval")
        eval_globals[FUNC_NAME] = build_locals[FUNC_NAME]

        return PyRunEvaluator(func_call=func_call, func_def=build_locals.get(FUNC_NAME), glob_env=eval_globals.copy(), where = where )

        
    def compile_str(self, source: Any | str, where: str = "") -> COMPILE_DOC:
        return self._compile(cast(str, source))



class PyRunPlugin(CompilerPlugin):
    def createCompiler(self, DocCompiler) -> StatementCompiler:
        return PyRunCompiler(DocCompiler)