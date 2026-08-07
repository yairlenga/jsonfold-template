# `logic.md` — Logic Element Reference

<!-- LTeX: dictionary+=foreach dictionary+=Foreach -->
<!-- cspell:words pyeval -->

## What is a Logic Element?

A logic element is a JSON object with `"$": true` that drives JFTL's non-literal processing: variable assignment, conditionals, iteration, selection, structural transformation, and error handling. Any object without `"$": true` is either treated as a literal structure (with its values recursively compiled) or, if it has `"$": false`, forced to a pure literal (no further compilation of its contents).

```json
{ "$": true, "out": "hello" }
```

A logic element runs in its own child frame — variables set via `set` (and the loop variables from `foreach`) are local to that element and anything nested inside it. See `variables.md` for full scoping rules.

Expressions inside a logic element (`"check"`, `"out"`, `"data"`, etc.) can be navigation (`navigation.md`), interpolated strings (`interpolation.md`), or expression-engine calls (`expression-engines.md`). This page only describes the logic pipeline itself — the keys, their order, and what each stage does.

---

## Pipeline Overview

A logic element is evaluated in four stages, in order. Every stage is optional — a logic element with no keys at all is legal. With no processing keys, the input current value passes through unchanged.

| Stage | Key(s) | Purpose |
|---|---|---|
| 1 — Setup | `set`, `check`, `data` | Declare local variables, gate execution, replace current data |
| 2 — Foreach | `foreach` | Iterate over an array, object, or numeric range |
| 3 — Output | `case` / `out`, `transform` | Select/produce and reshape the final value |
| 4 — Fallback | `fallback` / `error` | Fallback values if the pipeline produced missing/error |

If any stage produces `Missing` or an error, evaluation stops early and falls through to Stage 4 — later stages are skipped.

---

## Stage 1 — Setup: `set`, `check`, `data`

These three run in order, in the same frame, before any iteration or output logic.

### `set`

An object mapping variable names to expressions. Each is evaluated in order and bound as a local variable, visible for the rest of this logic element (including `check`, `data`, `foreach`, `case`, `out`) and to nested logic elements.

```json
{
  "$": true,
  "set": { "tax_rate": "$py=0.08", "label": "invoice" },
  "out": "$label"
}
```

The **first** frame containing user-defined variables establishes the render’s global variable scope. See `variables.md`.

### `check`

A condition, checked right after `set`. If it evaluates false, the entire logic element evaluates to `Missing` and **every later stage is skipped — including `data`**. If omitted, `check` defaults to `true`.

```json
{ "$": true, "check": "$py=_.age >= 18", "out": true, "fallback": false }
```

If `check` itself evaluates to an error notice, that error propagates to `error` handling (Stage 4), not `fallback`.

### `data`

Only runs if `check` passed. Replaces the "current" value (`_`) used by the rest of the pipeline — `foreach`'s default source and anything downstream that reads `_`. If omitted, `_` stays whatever it already was on entry to this logic element.

```json
{
  "$": true,
  "data": "$.order.ship_to",
  "out": {
    "address": "$.street",
    "city": "$.city",
    "state": "$.state",
    "zip": "$.zip"
  }
}
```

---

## Stage 2 — `foreach`

`foreach` is entirely optional. When omitted, the logic element's `_` simply passes from Stage 1 straight through to Stage 3.

