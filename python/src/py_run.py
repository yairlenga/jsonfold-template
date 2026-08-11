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
import types
from typing import Any, Callable, Optional

from model import COMPILE_DOC, RUNTIME_BOOL, RUNTIME_DOC, CompileContext, CompileNotice, CompilerPlugin, DocCompiler, Evaluator, RuntimeContext, StatementCompiler
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


@dataclass(slots=True, frozen=True, kw_only=True)
class PyEvalEvaluator(Evaluator):
    """One compiled '$pyrun:' expression."""

    code: Any                 # Precompiled Python code, passed to eval

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        env = _build_env(ctx)
        try:
            return eval(self.code, env)
        except Exception as e:
            return JFTLNotice(
                code="PYEVAL_RUNTIME_ERROR",
                where=self.where,
                message=f"error evaluating {self.source_code!r}: {e}",
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


    def _compile(self, source_text: str, cc: CompileContext) -> COMPILE_DOC:
        try:
            tree = ast.parse(source_text, mode="eval")
        except SyntaxError as e:
            return CompileNotice(cc, "INVALID_PYTHON",
                message=f"invalid Python expression {source_text!r}: {e}",
                source = source_text
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Lambda):
                return CompileNotice(cc, "INVALID_PYTHON",
                    message=f"lambda expressions are not allowed in {source_text!r}",
                )

        code = compile(tree, filename="<jftl-pyrun-expr>", mode="eval")
        return PyEvalEvaluator(cc, source_text, code=code)


    def compile_str(self, source: str, cc: CompileContext ) -> COMPILE_DOC :
        return self._compile(source, cc)


class PyEvalPlugin(CompilerPlugin):
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler :
        return PyEvalCompiler(docCompiler)

from types import CodeType
from typing import Any


@dataclass(slots=True, frozen=True, kw_only=True)
class PyRunEvaluator(Evaluator):
    func_call: CodeType
    func_def: Callable | Any
    glob_env: dict[str, Any]
    source: Optional[str] = None

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:

        names = _build_env(ctx)
        cache = ctx.env.cache
        key=id(self)
        func_def : Optional[types.FunctionType]= cache.get(key)
        if func_def is None:
            func_globals = {}
            func_def = types.FunctionType(self.func_def.__code__, func_globals)
            func_globals[self.func_def.__name__] = func_def         # bind name so func_call's lookup finds it
            cache[key] = func_def

        # Global Object
        g = func_def.__globals__
        g.clear()
        g.update(self.glob_env)
        g.update(names)
        g[self.func_def.__name__] = func_def

#        g["_"] = { "a": "X", "b": "X" }
#        self.func_def.__globals__["_"] = { "a": "Y", "b": "Y" }

        try:
            return eval(self.func_call, g)
        except Exception as e:
            return JFTLNotice(
                code="PYRUN_RUNTIME_ERROR",
                where=self.where,
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

    def _compile(self, source_text: str, cc:CompileContext) -> PyRunEvaluator:
        # Parse the user's text as ordinary Python statements.
        where = cc.where
        filename = where if where else "<pyrun>"
        FUNC_NAME = "_pyrun_func"
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

        return PyRunEvaluator(cc, func_call=func_call, func_def=build_locals.get(FUNC_NAME), glob_env=eval_globals)

    def compile_str(self, source: str, cc: CompileContext ) -> COMPILE_DOC:
        return self._compile(source, cc)


class PyRunPlugin(CompilerPlugin):
    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler :
        return PyRunCompiler(docCompiler)