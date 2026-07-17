"""
Reshape test — mixing input-derived values with template-inline constants.

Naming convention (so provenance is visible at a glance in the output):
  - INPUT document strings all start with '@', numbers are all positive.
  - TEMPLATE literal (inline) strings all start with '_', numbers are all negative.

Input document deliberately covers several shapes:
  - array of primitives            -> tags
  - object of primitives           -> counts
  - array of objects               -> items
  - object of arrays               -> groups
  - array of arrays (matrix)       -> nested.matrix
  - object of objects              -> nested.meta

The template reshapes all of this into a new structure that does NOT mirror
the input's shape, pulling values via '$.' navigation and mixing in literal
constants at every level.

Run with:  python -m unittest test_reshape.py -v
"""
import json
from typing import cast
import unittest

from core import Frame, Environment, JFTLTemplate
from engine import JFTLEngine


# ---------------------------------------------------------------------------
# Input document — every string starts with '@', every number is positive.
# ---------------------------------------------------------------------------

INPUT_DOCUMENT = {
    "tags": ["@tag1", "@tag2", "@tag3"],                    # array of primitives

    "counts": {"apples": 3, "oranges": 5},                  # object of primitives

    "items": [                                              # array of objects
        {"name": "@itemA", "qty": 2},
        {"name": "@itemB", "qty": 4},
    ],

    "groups": {                                             # object of arrays
        "fruits": ["@apple", "@banana"],
        "veggies": ["@carrot"],
    },

    "nested": {
        "matrix": [[1, 2], [3, 4]],                         # array of arrays
        "meta": {"owner": "@ownerName", "id": 42},          # object of objects (one level)
    },
}


# ---------------------------------------------------------------------------
# Template — every literal string starts with '_', every literal number is
# negative. Navigation expressions ('$.'-prefixed) pull from INPUT_DOCUMENT.
# The output shape is deliberately different from the input's shape.
# ---------------------------------------------------------------------------

TEMPLATE = {
    "summary": {
        "label": "_summary_label",
        "firstTag": "$.tags[0]",
        "secondTag": "$.tags[1]",
        "appleCount": "$.counts.apples",
        "bonus": -10,
    },

    "itemsReshaped": [
        {
            "itemName": "$.items[0].name",
            "itemQty": "$.items[0].qty",
            "note": "_note_static_a",
            "adjustment": -1,
        },
        {
            "itemName": "$.items[1].name",
            "itemQty": "$.items[1].qty",
            "note": "_note_static_b",
            "adjustment": -2,
        },
    ],

    "groupsReshaped": {
        "fruitList": ["$.groups.fruits[0]", "$.groups.fruits[1]", "_extra_fruit"],
        "vegList": ["$.groups.veggies[0]", "_extra_veg"],
    },

    "matrixCell": "$.nested.matrix[1][0]",

    "ownerInfo": {
        "owner": "$.nested.meta.owner",
        "id": "$.nested.meta.id",
        "flag": "_flagged",
        "penalty": -99,
    },
}


# ---------------------------------------------------------------------------
# Exact expected output — hand-computed from INPUT_DOCUMENT + TEMPLATE above.
# ---------------------------------------------------------------------------

EXPECTED_OUTPUT = {
    "summary": {
        "label": "_summary_label",
        "firstTag": "@tag1",
        "secondTag": "@tag2",
        "appleCount": 3,
        "bonus": -10,
    },
    "itemsReshaped": [
        {
            "itemName": "@itemA",
            "itemQty": 2,
            "note": "_note_static_a",
            "adjustment": -1,
        },
        {
            "itemName": "@itemB",
            "itemQty": 4,
            "note": "_note_static_b",
            "adjustment": -2,
        },
    ],
    "groupsReshaped": {
        "fruitList": ["@apple", "@banana", "_extra_fruit"],
        "vegList": ["@carrot", "_extra_veg"],
    },
    "matrixCell": 3,
    "ownerInfo": {
        "owner": "@ownerName",
        "id": 42,
        "flag": "_flagged",
        "penalty": -99,
    },
}


def make_root(current):
    """Root Frame: self-referencing parent, per the locked design."""
    env = Environment(template=None, input=current, to=None, top=None)
    root = Frame(env=env, current=current, parent=None, level=0)
    root.parent = root
    env.top = root
    return root


def check_provenance(value, path=""):
    """Recursively walk a reshaped output and verify the naming convention
    holds: every string is '@...' (from input) or '_...' (from template);
    every int is either > 0 (from input) or < 0 (from template)."""
    if isinstance(value, str):
        assert value.startswith("@") or value.startswith("_"), (
            f"string at {path!r} = {value!r} does not start with '@' or '_' — "
            f"provenance is ambiguous"
        )
    elif isinstance(value, bool):
        pass  # bools aren't part of this convention
    elif isinstance(value, int):
        assert value != 0, f"int at {path!r} is 0 — sign convention can't be checked"
    elif isinstance(value, dict):
        for k, v in value.items():
            check_provenance(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            check_provenance(v, f"{path}[{i}]")


class TestReshape(unittest.TestCase):

    def setUp(self):
        compiled, _ = JFTLEngine().compile( TEMPLATE, main_only=True)
        frame = make_root(INPUT_DOCUMENT)
        stmt = compiled.main_entry
        self.result = frame.eval_value(stmt)

    def test_pretty_print_for_visual_inspection(self):
        print("\n--- INPUT ---")
        print(json.dumps(INPUT_DOCUMENT, indent=2))
        print("\n--- TEMPLATE ---")
        print(json.dumps(TEMPLATE, indent=2))
        print("\n--- OUTPUT ---")
        print(json.dumps(self.result, indent=2))

    def test_full_output_matches_expected(self):
        self.assertEqual(self.result, EXPECTED_OUTPUT)

    def test_provenance_convention_holds_throughout_output(self):
        check_provenance(self.result)

    def test_summary_mixes_input_and_template_values(self):
        summary = self.result["summary"]
        self.assertEqual(summary["label"], "_summary_label")     # template
        self.assertEqual(summary["firstTag"], "@tag1")            # input
        self.assertEqual(summary["appleCount"], 3)                # input, positive
        self.assertEqual(summary["bonus"], -10)                   # template, negative

    def test_array_of_objects_reshaped_correctly(self):
        items = self.result["itemsReshaped"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["itemName"], "@itemA")
        self.assertEqual(items[0]["adjustment"], -1)
        self.assertEqual(items[1]["itemQty"], 4)
        self.assertEqual(items[1]["note"], "_note_static_b")

    def test_object_of_arrays_reshaped_with_appended_constant(self):
        groups = self.result["groupsReshaped"]
        self.assertEqual(groups["fruitList"], ["@apple", "@banana", "_extra_fruit"])
        self.assertEqual(groups["vegList"], ["@carrot", "_extra_veg"])

    def test_array_of_arrays_navigation(self):
        # matrix[1][0] -> second row, first column -> 3
        self.assertEqual(self.result["matrixCell"], 3)

    def test_nested_object_of_objects(self):
        owner_info = self.result["ownerInfo"]
        self.assertEqual(owner_info["owner"], "@ownerName")
        self.assertEqual(owner_info["id"], 42)
        self.assertEqual(owner_info["flag"], "_flagged")
        self.assertEqual(owner_info["penalty"], -99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
