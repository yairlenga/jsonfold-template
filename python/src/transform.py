
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
class _PairsToObject(Transformer):
    def transform(self, input: RUNTIME_DOC) -> dict[str, RUNTIME_DOC] | JFTLNotice:
        if not isinstance(input, list):
            return JFTLNotice(
                code="TO_OBJECT_INPUT",
                message=f"The 'to_object' transformation expects an array or object of entries, got {type(input)}",
            )

        pairs = [
            [pair[0], pair[1] ]
            for pair in input
            if isinstance(pair, list)
            and len(pair) == 2
            and (isinstance(pair[0], str) or isinstance(pair[0], RUNTIME_NULL_LIKE) and isinstance(pair[1], RUNTIME_NULL_LIKE))
        ]

        if len(pairs) != len(input):
            return JFTLNotice(
                code="FROM-PAIRS-ITEM", message=f"from_pairs expect all items to be 2 element array of [ key, value ]"
            )
        
        result = { k:v for k, v in pairs if isinstance(k, str) }
        return result

class _KVToObject(Transformer):

    def transform(self, input: RUNTIME_DOC) -> dict[str, RUNTIME_DOC] | JFTLNotice:
        if not isinstance(input, list):
            return JFTLNotice(
                code="FROM_KV_INPUT",
                message=f"The 'from_kv' transformation expects an array or object of entries, got {type(input)}",
            )

        if any(not isinstance(pair, dict) or len(pair) != 2 or not isinstance(pair.get("key"), str) for pair in input):
            return JFTLNotice(
                code="FROM_KV-ITEM", message=f"from_pairs expect all items to be 2 element array of [ key, value ]"
            )

        pairs = cast(list[dict], input)
        result = { pair.get("key"):pair.get("value") for pair in pairs }

        return result



default_plugins : dict[str, type[Transformer]] = {
    "flatten": _FlattenningTransformer,
    "merge": _MergeTransformer,
    "to_pairs": _ToPairsTransformer,

    "drop_missing": _DropMissingTransformer,
    "concat": _JoinStrTransformer,
    "from_pairs": _PairsToObject,
    "from_kv": _KVToObject,
}
