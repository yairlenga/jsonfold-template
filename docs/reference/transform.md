# Transformations

This page describes the `transform` attribute of a Logic Statement: where it sits in the evaluation pipeline, the built-in transformations, and their input/output shapes and error conditions.

---

## Where `transform` sits in the pipeline

A Logic Statement (`{"$": true, ...}`) evaluates in stages:

1. Setup — `set`, `check`, `data`
2. Iteration — `foreach` (optional)
3. Output — `out` / `case`
4. Transformation — `transform` (optional)
5. Recovery — `fallback`, `error`

`transform` is a **named structural transformation** applied to the value produced by the `out` or `case` stage (which may itself depend on the result of `foreach`).

A Logic Statement may specify **at most one** transformation. To perform multiple structural transformations, simply nest Logic Statements.

```json
{ "$": true, "out": "EXPR", "transform": "merge" }
```

Two things are worth noting:

* **Transforms are skipped for `Missing`.** If no value was produced (for example, because `check` failed or a previous stage returned `Missing`), the transformation is bypassed and processing continues with `fallback`.
* **Transformation errors are recoverable.** If a transformation reports an error (for example, because the input has the wrong shape), the resulting notice continues through the normal pipeline and may still be handled by `error`.

---

# Built-in transformations

The built-in transformations fall into four categories.

| Category            | Transformations                    |
| ------------------- | ---------------------------------- |
| Structural          | `flatten`, `merge`, `drop_missing` |
| Object conversion   | `to_pairs`, `to_object`            |
| Lookup construction | `to_map`                           |
| String construction | `concat`                           |

---

# Transformation reference

## Structural transformations

### `flatten`

**Description:** Concatenates an array of arrays into a single flat array. `null` sub-arrays are treated as empty and skipped.

**Common use case:** collapsing a `foreach` that produced one sub-array per item into a single combined array.

**Input:** an array whose elements are either `null` or arrays.

**Output:** a flat array preserving the original order.

**Errors:**

* `FLATTEN_INPUT` — top-level value is not an array.
* `FLATTEN_ITEM` — an element is neither `null` nor an array.

**Examples**

```json
{ "$": true, "out": "$.groups", "transform": "flatten" }
```

Input:

```json
{"groups": [[1,2],[3],null,[4,5]]}
```

Output:

```json
[1,2,3,4,5]
```

```json
{
  "$": true,
  "foreach": {
    "in": "$.orders",
    "var": "o",
    "out": "$o.items"
  },
  "transform": "flatten"
}
```

---

### `merge`

**Description:** Merges an array of objects into a single object. Keys from later objects overwrite keys from earlier ones. `null` entries are ignored.

**Common use case:** combining partial objects (defaults, overrides, or one object per iteration).

**Input:** an array containing objects or `null`.

**Output:** a single merged object.

**Errors:**

* `MERGE_INPUT`
* `MERGE_ITEM`

**Examples**

```json
{ "$": true, "out": "$.records", "transform": "merge" }
```

Input:

```json
{"records":[{"a":1},{"b":2},{"a":9}]}
```

Output:

```json
{"a":9,"b":2}
```

---

### `drop_missing`

**Description:** Removes entries whose value is the `Missing` sentinel.

**Common use case:** removing optional values generated during `foreach`.

**Input:**

* array
* object
* `null`
* `Missing`

**Output:** same container type with `Missing` entries removed.

**Errors:**

* `DROP_MISSING_INPUT`

