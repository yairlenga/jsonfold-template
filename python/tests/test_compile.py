"""
Tests for JFTLEngine.compile() only — verifying the Statement tree shape.
No eval() calls here; that's a separate concern (step 2: Evaluate).

Run with:  python -m unittest test_compile.py -v
"""
import unittest

from core import CompileError
from runtime import NavigationExprNode
from engine import JFTLEngine, Literal, LiteralStatement, PathStatement, ObjectStatement, ArrayStatement


def compile(source, where: str = ""):
    template = {
        "main": source
    }
    template, errors = JFTLEngine().compile(template, where)
    return template.main


class TestLiterals(unittest.TestCase):

    def test_plain_string_is_literal(self):
        stmt = compile("hello")
        self.assertIsInstance(stmt, LiteralStatement)
        self.assertEqual(stmt.value, "hello")

    def test_int_is_literal(self):
        stmt = compile(42)
        self.assertIsInstance(stmt, LiteralStatement)
        self.assertEqual(stmt.value, 42)

    def test_bool_is_literal(self):
        stmt = compile(True)
        self.assertIsInstance(stmt, LiteralStatement)
        self.assertIs(stmt.value, True)

    def test_none_is_literal(self):
        stmt = compile(None)
        self.assertIsInstance(stmt, LiteralStatement)
        self.assertIsNone(stmt.value)

    def test_string_not_starting_with_prefix_is_literal(self):
        # starts with '$' but not '$.' — should NOT be treated as a path
        stmt = compile("$5.00")
        self.assertIsInstance(stmt, LiteralStatement)
        self.assertEqual(stmt.value, "$5.00")


class TestPathStatements(unittest.TestCase):

    def test_dollar_dot_string_becomes_path_statement(self):
        stmt = compile("$.user.name")
        self.assertIsInstance(stmt, PathStatement)
        self.assertIsInstance(stmt.engine, NavigationExprNode)

    def test_stripped_prefix_keeps_leading_dot(self):
        stmt = compile("$.user.name")
        self.assertEqual(stmt.engine._path, ".user.name")

    def test_bare_dollar_dot_is_malformed(self):
        # "$." alone — a dot with nothing after it is not a valid path segment
        with self.assertRaises(CompileError):
            compile("$.")

    def test_malformed_path_raises_compile_error(self):
        with self.assertRaises(CompileError):
            compile("$.foo!bar")

    def test_where_is_threaded_through_for_diagnostics(self):
        stmt = compile("$.name", where="macros.personCard")
        self.assertEqual(stmt.engine._where, "macros.personCard")


class TestObjectStatements(unittest.TestCase):

    def test_empty_dict(self):
        stmt = compile({})
        self.assertIsInstance(stmt, ObjectStatement)
        self.assertEqual(stmt.entries, {})

    def test_flat_dict_keys_compiled(self):
        stmt = compile({"a": "x", "b": 1})
        self.assertIsInstance(stmt, ObjectStatement)
        self.assertEqual(set(stmt.entries.keys()), {"a", "b"})
        self.assertIsInstance(stmt.entries["a"], LiteralStatement)
        self.assertIsInstance(stmt.entries["b"], LiteralStatement)

    def test_dict_value_with_path_expression(self):
        stmt = compile({"name": "$.user.name"})
        self.assertIsInstance(stmt.entries["name"], PathStatement)

    def test_nested_dict(self):
        stmt = compile({"outer": {"inner": "$.x"}})
        self.assertIsInstance(stmt, ObjectStatement)
        inner_stmt = stmt.entries["outer"]
        self.assertIsInstance(inner_stmt, ObjectStatement)
        self.assertIsInstance(inner_stmt.entries["inner"], PathStatement)

    def test_malformed_path_inside_nested_dict_raises(self):
        with self.assertRaises(CompileError):
            compile({"a": {"b": "$.foo!bar"}})

    def test_where_includes_key_path(self):
        stmt = compile({"a": {"b": "$.x"}}, where="root")
        inner = stmt.entries["a"].entries["b"]
        self.assertEqual(inner.engine._where, "root.a.b")


class TestArrayStatements(unittest.TestCase):

    def test_empty_list(self):
        stmt = compile([])
        self.assertIsInstance(stmt, ArrayStatement)
        self.assertEqual(stmt.items, [])

    def test_flat_list(self):
        stmt = compile([1, "x", "$.y"])
        self.assertIsInstance(stmt, ArrayStatement)
        self.assertIsInstance(stmt.items[0], LiteralStatement)
        self.assertIsInstance(stmt.items[1], LiteralStatement)
        self.assertIsInstance(stmt.items[2], PathStatement)

    def test_list_of_dicts(self):
        stmt = compile([{"a": "$.x"}, {"b": "$.y"}])
        self.assertIsInstance(stmt, ArrayStatement)
        self.assertEqual(len(stmt.items), 2)
        self.assertIsInstance(stmt.items[0], ObjectStatement)
        self.assertIsInstance(stmt.items[1], ObjectStatement)

    def test_malformed_path_inside_list_raises(self):
        with self.assertRaises(CompileError):
            compile(["ok", "$.foo!bar"])

    def test_where_includes_index(self):
        stmt = compile(["a", "$.x"], where="root")
        self.assertEqual(stmt.items[1].engine._where, "root[1]")


class TestMixedNesting(unittest.TestCase):

    def test_realistic_template_shape(self):
        source = {
            "name": "$.user.name",
            "tags": ["static", "$.user.role"],
            "address": {
                "city": "$.user.address.city",
                "zip": "00000",
            },
        }
        stmt = compile(source)
        self.assertIsInstance(stmt, ObjectStatement)
        self.assertIsInstance(stmt.entries["name"], PathStatement)
        self.assertIsInstance(stmt.entries["tags"], ArrayStatement)
        self.assertIsInstance(stmt.entries["tags"].items[0], LiteralStatement)
        self.assertIsInstance(stmt.entries["tags"].items[1], PathStatement)
        self.assertIsInstance(stmt.entries["address"], ObjectStatement)
        self.assertIsInstance(stmt.entries["address"].entries["city"], PathStatement)
        self.assertIsInstance(stmt.entries["address"].entries["zip"], LiteralStatement)


if __name__ == "__main__":
    unittest.main(verbosity=2)