import itertools
import re
from types import NoneType
from typing import Any, Optional, cast
from dataclasses import dataclass

from model import FAST_INLINE, COMPILE_DOC, JFTL_BREAK, JFTL_SKIP, JSON_DOC, JSON_VALUE_TYPES, JSON_UNSET, RUNTIME_DOC, RUNTIME_LIST_TYPES, RUNTIME_NULL_TYPES, CompileContext, CompilerPlugin, DocCompiler, Evaluator, Expression, RuntimeContext, Condition, Statement, StatementCompiler, Transformer, my_profile
from template import MISSING_VALUE, JFTLNotice, Missing

@dataclass
class _DefineVar:
    name: str
    expr: Statement

@dataclass
class _CaseItem:
    cond: Condition
    body: Statement


@dataclass(slots=True, frozen=True, kw_only=True)
class _CaseEvaluator(Evaluator):
    cases: list[_CaseItem | JFTLNotice]
    default_case: Optional[Statement]

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        selected = self.default_case
        if (cases := self.cases):
            for case in cases:
                if isinstance(case, JFTLNotice):
                    return case
                cond_result = ctx.eval_bool(case.cond)
                if isinstance(cond_result, JFTLNotice):
                    return cond_result
                elif cond_result:
                    selected = case.body
                    break

        result = ctx.eval_value(selected)
        return result        

@dataclass(slots=True)
class _ForeachPart():
    key_var: Optional[str] = None
    value_var: Optional[str] = None
#    iter_var: Optional[str] = None
    set: Optional[list[_DefineVar]] = None
    items: Optional[Statement] = None
    cond: Optional[Condition] = None
    out: Optional[Statement] = None
    update: Optional[list[_DefineVar]] = None
    start: Optional[Statement] = None
    stop: Optional[Statement] = None
    limit: Optional[Statement] = None

