"""
Tests for LogicStatement.compile() only — no eval() calls.

Uses a FakeCompiler stub instead of a real Compiler, since Compiler.expression()/
condition()/statement() aren't implemented yet. The fake just tags whatever it's
given so we can verify compile() routes each field to the right method with the
right raw value, independent of what real compilation will eventually produce.

Adjust the import below if LogicStatement/Case live in a different module.

Run with:  python -m unittest test_logic_compile.py -v
"""
from dataclasses import asdict
import unittest

from logic import LogicStatement, Case


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


class FakeCompiler:
    def expression(self, raw, source):
        return Tagged("expression", raw), None

    def condition(self, raw, source):
        return Tagged("condition", raw), None

    def statement(self, raw, source):
        return Tagged("statement", raw), None


def compile_logic(args: dict) -> LogicStatement:
    return LogicStatement.compile(FakeCompiler(), args)


class TestEmptyInput(unittest.TestCase):

    def test_empty_dict_all_fields_none(self):
        stmt = compile_logic({})
        self.assertIsNone(stmt._defines)
        self.assertIsNone(stmt._if)
        self.assertIsNone(stmt._set_current)
        self.assertIsNone(stmt._cases)
        self.assertFalse(stmt._foreach)
        self.assertIsNone(stmt._foreach_key)
        self.assertIsNone(stmt._foreach_var)
        self.assertIsNone(stmt._foreach_in)
        self.assertIsNone(stmt._foreach_cond)
        self.assertIsNone(stmt._body)
        self.assertIsNone(stmt._default_val)
        self.assertIsNone(stmt._error_val)
        self.assertIsNone(stmt._transform)


class TestSet(unittest.TestCase):

    def test_single_set_binding(self):
        stmt = compile_logic({"set": {"total": "$.price"}})

        self.assertEqual(asdict(stmt)["_defines"],
                         [{"_name": "total", "_expr": Tagged("expression", "$.price")}])

    def test_multiple_set_bindings_preserve_all_keys(self):
        stmt = compile_logic({"set": {"a": "$.x", "b": "$.y", "c": "$.z"}})

        self.assertEqual(asdict(stmt)["_defines"],
            [
                { "_name": "a", "_expr": Tagged("expression", "$.x")},
                { "_name": "b", "_expr": Tagged("expression", "$.y")},
                { "_name": "c", "_expr": Tagged("expression", "$.z")},
            ])

    def test_missing_set_key_is_none(self):
        stmt = compile_logic({"data": "$.x"})
        self.assertIsNone(stmt._defines)

    def test_empty_set_dict_is_still_compiled_as_empty(self):
        # "set": {} is present but has no bindings — distinct from absent "set"
        stmt = compile_logic({"set": {}})
        self.assertEqual(stmt._defines, None)


class TestIf(unittest.TestCase):

    def test_if_compiled_as_condition(self):
        stmt = compile_logic({"if": "$.flag"})
        self.assertEqual(stmt._if, Tagged("condition", "$.flag"))

    def test_missing_if_is_none(self):
        stmt = compile_logic({})
        self.assertIsNone(stmt._if)


class TestData(unittest.TestCase):

    def test_data_compiled_as_expression(self):
        stmt = compile_logic({"data": "$.user.name"})
        self.assertEqual(stmt._set_current, Tagged("expression", "$.user.name"))

    def test_missing_data_is_none(self):
        stmt = compile_logic({})
        self.assertIsNone(stmt._set_current)


class TestForeach(unittest.TestCase):

    def test_full_foreach_block(self):
        stmt = compile_logic({
            "foreach": {"key": "idx", "var": "item", "in": "$.items", "if": "$.item.active"}
        })
        self.assertTrue(stmt._foreach)
        self.assertEqual(stmt._foreach_key, "idx")
        self.assertEqual(stmt._foreach_var, "item")
        self.assertEqual(stmt._foreach_in, Tagged("expression", "$.items"))
        self.assertEqual(stmt._foreach_cond, Tagged("condition", "$.item.active"))

    def test_foreach_without_optional_if(self):
        stmt = compile_logic({"foreach": {"key": "idx", "var": "item", "in": "$.items"}})
        self.assertTrue(stmt._foreach)
        self.assertIsNone(stmt._foreach_cond)

    def test_foreach_without_key(self):
        stmt = compile_logic({"foreach": {"var": "item", "in": "$.items"}})
        self.assertTrue(stmt._foreach)
        self.assertIsNone(stmt._foreach_key)
        self.assertEqual(stmt._foreach_var, "item")

    def test_missing_foreach_is_false_and_all_subfields_none(self):
        stmt = compile_logic({})
        self.assertFalse(stmt._foreach)
        self.assertIsNone(stmt._foreach_key)
        self.assertIsNone(stmt._foreach_var)
        self.assertIsNone(stmt._foreach_in)
        self.assertIsNone(stmt._foreach_cond)

    def test_foreach_wrong_type_is_treated_as_absent(self):
        # "foreach" present but not a dict — should not crash, should behave as absent
        stmt = compile_logic({"foreach": "not-a-dict"})
        self.assertFalse(stmt._foreach)
        self.assertIsNone(stmt._foreach_in)


