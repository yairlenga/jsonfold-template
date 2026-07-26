from types import NoneType
from typing import Any, Callable, ClassVar, Literal, Optional, cast
from dataclasses import dataclass, replace

from core import RUNTIME_DOC, Frame
from model import Evaluator, RuntimeState, CompileError, Condition, DocCompiler, Statement, Transformer
from template import SKIP_VALUE, JFTLNotice, Missing

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
    "transform": "flatten" | "merge" | "to_pairs" | "from_pairs" | "drop_missing" | "concat" | None,
    "error": "EXPR",
} """

@dataclass
class Case:
    _cond: Condition
    _body: Statement

@dataclass
class DefineVar:
    _name: str
    _expr: Statement

@dataclass
class ForeachStatement():
    key: Optional[str] = None
    value: Optional[str] = None
    index: Optional[str] = None
    items: Optional[Statement] = None
    cond: Optional[Condition] = None
    start: Optional[Statement] = None
    stop: Optional[Statement] = None
    limit: Optional[Statement] = None

    # List[list] -> List
class _FlattenningTransformer(Transformer):
    def transform(self, input: RUNTIME_DOC ) -> list[RUNTIME_DOC] | JFTLNotice:
        if not isinstance(input, list):
            return JFTLNotice(
                    code="FLATTEN_INPUT",
                    message=f"The 'flatten' transform input is array of array, got non-list",
                )

        for pos, item in enumerate(input):
            if item is None:
                continue
            if not isinstance(item, list):
                return JFTLNotice(
                    code="FLATTEN_ITEM",
                    message=f"The 'flatten' transformation input is array of array, got non list items in position {pos}",
                )
            
        valid_input = cast(list[list], input)

        result = [x for sub in valid_input if sub is not None for x in sub]
        return result

    
    # list[dict] -> dict
class _MergeTransformer(Transformer):
    def transform(self, input: RUNTIME_DOC) -> dict[str, RUNTIME_DOC] | JFTLNotice:
        if not isinstance(input, list):
            return JFTLNotice(
                    code="MERGE_INPUT",
                    message=f"The 'merge' transformation input is array of objects, got non-list input",
                )

        for pos, item in enumerate(input):
            if item is None:
                continue
            if not isinstance(item, dict):
                return JFTLNotice(
                    code="MERGE_ITEM",
                    message=f"The 'merge' transformation input is array of objects, got non list items in position {pos}",
                )
        valid_input = cast(list[dict], input)

        result = {k: v for d in valid_input if d for k, v in d.items()}
        return result
    
    # dict -> list[Pairs]
class _ToPairsTransformer(Transformer):
    def transform(self, input: RUNTIME_DOC) -> list[tuple[str, RUNTIME_DOC]] | JFTLNotice:
        if not isinstance(input, dict):
            return JFTLNotice(
                    code="TO_PAIRS_INPUT",
                    message=f"The 'to_pairs' transformation input is array of objects, got non-list input",
                )

        return list(input.items())
    

    # List->List, Dict->Dict
class _DropMissingTransformer (Transformer):
    def transform(self,input: RUNTIME_DOC) -> list[RUNTIME_DOC] | dict[str, RUNTIME_DOC] | JFTLNotice | None:
        if input is None or isinstance(input, Missing):
            return None
        if isinstance(input, dict):
            return { k:v for k, v in input.items() if not isinstance(v, Missing) }
        elif isinstance(input, list):
            return [x for x in input if not isinstance(x, Missing)]

        return JFTLNotice(
                code="DROP_MISSING_INPUT",
                message=f"The 'drop_missing' transformation input ",
            )


    # List[Pairs] -> Dict
class _FromPairsTransformer (Transformer):
    def transform(self, input: RUNTIME_DOC) -> dict[str, RUNTIME_DOC] | JFTLNotice :
        if not isinstance(input, list):
            return JFTLNotice(
                    code="FROM_PAIRS_INPUT",
                    message=f"The 'from_pairs' transformation input is array of objects, got non-list input",
                )

        for pos, item in enumerate(input):
            if not isinstance(item, list) or len(item) != 2:
                return JFTLNotice(
                    code="FROM_PAIRS_DATA",
                    message=f"The 'from_pairs' transformation input is array of pairs, got non pair in position {pos} {input}",
                )

            key = item[0]
            value = item[1]

            # Skiped entries: [ null, null], and [false, null]
            if value in [None, False] and not key:
                continue
            elif isinstance(value, Missing):
                continue

            # Validate key is string.
            if not isinstance(key, str):
                return JFTLNotice(
                    code="FROM_PAIRS_BAD_KEY",
                    message=f"Invalid key type {type(item[0])} for missing item in 'from_pairs' pairs position {pos}, {input}",
                )
            
        valid_input = cast(list[tuple], input)

        return dict(item for item in valid_input if item[0])
    
    # List[str] -> Str
class _JoinStrTransformer(Transformer):
    def transform(self, input: list[str | None | Missing]) -> str | JFTLNotice :
        result = []
        for item in input:
            if isinstance(item, (NoneType)):
                item_str = "null"
            elif isinstance(item, (bool, int, str, float)):
                item_str = str(item)
            else:
                return JFTLNotice(code='JOIN-STR-TYPE', message=f"Result contained unknown type {type(item)}")

            result.append(item_str)
        return "".join(result)


@dataclass(slots=True)
class LogicStatement(Evaluator):

    _defines: Optional[list[DefineVar]] = None
    _if: Optional[Condition] = None
    _set_current: Optional[Statement] = None
    _cases: Optional[list[Case]] = None
    _body: Optional[Statement] = None
    _foreach: Optional[ForeachStatement] = None
    _transformer: Optional[Transformer] = None
    _default_val: Optional[Statement] = None
    _error_val: Optional[Statement] = None

    _transformers: ClassVar[dict[str, type[Transformer]]] = {}  # just a type annotation here, no value yet

    @classmethod
    def compile_object(cls, compiler: DocCompiler, args: dict[str, Any]):

        source = ""
        v_defines = [
            DefineVar(_name = name, _expr = compiler.statement(expr, source))
            for name, expr in v.items()
            ] if ( v := args.get("set", None)) else None

        v_if = compiler.condition(v, source) if (v := args.get("if", True)) else False

        v_data = compiler.statement(v, source) if ( v:= args.get("data", None)) else None
        
        v_loop = args.get("foreach", None)
        v_foreach = None
        if isinstance(v_loop, dict):
            v_foreach = isinstance(v_loop, dict)
            # Compile time constants
            v_foreach_key = v_loop.get("key", None)
            v_foreach_value = v_loop.get("value", None)
            v_foreach_index = v_loop.get("index", None)
            # Runtime expressions
            v_foreach_in = compiler.statement(v, source) if ( v:= v_loop.get("in", None)) else None
            v_foreach_cond = compiler.statement(v, source) if ( v := v_loop.get("if", None)) else True
            v_foreach_start = compiler.statement(v, source) if ( v := v_loop.get("start", None)) else None
            v_foreach_stop = compiler.statement(v, source) if ( v := v_loop.get("stop", None)) else None
            v_foreach_limit = compiler.statement(v, source) if ( v := v_loop.get("limit", None)) else None
            v_foreach = ForeachStatement(
                key = v_foreach_key,
                value = v_foreach_value,
                index = v_foreach_index,
                items = v_foreach_in,
                cond = v_foreach_cond,
                start = v_foreach_start,
                stop = v_foreach_stop,
                limit = v_foreach_limit,
            )
        elif v_loop is not None:
            compiler.record_notice(JFTLNotice(
                    code="BAD_FOREACH",
                    message=f"foreach should be an object, got {type(v_loop)}",
            ))

        v_cases = [
            Case( _cond = compiler.condition( case["when"], source ), _body = compiler.statement( case[ "then" ], source ))
            for case in cases
            ] if (cases := args.get("case", None)) else None

        v_body = compiler.statement(v, source) if ( v := args.get("body", None)) is not None else None
        v_default = compiler.statement(v, source) if ( v := args.get("default", None)) is not None else None
        v_error = compiler.statement(v, source) if ( v := args.get("error", None)) is not None else None

        v_transformer = None
        if ( transform := args.get("transform", None)):
            transform_class = cls._transformers.get(transform, None)
            if not transform_class:
                compiler.record_notice(JFTLNotice(
                        code="BAD_TRANSFORM",
                        message=f"Unknown transformation {transform}",
                ))

            elif not issubclass(transform_class, Transformer):
                compiler.record_notice(JFTLNotice(
                        code="BAD_TRANSFORM",
                        message=f"Unknown transformation {transform}",
                ))
            else:
                v_transformer = transform_class()


        self = cls(
            _defines = v_defines,
            _if = v_if,
            _set_current = v_data,
            _foreach = v_foreach,
            _cases = v_cases,
            _body = v_body,
            _default_val = v_default,
            _error_val = v_error,
            _transformer = v_transformer,
        )
        return self

    def _eval_foreach(self, frame: RuntimeState, body: Statement) -> list[RUNTIME_DOC] | dict[str, RUNTIME_DOC] | JFTLNotice | Missing | None:
        foreach = cast(ForeachStatement, self._foreach)
        items = frame.eval_value(foreach.items) if foreach.items else frame.current

        ix_start = frame.eval_value(foreach.start)
        if ix_start is not None and not isinstance(ix_start, int):
            return JFTLNotice(
                    code="BAD_START",
                    message=f"foreach 'start' must be an integer value",
                ) 
        ix_stop = frame.eval_value(foreach.stop)
        if ix_stop is not None and not isinstance(ix_stop, int):
            return JFTLNotice(
                    code="BAD_STOP",
                    message=f"foreach 'stop' must be an integer value",
                ) 

        ix_limit = frame.eval_value(foreach.limit)
        if ix_limit is not None and not isinstance(ix_limit, int):
            return JFTLNotice(
                    code="BAD_STOP",
                    message=f"foreach 'stop' must be an integer value",
                ) 

        start_index = ix_start if ix_start is not None else 0
        loop_iter = None
        count = None

        do_dict = False
        if isinstance(items, list):
            if items == None:
                return None

            count = len(items)
            loop_iter = enumerate(items)

        elif isinstance(items, dict):
            do_dict = True
            count = len(items)
            loop_iter = iter(items.items())

        elif isinstance(items, int) and not isinstance(items, bool):
            count = items - start_index
            loop_iter = enumerate(range(start_index, items))
            ix_stop = ix_stop - start_index if ix_stop else None
            start_index = 0

        # Support negative indexes if count is known.
        stop_index = ix_stop
        if count is not None:
            # Make sure start_index has value
            if start_index < 0:
                start_index = count + start_index
            # Make sure that stop_index has value
            if stop_index is None:
                stop_index = count
            elif stop_index < 0:
                stop_index = count + stop_index

        new_vars = frame.vars
        # Process foreach loop
        v_value = foreach.value
        v_key = foreach.key
        v_cond = foreach.cond
        v_index = foreach.index
        dict_result : dict[str, Any]= {}
        list_result = []

        result = dict_result if do_dict else list_result
        if ix_limit == 0 or not loop_iter:
            return result

        pos = -1
        out_count = 0
        for key, item in loop_iter:
            pos = pos+1
            if (start_index is not None and pos < start_index) or (stop_index is not None and pos >= stop_index):
                continue
            new_key = cast(str, key) if do_dict else None
            if v_key:
                new_vars[v_key] = key

            if v_index:
                new_vars[v_index] = pos

            if v_value:
                new_vars[v_value] = item
            else:
                frame.set_current(item)

            if not frame.eval_bool(v_cond):
                continue
            new_val = frame.eval_value(body)
            if isinstance(new_val, JFTLNotice):
                return new_val
            elif new_val == SKIP_VALUE:
                continue

            if do_dict:
                dict_result[cast(str, new_key)] = new_val
            else:
                list_result.append(new_val)

            # Apply limit, if ix_limit is set
            out_count = out_count + 1
            if ix_limit is not None and out_count >= ix_limit:
                stop_index = start_index + ix_limit

        return dict_result if do_dict else list_result
        
    def _choose_body(self, frame: Frame) -> Statement | None:
        v_body = self._body
        if (cases := self._cases):
            for case in cases:
                if frame.eval_bool(case._cond):
                    v_body = case._body
                    break

        return v_body

    def eval(self, prev_frame: Frame) -> RUNTIME_DOC:

        # Create a new frame to use
        new_frame = prev_frame.child_state("logic")
        new_vars = new_frame.vars
        # Build local vars, inside the new frame.
        if (set_vars := self._defines):
            for set_var in set_vars:
                name = set_var._name
                value = new_frame.eval_value(set_var._expr)
                new_vars[name] = value
            if not new_frame.global_frame:
                new_frame.global_frame = new_frame
                new_vars["_global"] = new_frame

        # Check the condition
        if not new_frame.eval_bool(self._if):
            return new_frame.eval_value(self._default_val)
            
        # Consider new data object.
        if ( v_data := self._set_current):
            new_frame.set_current(new_frame.eval_value(v_data))
        
        # Choose body to execute
        v_body = self._choose_body(new_frame)

        if v_body is None:
            return new_frame.eval_value(self._default_val)

        # Check if executing foreach loop
        result = None
        if self._foreach:
            result = self._eval_foreach(new_frame, v_body)
            
            if result is None or isinstance(result, Missing):
                return new_frame.eval_value(self._default_val)

        # Process Single result
        else:
            result = new_frame.eval_value(v_body)

            if isinstance(result, Missing):
                return new_frame.eval_value(self._default_val)

        if not isinstance(result, (NoneType, JFTLNotice, Missing)) and self._transformer:
            result = self._transformer.transform(result)
             
        # Error handler
        if isinstance(result, JFTLNotice):
            if self._error_val is not None:
                return new_frame.eval_value(self._error_val)

        return result
    
    @classmethod
    def class_init(cls):
        cls._transformers = {
            "flatten": _FlattenningTransformer,
            "merge": _MergeTransformer,
            "to_pairs": _ToPairsTransformer,
            "from_pairs": _FromPairsTransformer,
            "drop_missing": _DropMissingTransformer,
            "concat": _JoinStrTransformer,
        }

LogicStatement.class_init()
