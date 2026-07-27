from __future__ import annotations
from dataclasses import dataclass, field, replace
from types import NoneType
from typing import Any, Optional, cast

from model import JFTL_NOTICE, JFTL_RAISE, JSON_UNSET, RUNTIME_BOOL, RUNTIME_DOC, NoValueType, Condition, Environment, Evaluator, RuntimeContext, Statement
from template import SKIP_VALUE, ERROR_VALUE, MISSING_VALUE, JFTLException, JFTLNotice, Missing

# Template Class - represent compiled templates

# Runtime Objects

@dataclass
class Frame (RuntimeContext):

    # Cached value, including inherited, calculated, ...
    _cache:  dict[str, Any] = field(default_factory=dict)
    _full_path: str = ""

    def _resolve(self, error: JFTLNotice, on: Any) -> Any:
        if on is JFTL_RAISE:
            raise JFTLException(error)
        if on is JFTL_NOTICE:
            return error
        return on

    def eval_value(
        self,
        stmt : Statement,
        *,
        context: Optional[str] = None,
        on_null: Any = JSON_UNSET,
        on_error: Any = JFTL_NOTICE,
        on_unset: Any = JFTL_RAISE,
    ) -> RUNTIME_DOC:
        
        self.env.eval_count += 1
        result = stmt.eval(self) if isinstance(stmt, Evaluator) else cast(RUNTIME_DOC, stmt)

        if isinstance(result, JFTLNotice):
            return self._resolve(result, on_error)

        elif isinstance(result, NoValueType):
            if on_unset is JFTL_RAISE or on_unset is JFTL_NOTICE:
                error = JFTLNotice(
                    code="UNSET_STATEMENT",
                    where=self.where(context),
                    message="Condition not specified",
                )
                return self._resolve(error, on_unset)
            return on_unset

        elif isinstance(result, (NoneType, Missing)):
            if on_null is JFTL_RAISE or on_null is JFTL_NOTICE:
                error = JFTLNotice(
                    code="MISSING_VALUE",
                    where=self.where(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_null)
            return result if on_null is JSON_UNSET else on_null

        return result        

    def eval_bool(
        self,
        cond : Condition,
        *,
        context: Optional[str] = None,
        on_null: Any = False,
        on_error: Any = JFTL_NOTICE,
        on_unset: Any = JFTL_RAISE,
    ) -> RUNTIME_BOOL:
        """Default: JFTL's strict falsiness — False | null | Missing are
        falsy, everything else truthy. Pass on_null=_RAISE (or _ERROR)
        to instead treat a missing/null result as a failure in this
        context. Override for engine-specific truthiness."""

        self.env.eval_count += 1
        result = cond.eval(self) if isinstance(cond, Evaluator) else cond

        if isinstance(result, JFTLNotice):
            return self._resolve(result, on_error)

        elif isinstance(result, NoValueType):
            if on_unset is JFTL_RAISE or on_unset is JFTL_NOTICE:
                error = JFTLNotice(
                    code="UNSET_CONDITION",
                    where=self.where(context),
                    message="Condition not specified",
                )
                return self._resolve(error, on_unset)
            return on_unset

        elif isinstance(result, (NoneType, Missing)):
            if on_null is JFTL_RAISE or on_null is JFTL_NOTICE:
                error = JFTLNotice(
                    code="MISSING_VALUE",
                    where=self.where(context),
                    message="value is missing or null",
                )
                return self._resolve(error, on_null)
            return on_null

        if result is False:
            return False
        return True


    def _update_current(self):
        self.vars["_"] = self.current

    def set_current(self, current: Any):
        super().set_current(current)
        self._update_current()

    @classmethod
    def root_context(cls, env: Environment) -> Frame:
        top_vars = {
            "_missing": MISSING_VALUE,
            "_error": ERROR_VALUE,
            "_skip" : SKIP_VALUE,
            "_input" : env.input,
            "_level" : 0,
            "_datasets": env.datasets,
            "_": env.input,
        }
        frame = cls(env=env, current=env.input, level=0, parent=None, vars=top_vars, part_path="")
        # Must "Patch" the environment to point back to the root frame.
        # May want one day to point each frame direct to the top, to avoid circular
        env.top = frame
        top_vars["_top"] = frame
        top_vars["_external"] = top_vars
        top_vars["_local"] = top_vars
        frame._update_current()
        return frame

    def child_state(self, name: str) -> Frame:
        child_vars : dict[str, Any] = {
            "_parent" : self,
        }
        frame = replace(
            self,
            parent = self,
            level = self.level+1,
            vars = child_vars,
            part_path = name,
            _cache = {},
            _full_path = self._full_path + " " + name
        )
        frame._update_current()
        child_vars["_local"] = child_vars
        return frame
    
    def  __getitem__(self, key):
        if key in self._cache:
            return self._cache[key]

        return self.lookup_var(key)
    
    def __iter__(self):
        return self.vars.__iter__()

    def __len__(self):
        return self.vars.__len__()

    def __contains__(self, key: object) -> bool:
        return key in self.vars

    def lookup_var(self, name: str, *, cache_value: bool = False) -> Any:
        """Search this frame, then parent, then parent's parent, ...
        for `name` in `vars`. Caches the result (or MISSING) at every
        frame walked through, so a repeated lookup from the same frame
        is O(1) afterward."""
        frame = self
        chain = []
        while frame is not None:
            if name in frame.vars:
                # Found a value - cache at all levels
                value = frame.vars[name]
                if cache_value:
                    for f in chain[1:]:
                        f._cache[name] = value
                return value
            chain.append(frame)
            frame = frame.parent

        # May want to cache missing at some time, but not use too much memory
#        for f in chain:
#            f._cache[name] = MISSING_VALUE
        return MISSING_VALUE
    
