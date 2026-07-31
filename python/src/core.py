from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Any

from model import JFTL_NOTICE, JFTL_RAISE, Environment, RuntimeContext
from template import SKIP_VALUE, ERROR_VALUE, MISSING_VALUE, JFTLException, JFTLNotice

# Template Class - represent compiled templates

# Runtime Objects

@dataclass
class Frame (RuntimeContext):

    # Cached value, including inherited, calculated, ...
    _cache:  dict[str, Any] = field(default_factory=dict)
    _full_path: str = ""
    _initial_current: str = ""

    def _resolve(self, error: JFTLNotice, on: Any) -> Any:
        if on is JFTL_RAISE:
            raise JFTLException(error)
        if on is JFTL_NOTICE:
            return error
        return on

    def _update_current(self):
        self.vars["_"] = self.current

    def set_current(self, current: Any):
        super().set_current(current)
        self._update_current()

    def set_state_data(self, current: Any):
        self.vars["_data"] = current

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
    
