import re
from types import NoneType
from typing import Any, ClassVar, Optional, cast
from dataclasses import dataclass

from core import JSON_DOC, RUNTIME_DOC
from model import COMPILE_DOC, JSON_UNSET, Evaluator, Expression, RuntimeContext, Condition, Statement, StatementCompiler, Transformer
from template import MISSING_VALUE, SKIP_VALUE, JFTLNotice, Missing

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
    cond: Condition
    body: Statement

@dataclass
class DefineVar:
    name: str
    expr: Statement

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
    
    # dict -> list[tuple[str, RUNTIME_DOC]]
class _ToPairsTransformer(Transformer):
    def _transform(self, input: dict[str, RUNTIME_DOC]) -> list[RUNTIME_DOC]:
        return [[key, value] for key, value in input.items()]
    
    def transform(self, input: RUNTIME_DOC) -> RUNTIME_DOC:
        if not isinstance(input, dict):
            return JFTLNotice(
                    code="TO_PAIRS_INPUT",
                    message=f"The 'to_pairs' transformation input is array of objects, got non-list input",
                )

        return self._transform(input)


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

    def _transform(self, input: list[str | None | Missing]) -> str | JFTLNotice :
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

    def transform(self, input: RUNTIME_DOC) -> RUNTIME_DOC:
        return self._transform(cast(list[str | None | Missing], input))


@dataclass(slots=True)
class LogicStatement(Evaluator):

    _defines: Optional[list[DefineVar]] = None
    _if: Optional[Condition] = None
    _set_current: Optional[Statement] = None
    _cases: Optional[list[Case | JFTLNotice ]] = None
    _body: Optional[Statement] = None
    _foreach: Optional[ForeachStatement] = None
    _transformer: Optional[Transformer] = None
    _default_val: Optional[Statement] = None
    _error_val: Optional[Statement] = None

    def _eval_foreach(self, ctx: RuntimeContext, body: Statement) -> list[RUNTIME_DOC] | dict[str, RUNTIME_DOC] | JFTLNotice | Missing:
        foreach = cast(ForeachStatement, self._foreach)
        items = ctx.eval_value(foreach.items) if foreach.items is not JSON_UNSET else ctx.current

        ix_start = ctx.eval_value(foreach.start)
        if ix_start is not None and not isinstance(ix_start, int):
            return JFTLNotice(
                    code="FOREACH_START",
                    message=f"foreach 'start' must be an integer value",
                ) 
        ix_stop = ctx.eval_value(foreach.stop)
        if ix_stop is not None and not isinstance(ix_stop, int):
            return JFTLNotice(
                    code="FOREACH_STOP",
                    message=f"foreach 'stop' must be an integer value",
                ) 

        ix_limit = ctx.eval_value(foreach.limit)
        if ix_limit is not None and not isinstance(ix_limit, int):
            return JFTLNotice(
                    code="FOREACH_LIMIT",
                    message=f"foreach 'stop' must be an integer value",
                ) 

        start_index = ix_start if ix_start is not None else 0
        loop_iter = None
        count = None

        do_dict = False
        if isinstance(items, list):
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
        else:
            return JFTLNotice(code="FOREACH_IN", message=f"foreach expecting list/dict/int, got {type(items)}")

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

        new_vars = ctx.vars
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
                ctx.set_current(item)

            if not ctx.eval_bool(v_cond):
                continue
            new_val = ctx.eval_value(body)
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
        
    def _choose_body(self, ctx: RuntimeContext) -> Statement:
        if (cases := self._cases):
            for case in cases:
                if isinstance(case, JFTLNotice):
                    return case
                if ctx.eval_bool(case.cond):
                    return case.body

        return self._body

    def _return_result(self, ctx: RuntimeContext, result: RUNTIME_DOC) -> RUNTIME_DOC:
        if isinstance(result, Missing):
            if self._default_val is not JSON_UNSET:
                result = ctx.eval_value(self._default_val)

        if isinstance(result, JFTLNotice):
            if self._error_val is not None:
                result = ctx.eval_value(self._error_val)
        
        return result

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:

        # Create a new frame to use
        new_frame = ctx.child_state("logic")
        new_vars = new_frame.vars
        # Build local vars, inside the new frame.
        if (set_vars := self._defines):
            for set_var in set_vars:
                name = set_var.name
                value = new_frame.eval_value(set_var.expr)
                new_vars[name] = value
            if not new_frame.global_ctx:
                new_frame.global_ctx = new_frame
                new_vars["_global"] = new_frame

        # Check the condition
        if not new_frame.eval_bool(self._if):
            return self._return_result(ctx, MISSING_VALUE)
            
        # Consider new data object.
        if ( v_data := self._set_current) is not JSON_UNSET:
            new_frame.set_current(new_frame.eval_value(v_data))
        
        # Choose body to execute
        v_body = self._choose_body(new_frame)

        if v_body is JSON_UNSET:
            return self._return_result(new_frame, MISSING_VALUE)

        # Check if executing foreach loop
        result = None

        if self._foreach:
            result = self._eval_foreach(new_frame, v_body)

        # Process Single result
        else:
            result = new_frame.eval_value(v_body)

        # Transformation, as long as the value is "something"
        if not isinstance(result, (JFTLNotice, Missing)) and self._transformer :
            result = self._transformer.transform(result)

        if isinstance(result, Missing):
            if self._default_val is not JSON_UNSET:
                result = new_frame.eval_value(self._default_val)

            return result
            
        # Error handler
        if isinstance(result, JFTLNotice):
            if self._error_val is not JSON_UNSET:
                return new_frame.eval_value(self._error_val)

        return result
    


