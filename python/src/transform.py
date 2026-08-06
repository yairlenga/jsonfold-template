
from types import NoneType
from typing import Any, Callable, cast

from model import RUNTIME_DOC, RUNTIME_LIST_LIKE, RUNTIME_NULL_LIKE, Transformer
from template import JFTLNotice, Missing

if callable( _ := globals().get("profile")):
    _profile = cast(Callable, _)
else:
    def _profile(func): return func


    # List[list] -> List
class _FlattenningTransformer(Transformer):
    def transform(self, input: RUNTIME_DOC ) -> list[RUNTIME_DOC] | JFTLNotice:
        if not isinstance(input, RUNTIME_LIST_LIKE):
            return JFTLNotice(
                    code="FLATTEN_INPUT",
                    message=f"The 'flatten' transform input is array of array, got non-list",
                )

        for pos, item in enumerate(input):
            if item is None:
                continue
            if not isinstance(item, RUNTIME_LIST_LIKE):
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
        if not isinstance(input, RUNTIME_LIST_LIKE):
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
        elif isinstance(input, RUNTIME_LIST_LIKE):
            return [x for x in input if not isinstance(x, Missing)]

        return JFTLNotice(
                code="DROP_MISSING_INPUT",
                message=f"The 'drop_missing' transformation input ",
            )
   
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
                return JFTLNotice(code="JOIN-STR-TYPE", message=f"Result contained unknown type {type(item)}")

            result.append(item_str)
        return "".join(result)

    def transform(self, input: RUNTIME_DOC) -> RUNTIME_DOC:
        return self._transform(cast(list[str | None | Missing], input))
    
# List[Pairs] | List[{key,value}] | Dict[Any, Pairs|{key,value}] -> Dict
class _ToObjectTransformer(Transformer):
    def _extract(self, entry: RUNTIME_DOC) -> tuple[Any, RUNTIME_DOC] | JFTLNotice:
        if isinstance(entry, list):
            if len(entry) != 2:
                return JFTLNotice(
                    code="TO_OBJECT_ITEM",
                    message=f"The 'to_object' transformation expects a [key, value] pair, got list of length {len(entry)}",
                )
            return entry[0], entry[1]

        if isinstance(entry, dict):
            if len(entry) != 2 or "key" not in entry or "value" not in entry:
                return JFTLNotice(
                    code="TO_OBJECT_ITEM",
                    message=f"The 'to_object' transformation expects an object with exactly 'key' and 'value', got {entry!r}",
                )
            return entry["key"], entry["value"]

        return JFTLNotice(
            code="TO_OBJECT_ITEM",
            message=f"The 'to_object' transformation expects a [key, value] pair or {{key, value}} object, got {type(entry)}",
        )

    def transform(self, input: RUNTIME_DOC) -> dict[str, RUNTIME_DOC] | JFTLNotice:
        if isinstance(input, dict):
            entries = input.values()
        elif isinstance(input, list):
            entries = input
        else:
            return JFTLNotice(
                code="TO_OBJECT_INPUT",
                message=f"The 'to_object' transformation expects an array or object of entries, got {type(input)}",
            )

        result: dict[str, RUNTIME_DOC] = {}
        for entry in entries:
            if isinstance(entry, RUNTIME_NULL_LIKE):
                continue

            pair = self._extract(entry)
            if isinstance(pair, JFTLNotice):
                return pair

            # Ignore missing/None Entries
            if isinstance(pair, RUNTIME_NULL_LIKE):
                continue

            key, value = pair
            # Silently ignore None/Missing entries
            if isinstance(key, RUNTIME_NULL_LIKE) and isinstance(value, RUNTIME_NULL_LIKE):
                continue

            if not isinstance(key, str):
                # Siltently ignore setting invalid keys to None/Missing
                if isinstance(value, RUNTIME_NULL_LIKE):
                    continue
                return JFTLNotice(
                    code="TO_MAP_BAD_KEY",
                    message=f"Invalid key type {type(key)} in 'to_object' entry {entry!r}",
                )

            result[key] = value  # later entries win on collision, matching 'merge'

        return result

default_plugins : dict[str, type[Transformer]] = {
    "flatten": _FlattenningTransformer,
    "merge": _MergeTransformer,
    "to_pairs": _ToPairsTransformer,

    "drop_missing": _DropMissingTransformer,
    "concat": _JoinStrTransformer,
    "to_object": _ToObjectTransformer,
}