@dataclass(slots=True, frozen=True, kw_only=True)
class LogicStatement(Evaluator):
    # Stage 1: setup "set", "check")
    _defines: Optional[list[_DefineVar]] = None
    _if: Optional[Condition] = None
    # Stage 2: current object selection "case", "data"
    _set_current: Optional[Statement] = None
    # Stage 3 ("foreach")
    _foreach: Optional[_ForeachPart] = None
    # Stage 4 — Returned value ("transform", "return")
    _out: Optional[Statement] = None
    _transformer: Optional[Transformer] = None
    # Stage 6 Fallback — wraps the whole pipeline
    _default_val: Optional[Statement] = None
    _error_val: Optional[Statement] = None

    @my_profile
    def _eval_foreach(self, ctx: RuntimeContext) -> list[RUNTIME_DOC] | dict[str, RUNTIME_DOC] | JFTLNotice | Missing:
        pass
        foreach = cast(_ForeachPart, self._foreach)
        items = ctx.eval_value(foreach.items) if foreach.items is not JSON_UNSET else ctx.current

        ix_start = ctx.eval_value(foreach.start)
        if not isinstance(ix_start, (NoneType, int)) or isinstance(ix_start, bool):
            return JFTLNotice(
                    code="FOREACH_START",
                    message=f"foreach 'start' must be an integer value",
                ) 
        ix_stop = ctx.eval_value(foreach.stop)
        if not isinstance(ix_stop, (NoneType, int)) or isinstance(ix_stop, bool):
            return JFTLNotice(
                    code="FOREACH_STOP",
                    message=f"foreach 'stop' must be an integer value",
                ) 

        ix_limit = ctx.eval_value(foreach.limit)
        if not isinstance(ix_limit, (NoneType, int)) or isinstance(ix_limit, bool):
            return JFTLNotice(
                    code="FOREACH_LIMIT",
                    message=f"foreach 'stop' must be an integer value",
                ) 

        start_index = ix_start if ix_start is not None else 0
        loop_iter = None
        count = None

        do_dict = False
        if isinstance(items, RUNTIME_LIST_TYPES):
            count = len(items)
            loop_iter = enumerate(items)

        elif isinstance(items, dict):
            do_dict = True
            count = len(items)
            loop_iter = iter(items.items())

        elif isinstance(items, int) and not isinstance(items, bool):
            if items < 0:
                return JFTLNotice(code="FOREACH_NEGATIVE", message=f"foreach 'in' accept only non-negative integer, got {items}")
            count = items - start_index
            loop_iter = enumerate(range(start_index, items))
            ix_stop = ix_stop - start_index if ix_stop else None
            start_index = 0
        elif isinstance(items, RUNTIME_NULL_TYPES):
            return MISSING_VALUE
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
        # Fetch foreach structure for fast performance
        v_value = foreach.value_var
        v_key = foreach.key_var
        v_cond = foreach.cond
        cond_expr = isinstance(v_cond, Evaluator)
        v_out = foreach.out
        v_out_expr = isinstance(v_out, Evaluator)
        v_update = foreach.update

        # Setup output
        dict_result : dict[str, Any]= {}
        list_result = []

        if ix_limit == 0:
            return dict_result if do_dict else list_result
        
        pos = -1
        out_count = 0

        if start_index or stop_index:
            loop_iter = itertools.islice(loop_iter, start_index, stop_index)

        # Dictionary - current context variables
        new_vars = ctx.vars
        for key, item in loop_iter:
            pos = pos+1

            if v_key:
                new_vars[v_key] = key

            if v_value:
                new_vars[v_value] = item
            elif FAST_INLINE:
                # Calling via ctx.set_current is 10X slower
                ctx.current = item
                new_vars["_"] = item
            else:
                ctx.set_current(item)

            if not v_cond is True:
                cond_result = ctx.eval_bool(v_cond) if cond_expr else v_cond
                if cond_result is True:
                    pass
                elif cond_result is False:
                    continue
                elif isinstance(cond_result, JFTLNotice):
                    return cond_result
                elif not cond_result:
                    continue
                
            if v_out:
                # No point of inlining - v_out is always an expression.
                item = ctx.eval_value(v_out) if v_out_expr else v_out
                if FAST_INLINE:
                    # Calling via ctx.set_current is 10X slower
                    ctx.current = item
                    new_vars["_"] = item
                else:
                    ctx.set_current(item)

                if isinstance(item, JSON_VALUE_TYPES):
                    pass
                elif item is JFTL_SKIP:
                    continue
                elif item is JFTL_BREAK:
                    break
                elif isinstance(item, JFTLNotice):
                    return item

            if do_dict:
                dict_result[cast(str, key)] = item
            else:
                list_result.append(item)

            # Build local vars, inside the new frame.
            if (v_update):
                for set_var in v_update:
                    name = set_var.name
                    value = ctx.eval_value(set_var.expr)
                    if isinstance(value, JFTLNotice):
                        return value
                    new_vars[name] = value

            # Apply limit, if ix_limit is set
            out_count = out_count + 1
            if ix_limit is not None and out_count >= ix_limit:
                break

        return dict_result if do_dict else list_result

    def _return_result(self, ctx: RuntimeContext, result: RUNTIME_DOC) -> RUNTIME_DOC:
        if isinstance(result, Missing):
            if self._default_val is not JSON_UNSET:
                result = ctx.eval_value(self._default_val)

        if isinstance(result, JFTLNotice):
            if self._error_val is not JSON_UNSET:
                result = ctx.eval_value(self._error_val)
        
        return result 

    def _eval(self, ctx: RuntimeContext) ->RUNTIME_DOC:
        new_vars = ctx.vars

        # Build local vars, inside the new frame.
        if (set_vars := self._defines):
            for set_var in set_vars:
                name = set_var.name
                value = ctx.eval_value(set_var.expr)
                new_vars[name] = value
            if not ctx.global_ctx:
                ctx.global_ctx = ctx
                new_vars["_global"] = ctx

        # Check the condition
        if_result = ctx.eval_bool(self._if)
        if isinstance(if_result, JFTLNotice):
            return self._return_result(ctx, if_result)
        if not if_result:
            return self._return_result(ctx, MISSING_VALUE)

        # Set new data object, if needed
        current = ctx.current
        if ( v_set_current := self._set_current ) is not JSON_UNSET:
            v_data = ctx.eval_value(v_set_current)
            if isinstance(v_data, JFTLNotice):
                return self._return_result(ctx, v_data)
            current = v_data
            ctx.set_state_data(current)
            ctx.set_current(current)

        # Check if executing foreach loop
        # May return Missing, which should result in early exit
        if self._foreach:
            v_foreach = self._eval_foreach(ctx)
            if isinstance(v_foreach, (RUNTIME_NULL_TYPES, JFTLNotice)):
                return self._return_result(ctx, v_foreach)
            ctx.set_current(v_foreach)
            current = v_foreach

        # Transformation, as long as the value is "something"
        if ( v_return := self._out):
            current = ctx.eval_value(v_return)
            if isinstance(current, JFTLNotice):
                return self._return_result(ctx, current)

        if self._transformer and not isinstance(current, Missing):
            current = self._transformer.transform(current)
            if isinstance(current, (RUNTIME_NULL_TYPES, JFTLNotice)):
                return self._return_result(ctx, current)
            ctx.set_current(current)

        return current

    def eval(self, ctx: RuntimeContext) -> RUNTIME_DOC:
        new_frame = ctx.child_state("logic")

        result = self._eval(new_frame)
        # Create a new frame to use
        if isinstance(result, Missing):
            if self._default_val is not JSON_UNSET:
                result = new_frame.eval_value(self._default_val)
            
        # Error handler
        if isinstance(result, JFTLNotice):
            if self._error_val is not JSON_UNSET:
                return new_frame.eval_value(self._error_val)

        return result