`foreach` is itself an object with its own keys. It iterates over an array, object, or integer range, and produces either an array or an object as its result (which becomes the new `_` for the rest of the pipeline). It's also the mechanism for driving per-item processing over container elements — running a nested logic element (or any expression) once per item of an array or object, rather than operating on the container as a whole.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "var": "item",
    "key": "k",
    "if": "$py=item['active']",
    "out": "$item.sku",
    "update": { "count": "$py=(count or 0) + 1" }
  }
}
```

### Source (`in`)

- `in` — the collection to iterate. If omitted, defaults to the current `_` (i.e. Stage 1's result).
- Accepts an **array** (iterates by position), an **object** (iterates key/value pairs, result is an object), or a non-negative **integer** (iterates the numeric range `start` .. `in-1`, like Pthons rnage `range(start, in)`).
- If the source is **`null`/`Missing`**, `foreach` produces `Missing` for the whole logic element — falling through to Stage 4's `fallback`, the same as a false `check`. This is a "soft" outcome, not an error: a missing/absent collection is treated as an expected, recoverable case.
- If the source is anything else (a string, a float, a boolean, etc.), it's a hard error (`FOREACH_IN`), falling through to Stage 4's `error` instead.


### Windowing (`start`, `stop`, `limit`)

- `start` (default `0`), `stop` (default: end), `limit` (max number of *output* items).
- Negative `start`/`stop` resolve against the total item count (array length, object item count, or range bound) — like Python negative slicing.
- `start`/`stop` windowing applies to raw source positions, *before* the per-item `check` filter runs. An item excluded by `start`/`stop` is skipped outright; an item excluded by `check` is skipped only after being counted toward the window. These are independent — `start`/`stop` doesn't count only condition-matching items.
- `limit` caps the number of items actually included in the *result* (after `check` filtering), and stops iteration early once reached. In particular, `limit: 1` efficiently implements “find the first item that matches,” because iteration stops after the first accepted output.

When iterating over **array** or **object**, `start` and `stop` negative indices indicate position from the tail, therefore stop=-2 will not iterate over the last 2 elements, and start=-5 will start from the 5th element from the tail. 

When iterating over ranges, `start` specifies the starting location, which can be negative, or positive.

### Binding variables

- `var` — variable name bound to the current item's value. If omitted, the item value is stored in the current value variable (`_`).
- `key` — variable name bound to the current key or position. If omitted, the item key or position is stored in the variables called `_key`.
  
When iterating over **array**, the key variable (or the default `_key`) is the (0-base) integer position of each item. When iterating over an **object**, the key is the (string) key value. When iterating over a range, the key is (0-based integer position from the start of the range).

Note that when `start` is used on an **object** or **array**, the key references the position of the item in the original source. If `start` is used over integer range, it reduces the range, and the first key will be 0.


### Per-item filter (`if`)

Same truthiness rule used throughout JFTL: `false`, `null`, and `Missing` are falsy, everything else truthy. An item failing this condition is skipped — not included in the result, doesn't count against `limit`.

### Per-item output (`case` / `out`)

For each included item, its contribution to the result is produced by `case` or `out` — the same two keys, with the same rules, that Stage 3 uses for the logic element's overall result (see Stage 3 below):

- `case` and `out` are mutually exclusive — using both is a compile error.
- `out` is a plain expression, evaluated per item.
- `case` is an array of `{ "when": COND, "then": EXPR }` objects, evaluated in order — first match wins. The last item may instead be `{ "else": EXPR }`, an unconditional fallback if nothing else matched.
- If neither `case` nor `out` is given, the item itself is used as-is.
- If the result is the skip sentinel `_skip`, the item is dropped from the result entirely (not included, doesn't count against `limit`).
- If the result is the break sentinel value `_break`, processing of the current collection stop, and not additional items are processes.

```json
"foreach": {
  "in": "$.orders",
  "var": "o",
  "case": [
    { "when": "$py=o['total'] > 100", "then": "large" },
    { "else": "small" }
  ]
}
```

### `update` — per-iteration accumulator

`update` is nested inside `foreach`. It's an object mapping variable names to expressions, evaluated once per included item, *after* that item's `case`/`out` has been computed and set as the current value (`_`) — so `update` expressions can read `_` to mean "this item's output."

```json
"foreach": {
  "in": "$.orders",
  "var": "o",
  "out": "$o.total",
  "update": { "sum": "$py=(sum or 0) + _" }
}
```

Variables set by `update` live in the same frame as Stage 1's `set` — they persist across iterations and remain visible after `foreach` completes, for use in Stage 3's `out`.

### Result shape

- **Array** source → result is an **array**
- **Range** source - result is in **array**
- **Object** source → result is an **object**, with the same keys as the original source keys.

If the source is empty, or every item is filtered out, the result is an empty array/object — not `Missing`.

---

## Stage 3 — Output: `case` / `out`, `transform`

### `case` / `out`

The value-selection step, applied once (not per-item) over whatever `_` is at this point (the `foreach` result, or Stage 1's result if there was no `foreach`).

`case` and `out` are mutually exclusive — a logic element uses one or the other, never both. Combining them is a compile error (`OUT-CASE-CONFLICT`).

- **`out`** — a plain expression, evaluated and used directly as the result.
- **`case`** — an array of `{ "when": COND, "then": EXPR }` objects, evaluated in order. The **first** matching `when` wins, and its `then` is the result.
  The **last item in the list may instead be `{ "else": EXPR }`** — a single-key object naming the fallback used if no earlier `when` matched. If there's no `else` and nothing matched, the result is `Missing`.

```json
{
  "$": true,
  "case": [
    { "when": "$py=_.score >= 90", "then": "A" },
    { "when": "$py=_.score >= 80", "then": "B" },
    { "else": "F" }
  ]
}
```

If neither `case` nor `out` is present, this step is skipped and `_` passes through unchanged.

### `transform`

Names a structural transformation applied to the `case`/`out` result. See `transformation.md` for the available transforms (`flatten`, `merge`, `to_pairs`, `to_object`, `drop_missing`, `concat`) and what each expects/produces. Only runs if the current value isn't `Missing`.

```json
{ "$": true, "foreach": { "in": "$.groups", "out": "$_" }, "transform": "flatten" }
```

---

## Stage 4 — Fallback: `fallback` / `error`

Checked at the very end, and also whenever an earlier stage produces missing/error (short-circuiting the rest of the pipeline):

- `fallback` — used whenever the pipeline's result is `Missing` at any point (a false `check`, an unset `out`, etc.).
- `error` — used whenever the pipeline's result is an error at any point.

```json
{
  "$": true,
  "data": "$.optional_field",
  "out": "$py=_.upper()",
  "fallback": "N/A",
  "error": "invalid"
}
```

Both are plain expressions (not case/out blocks) — evaluated fresh, in the same frame, when needed.

---

## Complete Shape Reference

```json
{
  "$": true,

  "set": { "VAR": "EXPR" },
  "check": "COND",
  "data": "EXPR",

  "foreach": {
    "in": "EXPR",
    "var": "VAR", "key": "VAR",
    "start": "EXPR", "stop": "EXPR", "limit": "EXPR",
    "if": "COND",
    "case": [ { "when": "COND", "then": "EXPR" } ..., { "else": "EXPR" } ],
    "out": "EXPR",
    "update": { "VAR": "EXPR" }
  },

  "case": [ { "when": "COND", "then": "EXPR" }, ..., { "else": "EXPR" } ],
  "out": "EXPR",

  "transform": "merge",

  "fallback": "EXPR",
  "error": "EXPR"
}
```

---

## Worked Examples

### Setup — conditional field with default

**Input**
```json
{ "age": 15 }
```
**Template**
```json
{ "main": { "$": true, "check": "$py=_.age >= 18", "out": true, "fallback": false } }
```
**Output**
```json
{ "main": false }
```

### Foreach with case/out

**Input**
```json
{ "scores": [95, 82, 61] }
```
**Template**
```json
{
  "main": {
    "$": true,
    "foreach": {
      "in": "$.scores",
      "var": "s",
      "case": [
        { "when": "$py=s >= 90", "then": "A" },
        { "when": "$py=s >= 80", "then": "B" },
        { "else": "F" }
      ]
    }
  }
}
```
**Output**
```json
{ "main": ["A", "B", "F"] }
```

### Windowed foreach with running total via `update`

**Input**
```json
{ "orders": [ { "total": 10 }, { "total": 25 }, { "total": 5 }, { "total": 40 } ] }
```
**Template**
```json
{
  "main": {
    "$": true,
    "foreach": {
      "in": "$.orders",
      "var": "o",
      "start": 1, "limit": 2,
      "out": "$o.total",
      "update": { "sum": "$py=(sum or 0) + _" }
    },
    "out": "$sum"
  }
}
```
Windowing starts at position 1 (skips the first order), takes 2 items (`25`, `5`), and `sum` accumulates across those.

**Output**
```json
{ "main": 30 }
```

---

## See Also

- `navigation.md` — `$`, `.foo`, `[...]` path expressions used throughout `check`/`out`/`data`/etc.
- `interpolation.md` — `${...}` string interpolation.
- `variables.md` — full list of built-in variables (`_`, `_input`, `_top`, `_global`, foreach specific vars, ...) and frame/scoping rules.
- `expression-engines.md` — `$py=`, `$pyeval=`, `$pyrun=` and how to choose one.
- `transformation.md` — the transforms usable via `transform`.
- `template.md` — top-level `config` (e.g. `drop_null_attributes`, which affects how `Missing`/`null` values are rendered) and `datasets`.