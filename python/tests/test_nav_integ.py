"""
Navigation-through-compiled-templates demo — valid templates only.

Builds one realistic input document, then for each case compiles a tiny
template ({"result": "$.<path>"}), evaluates it against the document, and
checks the extracted value matches what's actually in the document.

Every path starts with a named key (never a bare array index at the root),
per the constraint given. Covers:
  - named first element (baseline)
  - array elements via index
  - object keys with spaces / apostrophes (bracket notation)
  - deep nesting: array-in-object, object-in-array, array-in-array,
    object-in-object-in-array, etc.

Run with:  python -m unittest test_navigation_integration.py -v
"""
import unittest

from core import Frame, Environment
from engine import JFTLEngine


# ---------------------------------------------------------------------------
# One input document, reused by every test — deliberately deep/varied.
# ---------------------------------------------------------------------------

INPUT_DOCUMENT = {
    "user": {
        "name": "Alice",
        "first name": "Alice",           # key with a space
        "O'brien": "family-name-example", # key with an apostrophe
        "roles": ["admin", "editor", "viewer"],
        "address": {
            "city": "Springfield",
            "zip": "00000",
        },
    },
    "orders": [
        {"item": {"name": "Widget", "price": 9.99}},
        {"item": {"name": "Gadget", "price": 19.99}},
    ],
    "company": {
        "name": "Acme",
        "locations": [
            {"city": "NYC", "tags": ["hq", "east"]},
            {"city": "LA", "tags": ["west"]},
        ],
        "dept codes": {"eng": "E1", "sales": "S1"},
    },
    "matrix": [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    ],
    "grid": {
        "rows": [
            {"cells": [{"v": "a1"}, {"v": "a2"}]},
            {"cells": [{"v": "b1"}, {"v": "b2"}]},
        ]
    },
}


def make_root(current):
    """Root Frame: self-referencing parent, per the locked design."""
    env = Environment(template=None, input=current, to=None, top=None)
    root = Frame(env=env, current=current, parent=None, level=0)
    root.parent = root
    env.top = root
    return root


def extract(path_expr: str):
    """Compile a tiny template wrapping one '$.'-prefixed path, evaluate it
    against INPUT_DOCUMENT, and return the extracted 'result' value."""
    template = {"result": path_expr}
    stmt = JFTLEngine().compile(template)
    frame = make_root(INPUT_DOCUMENT)
    result = stmt.eval(frame)
    return result["result"]


# ---------------------------------------------------------------------------

class TestNamedRootElement(unittest.TestCase):
    """Baseline: every path starts with a named top-level key."""

    def test_named_string_field(self):
        self.assertEqual(extract("$.user.name"), "Alice")

    def test_named_nested_object_field(self):
        self.assertEqual(extract("$.user.address.city"), "Springfield")

    def test_named_scalar_from_second_root_key(self):
        self.assertEqual(extract("$.company.name"), "Acme")


class TestArrayIndices(unittest.TestCase):
    """Sub-elements that are arrays, accessed by index."""

    def test_array_element_by_index(self):
        self.assertEqual(extract("$.user.roles[0]"), "admin")

    def test_array_element_middle_index(self):
        self.assertEqual(extract("$.user.roles[1]"), "editor")

    def test_array_element_negative_index(self):
        self.assertEqual(extract("$.user.roles[-1]"), "viewer")

    def test_array_of_objects_by_index_then_key(self):
        self.assertEqual(extract("$.orders[0].item.name"), "Widget")
        self.assertEqual(extract("$.orders[1].item.price"), 19.99)


class TestObjectKeysWithAndWithoutFunnyCharacters(unittest.TestCase):
    """Plain keys via dot notation vs. keys needing bracket notation."""

    def test_plain_key_dot_notation(self):
        self.assertEqual(extract("$.user.name"), "Alice")

    def test_key_with_space_via_bracket(self):
        self.assertEqual(extract('$.user["first name"]'), "Alice")

    def test_key_with_apostrophe_via_double_quoted_bracket(self):
        self.assertEqual(extract("$.user[\"O'brien\"]"), "family-name-example")

    def test_key_with_space_nested_deeper(self):
        self.assertEqual(extract('$.company["dept codes"].eng'), "E1")

    def test_key_with_space_via_single_quoted_bracket(self):
        self.assertEqual(extract("$.company['dept codes'].sales"), "S1")


class TestDeepNesting(unittest.TestCase):
    """Combinations: array-in-object, object-in-array, array-in-array, etc."""

    def test_array_inside_object_inside_object(self):
        # company (obj) -> locations (array) -> [1] -> city (obj field)
        self.assertEqual(extract("$.company.locations[1].city"), "LA")

    def test_array_inside_object_inside_array_inside_object(self):
        # company -> locations[0] -> tags (array) -> [1]
        self.assertEqual(extract("$.company.locations[0].tags[1]"), "east")

    def test_object_inside_array_inside_object(self):
        # orders (array) -> [1] -> item (object) -> name
        self.assertEqual(extract("$.orders[1].item.name"), "Gadget")

    def test_array_inside_array(self):
        # matrix (array of arrays) -> [1] -> [2]
        self.assertEqual(extract("$.matrix[1][2]"), 6)

    def test_array_inside_array_first_row(self):
        self.assertEqual(extract("$.matrix[0][0]"), 1)

    def test_object_in_array_in_object_in_array_in_object(self):
        # grid -> rows (array) -> [1] -> cells (array) -> [0] -> v (object field)
        self.assertEqual(extract("$.grid.rows[1].cells[0].v"), "b1")

    def test_deepest_combo(self):
        # grid -> rows[0] -> cells[1] -> v
        self.assertEqual(extract("$.grid.rows[0].cells[1].v"), "a2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
