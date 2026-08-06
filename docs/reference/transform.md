# Transformations

This page describes the `transform` attribute of a Logic Statement: where
it sits in the evaluation pipeline, the built-in transformers, and their
input/output shapes and error conditions.

---

## Where `transform` sits in the pipeline

A Logic Statement (`{"$": true, ...}`) evaluates in stages:

1. Setup — set, if, data
2. Iterations: foreach (optional)
3. Output: out/case, transform
4. Fallback: default, error

`transform` is a **named, structural reshape** applied to whatever produced by 
(`case`/`out` (potentially relying on the output of `foreach` stage). Up to one
transformation can be performed in single Logic statement. Multiple transformation
can be applied by nesting Logic Statements if you need more than one).

Two things worth knowing about when it runs:

- **It's skipped if the value is `Missing`.** `transform` only runs when
  something was generated — so a failed `check`, an empty `foreach` short-circuit,
  etc., bypass `transform` entirely and fall straight through to `fallback`.
- **A transform's own errors are still recoverable via `error`.** If the
  transformer itself returns an error notice (wrong input shape, bad item
  type, ...), that flows into Stage 6 exactly like any other mid-pipeline
  error — `error` can still catch it and supply a fallback value.

```json
{ "$": true, "out": "EXPR", "transform": "merge" }
```

---

## Built-in transformers, at a glance

| Name           | Input | Output | Description |
|----------------|-------|--------|-------------|
| `flatten`      | Array of Arrays | Array | concatenate multiple arrays  |
| `merge`        | Array of objects | Object | concatenate multiple objects |
| `to_pairs`     | Object | Array of Pairs | Split objects into array of `[key, value]` pairs |
| `drop_missing` | Array or object | Same | Remove entries with `Missing` |
| `concat`       | Array of scalars | String | concatenate stringified elements |
| `to_object`    | Arrays of entries | Object | Create from individual entries, each can be  `[ key, value ]` or `{ "key": ..., "value": ... }`|

---

## Built-in transformation details:

### `flatten`

**Description:** Concatenates a array of arrays into one flat array, in
order. `null` sub-arrays are treated as empty and skipped (not an error).

**Common use case:** collapsing a `foreach` that produced one sub-array per
item (e.g. "for each order, its line items") into a single combined array.

**Input:** a array where every item is either `null` or itself a array
(nested objects/objects are *not* flattened — only the outer level).
**Output:** a flat array — concatenation of every non-null sub-array, in
order.
**Errors:** `FLATTEN_INPUT` if the top-level value isn't a array;
`FLATTEN_ITEM` if a non-null item isn't a array either.

**Examples**

```json
{ "$": true, "out": "$.groups", "transform": "flatten" }
```
Input: `{"groups": [[1, 2], [3], null, [4, 5]]}`
Output: `[1, 2, 3, 4, 5]`

```json
{
  "$": true,
  "foreach": { "in": "$.orders", "var": "o", "out": "$o.items" },
  "transform": "flatten"
}
```
Input: `{"orders": [{"items": ["a", "b"]}, {"items": ["c"]}]}`
Output: `["a", "b", "c"]`

---

### `merge`

**Description:** Merges a array of objects into a single object. Keys from
later entries overwrite keys from earlier ones — same rule as Python's
`{**a, **b}`. `null` entries are ignored.

**Common use case:** combining several partial/optional objects (e.g.
defaults + overrides, or one object per `foreach` item) into one flat
result.

**Input:** a array where every item is either `null` or a object.
**Output:** a single object.
**Errors:** `MERGE_INPUT` if the top-level value isn't a array;
`MERGE_ITEM` if a non-null item isn't a object.

**Examples**

```json
{ "$": true, "out": "$.records", "transform": "merge" }
```
Input: `{"records": [{"a": 1}, {"b": 2}, {"a": 9}]}`
Output: `{"a": 9, "b": 2}` — the second `a` wins.

```json
{
  "$": true,
  "out": [{ "theme": "dark" }, "$.user_overrides"],
  "transform": "merge"
}
```
Input: `{"user_overrides": {"theme": "light", "lang": "en"}}`
Output: `{"theme": "light", "lang": "en"}` — defaults, then overrides layered on top.

---

### `to_pairs`

**Description:** Converts an object into a array of `[key, value]` pairs,
in the object's iteration order.

**Common use case:** turning a object into something a `foreach` can walk
positionally, or preparing data for `to_object` round-tripping after some
array-oriented reshaping in between.

**Input:** a object.
**Output:** a array of two-element `[key, value]` arrays.
**Errors:** `TO_PAIRS_INPUT` if the value isn't a object.

**Examples**

```json
{ "$": true, "out": "$.settings", "transform": "to_pairs" }
```
Input: `{"settings": {"x": 1, "y": 2}}`
Output: `[["x", 1], ["y", 2]]`

