"""
Linear test progression for the logic element, against the PUBLIC API only
(create_engine / engine.compile / engine.render) — no internal imports from
core.py, template.py, runtime.py, or logic.py.

Order:
  1. body only
  2. body + if   (true and false branches)
  3. body + case (matched and unmatched -> falls back to body)

Run with:  python -m unittest test_public_logic.py -v

"""
import unittest

from template import create_engine


def compile_and_render(top: dict, input_doc):
    engine = create_engine()

    status, result, errors = engine.compile_and_render(top, input_doc, main_only=True)
    assert not errors, f"unexpected compile errors: {errors}"
    return status, result


class TestBodyOnly(unittest.TestCase):
    """1. body only — simplest possible logic element."""

    def test_body_returns_navigated_value(self):
        template = {"$": True, "body": "$.name"}
        status, result = compile_and_render(template, {"name": "Alice"})
        self.assertTrue(status.ok)
        self.assertEqual(result, "Alice")

    def test_body_navigates_nested_path(self):
        template = {"$": True, "body": "$.user.address.city"}
        status, result = compile_and_render(
            template, {"user": {"address": {"city": "Springfield"}}}
        )
        self.assertTrue(status.ok)
        self.assertEqual(result, "Springfield")

    def test_body_missing_path_produces_missing_like_result(self):
        # No "name" key in the input — the path resolves to Missing.
        template = {"$": True, "body": "$.name"}
        status, result = compile_and_render(template, {})
        self.assertTrue(status.ok) 
        # a Missing navigation result is not itself an execution error
        # Exact representation of "Missing" via the public API (None after
        # JSON-ification, or a Missing sentinel) is unconfirmed — flag if wrong.
        self.assertFalse(result)


class TestBodyPlusIf(unittest.TestCase):
    """2. body + if — condition gates whether body runs at all."""

    def test_if_true_runs_body(self):
        template = {"$": True, "if": "$.enabled", "body": "$.name"}
        status, result = compile_and_render(
            template, {"enabled": True, "name": "Alice"}
        )
        self.assertTrue(status.ok)
        self.assertEqual(result, "Alice")

    def test_if_false_skips_body_and_returns_none(self):
        template = {"$": True, "if": "$.enabled", "body": "$.name"}
        status, result = compile_and_render(
            template, {"enabled": False, "name": "Alice"}
        )
        self.assertTrue(status.ok)
        self.assertIsNone(result)

    def test_if_false_with_default_returns_default(self):
        template = {
            "$": True,
            "if": "$.enabled",
            "body": "$.name",
            "default": "$.fallbackName",
        }
        status, result = compile_and_render(
            template, {"enabled": False, "name": "Alice", "fallbackName": "Guest"}
        )
        self.assertTrue(status.ok)
        self.assertEqual(result, "Guest")


class TestBodyPlusCase(unittest.TestCase):
    """3. body + case — case overrides body when a 'when' matches;
    falls back to body when no case matches."""

    def test_matching_case_overrides_body(self):
        template = {
            "$": True,
            "case": [{"when": "$.useSpecial", "then": "$.specialName"}],
            "body": "$.name",
        }
        status, result = compile_and_render(
            template,
            {"useSpecial": True, "specialName": "Bob", "name": "Alice"},
        )
        self.assertTrue(status.ok)
        self.assertEqual(result, "Bob")

    def test_no_matching_case_falls_back_to_body(self):
        template = {
            "$": True,
            "case": [{"when": "$.useSpecial", "then": "$.specialName"}],
            "body": "$.name",
        }
        status, result = compile_and_render(
            template,
            {"useSpecial": False, "specialName": "Bob", "name": "Alice"},
        )
        self.assertTrue(status.ok)
        self.assertEqual(result, "Alice")

    def test_first_matching_case_wins_among_several(self):
        template = {
            "$": True,
            "case": [
                {"when": "$.flagA", "then": "$.valA"},
                {"when": "$.flagB", "then": "$.valB"},
            ],
            "body": "$.fallback",
        }
        status, result = compile_and_render(
            template,
            {
                "flagA": False,
                "flagB": True,
                "valA": "A",
                "valB": "B",
                "fallback": "F",
            },
        )
        self.assertTrue(status.ok)
        self.assertEqual(result, "B")


if __name__ == "__main__":
    unittest.main(verbosity=2)
