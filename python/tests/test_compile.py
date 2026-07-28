"""
Tests for JFTLEngine.compile() only — verifying the Statement tree shape.
No eval() calls here; that's a separate concern (step 2: Evaluate).

Run with:  python -m unittest test_compile.py -v
"""
import unittest

from navigation import NavigationStatement
from engine import JFTLEngine, LiteralStatement, ObjectStatement, ArrayStatement


def template_of(source, where = ""):
    template, _ = JFTLEngine().compile(source, where=where, main_only=True)
    return template

def compile(source, where: str = ""):
    template = template_of(source, where)
    assert(template.valid)
    return template.main_entry

class TestLiterals(unittest.TestCase):

    def test_plain_string_is_literal(self):
        stmt = compile("hello")
        self.assertEqual(stmt, "hello")

    def test_int_is_literal(self):
        stmt = compile(42)
        self.assertEqual(stmt, 42)

    def test_bool_is_literal(self):
        stmt = compile(True)
        self.assertEqual(stmt, True)

    def test_none_is_literal(self):
        stmt = compile(None)
        self.assertTrue(stmt, bool(stmt))
        self.assertIsInstance(stmt, LiteralStatement)
        assert isinstance(stmt, LiteralStatement)
        self.assertIs(stmt.value, None)

    def test_string_not_starting_with_prefix_is_literal(self):
        # starts with '$' but not '$.' — should NOT be treated as a path
        stmt = compile("$$5.00")
        self.assertEqual(stmt, "$5.00")


class TestPathStatements(unittest.TestCase):

    def test_dollar_dot_string_becomes_path_statement(self):
        stmt = compile("$.user.name")
        self.assertIsInstance(stmt, NavigationStatement)

    def test_stripped_prefix_keeps_leading_dot(self):
        stmt = compile("$.user.name")
        assert(isinstance(stmt, NavigationStatement))
        self.assertIsInstance(stmt, NavigationStatement)
        self.assertEqual(stmt._path, ".user.name")

    def test_bare_dollar_dot_is_ok(self):
        # "$." alone — a dot with nothing after it is not a valid path segment
        stmt = compile("$")
        self.assertIsInstance(stmt, NavigationStatement)

    def test_malformed_path_compile_error(self):
        template = template_of("$.foo!bar")
        self.assertFalse(template.valid)

    def test_where_is_threaded_through_for_diagnostics(self):
        stmt = compile("$.name", where="macros.personCard")
        assert(isinstance(stmt, NavigationStatement))
        self.assertEqual(stmt.where, "macros.personCard")


class TestObjectStatements(unittest.TestCase):

    def test_empty_dict(self):
        stmt = compile({})
        assert isinstance(stmt, LiteralStatement)
        self.assertEqual(stmt.value, {})

    def test_flat_dict_keys_compiled(self):
        stmt = compile({"a": "x", "b": 1})
        assert isinstance(stmt, LiteralStatement)
        self.assertEqual(set(stmt.value.keys()), {"a", "b"})
        self.assertIsInstance(stmt.value["a"], str)
        self.assertIsInstance(stmt.value["b"], int)

    def test_dict_value_with_path_expression(self):
        stmt = compile({"name": "$.user.name"})
        assert isinstance(stmt, ObjectStatement)

    def test_nested_dict(self):
        stmt = compile({"outer": {"inner": "$.x"}})
        assert isinstance(stmt, ObjectStatement)
        inner_stmt = stmt.entries["outer"]
        assert isinstance(inner_stmt, ObjectStatement)
        self.assertIsInstance(inner_stmt.entries["inner"], NavigationStatement)

    def test_malformed_path_inside_nested_dict_raises(self):
        template = template_of({"a": {"b": "$.foo!bar"}})
        self.assertFalse(template.valid)

    def test_where_includes_key_path(self):
        stmt = compile({"a": {"b": "$.x"}}, where="root")
        assert isinstance(stmt, ObjectStatement)
        assert isinstance(stmt.entries["a"], ObjectStatement)
        assert isinstance(stmt.entries["a"].entries["b"], NavigationStatement)
        inner = stmt.entries["a"].entries["b"]
        self.assertEqual(inner.where, "root.a.b")


class TestArrayStatements(unittest.TestCase):

    def test_empty_list(self):
        stmt = compile([])
        assert isinstance(stmt, LiteralStatement)
        self.assertEqual(stmt.value, [])

    def test_flat_list(self):
        stmt = compile([1, "x", "$.y"])
        assert isinstance(stmt, ArrayStatement)
        self.assertIsInstance(stmt.items[0], int)
        self.assertIsInstance(stmt.items[1], str)
        self.assertIsInstance(stmt.items[2], NavigationStatement)

    def test_list_of_dicts(self):
        stmt = compile([{"a": "$.x"}, {"b": "$.y"}])
        assert isinstance(stmt, ArrayStatement)
        self.assertEqual(len(stmt.items), 2)
        self.assertIsInstance(stmt.items[0], ObjectStatement)
        self.assertIsInstance(stmt.items[1], ObjectStatement)

    def test_malformed_path_inside_list_raises(self):
        template = template_of(["ok", "$.foo!bar"])
        self.assertFalse(template.valid)

    def test_where_includes_index(self):
        stmt = compile(["a", "$.x"], where="root")
        assert isinstance(stmt, ArrayStatement)
        assert isinstance(stmt.items[1], NavigationStatement)
        self.assertEqual(stmt.items[1].where, "root[1]")


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
        assert isinstance(stmt, ObjectStatement)
        self.assertIsInstance(stmt.entries["name"], NavigationStatement)
        assert isinstance(stmt.entries["tags"], ArrayStatement)
        self.assertIsInstance(stmt.entries["tags"].items[0], str)
        self.assertIsInstance(stmt.entries["tags"].items[1], NavigationStatement)
        assert isinstance(stmt.entries["address"], ObjectStatement)
        self.assertIsInstance(stmt.entries["address"].entries["city"], NavigationStatement)
        self.assertIsInstance(stmt.entries["address"].entries["zip"], str)


if __name__ == "__main__":
    unittest.main(verbosity=2)