@dataclass
class LogicCompiler(StatementCompiler):

    _transformers: ClassVar[dict[str, type[Transformer]]] = {}  # just a type annotation here, no value yet

    def compile_str(self, source: str, where: str = "" ) -> COMPILE_DOC :
        return JFTLNotice(code="LOGIC-NO-STR", message="Logic Plugin does not accept strings")

    def _compile_expr(self, args: dict[str, JSON_DOC], tag: str, unset_value: Expression = JSON_UNSET ) -> Expression:
        if not tag in args:
            return unset_value
        
        expr = self.compiler.statement(args[tag], tag)
        return expr
    
    def _compile_cond(self, args: dict[str, JSON_DOC], tag: str, unset_value: Expression = JSON_UNSET ) -> Condition:
        if not tag in args:
            return unset_value
        
        expr = self.compiler.condition(args[tag], tag)
        return expr

    TOKEN_RE = re.compile(r"^[A-Za-z]\w*$", re.ASCII)
    def _get_named_var(self, args: dict[str, JSON_DOC], tag: str) -> str | None :
        if not tag in args:
            return None
        var_name = args[tag]
        if not isinstance(var_name, str):
            self.compiler.record_notice(JFTLNotice(code="LOGIC-BAD-ID", message=f"Expecting variable name for '{tag}', got '{type(var_name)}'"))
            return None
        return var_name

    def _compile_object(self, source: dict[str, JSON_DOC], where: str = "") -> LogicStatement:
        compiler = self.compiler

        v_defines = None
        defines = source.get("set", {})
        if isinstance( defines, dict ):
            v_defines = [
                DefineVar(
                    name = name,
                    expr = compiler.statement(expr, f"set({name})")
                    )
                for name, expr in defines.items()
            ]
        else:
            compiler.record_notice(JFTLNotice(code="LOGIC-BAD-SET", message=f"Logic 'set' expecting dictionary, got {type(defines)}"))
            
        v_if = self._compile_cond(source, "if", True)

        v_data = self._compile_expr(source, "data")
        
        v_loop = source.get("foreach", None)
        v_foreach = None
        if isinstance(v_loop, dict):
            # Compile time constants
            v_foreach_key = self._get_named_var(v_loop, "key")
            v_foreach_value = self._get_named_var(v_loop, "value")
            v_foreach_index = self._get_named_var(v_loop, "index")
            # Runtime expressions
            v_foreach_in = self._compile_expr(v_loop, "in")
            v_foreach_cond = self._compile_cond(v_loop, "if", True)
            v_foreach_start = self._compile_expr(v_loop, "start", 0)
            v_foreach_stop = self._compile_expr(v_loop, "stop", None)
            v_foreach_limit = self._compile_expr(v_loop, "limit", None)
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

        v_cases = None
        cases = source.get("case", [])
        if isinstance(cases, list):
            v_cases = [
                Case(
                    cond = self._compile_cond(case, "when"),
                    body = self._compile_expr(case, "then"),
                )
                if isinstance(case, dict)
                else JFTLNotice(code="LOGIC-BAD-CASE", message=f"Logic `case` expecting 'case, got {type(case)}")
                for case in cases
            ]
        else:
            compiler.record_notice(JFTLNotice(code="LOGIC-BAD-CASE", message=f"Logic 'case' expecting list[case], got {type(cases)}"))


        v_body = self._compile_expr(source, "body")
        v_default =  self._compile_expr(source, "default")
        v_error =  self._compile_expr(source, "error")

        v_transformer = None
        if ( transform := self._get_named_var(source, "transform")):
            transform_class = self._transformers.get(transform, None)
            if not transform_class:
                compiler.record_notice(JFTLNotice(
                        code="BAD_TRANSFORM",
                        message=f"Unknown transformation {transform}",
                ))

            else:
                v_transformer = transform_class()


        self = LogicStatement(
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
    
    def compile(self, source: JSON_DOC, where: str = "") -> LogicStatement | JFTLNotice:
        if not isinstance(source, dict):
            return JFTLNotice(code="LOGIC-BAD-SOURCE", message=f"Logic expect object, got {type(source)}")

        return self._compile_object(source, where)

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


LogicCompiler.class_init()
