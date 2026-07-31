# Logic Statement

The logic statement is JFTL's single, general-purpose construct for
computation: variable assignment, conditionals, iteration, and reshaping.
There is no separate "if" statement, "loop" statement, or "function" —
everything is one statement type, distinguished by which fields are present.

A logic statement is a JSON object with `"$": true`:

```jsonc
{
  "$": true,
  "set": { "x": 1 }
}
```

Any JSON object that does **not** contain a `"$"` key is treated as an
ordinary object template — each of its values is compiled recursively, and
the object is rebuilt with those values substituted in. `"$": true` is what
tells the compiler "this object is not literal data, it's a logic
statement — interpret its keys as pipeline stages, not as output fields."

(`"$": false` marks the opposite case: an object that would otherwise look
like a logic statement but should be treated as a literal value. `"$"` set
to any other string selects a different statement kind entirely — for
example `"$": "tree"` for recursive tree traversal — which has its own
documentation and is not covered here.)

---

## Overview
```
{
  "$": true,

  // Stage 1 — Init
  "set": { "VAR": "EXPR" },
  "if": "EXPR",

  // Stage 2 — Select (pre-loop)
  "case": [ { "when": "COND", "then": "EXPR" } ],
  "data": "EXPR",

  // Stage 3 — Foreach (optional)
  "foreach": {
    "in": "EXPR",
    "if": "EXPR",
    "key": "KEY-VAR", "value": "ITEM-VAR", "index": "INDEX-VAR",:q
    "start": "EXPR", "stop": "EXPR", "limit": "EXPR",

    // per-item select (same mechanism as Stage 2/4)
    "case": [ { "when": "COND", "then": "EXPR" } ],
    "data": "EXPR",

    // per-iteration accumulator update
    "update": { "VAR": "EXPR" }
  },

  // Stage 4 — Transform (named, closed vocabulary; excl. with "return")
  "transform": "merge",
  "return": "EXPR",

  // Stage 5 — Return (general expression; excl. with "transform")

  // Stage 6 Fallback — wraps the whole pipeline
  "default": "EXPR",
  "error": "EXPR"
}
```

## Mental model: one pipeline, six stages

Every logic statement is a pipeline that starts with an input value and
ends with an output value. Internally, the pipeline tracks two things in
its own local scope (frame):

- **`_`** — the "current" value. Every stage below may reassign it. Think
  of it as the pipeline's working register.
- **`_current`** — a frozen snapshot of `_` exactly as it was when the
  pipeline began, captured before any stage runs. Nothing after Stage 0
  ever changes it. Use it when a later stage needs to look back at the
  original input, after `_` has already moved on.

The stages, in the order they always run:

```
Stage 0  Frame entry           "_" and "_data" both = input value
Stage 1  Init                  set, if
Stage 2  Select (pre-loop)     case, data
Stage 3  Foreach (optional)    in, if, key/value/index, start/stop/limit,
                                per-item case/data, per-item set
Stage 4  Select (post-loop)    (same case/data fields as Stage 2)
Stage 5  Transform (optional)  named, closed-vocabulary reshape
Stage 6  Return (optional)     general expression, final result
         Fallback              default, error
```

A minimal statement only needs the fields it actually uses. Most templates
use two or three stages, not all six.

---

## Field reference, in pipeline order

### Stage 1 — Init: `set`, `if`

```jsonc
{ "$": true, "set": { "x": "$=y", "count": 0 } }
```

`set` is a map of variable name → expression. Each expression is evaluated
once, in this statement's own local scope, and the results become named
variables visible to every later stage (and to any nested statement, via
the normal parent-chain lookup). Order of evaluation follows key order;
later entries may reference earlier ones.

```jsonc
{ "$": true, "if": "$=user.active", "data": "..." }
```

`if` is a guard condition, evaluated once. If it is false (or null/Missing,
under JFTL's strict falsiness — only `false`, `null`, and Missing are
falsy), the entire statement short-circuits straight to `default` and no
later stage runs at all. Omitting `if` is equivalent to `"if": true`.

### Stage 2 & Stage 4 — Select: `case`, `data`

These two fields are **one mechanism used at two points** in the pipeline:
once before `foreach` (Stage 2) and once after it (Stage 4). If there is no
`foreach`, Stages 2 and 4 collapse into a single evaluation. The fields
themselves are not duplicated — a statement has one `case` and one `data`.