@dataclass(slots=True)
class LogicCompiler(StatementCompiler):

    def compile_str(self, source: str, where: CompileContext ) -> COMPILE_DOC :
        return JFTLNotice(code="LOGIC-NO-STR", message="Logic Plugin does not accept strings")

    def _compile_expr(self, args: dict[str, JSON_DOC], tag: str, cc: CompileContext,  *, unset_value: Expression = JSON_UNSET, record: bool = False ) -> Expression:
        if not tag in args:
            return unset_value
               
        expr = self.compiler.statement(args.pop(tag), cc.child(tag))
        if isinstance(expr, JFTLNotice) and record:
            self.compiler.record_notice(expr)
        return expr
    
    def _compile_cond(self, args: dict[str, JSON_DOC], tag: str, cc: CompileContext, *, unset_value: Expression = JSON_UNSET ) -> Condition:
        if not tag in args:
            return unset_value
        
        expr = self.compiler.condition(args.pop(tag), cc.child(tag))
        return expr
    

    # Compile the 'out' statement or a 'case' statement with chain if if-elif-elif-else.
    def _compile_out_or_case(self, source: dict[str, JSON_DOC], cc: CompileContext) -> Expression:

        # If 'out' is present, make sure no 'case' exists (OK to hav case=None!)
        cases = source.pop("case", None)

        if "out" in source:
            if not cases in (None, []):
                return JFTLNotice(code="OUT-CASE-CONFLICT", message="Either 'out' or 'case' are allowed, but not both")

            return self._compile_expr(source, "out", cc, record=True)
        
        if cases in (None, []):
            return None

        if not isinstance(cases, list):
            return JFTLNotice(code="LOGIC-BAD-CASE", message=f"Logic `case` expecting 'case, got {type(cases)}")

        # The last case can be 'else': 'expr', and is converted to 'when': True, 'then': 'expr'
        default_case = None
        else_case = cases.pop() if cases and isinstance(cases[-1], dict) and len(cases[-1]) == 1 and "else" in cases[-1] else None
        if isinstance(else_case, dict):
            default_case = self._compile_expr(else_case, "else", cc)
           
        v_cases = [
            _CaseItem(
                cond = self._compile_cond(case, "when", cc),
                body = self._compile_expr(case, "then", cc),
            )
            if isinstance(case, dict) and len(case) == 2 and "when" in case and "then" in case
            else JFTLNotice(code="LOGIC-BAD-CASE", message=f"Logic `case` expecting dict with when/then {type(case)}")
            for case in cases
            ]

        return _CaseEvaluator(cc, source_code=None, cases=v_cases, default_case=default_case)


    _TOKEN_RE = re.compile(r"^[A-Za-z]\w*$", re.ASCII)

    def _parse_var(self, var_name, label: str) -> str | None:
        if not isinstance(var_name, str):
            self.compiler.record_notice(JFTLNotice(code="LOGIC-BAD-ID", message=f"Expecting variable name for '{label}', got '{type(var_name)}'"))
            return None
        if not self._TOKEN_RE.fullmatch(var_name):
            self.compiler.record_notice(JFTLNotice(code="LOGIC-BAD-ID", message=f"Invalid variable name for '{label}', got 'var_name'"))
            return None
        return var_name


    def _get_named_var(self, args: dict[str, JSON_DOC], tag: str, fallback: Optional[str] = None) -> str | None :
        if not tag in args:
            return fallback
        return self._parse_var(args.pop(tag), tag)
    
    def _parse_set_var(self, source: dict[str, JSON_DOC], cc: CompileContext) -> Optional[list[_DefineVar]]:

        set_list = [
            (
                self._parse_var(name, f"{pos+1}"),
                self.compiler.statement(expr, cc.child(name)),
            )
            for pos, [name, expr] in enumerate(source.items())
        ]

        var_list = [ _DefineVar(name= n, expr= e ) for n, e in set_list if isinstance(n, str)]
        return var_list

    def _compile_set_vars(self, source: dict[str, JSON_DOC], tag: str, cc: CompileContext) -> Optional[list[_DefineVar]]:
        if not tag in source:
            return None
        
        set_body = source.pop(tag)
        if set_body is None:
            return None

        if not isinstance( set_body, dict ):
            self.compiler.record_notice(JFTLNotice(code="LOGIC-BAD-SET", message=f"Logic {tag} expecting dictionary, got {type(source)}"))
            return None
        
        return self._parse_set_var(set_body, cc.child(tag))

    def _record_notice(self, notice: JFTLNotice):
        return self.compiler.record_notice(notice)

    def _compile_foreach(self, source_elem: dict[str, JSON_DOC], cc: CompileContext) -> _ForeachPart:

        source = dict(source_elem)
        v_foreach_key = self._get_named_var(source, "key", "_key")
        v_foreach_value = self._get_named_var(source, "var")
