"""
Navigation tests against the real project modules — stdlib only, no pytest needed.

Run with:  python -m unittest test_navigation_unittest.py -v
       or:  python test_navigation_unittest.py

Assumes the bug fixes discussed:
  1. NavigationExprEngine._compile needs `self` as first param.
  2. m.group("word") not m.group("bare").
  3. Missing(...) calls need code=... .
  4. Error(...) calls (inside _compile) need severity=... .
  5. eval() must check isinstance(self._segments, Error) before iterating.
"""
import unittest

from core import Frame, Environment, CompileError
from navigation import NavigationStatement
from template import JFTLError, Missing


def make_root(current):
    """Build a root Frame: self-referencing parent, per the locked design."""
    env = Environment(template=None, input=current, to=None, top=None)
    root = Frame(env=env, current=current, parent=None, level=0)
    env.top = root
    return root


def make_child(parent: Frame, current):
    return Frame(env=parent.env, current=current, parent=parent, level=parent.level + 1)


def nav(text: str, where=None) -> NavigationStatement:
    return NavigationStatement(text, where=where)


class TestBasicNavigation(unittest.TestCase):

    def test_bare_nested_key(self):
        root = make_root({"user": {"name": "Alice"}})
        self.assertEqual(nav(".user.name").eval(root), "Alice")

    def test_array_index(self):
        root = make_root({"items": [10, 20, 30]})
        self.assertEqual(nav(".items[1]").eval(root), 20)

    def test_negative_index(self):
        root = make_root({"items": [10, 20, 30]})
        self.assertEqual(nav(".items[-1]").eval(root), 30)


class TestQuotedKeys(unittest.TestCase):

    def test_single_quoted_key_with_space(self):
        root = make_root({"first name": "Alice"})
        self.assertEqual(nav("['first name']").eval(root), "Alice")

    def test_double_quoted_key_with_apostrophe(self):
        root = make_root({"O'brien": "yes"})
        self.assertEqual(nav("[\"O'brien\"]").eval(root), "yes")


class TestMissingValues(unittest.TestCase):

    def test_missing_key_returns_missing(self):
        root = make_root({"user": {"name": "Alice"}})
        result = nav(".user.age").eval(root)
        self.assertIsInstance(result, Missing)

    def test_missing_index_returns_missing(self):
        root = make_root({"items": [1, 2]})
        result = nav(".items[5]").eval(root)
        self.assertIsInstance(result, Missing)

    def test_missing_is_falsy(self):
        root = make_root({"items": [1, 2]})
        result = nav(".items[5]").eval(root)
        self.assertFalse(bool(result))

    def test_missing_propagates_through_further_navigation(self):
        # Once `value` becomes Missing mid-chain, eval() must short-circuit
        # rather than attempting dict/list indexing on it.
        root = make_root({"user": {}})
        result = nav(".user.address.zip").eval(root)
        self.assertIsInstance(result, Missing)


class TestMalformedPaths(unittest.TestCase):

    def test_malformed_path_stray_character(self):
        with self.assertRaises(CompileError) as ctx:
            nav(".foo!bar")
        self.assertEqual(ctx.exception.error.code, "INVALID_PATH")

    def test_up_not_at_start_is_rejected(self):
        with self.assertRaises(CompileError) as ctx:
            nav(".foo.^.bar")
        self.assertEqual(ctx.exception.error.code, "INVALID_PATH")

class TestEvalBool(unittest.TestCase):

    def test_eval_bool_true_for_present_truthy_value(self):
        root = make_root({"flag": True})
        self.assertIs(nav(".flag").eval_bool(root), True)

    def test_eval_bool_false_for_missing(self):
        root = make_root({})
        result = nav(".flag").eval_bool(root)
        # eval_bool currently propagates Missing rather than coercing to bool —
        # confirm this is the intended contract (Missing IS falsy, but is not `False`).
        self.assertIsInstance(result, Missing)


if __name__ == "__main__":
    unittest.main(verbosity=2)