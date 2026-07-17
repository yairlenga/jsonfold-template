# JFTL Logic Statements

A **logic statement** is a JSON object marked with `"$": true`. It is the
one construct in JFTL where control flow — conditions, loops, branching —
happens. Everything else in a template (plain objects, arrays, literals,
and expressions from `EXPRESSION.md`) is data-shaped; a logic statement is
the only place a template makes a decision.

```json
{
    "$": true,
    "set": { "var1": "EXPR", "var2": "EXPR" },
    "if": "EXPR",
    "data": "EXPR",
    "foreach": {
        "key": "KEY-VAR",
        "value": "ITEM-VAR",
        "index": "INDEX-VAR",
        "in": "EXPR",
        "if": "EXPR",
        "shape": null | "array" | "object" | "range",
        "start": "EXPR",
        "stop": "EXPR",
        "limit": "EXPR"
    },
    "case": [
        { "when": "COND-1", "then": "EXPR-1" },
        { "when": "COND-2", "then": "EXPR-2" }
    ],
    "body": "EXPR",
    "default": "EXPR",
    "transform": null | "object",
    "error": "EXPR"
}
```

Every field is optional except `"$": true` itself. Fields not present are
simply skipped.

## Execution order

A logic statement always runs its fields in the same fixed order,
regardless of the order they're written in the JSON:

```
set → if → data → foreach → (case → body) → transform → error
```

`case`/`body` choose a single body statement — this happens **once**, not
per loop iteration (see **Foreach** below for what that means when
combined with `foreach`). `error` is reserved for future use — see
**Reserved: `error`**.

## Scope

Every logic statement creates a **new child frame** the moment it starts
evaluating. All `set` bindings, `if`/`case` conditions, `data`, and `body`
are evaluated against this new frame — never the parent's. This is the
only place a new frame boundary is introduced; plain objects and arrays
don't create one.

## `set` — local variable bindings

```json
"set": { "total": "EXPR", "tax": "EXPR" }
```

Each entry binds a name to the result of evaluating its expression,
in the new frame created for this statement. Bindings are evaluated in
the order written, so later bindings may reference earlier ones. Names
may not start with `_` (reserved — see `NAVIGATION.md`).

## `if` — guard condition

```json
"if": "EXPR"
```

Evaluated in the new frame, after `set`. If it evaluates falsy (`false`,
`null`, or MISSING — not numeric zero), the entire statement short-
circuits and returns the result of `default` (or MISSING, if no
`default` is given). Nothing past this point — `data`, `foreach`,
`case`/`body` — runs at all.

## `data` — rebind current scope

```json
"data": "EXPR"
```

If present, evaluates in the new frame and replaces that frame's current
data (`_`) with the result. Everything evaluated afterward — `foreach`'s
default iteration target, `case`/`body` — sees this new current data
unless it names its own source explicitly.

## `case` / `body` — choosing what to evaluate

```json
"case": [
    { "when": "COND-1", "then": "EXPR-1" },
    { "when": "COND-2", "then": "EXPR-2" }
],
"body": "EXPR"
```

If `case` is present, its entries are checked in order; the first `when`
that evaluates truthy selects that entry's `then` as the body to use.
If no `case` entry matches, `body` (if present) is used instead. If
neither `case` nor `body` produces something to run, the statement
returns `default`.

This selection happens **exactly once per statement**, before any
`foreach` loop runs — not once per loop iteration. If `foreach` is also
present, the single chosen body is the one executed for every iteration
of the loop; different iterations cannot select different `case` branches
from the same statement. If you need per-item branching, nest a second
logic statement (with its own `case`) as the loop body.

## `foreach` — iteration

```json
"foreach": {
    "key": "KEY-VAR",
    "value": "ITEM-VAR",
    "index": "INDEX-VAR",
    "in": "EXPR",
    "if": "EXPR",
    "shape": "array",
    "start": "EXPR",
    "stop": "EXPR",
    "limit": "EXPR"
}
```

If `foreach` is present, the chosen body (see above) is evaluated once
per item, and the statement's result is a list (or object — see
`transform`) collecting each iteration's value.

**Source of iteration** — `in`, if present, is evaluated once and
iterated. If absent, the frame's current data (`_`, as of after `data`)
is iterated instead.

- A list source produces `(position, item)` pairs, positions counting
  from 0.
- A dict source produces `(key, value)` pairs, in the dict's own key
  order.
