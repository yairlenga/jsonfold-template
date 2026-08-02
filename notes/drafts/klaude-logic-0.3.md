# The Logic Element

A **logic element** is any object node in a JFTL template that carries `"$": true`:

```json
{ "$": true, ... }
```

When the compiler sees `"$": true` it hands the whole object to the logic
compiler, which reads a fixed set of keys off it and builds a single
`LogicStatement`. (Writing `"$": false` instead means "treat this object as a
literal value, do not compile it as logic" — everything below only applies to
`"$": true` nodes.)

At render time a logic element always runs in its **own child frame** (a
fresh `"logic"` scope, child of whatever frame contains it). It evaluates in
a fixed pipeline of stages, always in this order:

1. **Init** — `set`, `if`
2. **Data** — `data`
3. **Foreach** — `foreach` (+ sibling `update`)
4. **Select** — `case` / `out`
5. **Transform** — `transform`
6. **Fallback** — `default`, `error`

Each stage can hand back early (skipping the rest) via **Missing** (`null`/
absent) or an **error notice**; stage 6's `default`/`error` are the only
things that can recover from that. The sections below walk through the
pipeline from simplest to most advanced usage.

---

## 1. Basic operation: `set`, `if`, `data`, `out`, `case`

### `set` — local variables

```json
{ "$": true, "set": { "tax": "$rate", "total": "$price" }, "out": "..." }
```

`set` is a dictionary of `NAME: EXPR`. Each expression is evaluated (in
declaration order) and bound as a variable (`$tax`, `$total`, ...) in the
logic element's frame. These variables are visible to every later stage of
the *same* logic element, and to any nested logic elements underneath it
(ordinary variable-scoping rules apply — inner frames can see outer `set`
variables).

The first logic element in a chain that declares `set` also stashes a
reference to its own frame as `_global`, reachable from anywhere below it.

### `if` — guard condition

```json
{ "$": true, "if": "$active", "out": "$name" }
```

`if` is evaluated as a boolean (JFTL truthiness: `false`/`null`/missing are
falsy, everything else truthy). Defaults to `true` when omitted.

- If `if` evaluates to an error notice, the whole logic element resolves to
  that error (subject to `error`, see §1.4).
- If `if` evaluates to `false`, the whole logic element resolves to
  **Missing** (subject to `default`, see §1.4) — none of the later stages
  (`data`, `foreach`, `out`, `transform`) run at all.

### `data` — rebind the current value

```json
{ "$": true, "data": "$user.address", "out": "$_.city" }
```

`data` re-evaluates and replaces "current" (`_`) and the data root (`$`) for
everything below it in this logic element (and any nested elements). It's
how you "step into" a sub-object before running further logic on it. If
omitted, `_`/`$` stay whatever they were coming into the logic element.

### `out` / `case` — the result (Select stage)

```json
{ "$": true, "data": "$user", "out": "$_.name" }
```

```json
{
  "$": true,
  "case": [
    { "when": "$_.age >= 18", "then": "adult" },
    { "when": "$_.age >= 13", "then": "teen" }
  ],
  "out": "child"
}
```

`out` is a plain expression: the result of the logic element (after `set`/
`if`/`data`, and after `foreach` if present — see §2).

`case` is a list of `{ "when": COND, "then": EXPR }` pairs, checked in
order; the first `when` that's true wins and its `then` is the result.
`out` doubles as the **default/fallback** result if no case matches (or if
`case` is absent/empty). If neither `out` nor `case` is given, the logic
element simply passes through whatever `data`/`foreach` produced (or the
incoming `_`, if neither was used).

If a `when` condition itself errors, evaluation stops immediately with that
error — later cases are not tried.

### `default` / `error` — fallback stage

```json
{ "$": true, "data": "$user.nickname", "default": "'(none)'" }
```

```json
{ "$": true, "data": "$1/0", "error": "'could not compute'" }
```

