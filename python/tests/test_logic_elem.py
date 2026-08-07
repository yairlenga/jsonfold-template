"""
Tests for LogicStatement.compile() only — no eval() calls.

Uses a FakeCompiler stub instead of a real Compiler, since Compiler.expression()/
condition()/statement() aren't implemented yet. The fake just tags whatever it's
given so we can verify compile() routes each field to the right method with the
right raw value, independent of what real compilation will eventually produce.

Adjust the import below if LogicStatement/Case live in a different module.

Run with:  python -m unittest test_logic_compile.py -v
"""
# pyright: basic

from dataclasses import asdict
from typing import Any, cast
import unittest

from model import JSON_UNSET, DocCompiler, Statement, Transformer
from logic import _CaseEvaluator, _CaseItem, _ForeachPart, LogicCompiler, LogicStatement
from transform import _FlattenningTransformer, _MergeTransformer


class Tagged:
    """Marker wrapper so tests can assert 'this field was compiled as an
    expression/condition/statement from this exact raw value', without
    depending on real Expression/Condition/Statement implementations."""
    def __init__(self, kind: str, raw):
        self.kind = kind
        self.raw = raw

    def __eq__(self, other):
        return isinstance(other, Tagged) and self.kind == other.kind and self.raw == other.raw

    def __repr__(self):
        return f"Tagged({self.kind!r}, {self.raw!r})"


class FakeTransformer(Transformer, Tagged):

    def transform(self):
        pass

class FakeCompiler(DocCompiler):

    def compile_str(self, source: Any, where: str = "", **kwards) -> None:
        return None

    def compile(self, source: Any, where: str = "", **kwards) -> None:
        return None

    def expression(self, source, where):
        return Tagged("expression", source)

    def condition(self, source, where):
        return Tagged("condition", source)

    def statement(self, source, where: str = "") -> Statement | Tagged:
        return Tagged("statement", source)

    def plugin(self, name: str) -> Any:
        return FakeTransformer("plugin", name)


def compile_logic(args: dict) -> LogicStatement:
    return cast(LogicStatement, LogicCompiler(FakeCompiler()).compile(args))


class TestEmptyInput(unittest.TestCase):

    def test_empty_dict_all_fields_none(self):
        stmt = compile_logic({})
        self.assertEqual(stmt._defines or [], [])
        self.assertEqual(stmt._if, True)
        self.assertIs(stmt._set_current, JSON_UNSET)
        self.assertEqual(stmt._set_current, JSON_UNSET)
        self.assertFalse(stmt._foreach)



class TestSet(unittest.TestCase):

    def test_single_set_binding(self):
        stmt = compile_logic({"set": {"total": "$.price"}})

        self.assertEqual(asdict(stmt)["_defines"],
                         [{"name": "total", "expr": Tagged("statement", "$.price")}])

    def test_multiple_set_bindings_preserve_all_keys(self):
        stmt = compile_logic({"set": {"a": "$.x", "b": "$.y", "c": "$.z"}})

        self.assertEqual(asdict(stmt)["_defines"],
            [
                { "name": "a", "expr": Tagged("statement", "$.x")},
                { "name": "b", "expr": Tagged("statement", "$.y")},
                { "name": "c", "expr": Tagged("statement", "$.z")},
            ])

    def test_missing_set_key_is_none(self):
        stmt = compile_logic({"data": "$.x"})
        self.assertIn(stmt._defines, (None, []))

    def test_empty_set_dict_is_still_compiled_as_empty(self):
        # "set": {} is present but has no bindings — distinct from absent "set"
        stmt = compile_logic({"set": {}})
        self.assertIn(stmt._defines, (None, []))


class TestIf(unittest.TestCase):

    def test_if_compiled_as_condition(self):
        stmt = compile_logic({"check": "$.flag"})
        self.assertEqual(stmt._if, Tagged("condition", "$.flag"))

    def test_missing_if_is_none(self):
        stmt = compile_logic({})
        self.assertEqual(stmt._if, True)


class TestData(unittest.TestCase):

    def test_data_compiled_as_expression(self):
        stmt = compile_logic({"out": "$.user.name"})
        self.assertEqual(stmt._out, Tagged("statement", "$.user.name"))

    def test_missing_data_is_none(self):
        stmt = compile_logic({})
        self.assertIs(stmt._set_current, JSON_UNSET )


class TestForeach(unittest.TestCase):

    def test_full_foreach_block(self):
        stmt = compile_logic({
            "foreach": {"key": "idx", "var": "item", "in": "$.items", "if": "$.item.active"}
        })
        assert isinstance(stmt._foreach, _ForeachPart)
        self.assertEqual(stmt._foreach.key_var, "idx")
        self.assertEqual(stmt._foreach.value_var, "item")
        self.assertEqual(stmt._foreach.items, Tagged("statement", "$.items"))
        self.assertEqual(stmt._foreach.cond, Tagged("condition", "$.item.active"))

    def test_full_foreach_block_with_default_key(self):
        stmt = compile_logic({
            "foreach": {"var": "item", "in": "$.items", "if": "$.item.active"}
        })
        assert isinstance(stmt._foreach, _ForeachPart)
        self.assertEqual(stmt._foreach.key_var, "_key")
        self.assertEqual(stmt._foreach.value_var, "item")
        self.assertEqual(stmt._foreach.items, Tagged("statement", "$.items"))
        self.assertEqual(stmt._foreach.cond, Tagged("condition", "$.item.active"))


    def test_foreach_without_optional_if(self):
        stmt = compile_logic({"foreach": {"key": "idx", "var": "item", "in": "$.items"}})
        assert isinstance(stmt._foreach, _ForeachPart)
        self.assertTrue(stmt._foreach.cond)

    def test_foreach_without_key(self):
        stmt = compile_logic({"foreach": {"var": "item", "in": "$.items"}})
        assert isinstance(stmt._foreach, _ForeachPart)
        self.assertEqual(stmt._foreach.key_var, "_key")
        self.assertEqual(stmt._foreach.value_var, "item")

    def test_missing_foreach_is_false_and_all_subfields_none(self):
        stmt = compile_logic({})
        self.assertFalse(stmt._foreach)

    def test_foreach_wrong_type_is_treated_as_absent(self):
        # "foreach" present but not a dict — should not crash, should behave as absent
        stmt = compile_logic({"foreach": "not-a-dict"})
        self.assertFalse(stmt._foreach)