```jsonc
{
  "$": true,
  "case": [
    { "when": "$=age >= 18", "then": "adult" },
    { "when": "$=age >= 13", "then": "teen" }
  ],
  "data": "child"
}
```

`case` is a list of `{ "when": COND, "then": EXPR }` entries, checked in
order. The first entry whose `when` is truthy has its `then` evaluated and
assigned to `_`. If no entry matches (or `case` is omitted), `data` is
evaluated instead and assigned to `_`. If both `case` and `data` are
omitted, `_` simply carries over unchanged from the previous stage.

`case` and `data` are the only fields in the pipeline that can branch.
Every other stage is a straight-line assignment to `_`.

### Stage 3 — Foreach (optional)

```jsonc
{
  "$": true,
  "foreach": {
    "in": "$=items",
    "if": "$=_.active",
    "key": "k", "value": "v", "index": "i",
    "start": 0, "stop": null, "limit": null,
    "case": [ { "when": "COND", "then": "EXPR" } ],
    "data": "$py=_*_",
    "set": { "sum": "$py=sum+_", "count": "$py=count+1" }
  }
}
```

If `foreach` is present, this statement iterates.

- **`in`** — the collection to iterate. If omitted, iterates over the
  current `_` (whatever Stage 2 produced). Accepts a list, a dict (iterates
  key/value pairs), or an integer (iterates `range`-style).
- **`if`** — per-item filter, evaluated before binding. Filtered-out items
  are skipped entirely: they are not collected, and per-item `set` does not
  run for them.
- **`key`**, **`value`**, **`index`** — variable names to bind, per
  iteration, to the current key (dict iteration), item value, and 0-based
  position respectively. If `value` is omitted, the item is available as
  `_` instead of under a named variable.
- **`start`**, **`stop`**, **`limit`** — bound the range of positions
  processed, evaluated once before the loop begins. Negative `start`/`stop`
  count from the end, same convention as most slicing.
- **`case`** / **`data`** — this stage's *own* case/data pair, distinct
  from the top-level Stage 2/4 fields. Evaluated fresh on every iteration.
  Determines the per-item value that gets collected. If both are omitted,
  the raw item passes through unchanged (identity map).
- **`set`** — a per-*iteration* accumulator update, evaluated once per
  item, immediately after this iteration's `case`/`data` result is bound to
  `_`. Targets are ordinary variables in the statement's frame — the same
  frame Stage 1's `set` wrote into — so an accumulator seeded in Stage 1
  (`"set": { "sum": 0 }` at the top level) can be updated here across
  iterations (`"set": { "sum": "$py=sum+_" }` inside `foreach`) and read
  afterward in Stage 5/6. This is how reductions (sum, average, running
  totals) are expressed — no separate "reduce" construct is needed.

After the loop finishes, `_` becomes the **collected** result: a list (if
`in` was a list or an integer range) or a dict (if `in` was a dict),
containing each iteration's per-item value, in order, with filtered-out
items simply absent.

If `foreach` is entirely omitted, none of this runs, and `_` is whatever
Stage 2 left it as.

### Stage 5 — Transform (optional, named)

```jsonc
{ "$": true, "foreach": { "...": "..." }, "transform": "merge" }
```

