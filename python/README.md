# jsonfold-template (JFTL)

Python reference implementation of **JFTL (JSONFold Template Language)** —
a JSON-to-JSON transformation language where templates are themselves valid
JSON documents.

This is an early skeleton. Spec documents (goals/architecture, expression
evaluation) live outside this repo and are the source of truth; this package
tracks them as they stabilize.

## Status

Pre-alpha. Core pieces scaffolded:

- `sentinels` — `MISSING` / `ERROR` / JSON `null` distinction
- `navigation` — static-path navigation engine (dot, index, quoted key, `$var` roots)
- `context` — `_`, `_input`, `_global`, `_ctx` context model
- `expressions` — two-mode evaluation (literal / expression), CEL via `cel-python`
- `processors.logic` — fixed execution order: `set → if → data → foreach → case/body → transform → error`
- `serializer` — final-pass resolution of `MISSING` (omit from objects, `null` in arrays)

Not yet implemented: full `transform` vocabulary, macro dispatch wiring,
`where`-clause filtering details, non-CEL engine adapters.

## Install (editable, for development)

```bash
pip install -e ".[dev]"
```

## Quick usage (target shape)

```python
from jsonfold_template import Engine

engine = Engine()
result = engine.render(
    template={"name": "expr:_input.user.name"},
    input_data={"user": {"name": "Ada"}},
)
```