class TestCases(unittest.TestCase):

    def test_single_case(self):
        stmt = compile_logic({"case": [{"when": "$.a", "then": "$.b"}]})
        assert isinstance(stmt, LogicStatement)
        assert isinstance(stmt._out, _CaseEvaluator)
        assert isinstance(stmt._out.cases, list)

        self.assertEqual(len(stmt._out.cases), 1)
        assert isinstance(stmt._out.cases[0], _CaseItem)
        self.assertEqual(stmt._out.cases[0].cond, Tagged("condition", "$.a"))
        self.assertEqual(stmt._out.cases[0].body, Tagged("statement", "$.b"))

    def test_multiple_cases_preserve_order(self):
        stmt = compile_logic({
            "case": [
                {"when": "$.a", "then": "$.x"},
                {"when": "$.b", "then": "$.y"},
                {"when": "$.c", "then": "$.z"},
            ]
        })
        assert isinstance(stmt._out, _CaseEvaluator)
        cases = cast(list[_CaseItem], stmt._out.cases)

        self.assertEqual(len(cases), 3)
        self.assertEqual(cases[0].cond, Tagged("condition", "$.a"))
        self.assertEqual(cases[1].cond, Tagged("condition", "$.b"))
        self.assertEqual(cases[2].cond, Tagged("condition", "$.c"))
        self.assertEqual(cases[2].body, Tagged("statement", "$.z"))

    def test_missing_case_is_none(self):
        stmt = compile_logic({})
        self.assertIs(stmt._set_current, JSON_UNSET)

    def test_empty_case_list_is_empty_not_none(self):
        stmt = compile_logic({"case": []})
        self.assertIs(stmt._set_current, JSON_UNSET)


class TestBodyDefaultError(unittest.TestCase):

    def test_body_compiled_as_statement(self):
        stmt = compile_logic({"data": "$.result"})
        self.assertEqual(stmt._set_current, Tagged("statement", "$.result"))

    def test_default_compiled_as_statement(self):
        stmt = compile_logic({"fallback": "$.fallback"})
        self.assertEqual(stmt._default_val, Tagged("statement", "$.fallback"))

    def test_error_compiled_as_statement(self):
        stmt = compile_logic({"error": "$.errorHandler"})
        self.assertEqual(stmt._error_val, Tagged("statement", "$.errorHandler"))

    def test_body_default_error_independent(self):
        # setting one should not accidentally populate the others
        stmt = compile_logic({"data": "$.b"})
        self.assertEqual(stmt._set_current, Tagged("statement", "$.b"))
        self.assertIs(stmt._default_val, JSON_UNSET)
        self.assertIs(stmt._error_val, JSON_UNSET)


class TestTransform(unittest.TestCase):

    def test_transform_merge(self):
        stmt = compile_logic({"transform": "merge"})
        self.assertEqual(stmt._transformer, Tagged("plugin", "merge"))

    def test_transform_flatten(self):
        stmt = compile_logic({"transform": "flatten"})
        self.assertEqual(stmt._transformer, Tagged("plugin", "flatten"))

    def test_missing_transform_is_none(self):
        stmt = compile_logic({})
        self.assertIsNone(stmt._transformer)


class TestFullRealisticBlock(unittest.TestCase):

    def test_everything_together(self):
        args = {
            "set": {"total": "$.price"},
            "check": "$.enabled",
            "foreach": {"key": "idx", "var": "row", "in": "$.rows"},
            "case": [{"when": "$.a", "then": "$.x"}, { "else": "$.output"}],
            "transform": "merge",
            "error": "$.onError",
        }
        stmt = compile_logic(args)

        self.assertEqual(asdict(stmt)["_defines"],
                         [{"name": "total", "expr": Tagged("statement", "$.price")}])
        self.assertEqual(stmt._if, Tagged("condition", "$.enabled"))
        assert isinstance(stmt._foreach, _ForeachPart)
        self.assertEqual(stmt._foreach.key_var, "idx")
        self.assertEqual(stmt._foreach.value_var, "row")
        self.assertEqual(stmt._foreach.items, Tagged("statement", "$.rows"))
        assert isinstance(stmt._out, _CaseEvaluator)
        assert isinstance(stmt._out.cases, list)
        self.assertEqual(len(stmt._out.cases), 1)
        self.assertEqual(stmt._out.default_case, Tagged("statement", "$.output"))
        self.assertEqual(stmt._transformer, Tagged("plugin", "merge"))
        self.assertEqual(stmt._error_val, Tagged("statement", "$.onError"))
        self.assertIsNotNone(stmt._set_current)
        self.assertIs(stmt._default_val, JSON_UNSET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