- `default` is evaluated (and substituts the result) whenever the logic
  element would otherwise resolve to **Missing** (a failed `if`, a `data`/
  `out`/`transform` expression that came back missing/null, etc.).
- `error` is evaluated (and substitutes the result) whenever the logic
  element would otherwise resolve to an **error notice**.
- Both are checked at every internal exit point, not just at the very end,
  and in that order — so if `default` itself produces an error, `error` can
  still catch it. If `default`/`error` are omitted, Missing/errors simply
  propagate outward as-is.

---

## 2. Foreach basics: `value`, `key`, `index`, `in`, `out`, `case`

`foreach` (a sub-object under the logic element) iterates over a
collection, producing a new collection — one entry per surviving item —
which becomes the logic element's "current" value for the Select stage (§1)
that follows it.

```json
{
  "$": true,
  "foreach": {
    "in": "$items",
    "value": "item",
    "out": "$item.name"
  }
}
```

- **`in`** — the collection to iterate. If omitted, iterates over the
  current value (`_`) coming into the logic element.
- **`value`** — variable name bound to each element's value. If omitted,
  the element itself is set as "current" (`_`) instead, so you can write
  `"out": "$_.name"` without declaring a `value` var.
- **`key`** — variable name bound to each element's key: for a list this is
  the item's numeric index (its position in the *original* collection,
  before any `start`/`stop` trimming); for a dict this is the string key.
- **`index`** — variable name bound to the item's 0-based position *within
  the loop's output* (i.e. counting only items that survive `start`/`stop`
  trimming and the loop's own `if`, in emission order). This is distinct
  from `key` on a list, where `key` is the item's original index.
- **`out`** / **`case`** — same mechanics as the top-level Select (§1.4):
  transform each surviving item before it's added to the output collection.
  If omitted, the item's own value is emitted unchanged. If an `out`/`case`
  expression for an item returns the special "skip" sentinel, that item is
  dropped from the output entirely; if it errors, the whole `foreach`
  aborts with that error.
- A per-item **`if`** (inside `foreach`, defaults to `true`) can also be
  given: items for which it's false are skipped (not added to the output,
  not counted for `limit`). If it errors, the whole `foreach` aborts.

Iterating a **list** produces a list; iterating a **dict** produces a dict
(keyed the same way, unless you reshape with `transform` afterward — §5).

If the whole `foreach` step itself yields Missing, an error, or `None`, the
logic element short-circuits there (same `default`/`error` fallback rules
as §1.4 apply).

---

## 3. Foreach core: dicts, ranges, `start`/`stop`/`limit`

### Iterating a dict

```json
{
  "foreach": {
    "in": "$config",
    "key": "k", "value": "v",
    "out": "${k}=${v}"
  }
}
```

Iterating a dict binds `key` to each string key and `value` to each value,
and (unless reshaped by `transform`) produces a **dict** result with the
same keys, mapped to each item's `out` value.

### Iterating a number (range mode)

```json
{
  "foreach": {
    "in": 5,
    "value": "n",
    "out": "$n"
  }
}
```

If `in` evaluates to a plain integer `N` (rather than a list or dict), the
loop instead iterates the range of integers, honoring `start` as the range's
starting point. `value` is bound to the actual integer for each iteration;
`key`/`index` are bound to the iteration's position within that generated
range, not the integer itself.

### `start` / `stop` / `limit`

```json
{
  "foreach": {
    "in": "$items",
    "start": 1,
    "stop": -1,
    "out": "$_"
  }
}
```

- **`start`** (default `0`) — first index to include. Negative values count
  from the end of the collection (`count + start`).
- **`stop`** (default: end of collection) — index to stop *before*.
  Negative values count from the end the same way as `start`.
- **`limit`** — caps the number of items *emitted* (after `if`/skip
  filtering) — once `limit` items have been produced, no further items are
  emitted, regardless of how much of the collection remains.