`transform` applies a **named, predefined** structural reshape to whatever
`_` currently is (Stage 4's result). The value must be a bare string
literal — not an expression — chosen from this fixed set:

| name           | input shape          | effect                                   |
|----------------|----------------------|-------------------------------------------|
| `merge`        | list of objects      | shallow-merges all objects into one        |
| `flatten`      | list of lists        | concatenates the sublists into one list    |
| `to_pairs`     | object                | converts to a list of `[key, value]` pairs |
| `from_pairs`   | list of `[key, val]`  | converts back into an object               |
| `drop_missing` | list or object        | removes entries whose value is Missing     |
| `join`         | list of scalars       | concatenates into a single string          |

An unrecognized name is a compile-time error. `transform` is mutually
exclusive with `return` (Stage 6) — a statement uses one or the other, not
both, since both stages exist to produce the statement's final shape.

### Stage 6 — Return (optional, general)

```jsonc
{
  "$": true,
  "set": { "sum": 0, "count": 0 },
  "foreach": {
    "in": "$=items",
    "data": "$py=_*_",
    "set": { "sum": "$py=sum+_", "count": "$py=count+1" }
  },
  "return": "$py=sum/count"
}
```

`return` evaluates a general expression — nav shorthand, `$py=`,
`$pyeval=`, `$pyrun=`, or any other registered expression engine — with `_`
bound to Stage 4/5's result. Its output becomes the statement's final
result, replacing everything that came before. Because it runs in the
statement's own frame, it can reference any variable set anywhere earlier
in the pipeline, including accumulators updated inside `foreach.set`.

Omitting `return` means the statement's result is simply whatever `_`
already is after Stage 4/5 — this is the common case for plain
selection/looping templates that don't need a final calculation.

`return` is mutually exclusive with `transform` — pick whichever one
matches what you're doing: `transform` for a known reshape, `return` for
anything else.

### Fallback: `default`, `error`

```jsonc
{ "$": true, "if": "$=user.active", "data": "...", "default": null }
```

`default` is evaluated and returned whenever the "normal" result is
unavailable: `if` was false, or the pipeline's result came out Missing.

```jsonc
{ "$": true, "data": "$py=1/0", "error": "\"unavailable\"" }
```

`error` is evaluated and returned whenever any stage produced an error
notice. If `error` is omitted, an error propagates upward unchanged (and
will surface as a render failure unless a surrounding statement handles
it).

---

## Sentinel values

Three special values can appear as the result of any stage, and are
handled consistently everywhere in the pipeline:

- **`null`** — an ordinary JSON null.
- **Missing** — "there is no value here" (e.g. a navigation path that
  didn't resolve). Distinct from `null`. Triggers `default` handling.
  Accessible as the reserved variable `_missing`.
- **`_skip`** — a special sentinel meaning "omit this entry entirely."
  Returning `_skip` from an object-building context drops that key; from
  a `foreach` per-item result, drops that item from the collected output
  without it counting toward `index`. Accessible as the reserved variable
  `_skip`.

---

## Reserved variables

Available inside any logic statement's expressions (nav shorthand or
`$py=`/`$pyeval=`/`$pyrun=`), via ordinary variable lookup up the parent
chain:

| name        | meaning                                                        |
|-------------|-----------------------------------------------------------------|
| `_`         | current pipeline value (the "working register")                 |
| `_current`  | this statement's input value, frozen at Stage 0                 |
| `_parent`   | the enclosing frame (one level up)                               |
| `_top`      | the root frame of the whole render                                |
| `_input`    | the original top-level input document                            |
| `_missing`  | the Missing sentinel                                              |
| `_error`    | the generic error sentinel                                        |
| `_skip`     | the skip sentinel                                                  |
| `_level`    | nesting depth of the current frame                                 |
| `_datasets` | registered external datasets, by name                              |

`_current` vs. `$<` (parent-current nav shorthand): `_current` is *this*
frame's own frozen entry value; `$<` reaches into the *enclosing* frame's
live current. They answer different questions — "what did I start with"
versus "what is my caller currently looking at."

---

## Worked examples

**Simple conditional value:**
```jsonc
{
  "$": true,
  "case": [
    { "when": "$=score >= 90", "then": "A" },
    { "when": "$=score >= 80", "then": "B" }
  ],
  "data": "F"
}
```

**Filter and reshape a list:**
```jsonc
{
  "$": true,
  "foreach": {
    "in": "$=users",
    "if": "$=_.active",
    "data": "$=_.name"
  }
}
```
Result: a list of active users' names.

**Average of squares (reduction via `foreach.set`):**
```jsonc
{
  "$": true,
  "set": { "sum": 0, "count": 0 },
  "foreach": {
    "in": "$=items",
    "data": "$py=_*_",
    "set": { "sum": "$py=sum+_", "count": "$py=count+1" }
  },
  "return": "$py=sum/count"
}
```

**Merge a list of per-item objects into one:**
```jsonc
{
  "$": true,
  "foreach": {
    "in": "$=records",
    "data": { "${_.key}": "$=_.value" }
  },
  "transform": "merge"
}
```

**Guard with fallback:**
```jsonc
{
  "$": true,
  "if": "$=order.paid",
  "data": "$=order.confirmationCode",
  "default": "\"pending\""
}
```