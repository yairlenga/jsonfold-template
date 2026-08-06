# JSONFold Template Language (JFTL)

## Goal

Template language to generate JSON documents from (1) JSON Template (2) JSON Input.

## Template Structure

{
    body: { TEMPLATE-BODY },
    macro: {
        "macro1": { MACRO-BODY },
        "macro2": { MACRO-BODY },
        ...
    }
    data: {
        "item1": { JSON-DATA },
        "item2": { JSON-DATA },
        ...
    }
}

## Template Processing

The JSON output is the result of processing the template `body`, according to the following rules:

1. Scalars:
   - Each scalar is passed as-is
2. Arrays:
   - Each element is processed.
   - Each element whose value is NONE is ignored.
   - The output is an array of all remaining elements
3. Objects without execution tag - no '$' attribute.
   - Each keyword is processed
   - If the keyword is NONE, or if it is not a string, this KV pair is ignored
   - The value is processed
   - If the value is NONE, this KV pair is ignored
   - Otherwise, keyword/value is added to the output object.
   - The output is the object containing all elements.  
4. Objects with other execution tag.
   - Will be processed by the logic engine.

## Logic Engine

```json
{
    "$": true,
    "set": {
        "var1": "EXPR-1",
        "var2": "EXPR-2",
        ...
    },
    "if": "EXPR",
    "data": "EXPR",
    "foreach": {
        "key": "KEY-VAR",
        "item": "ITEM-VAR",
        "in": "EXPR",
    },
    "case": [
        { "when": "COND-1", "then": "EXPR-1" },
        { "when": "COND-2", "then": "EXPR-2" },
    ],
    "body": "EXPR",
    "transform": "MERGE|FLATTEN|NONE",
    "error": "EXPR",
}
```

### Context

# JFTL Execution Context

Every evaluation node runs with a context of this shape:

```json
{
  "_": {
    "template": {},
    "root": {},
    "top": {},
    "parent": {},
    "global": {},
    "level": 0
  },
  "data": {},
  "MISSING": "...",
  "ERROR": "...",
  "var1": "..."
}
```

## `_` — reserved structural namespace

| Field | Meaning |
|---|---|
| `_.template` | The static template/macro library. Not isolation-scoped — any macro may reference any other macro defined in the same template, regardless of data isolation. Macro invocation (`$: "name"`) is sugar for evaluating `_.template.macro.<name>`. |
| `_.root` | Pointer to the **root context** (the context as it existed before any descent/macro call). Always visible, including inside macros — the sanctioned exception to isolation, and the mechanism that makes `_.global` work without parameter drilling. |
| `_.top` | Pointer to the root of the **input document data**. Sugar for `_.root.data`. |
| `_.parent` | The enclosing context. Supports ascent (`../`) for join-style access. **Set to `null` at every macro invocation** — this is the actual isolation boundary: a macro cannot ascend into its caller's local tree. |
| `_.global` | The immutable environment object (host-supplied constants + explicitly exported root bindings). Not separately stored outside the root — sugar for `_.root.global`, always resolves to the same object regardless of nesting depth. |
| `_.level` | `0` at root, `parent.level + 1` otherwise. |

## Top-level, alongside `data`

| Field | Meaning |
|---|---|
| `data` | The "current" node (`self`) — what `sel:`/relative paths resolve against. Set by the `data` step in a logic object, or per-element inside `foreach`. |
| `MISSING` | Sentinel returned by unresolved path access (e.g. `a.b` where `b` doesn't exist). Distinct from JSON `null` — the JS `undefined`/`null` split, not Python's conflated `None`. Falsy in strict `if`. Dropped silently when it occurs as an array element or object value; converted to `null` only if it's the final result of the whole template. |
| `ERROR` | Sentinel for a cleanly-returned failure. Falsy in strict `if` and in bare guards. Safe to test via identity (`X == ERROR`) without triggering propagation; using it for anything else (arithmetic, output embedding, etc.) throws, caught by the nearest `error:` handler — and, unlike `MISSING`, must never be silently dropped from output. |
| `var1`, `var2`, ... | User-defined `set`/`foreach` bindings. Reserved names (`MISSING`, `ERROR`, `data`, `_`) may not be redefined here — a hard template-validation error. |

## Truthiness / test modifiers

| Form | Meaning |
|---|---|
| bare `X` | strict: falsy only if `false`, `null`, or `MISSING` |
| `not:X` | strict negation |
| `exists:X` | `X != MISSING` |
| `error:X` | `X == ERROR` (safe identity check, no propagation) |
| `empty:X` | broad Python-style falsy table (`false`, `null`, `MISSING`, `0`, `""`, `[]`, `{}`) |
| `not:empty:X` | broad truthy / "has real content" |