from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

from model import JFTL_BREAK, JFTL_NOTICE, JFTL_RAISE, JFTL_SKIP, Environment, RuntimeContext
from template import ERROR_VALUE, MISSING_VALUE, JFTLException, JFTLNotice


try:
    _profile = profile
except NameError:
    def _profile(func):
        return func

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

    @_profile
    def _update_current(self):
        pass
        self.vars["_"] = self.current
        return

    @_profile
    def set_current(self, current: Any):
        pass
        super().set_current(current)
        self._update_current()
        return

    def set_state_data(self, current: Any):
        self.vars["_data"] = current

    def _set_frame_vars(self):
        self.vars["_level"] = self.level
        self._cache["_local"] = self.vars

    @classmethod
    def root_context(cls, env: Environment) -> Frame:
        top_vars = {
            "_missing": MISSING_VALUE,
            "_error": ERROR_VALUE,
            "_skip" : JFTL_SKIP,
            "_break": JFTL_BREAK,
            "_input" : env.input,
            "_datasets": env.datasets,
            "_": env.input,
        }
        frame = cls(env=env, current=env.input, level=0, parent=None, vars=top_vars, part_path="")
        # Must "Patch" the environment to point back to the root frame.
        # May want one day to point each frame direct to the top, to avoid circular
        env.top = frame
        top_vars["_top"] = frame
        top_vars["_external"] = top_vars
        # The _local and _parent variable are not regular variables - they are "namespaces" resolving
        # variable names from the local variables, injected variables, and parent chain. There are
        # NOT stored in the 'var' space to avoid cycles, and will resolve to null at materialization
        # time, if they somehow become part of the result.
        frame._set_frame_vars()
        frame._update_current()
        return frame

    def child_state(self, name: str) -> Frame:
        # The _local and _parent variables are "namespaces", and are injected directly into the
        # cache, no stored in the regular "vars" space to avoid cycles.
        frame = (type(self))(
            parent=self,
            env=self.env,
            current=self.current,
            level = self.level+1,
            part_path = name,
            _full_path = self._full_path + " " + name,
            global_ctx = self.global_ctx
        )
        frame._cache["_parent"] = frame.parent
        frame._set_frame_vars()
        frame._update_current()
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

    @_profile
    def lookup_var(self, name: str, *, cache_mode: Optional[bool] = None) -> Any:
        """Search this frame, then parent, then parent's parent, ...
        for `name` in `vars`. Caches the result (or MISSING) at every
        frame walked through, so a repeated lookup from the same frame
        is O(1) afterward."""
        frame = self
        chain = []
        while frame is not None:
# TODO: Check if dict.get outperform in/getitem            
#   if (v := frame._cache.get(name, JFTL_NONE) is not JFTL_NONE or (v := frame.vars.get(name, JFTL_NONE)) is not JFTL_NONE:
#   return v
            if name in frame._cache:
                return frame._cache[name]
            if name in frame.vars:
                # Found a value - cache at all levels
                value = frame.vars[name]
                # TODO: cache by default ?
                if cache_mode:
                    for f in chain[1:]:
                        f._cache[name] = value
                return value
            chain.append(frame)
            frame = frame.parent

        # May want to cache missing at some time, but not use too much memory
#        for f in chain:
#            f._cache[name] = MISSING_VALUE
        return MISSING_VALUE
    
