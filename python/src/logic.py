from typing import Any, ItemsView, Iterator, Literal, Optional
from dataclasses import dataclass, replace

from core import Statement, Error, Missing, Frame, Expression, Evaluator, Condition, Compiler
from template import MISSING_VALUE

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
    _cond: Condition
    _body: Statement

@dataclass
class SetVar:
    _name: str
    _expr: Expression

@dataclass
class LogicStatement(Statement):

    _set_vars: Optional[list[SetVar]]
    _if: Optional[Condition]
    _current_val: Optional[Expression]
    _cases: Optional[list[Case]]
    _foreach: Optional[bool]
    _foreach_key: Optional[str]
    _foreach_var: Optional[str]
    _foreach_in: Optional[Expression]
    _foreach_cond: Optional[Condition]
    _body: Optional[Statement]
    _transform: Literal["MERGE", "FLATTEN", None]
    _default_val: Optional[Statement]
    _error_val: Optional[Statement]

    @classmethod
    def compile(cls, compiler: Compiler, args: dict[str, Any]):

        source = ""
        v_set_vars = [
            SetVar(_name = name, _expr = compiler.expression(expr, source)[0])
            for name, expr in v.items()
            ] if ( v := args.get("set", None)) else None

        v_if, _ = compiler.condition(v, source) if (v := args.get("if", None))  else (None, None)

        v_data, _ = compiler.expression(v, source) if ( v:= args.get("data", None)) else (None, None)
        
        v_loop = args.get("foreach", None)
        v_foreach = isinstance(v_loop, dict)
        v_foreach_key = v if v_foreach and (v:= v_loop.get("key", None)) else None
        v_foreach_var = v if v_foreach and (v:= v_loop.get("var", None)) else None
        v_foreach_in, _ = compiler.expression(v, source) if v_foreach and ( v:= v_loop.get("in", None)) else (None, None)
        v_foreach_cond, _ = compiler.condition(v, source) if v_foreach and ( v := v_loop.get("if", None)) else (None, None)

        v_cases = [
            Case( _cond = compiler.condition( case["when"], source )[0], _body = compiler.statement( case[ "then" ], source )[0])
            for case in cases
            ] if (cases := args.get("case", None)) else None

        v_body, _ = compiler.statement(v, source) if ( v := args.get("body", None)) else (None, None)
        v_default, _ = compiler.statement(v, source) if ( v := args.get("default", None)) else (None, None)
        v_error, _ = compiler.statement(v, source) if ( v := args.get("error", None)) else (None, None)
        v_transform = args.get("transform", None) 

        self = cls(
            _set_vars = v_set_vars,
            _if = v_if,
            _current_val = v_data,
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

    def _eval_foreach(self, frame: Frame, body: Statement) -> list | dict | Error | Missing:
        items = frame.eval_value(self._foreach_in) if self._foreach_in else frame.current
        if isinstance(items, list):
            loop_iter = enumerate(items)
        elif isinstance(items, dict):
            loop_iter = iter(items.items())
        elif items is None:
            return None ;

            v_body = None
        new_vars = frame.vars
        # Process foreach loop
        if loop_iter:
            v_var = self._foreach_var
            v_key = self._foreach_key
            v_cond = self._foreach_cond
            dict_result : dict[str, Any]= {}
            list_result = []
            do_dict = self._transform == "OBJECT"
            for key, item in loop_iter:
                new_key = key if do_dict else None
                if v_key:
                    new_vars[v_key] = key
                if v_var:
                    new_vars[v_var] = item
                else:
                    frame.current = item
                if not frame.eval_bool(v_cond, True):
                    continue
                new_val = frame.eval_value(body)
                if new_key is None:
                    list_result.append(new_val)
                else:
                    dict_result[new_key] = new_val

            return dict_result if do_dict else list_result
        
    def _choose_body(self, frame: Frame) -> Statement | None:
        v_body = self._body
        if (cases := self._cases):
            for case in cases:
                if frame.eval_bool(case._cond, False):
                    v_body = case._body
                    break

        return v_body


    def eval(self, prev_frame: Frame) -> Any | Error | Missing:

        # Create a new frame to use
        new_vars : dict[str, Any]= {}

        new_frame = replace(prev_frame, parent = prev_frame, level = prev_frame.level+1, vars = new_vars, _cache = {})
        # Build local vars, inside the new frame.
        if (set_vars := self._set_vars):
            for set_var in set_vars:
                name = set_var._name
                value = new_frame.eval_value(set_var._expr)
                new_vars[name] = value

        # Check the condition
        if not new_frame.eval_bool(self._if, True):
            return new_frame.eval_value(self._default_val)
            
        # Consider new data object.
        if ( v_data := self._current_val):
            new_frame.current = new_frame.eval_value(v_data)
        
        # Choose body to execute
        v_body = self._choose_body(new_frame)

        if not v_body:
            return new_frame.eval_value(self._default_val)

        # Check if executing foreach loop
        if self._foreach:
            result = self._eval_foreach(new_frame, v_body)
            
            if result is None:
                return new_frame.eval_value(self._default_val)

            return result
        # Process Single result
        result = new_frame.eval_value(v_body)

        if isinstance(result, Missing):
            return new_frame.eval_value(self._default_val)
        
        return result