`start`/`stop`/`limit` must evaluate to integers (or `null`/absent); a
non-integer value is a compile-safe runtime error. `start`/`stop` are
applied to the item's *original* position in the collection (its `key`, for
lists), before the per-item `if`.

---

## 4. Foreach advanced: reduction with `update` and outer `out`

`foreach` can do more than map-and-collect — it can also **accumulate** a
value across iterations, which the *enclosing* logic element's own `out`/
`case` (Stage 4, §1.4) can then return instead of the mapped collection.
This is the reduce/aggregate pattern.

```json
{
  "$": true,
  "set": { "total": 0 },
  "foreach": {
    "in": "$items",
    "value": "item"
  },
  "update": {
    "total": "$total + $item.price"
  },
  "out": "$total"
}
```

Important: **`update` is a sibling key of `foreach`**, not something
written inside the `foreach` object — it lives at the same level as `set`,
`data`, `out`, and `case` on the logic element.

- `update` is a dict of `NAME: EXPR`, just like `set`. After each surviving
  item is produced (and after its own `foreach.out`/`case`, if any), every
  `update` expression is evaluated and (re-)assigned into the *logic
  element's own frame* — the same frame used across all iterations. That's
  what makes it an accumulator: a variable set by `update` on iteration 1 is
  still there (with its updated value) on iteration 2, and so on.
- Because `update` variables live in the same frame as `set` and the outer
  `out`, the final `out`/`case` (Stage 4) — which runs *after* the entire
  `foreach` has finished — can read the accumulated variable(s) directly
  (`"out": "$total"` above) instead of returning the mapped array/dict that
  `foreach` collected.
- The mapped collection that `foreach` itself produces is still built
  normally (per §2/§3) and still becomes "current" going into Stage 4 — you
  simply choose, via `out`/`case`, whether to return that collection, the
  accumulator, or some combination (e.g. `{ "items": "$_", "total": "$total" }`).

This combination — seed accumulator(s) with `set`, update them with
`update` on every iteration, and read them back in the enclosing `out` — is
the standard way to implement sums, counts, string-joins, "first match",
running max/min, or any other reduction over a collection.

---

## 5. Transform

`transform` (Stage 5) is a **named, structural reshape** applied to
whatever Stage 4 (`out`/`case`, or the `foreach`/`data` result if Stage 4
was skipped) produced. It only runs if the current value isn't Missing, and
if it fails (wrong input shape) it produces an error, subject to the usual
`default`/`error` fallback.

```json
{
  "$": true,
  "foreach": { "in": "$groups", "value": "g", "out": "$g.members" },
  "transform": "flatten"
}
```

Available transforms:

| Name           | Input           | Output          | Behavior |
|----------------|-----------------|-----------------|----------|
| `flatten`      | list of lists   | list            | Concatenates all sub-lists into one flat list. `null` entries are skipped; a non-list entry (other than `null`) is an error. |
| `merge`        | list of dicts   | dict            | Merges all dicts into one; later entries win on key collisions. `null` entries are skipped; a non-dict entry is an error. |
| `to_pairs`     | dict            | list of `[k, v]`| Converts a dict into a list of two-element `[key, value]` pairs. |
| `from_pairs`   | list of `[k, v]`| dict            | Converts a list of `[key, value]` pairs back into a dict. A pair is silently dropped if its value is Missing, or if its value is `null`/`false` and its key is falsy. Any non-string key is an error. |
| `drop_missing` | dict or list    | same shape      | Removes Missing entries (dict values or list items). `null`/Missing input passes through as `null`. |
| `concat`       | list of scalars | string          | Joins all items into a single string; `null` becomes the literal text `null`; booleans/numbers are stringified. A non-scalar item is an error. |

`transform` is most often paired with `foreach` (map with `out`, then
reshape the whole collection in one step), but it can just as well be
applied to a plain `data` value or nested logic result — anything that
reaches Stage 5 in the right shape for the chosen transform.