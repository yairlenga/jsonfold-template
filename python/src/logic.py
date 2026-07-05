from typing import Any, Literal, Optional
from dataclasses import dataclass

from core import Statement, Error, Missing, Frame, Expression, Evaluator, Condition, Compiler

""" {
    "$": true,
    "set": {
        "var1": "EXPR-1",
        "var2": "EXPR-2",
        ...
    },
    "if": "EXPR",
    "data": "EXPR",
    "foreach": {
        "key": "KEY-VAR",
        "item": "ITEM-VAR",
        "in": "EXPR",
    },
    "case": [
        { "when": "COND-1", "then": "EXPR-1" },
        { "when": "COND-2", "then": "EXPR-2" },
    ],
    "body": "EXPR",
    "transform": "MERGE|FLATTEN|NONE",
    "error": "EXPR",
} """

@dataclass
class Case:
    _cond: Expression
    _body: Statement

@dataclass
class LogicStatement(Statement):

    _set: dict[str, Evaluator] | None
    _if: Optional[Condition]
    _data: Expression | None
    _cases: list[Case] | None
    _foreach: bool
    _foreach_key: str | None
    _foreach_var: str | None
    _foreach_in: Expression | None
    _foreach_cond: Expression | None
    _body: Evaluator | None
    _transform: Literal["MERGE", "FLATTEN", None]
    _default_val: Evaluator | None
    _error_val: Evaluator | None

    @classmethod
    def compile(cls, compiler: Compiler, args: dict[str, Any]):

        v_set = { name: compiler.expression(expr) for name, expr in v.items() } if ( v := args.get("set", None)) else None

        v_if = compiler.condition(v) if (v := args.get("if", None))  else None

        v_data = compiler.expression(v) if ( v:= args.get("data", None)) else None
        
        v_loop = args.get("foreach", None)
        v_foreach = isinstance(v_loop, dict)
        v_foreach_key = v if v_foreach and (v:= v_loop.get("key", None)) else None
        v_foreach_var = v if v_foreach and (v:= v_loop.get("var", None)) else None
        v_foreach_in = compiler.expression(v) if v_foreach and ( v:= v_loop.get("in", None)) else None
        v_foreach_cond = compiler.condition(v) if v_foreach and ( v := v_loop.get("if", None)) else None

        v_cases = [
            Case( _cond = compiler.condition( case["when"] ), _body = compiler.statement( case[ "then" ] ))
            for case in cases ] if (cases := args.get("case", None)) else None

        v_body = compiler.statement(v) if ( v := args.get("body", None)) else None
        v_default = compiler.statement(v) if ( v := args.get("default", None)) else None
        v_error = compiler.statement(v) if ( v := args.get("error", None)) else None
        v_transform = args.get("transform", None) 

        self = cls(
            _set = v_set,
            _if = v_if,
            _data = v_data,
            _foreach = v_foreach,
            _foreach_var = v_foreach_var,
            _foreach_key = v_foreach_key,
            _foreach_in = v_foreach_in,
            _foreach_cond = v_foreach_cond,
            _cases = v_cases,
            _body = v_body,
            _default_val = v_default,
            _error_val = v_error,
            _transform = v_transform,
        )
        return self


       
    def eval(self, frame: Frame) -> Any | Error | Missing:

        new_frame = frame.clone()