#            v_foreach_iter = self._get_named_var(v_loop, "var")

        # Runtime expressions
        v_foreach_in = self._compile_expr(source, "in", cc)
        v_foreach_start = self._compile_expr(source, "start", cc, unset_value=0)
        v_foreach_stop = self._compile_expr(source, "stop", cc, unset_value=None)
        v_foreach_limit = self._compile_expr(source, "limit", cc, unset_value=None)

        v_foreach_cond = self._compile_cond(source, "if", cc, unset_value=True)
        v_foreach_out = self._compile_out_or_case(source, cc)
        v_foreach_update = self._compile_set_vars(source, "update", cc)
        
        v_foreach = _ForeachPart(
            key_var = v_foreach_key,
            value_var = v_foreach_value,
#                iter_var = v_foreach_iter,

            items = v_foreach_in,               
            start = v_foreach_start,
            stop = v_foreach_stop,
            limit = v_foreach_limit,

            cond = v_foreach_cond,
            out = v_foreach_out,
            update = v_foreach_update,
        )

        if source:
            self._record_notice(JFTLNotice(
                    code="FOREACH-UNKNOWN-TAGS",
                    message=f"Found {len(source)} unknown attributes: { list(source.keys())[:3] }",
                ))

        return v_foreach


    def _compile_object(self, source_elem: dict[str, JSON_DOC], cc: CompileContext) -> LogicStatement:

        source = dict(source_elem)

        v_defines = None
        v_defines = self._compile_set_vars(source, "set", cc)
            
        v_if = self._compile_cond(source, "check", cc, unset_value=True)
        v_set_data = self._compile_expr(source, "data", cc)
        
        v_loop = source.pop("foreach", None)
        v_foreach = None
        if isinstance(v_loop, dict):
            v_foreach = self._compile_foreach(v_loop, cc.child("foreach"))
        elif v_loop is not None:
            self._record_notice(JFTLNotice(
                    code="BAD_FOREACH",
                    message=f"foreach should be an object, got {type(v_loop)}",
            ))

        v_transformer = None
        if ( transform := self._get_named_var(source, "transform")):
            plugin = self.compiler.plugin(transform)
            v_transformer = plugin if isinstance(plugin, Transformer) else None
            if not v_transformer:
                self._record_notice(JFTLNotice(
                        code="BAD_TRANSFORM",
                        message=f"Unknown transformation {transform}",
                ))

        v_out = self._compile_out_or_case(source, cc)
        v_default =  self._compile_expr(source, "fallback", cc)
        v_error =  self._compile_expr(source, "error", cc)


        stmt = LogicStatement(cc,
            _defines = v_defines,
            _if = v_if,
            _set_current = v_set_data,
            _foreach = v_foreach,
            _default_val = v_default,
            _error_val = v_error,
            _transformer = v_transformer,
            _out = v_out,
        )

        if source:
            self._record_notice(JFTLNotice(
                    code="LOGIC-UNKNOWN-TAGS",
                    message=f"Found {len(source)} unknown attributes: { list(source.keys())[:3] }",
                    where = cc.where
                ))

             # Make sure no unprocessed attributes
        return stmt
    
    def compile(self, source: JSON_DOC, where: CompileContext) -> LogicStatement | JFTLNotice:
        if not isinstance(source, dict):
            return JFTLNotice(code="LOGIC-BAD-SOURCE", message=f"Logic expect object, got {type(source)}")

        return self._compile_object(source, where)

class LoginPlugin(CompilerPlugin):

    def createCompiler(self, docCompiler: DocCompiler) -> StatementCompiler :
        return LogicCompiler(docCompiler)
