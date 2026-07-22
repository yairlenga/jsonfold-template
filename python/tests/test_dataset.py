import unittest

import template as jftl

def merge_datasets(template_datasets=None, engine_datasets=None, render_datasets=None):
    engine = jftl.create_engine()
    for k, v in (engine_datasets or {}).items():
        engine.add_dataset(k, v)

    source = {
        "main": "$_datasets",
        "datasets": template_datasets,
    }
    template, _ = engine.compile(source)
    _, result = engine.render(template, None, datasets=render_datasets)
    return result

TEMPLATE = {"template": "template_value", "merged": "from_template"}
ENGINE = {"engine": "engine_value", "merged": "from_engine"}
RENDER = {"render": "render_value", "merged": "from_render"}


class TestDatasetMerge(unittest.TestCase):

    # 1. all three None
    def test_all_none(self):
        merged = merge_datasets(None, None, None)
        self.assertEqual(merged, {})

    # 2. template only
    def test_template_only(self):
        merged = merge_datasets(TEMPLATE, None, None)
        self.assertEqual(merged, {"template": "template_value", "merged": "from_template"})

    # 3. engine only
    def test_engine_only(self):
        merged = merge_datasets(None, ENGINE, None)
        self.assertEqual(merged, {"engine": "engine_value", "merged": "from_engine"})

    # 4. render only
    def test_render_only(self):
        merged = merge_datasets(None, None, RENDER)
        self.assertEqual(merged, {"render": "render_value", "merged": "from_render"})

    # 5. template + engine — distinct keys both present, "merged" resolved by precedence
    def test_template_and_engine(self):
        merged = merge_datasets(TEMPLATE, ENGINE, None)
        self.assertEqual(merged, {
            "template": "template_value",
            "engine": "engine_value",
            "merged": "from_engine",
        })

    # 6. template + render — distinct keys both present, "merged" resolved by precedence
    def test_template_and_render(self):
        merged = merge_datasets(TEMPLATE, None, RENDER)
        self.assertEqual(merged, {
            "template": "template_value",
            "render": "render_value",
            "merged": "from_render",
        })

    # 7. engine + render — distinct keys both present, "merged" resolved by precedence
    def test_engine_and_render(self):
        merged = merge_datasets(None, ENGINE, RENDER)
        self.assertEqual(merged, {
            "engine": "engine_value",
            "render": "render_value",
            "merged": "from_render",
        })

    # 8. all three present — every distinct key survives, "merged" resolved by full precedence
    def test_all_three_present(self):
        merged = merge_datasets(TEMPLATE, ENGINE, RENDER)
        self.assertEqual(merged, {
            "template": "template_value",
            "engine": "engine_value",
            "render": "render_value",
            "merged": "from_render",
        })

if __name__ == "__main__":
    unittest.main()

