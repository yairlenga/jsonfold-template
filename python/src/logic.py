from typing import Any, ItemsView, Iterator, Literal, Optional
from dataclasses import dataclass, replace

from core import RenderError, Statement, Error, Missing, Frame, Expression, Evaluator, Condition, Compiler
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
class DefineVar:
    _name: str
    _expr: Expression


@dataclass
class ForeachStatement():
    key: Optional[str] = None
    var: Optional[str] = None
    index: Optional[str] = None
    items: Optional[Expression] = None
    cond: Optional[Condition] = None
    shape: Literal["array", "range", None] = None
    start: Optional[Expression] = None
    stop: Optional[Expression] = None
    limit: Optional[Expression] = None

@dataclass
class LogicStatement(Statement):

    _defines: Optional[list[DefineVar]] = None
    _if: Optional[Condition] = None
    _set_current: Optional[Expression] = None
    _cases: Optional[list[Case]] = None
    _body: Optional[Statement] = None
    _foreach: Optional[ForeachStatement] = None
    _transform: Literal["MERGE", "FLATTEN", None] = None
    _default_val: Optional[Statement] = None
    _error_val: Optional[Statement] = None

    @classmethod
    def compile(cls, compiler: Compiler, args: dict[str, Any]):

        source = ""
        v_defines = [
            DefineVar(_name = name, _expr = compiler.expression(expr, source)[0])
            for name, expr in v.items()
            ] if ( v := args.get("set", None)) else None

        v_if, _ = compiler.condition(v, source) if (v := args.get("if", None))  else (None, None)

        v_data, _ = compiler.expression(v, source) if ( v:= args.get("data", None)) else (None, None)
        
        v_loop = args.get("foreach", None)
        v_foreach = None
        if isinstance(v_loop, dict):
            v_foreach = isinstance(v_loop, dict)
            # Compile time constants
            v_foreach_key = v_loop.get("key", None)
            v_foreach_var = v_loop.get("var", None)
            v_foreach_index = v_loop.get("index", None)
            v_foreach_shape = v_loop.get("shape", None)
            # Runtime expressions
            v_foreach_in, _ = compiler.expression(v, source) if ( v:= v_loop.get("in", None)) else (None, None)
            v_foreach_cond, _ = compiler.condition(v, source) if ( v := v_loop.get("if", None)) else (None, None)
            v_foreach_start, _ = compiler.expression(v, source) if ( v := v_loop.get("start", None)) else (None, None)
            v_foreach_stop, _ = compiler.expression(v, source) if ( v := v_loop.get("stop", None)) else (None, None)
            v_foreach_limit, _ = compiler.expression(v, source) if ( v := v_loop.get("limit", None)) else (None, None)
            v_foreach = ForeachStatement(
                key = v_foreach_key,
                var = v_foreach_var,
                index = v_foreach_index,
                items = v_foreach_in,
                cond = v_foreach_cond,
                start = v_foreach_start,
                stop = v_foreach_stop,
                limit = v_foreach_limit,
                shape = v_foreach_shape,
            )

        v_cases = [
            Case( _cond = compiler.condition( case["when"], source )[0], _body = compiler.statement( case[ "then" ], source )[0])
            for case in cases
            ] if (cases := args.get("case", None)) else None

        v_body, _ = compiler.statement(v, source) if ( v := args.get("body", None)) else (None, None)
        v_default, _ = compiler.statement(v, source) if ( v := args.get("default", None)) else (None, None)
        v_error, _ = compiler.statement(v, source) if ( v := args.get("error", None)) else (None, None)
        v_transform = args.get("transform", None) 


        self = cls(
            _defines = v_defines,
            _if = v_if,
            _set_current = v_data,
            _foreach = v_foreach,
            _cases = v_cases,
            _body = v_body,
            _default_val = v_default,
            _error_val = v_error,
            _transform = v_transform,
        )
        return self

    def _eval_foreach(self, frame: Frame, body: Statement) -> list | dict | Error | Missing:
        foreach = self._foreach
        items = frame.eval_value(foreach.items) if foreach.items else frame.current
        loop_iter = None
        count = None
        if foreach.shape == "range":
            pass

        elif isinstance(items, list):
            count = len(items)
            loop_iter = enumerate(items)
        elif isinstance(items, dict):
            count = len(items)
            loop_iter = iter(items.items())
        elif items is None or isinstance(items, Missing):
            return None

        else:
            raise RenderError(Error(
                code="NOT_ITERABLE", severity="ERROR",
                message=f"foreach 'in' expression produced a {type(items).__name__}, which cannot be iterated (expected an array or object)",
            ))

        ix_start = frame.eval_value(foreach.start) if foreach.start else 0
        ix_stop = frame.eval_value(foreach.stop) if foreach.stop else None
        ix_limit = frame.eval_value(foreach.limit) if foreach.limit else None

        # Support negative indexes if count is known.
        start_index = count-ix_start if count is not None and ix_start<0 else ix_start
        stop_index = start_index + ix_limit if ix_limit else count-ix_stop if count is not None and ix_stop is not None and ix_stop < 0 else ix_stop

        new_vars = frame.vars
        # Process foreach loop
        v_var = foreach.var
        v_key = foreach.key
        v_cond = foreach.cond
        v_index = foreach.index
        dict_result : dict[str, Any]= {}
        list_result = []
        do_dict = self._transform == "OBJECT"
        if foreach.shape == "range":
            count = stop_index - start_index
            loop_iter = enumerate(range(start_index, stop_index))
            start_index = None
            stop_index = None

        pos = -1
        for key, item in loop_iter:
            pos = pos+1
            if (start_index and pos < start_index) or (stop_index and pos >= stop_index):
                continue
            new_key = key if do_dict else None
            if v_key:
                new_vars[v_key] = key
            if v_index:
                new_vars[v_index] = pos

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
        if (set_vars := self._defines):
            for set_var in set_vars:
                name = set_var._name
                value = new_frame.eval_value(set_var._expr)
                new_vars[name] = value

        # Check the condition
        if not new_frame.eval_bool(self._if, True):
            return new_frame.eval_value(self._default_val)
            
        # Consider new data object.
        if ( v_data := self._set_current):
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