class TestCases(unittest.TestCase):

    def test_single_case(self):
        stmt = compile_logic({"case": [{"when": "$.a", "then": "$.b"}]})
        self.assertEqual(len(stmt._cases), 1)
        self.assertEqual(stmt._cases[0]._cond, Tagged("condition", "$.a"))
        self.assertEqual(stmt._cases[0]._body, Tagged("statement", "$.b"))

    def test_multiple_cases_preserve_order(self):
        stmt = compile_logic({
            "case": [
                {"when": "$.a", "then": "$.x"},
                {"when": "$.b", "then": "$.y"},
                {"when": "$.c", "then": "$.z"},
            ]
        })
        self.assertEqual(len(stmt._cases), 3)
        self.assertEqual(stmt._cases[0]._cond, Tagged("condition", "$.a"))
        self.assertEqual(stmt._cases[1]._cond, Tagged("condition", "$.b"))
        self.assertEqual(stmt._cases[2]._cond, Tagged("condition", "$.c"))
        self.assertEqual(stmt._cases[2]._body, Tagged("statement", "$.z"))

    def test_missing_case_is_none(self):
        stmt = compile_logic({})
        self.assertIsNone(stmt._cases)

    def test_empty_case_list_is_empty_not_none(self):
        stmt = compile_logic({"case": []})
        self.assertEqual(stmt._cases, None)


class TestBodyDefaultError(unittest.TestCase):

    def test_body_compiled_as_statement(self):
        stmt = compile_logic({"body": "$.result"})
        self.assertEqual(stmt._body, Tagged("statement", "$.result"))

    def test_default_compiled_as_statement(self):
        stmt = compile_logic({"default": "$.fallback"})
        self.assertEqual(stmt._default_val, Tagged("statement", "$.fallback"))

    def test_error_compiled_as_statement(self):
        stmt = compile_logic({"error": "$.errorHandler"})
        self.assertEqual(stmt._error_val, Tagged("statement", "$.errorHandler"))

    def test_body_default_error_independent(self):
        # setting one should not accidentally populate the others
        stmt = compile_logic({"body": "$.b"})
        self.assertEqual(stmt._body, Tagged("statement", "$.b"))
        self.assertIsNone(stmt._default_val)
        self.assertIsNone(stmt._error_val)


class TestTransform(unittest.TestCase):

    def test_transform_merge(self):
        stmt = compile_logic({"transform": "MERGE"})
        self.assertEqual(stmt._transform, "MERGE")

    def test_transform_flatten(self):
        stmt = compile_logic({"transform": "FLATTEN"})
        self.assertEqual(stmt._transform, "FLATTEN")

    def test_missing_transform_is_none(self):
        stmt = compile_logic({})
        self.assertIsNone(stmt._transform)


class TestFullRealisticBlock(unittest.TestCase):

    def test_everything_together(self):
        args = {
            "set": {"total": "$.price"},
            "if": "$.enabled",
            "foreach": {"key": "idx", "var": "row", "in": "$.rows"},
            "case": [{"when": "$.a", "then": "$.x"}],
            "body": "$.output",
            "transform": "MERGE",
            "error": "$.onError",
        }
        stmt = compile_logic(args)

        self.assertEqual(asdict(stmt)["_defines"],
                         [{"_name": "total", "_expr": Tagged("expression", "$.price")}])
        self.assertEqual(stmt._if, Tagged("condition", "$.enabled"))
        self.assertTrue(stmt._foreach)
        self.assertEqual(stmt._foreach_key, "idx")
        self.assertEqual(stmt._foreach_var, "row")
        self.assertEqual(stmt._foreach_in, Tagged("expression", "$.rows"))
        self.assertEqual(len(stmt._cases), 1)
        self.assertEqual(stmt._body, Tagged("statement", "$.output"))
        self.assertEqual(stmt._transform, "MERGE")
        self.assertEqual(stmt._error_val, Tagged("statement", "$.onError"))
        self.assertIsNone(stmt._set_current)
        self.assertIsNone(stmt._default_val)


if __name__ == "__main__":
    unittest.main(verbosity=2)