```json
{ "$": true, "out": "$.headers", "transform": "to_pairs" }
```
Input: `{"headers": {"Content-Type": "application/json"}}`
Output: `[["Content-Type", "application/json"]]`

The `to_pairs` is usually used on objects that represent lookup table. The following will reshape a map of countries (e.g., `"country": "US Dollar"`), to array of entries { e.g. `{ "country": "USA", "currency": "US Dollar" }`).
```json
{
    "main": {
        "$": true,
        "data": { "$": true, "data": "$_datasets.country", "transform": "to_pairs" },
        "foreach": { "out": { "country": "$_[0]", "currency": "$_[1]" } }
    },

    "datasets": {
        "country": {
            "USA": "US Dollar",
            "GBR": "British Pound",
            "JPY": "Japanese Yen"
        }
    }
}
```
Output:
```json
[
  {
    "country": "USA",
    "currency": "US Dollar"
  },
  {
    "country": "GBR",
    "currency": "British Pound"
  },
  {
    "country": "JPY",
    "currency": "Japanese Yen"
  }
]
```
---

### `drop_missing`

**Description:** Removes any entry whose *value* is the `Missing`
sentinel, keeping the container's shape (array stays a array, object stays a
object). If the input itself is `null`/`Missing`, the result is `null`.

**Common use case:** cleaning up a `foreach` result where some per-item
`out` expressions legitimately produced `Missing` (e.g. an optional field
that isn't present on every item) and you want those entries dropped
rather than left as holes.

**Input:** a array, a object, or `null`/`Missing`.
**Output:** same container type with `Missing`-valued entries removed
(array values are removed outright; object keys whose value is `Missing` are
removed); `null` in, `null` out.
**Errors:** `DROP_MISSING_INPUT` for any other input type.

**Examples**

```json
{
  "$": true,
  "foreach": { "in": "$.items", "var": "item", "out": "$item.optional" },
  "transform": "drop_missing"
}
```
Input: `{"items": [{"optional": "a"}, {"other": 1}, {"optional": "c"}]}`
(the second item has no `optional` field, so its per-item `out` is `Missing`)
Output: `["a", "c"]`

```json
{ "$": true, "out": "$.profile", "transform": "drop_missing" }
```
Input: a `profile` object where a nested lookup for `nickname` came back
`Missing` alongside present `name`/`email` fields.
Output: the same object with the `nickname` key removed entirely.

---

### `concat`

**Description:** Joins a array of scalar values into a single string, in
order, with no separator. `null` becomes the literal string `"null"`,
booleans become `"true"`/`"false"`, numbers are stringified.

**Common use case:** building a display string or composite key out of
several `foreach`-collected pieces, without reaching for a `$py=`
expression just to call `"".join(...)`.

**Input:** a array whose items are each `null`, `bool`, `int`, `float`, or
`str`.
**Output:** a single string.
**Errors:** `JOIN-STR-TYPE` if any item is a array/object (or otherwise not
one of the scalar types above).

**Examples**

```json
{ "$": true, "out": "$.parts", "transform": "concat" }
```
Input: `{"parts": ["Hello, ", "World", "!"]}`
Output: `"Hello, World!"`

```json
{ "$": true, "out": ["Count: ", "$.count", " (", "$.active", ")"], "transform": "concat" }
```
Input: `{"count": 3, "active": true}`
Output: `"Count: 3 (true)"`

---

### `to_object`

**Description:** Builds an object out of a collection of key/value
entries. Each entry may be a `[key, value]` two-element array, or a
`{"key": ..., "value": ...}` object with exactly those two attributes.
The input collection itself may be a array of such entries, or a object of
such entries (only the object's *values* are used as entries — its own keys
are discarded). `null`/`Missing` entries are skipped; later entries win on
key collision, matching `merge`.

**Common use case:** the inverse of `to_pairs` — reassembling a
`[key, value]` array (possibly reshaped by a `foreach`/`case` step in
between) back into a plain object.

**Input:** a array of entries, or a object whose values are entries. Each
entry: `[key, value]` (length 2) or `{"key": K, "value": V}`.
**Output:** a object. Non-string keys are dropped silently if their value is
`null`/`Missing`; otherwise a non-string key is an error.
**Errors:** `TO_OBJECT_INPUT` if the top-level value is neither array nor
object; `TO_OBJECT_ITEM` if an entry isn't a valid pair/`{key,value}` shape;
`TO_MAP_BAD_KEY` if an entry's key isn't a string (and its value isn't
`null`/`Missing`, in which case it's silently dropped instead).

**Examples**

```json
{ "$": true, "out": "$.pairs", "transform": "from_pairs" }
```
Input: `{"pairs": [["a", 1], ["b", 2]]}`
Output: `{"a": 1, "b": 2}`

```json
{ "$": true, "out": "$.entries", "transform": "from_kv" }
```
Input: `{"entries": [{"key": "a", "value": 1}, {"key": "b", "value": 2}]}`
Output: `{"a": 1, "b": 2}`