- `null` or MISSING as the source means "nothing to iterate" — the loop
  produces **no items at all**, and the whole statement returns
  `default` (not an empty list/object). This is different from the
  source being a non-empty collection that every item happens to fail
  its `if` filter against — that case *does* return an empty list/object,
  not `default`.
- Any other type (a string, a number, a boolean) as the source is an
  error.

**`shape`** — when set to `"range"`, `in` is ignored entirely. The loop
instead iterates a numeric range built from `start`/`stop`/`limit`
(below), with `value` bound to the numeric value at each step and `index`
bound to the same value as `value` (position and value coincide in range
mode). `shape` is case-sensitive; the only recognized values are
`"array"` (the default — iterate `in`/current data as described above)
and `"range"`. Any other value is a compile-time error.

**`start` / `stop` / `limit`** — apply to the sequence of positions being
walked (0, 1, 2, ... for a list/dict source; or the numeric range itself,
for `shape: "range"`):

- `start` (default `0`) — first position to include, inclusive. Negative values
  can be used to specify position from the end.
- `stop` — position to stop before, exclusive. Negative values can be used to
  specify position the end.
- `limit` — maximum number of items to include, measured from `start`.
- If both `stop` and `limit` are provided the smaller values will override.
  For example "start=5, stop=-3, limit=5 on the range "a" to "z" will produce
  the array [ "f", "g", "h", "i", "j"]: The first 5 elements from the sequence
  [ "f" ... "y" ].
- All three are ordinary expressions evaluated once, before the loop
  begins — not per-iteration. They must resolve to integer expressions or None,
  otherwise, an error is triggered.

**Per-iteration bindings** — for each item that survives `start`/
`stop`/`limit` filtering:

- `value`, if given, is bound to the item's value in the loop's frame.
  If `value` is omitted, the frame's current data (`_`) is set to the item
  instead, for the duration of that iteration.
- `key`, if given, is bound to the item's key (dict source) or position
  (list source, `shape: "array"`) or numeric value (`shape: "range"`).
- `index`, if given, is bound to the item's position in the walked
  sequence (0-based, counting only items that reach this point — i.e.
  after `start`/`stop`/`limit` filtering, not the original source's
  positions).
- `if`, if given, is evaluated per-item **after** the above bindings are
  set. If falsy, that item is skipped entirely — it contributes nothing
  to the result and does not consume an `index` slot for the *next* item
  (skipped items are simply absent, not represented as `null`/MISSING
  placeholders).

The loop's own frame and its variable bindings are reused across all
iterations rather than each iteration getting an isolated copy — each
item's bindings simply overwrite the previous item's. Because frame data
itself is read-only, this carries no correctness risk between iterations;
it's a deliberate reuse rather than a fresh frame per item.

## `transform` — shaping the foreach result

```json
"transform": "OBJECT"
```

By default, a `foreach` result is a **list**, in iteration order. Setting
`transform` to `"OBJECT"` produces a **dict** instead, keyed by each
iteration's `key` binding (see above) rather than appended to a list.

No other `transform` values are currently implemented. This field is a
placeholder for additional output shapes and is not yet finalized —
treat any value other than `"OBJECT"` (including omitting the field) as
"produce a list," and don't rely on any other specific value being
accepted or rejected yet.

## `default` — fallback value

```json
"default": "EXPR"
```

Evaluated (in the new frame) and used as the statement's result whenever:

- `if` evaluates falsy, or
- neither `case` nor `body` produces something to run, or
- `foreach` is present but its iteration source is `null`/MISSING
  (nothing to iterate at all — not merely zero items surviving `if`
  filtering), or
- (non-`foreach` case) the chosen body itself evaluates to MISSING.
- The 'default' does NOT apply to individual value inside a `foreach`
  loop. Those will be converted to null (when the output shape is
  LIST).

If `default` itself is absent in any of these situations, the statement's
result is MISSING.

## Reserved: `error`

```json
"error": "EXPR"
```

This field is accepted and parsed but has **no runtime behavior yet** —
it is reserved for future error-handling semantics and should not be
relied on to do anything at this time.

## Result and MISSING

A single (non-`foreach`) logic statement's result is either the chosen
body's evaluated value, or `default` if that value is MISSING.

A `foreach` statement's result is a list or object (per `transform`)
built from every surviving iteration's value, **without** filtering
MISSING values out of that collection itself — MISSING entries inside a
`foreach` result are handled the same way MISSING is handled anywhere
else it ends up inside a containing object or array (silently dropped
from objects, kept as `null` in arrays).