**Examples**

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "var": "item",
    "out": "$item.optional"
  },
  "transform": "drop_missing"
}
```

---

# Object conversion

### `to_pairs`

**Description:** Converts an object into an array of `[key, value]` pairs.

**Common use case:** preparing an object for processing by `foreach`, or reshaping a lookup table before reconstructing it with `to_object`.

**Input:** object

**Output:** array of `[key, value]` pairs, preserving iteration order.

**Errors:**

* `TO_PAIRS_INPUT`

**Examples**

```json
{
    "main": {
        "$": true,
        "data": {
            "$": true,
            "data": "$_datasets.country",
            "transform": "to_pairs"
        },
        "foreach": {
            "out": {
                "country": "$_[0]",
                "currency": "$_[1]"
            }
        }
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

### `to_object`

**Description:** Builds an object from explicit key/value entries.

Each entry may be represented as either:

* `[key, value]`
* `{ "key": ..., "value": ... }`

The top-level input may be either:

* an array of entries
* an object whose values are entries

Later entries overwrite earlier ones.

**Common use case:** reconstructing an object after processing the individual entries with `foreach`.

**Input**

| Top-level input | Entry format                   |
| --------------- | ------------------------------ |
| Array           | `[key, value]`                 |
| Array           | `{ "key": ..., "value": ... }` |
| Object          | `[key, value]`                 |
| Object          | `{ "key": ..., "value": ... }` |

**Output:** object

**Errors:**

* `TO_OBJECT_INPUT`
* `TO_OBJECT_ITEM`
* `TO_OBJECT_BAD_KEY`

**Examples**

```json
{
    "$": true,
    "out": "$.pairs",
    "transform": "to_object"
}
```

Input:

```json
{
    "pairs": [
        ["a",1],
        ["b",2]
    ]
}
```

Output:

```json
{
    "a":1,
    "b":2
}
```

---

# Lookup construction

### `to_map`

**Description:** Builds a lookup table by extracting key/value pairs from an existing collection.

Unlike `to_object`, which reconstructs an object from explicit key/value entries, `to_map` is intended for building **transition maps** that allow efficient conversion between identifiers.

**Common use cases**

* ISO code → currency
* Currency → country
* Employee ID → employee record
* Product code → product definition

**Input:** a collection whose values are two-element arrays:

```text
[key, value]
```

**Output:** an object mapping every extracted key to its corresponding value.

If duplicate keys are generated, the last occurrence wins.

**Errors:**

* `TO_MAP_INPUT`
* `TO_MAP_ITEM`

### Example — Building transition maps

```json
{
    "main": {
        "$": {
            "set": {
                "db": {
                    "US": { "code": "USA", "country": "United States", "currency": "USD", "captial": "Washington DC" },
                    "UK": { "code": "GBR", "country": "Great Britian", "currency": "GBP", "captial": "London" },
                    "JP": { "code": "JPN", "country": "Japan", "currency": "JPY", "captial": "Tokyo"}
                },

                "currency_of": {
                    "$": true,
                    "data": "$db",
                    "foreach": {
                        "out": [ "$.code", "$.currency" ]
                    },
                    "transform": "to_map"
                },

                "country_of": {
                    "$": true,
                    "data": "$db",
                    "foreach": {
                        "out": [ "$.currency", "$.country" ]
                    },
                    "transform": "to_map"
                },

                "globus": {
                    "$": true,
                    "data": "$db",
                    "foreach": {
                        "out": [ "$.code", "$" ]
                    },
                    "transform": "to_map"
                }
            }
        },

        "JP currency": "$db.JP.currency",
        "currency of USA": "$currency_of.USA",
        "country of JPY": "$country_of.JPY",
        "Capital of UK": "$globus.GBR.captial"
    }
}
```

The generated transition maps can then be used through ordinary navigation expressions, providing efficient lookups throughout the remainder of the template.

---

# String construction

### `concat`

**Description:** Joins an array of scalar values into a single string.

`null` becomes `"null"`, booleans become `"true"` or `"false"`, and numbers are converted to their string representation.

**Common use case:** building display strings or composite identifiers without requiring an expression engine.

**Input:** array of scalar values.

**Output:** string.

**Errors:**

* `JOIN-STR-TYPE`

**Examples**

```json
{
    "$": true,
    "out": "$.parts",
    "transform": "concat"
}
```

Input:

```json
{
    "parts": [
        "Hello, ",
        "World",
        "!"
    ]
}
```

Output:

```json
"Hello, World!"
```

```json
{
    "$": true,
    "out": [
        "Count: ",
        "$.count",
        " (",
        "$.active",
        ")"
    ],
    "transform": "concat"
}
```

Input:

```json
{
    "count": 3,
    "active": true
}
```

Output:

```json
"Count: 3 (true)"
```
