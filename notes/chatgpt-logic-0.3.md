# Logic Elements

A logic element is a JSON object whose `"$"` member is `true`:

```json
{
  "$": true
}
```

It evaluates in its own local frame. The frame inherits the current input value and variables from its enclosing frame, while variables created by the logic element remain local to that element.

A logic element is processed in this order:

1. `set` — define local variables.
2. `if` — decide whether the element runs.
3. `data` — replace the element's current value.
4. `foreach` — optionally iterate and collect results.
5. `case` / `out` — select the element's final output.
6. `transform` — structurally transform that output.
7. `default` or `error` — handle missing values or evaluation errors.

The current value is available to expressions as `_` and through the navigation expression `$`.

---

## 1. Basic Operation

### Defining variables with `set`

`set` defines local variables before any other processing occurs.

```json
{
  "$": true,
  "set": {
    "first": "$.first_name",
    "last": "$.last_name"
  },
  "out": {
    "display_name": "${first} ${last}"
  }
}
```

Each value in `set` is evaluated once, in declaration order. Later definitions can therefore use variables defined earlier in the same `set` object.

Variables are referenced by name in expression engines and with `$name` in navigation expressions:

```json
{
  "$": true,
  "set": {
    "price": "$.price",
    "quantity": "$.quantity",
    "total": "$=price * quantity"
  },
  "out": "$total"
}
```

`set` does not change the current value. It only adds local variables.

### Conditional execution with `if`

`if` is a guard for the whole logic element.

```json
{
  "$": true,
  "if": "$=_.active",
  "out": {
    "name": "$.name",
    "status": "active"
  }
}
```

When `if` is false, `null`, or missing, the logic element returns a missing value. That missing result may then be handled by `default`.

```json
{
  "$": true,
  "if": "$=_.active",
  "out": "$.name",
  "default": "inactive"
}
```

JFTL conditions treat only `false`, `null`, and missing as false. Other values are true unless the selected expression engine defines its own condition rules.

### Replacing the current value with `data`

`data` evaluates an expression and makes its result the current value for the remaining stages.

```json
{
  "$": true,
  "data": "$.customer",
  "out": {
    "id": "$.id",
    "name": "$.name"
  }
}
```

In this example, the input to the logic element may contain many fields, but after `data`, `$` and `_` refer to the `customer` object.

`data` is evaluated after `set`, so it may use variables defined by `set`:

```json
{
  "$": true,
  "set": {
    "selected": "$.preferred_customer"
  },
  "data": "$selected",
  "out": "$.name"
}
```

### Producing a result with `out`

`out` evaluates the final result expression for the logic element.

```json
{
  "$": true,
  "out": {
    "name": "$.name",
    "age": "$.age"
  }
}
```

When `out` is omitted, the current value is returned unchanged.

```json
{
  "$": true,
  "data": "$.customer"
}
```

This returns the selected customer object.

### Conditional output with `case`

`case` selects the first matching `then` expression. If no case matches, `out` is used as the fallback.

```json
{
  "$": true,
  "case": [
    {
      "when": "$=_.score >= 90",
      "then": "A"
    },
    {
      "when": "$=_.score >= 80",
      "then": "B"
    },
    {
      "when": "$=_.score >= 70",
      "then": "C"
    }
  ],
  "out": "F"
}
```

Cases are tested in order. Only the selected `then` expression is evaluated.

`case` and `out` share one output position:

- `case` provides conditional alternatives.
- `out` provides the fallback when no case matches.
- If neither produces a value, the result is missing.

### Missing and error fallbacks

`default` is evaluated when the logic element produces a missing value:

```json
{
  "$": true,
  "data": "$.optional_value",
  "default": "not available"
}
```

`error` is evaluated when a stage returns a JFTL error notice:

```json
{
  "$": true,
  "data": "$=10 / _.divisor",
  "error": {
    "ok": false,
    "message": "Unable to calculate value"
  }
}
```

`default` and `error` wrap the entire logic pipeline, not only `data` or `out`.

---

## 2. Foreach Basics

A `foreach` block iterates over an array, object, or integer range and collects one output value per accepted item.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "key": "key",
    "index": "index",
    "out": "$item"
  }
}
```

### Selecting the input with `in`

`in` specifies the value to iterate.

```json
{
  "$": true,
  "foreach": {
    "in": "$.orders",
    "value": "order",
    "out": "$order.id"
  }
}
```

When `in` is omitted, `foreach` iterates over the current value.

```json
{
  "$": true,
  "data": "$.orders",
  "foreach": {
    "value": "order",
    "out": "$order.id"
  }
}
```

### Binding the item with `value`

`value` names a variable that receives the current item.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": {
      "id": "$item.id",
      "name": "$item.name"
    }
  }
}
```

When `value` is omitted, the current item becomes the current value. In that form, `$` and `_` refer directly to the item:

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "out": {
      "id": "$.id",
      "name": "$.name"
    }
  }
}
```

Using `value` is useful when the expression also needs access to the existing current value. Omitting it is often shorter when the loop body operates only on the item.

### Binding object keys with `key`

When iterating over an object, `key` receives the current property name.

Input:

```json
{
  "prices": {
    "apple": 3,
    "orange": 4
  }
}
```

Template:

```json
{
  "$": true,
  "foreach": {
    "in": "$.prices",
    "key": "product",
    "value": "price",
    "out": {
      "product": "$product",
      "price": "$price"
    }
  }
}
```

Object iteration preserves the original keys in the collected result. The example therefore produces an object shaped like:

```json
{
  "apple": {
    "product": "apple",
    "price": 3
  },
  "orange": {
    "product": "orange",
    "price": 4
  }
}
```

For array and integer iteration, `key` receives the generated numeric key, although `index` is normally clearer for that purpose.

### Binding the position with `index`

`index` receives the zero-based position in the original iteration sequence.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "index": "position",
    "out": {
      "position": "$position",
      "value": "$item"
    }
  }
}
```

The index is the input position, not the number of emitted results. Items rejected by `if`, skipped by `_skip`, or excluded by `start` and `stop` do not renumber later items.

### Filtering with foreach `if`

A foreach-local `if` controls whether the current item is emitted.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "if": "$=item.enabled",
    "out": "$item"
  }
}
```

The condition is evaluated after the loop variables have been assigned and before the per-item `case` or `out` is evaluated.

### Per-item `out`

The `out` inside `foreach` determines the value collected for each item.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": "$=item.price * item.quantity"
  }
}
```

For arrays and ranges, outputs are appended to an array. For objects, each output is stored under the corresponding input key.

If foreach `out` is omitted, the original item is collected.

### Per-item `case`

`case` inside `foreach` selects the output for each item. The foreach `out` is the fallback.

```json
{
  "$": true,
  "foreach": {
    "in": "$.values",
    "value": "value",
    "case": [
      {
        "when": "$=value < 0",
        "then": "negative"
      },
      {
        "when": "$=value == 0",
        "then": "zero"
      }
    ],
    "out": "positive"
  }
}
```

The first matching case wins.

### Skipping individual outputs

An output equal to the built-in `_skip` sentinel is not collected.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": "$=_skip if item.deleted else item"
  }
}
```

For ordinary filtering, foreach `if` is clearer. `_skip` is useful when the decision naturally belongs in a `case`, expression, or nested template.

---

## 3. Foreach Core

### Iterating over arrays

For an array, foreach processes each element in order and returns an array.

Input:

```json
[10, 20, 30]
```

Template:

```json
{
  "$": true,
  "foreach": {
    "value": "n",
    "index": "i",
    "out": "$=n + i"
  }
}
```

Result:

```json
[10, 21, 32]
```

### Iterating over objects

For an object, foreach processes properties in object iteration order and returns an object using the original keys.

Input:

```json
{
  "a": 2,
  "b": 4
}
```

Template:

```json
{
  "$": true,
  "foreach": {
    "key": "name",
    "value": "number",
    "out": "$=number * 10"
  }
}
```

Result:

```json
{
  "a": 20,
  "b": 40
}
```

The current implementation does not let foreach `out` replace the dictionary key directly. To construct new keys, emit key/value pairs and apply `from_pairs`, or emit one-property objects and apply `merge`.

### Iterating over integer ranges

When `in` evaluates to an integer `N`, foreach iterates over the values produced by:

```python
range(start, N)
```

The default `start` is `0`.

```json
{
  "$": true,
  "foreach": {
    "in": 5,
    "value": "n",
    "out": "$n"
  }
}
```

Result:

```json
[0, 1, 2, 3, 4]
```

With an explicit start:

```json
{
  "$": true,
  "foreach": {
    "in": 8,
    "start": 3,
    "value": "n",
    "out": "$n"
  }
}
```

Result:

```json
[3, 4, 5, 6, 7]
```

An integer foreach is therefore a compact range generator. The integer supplied by `in` is the exclusive upper bound, not the number of requested outputs when `start` is nonzero.

### `start`

`start` gives the zero-based input position at which iteration begins.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "start": 2,
    "out": "$"
  }
}
```

This skips input positions `0` and `1`.

Negative `start` values count backward from the end when the input size is known:

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "start": -2,
    "out": "$"
  }
}
```

This selects the final two input positions.

### `stop`

`stop` is an exclusive input-position boundary.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "start": 1,
    "stop": 4,
    "out": "$"
  }
}
```

This considers positions `1`, `2`, and `3`.

Negative `stop` values count backward from the end:

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "stop": -1,
    "out": "$"
  }
}
```

This excludes the final input item.

`start` and `stop` are based on the original input positions. Filtering does not change their meaning.

### `limit`

`limit` restricts the number of emitted results.

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "if": "$=item.enabled",
    "limit": 3,
    "out": "$item"
  }
}
```

This returns at most three enabled items.

Unlike `stop`, `limit` counts accepted outputs rather than visited inputs:

- `start` and `stop` select input positions.
- foreach `if` may reject selected inputs.
- `_skip` may suppress an output.
- `limit` counts only values that are actually collected.

A `limit` of `0` returns an empty array or object without evaluating any item body.

### Combining `start`, `stop`, and `limit`

```json
{
  "$": true,
  "foreach": {
    "in": "$.events",
    "start": 10,
    "stop": 100,
    "limit": 5,
    "value": "event",
    "if": "$=event.severity == 'ERROR'",
    "out": "$event"
  }
}
```

This scans input positions `10` through `99` and returns the first five matching errors.

---

## 4. Foreach: Advanced Reduction

`foreach` normally returns the collection of per-item outputs. It can also update local accumulator variables after each emitted item.

Reduction uses three parts:

1. `set` initializes accumulator variables.
2. top-level `update` changes them after every accepted foreach output.
3. the outer `out` returns the accumulated result instead of the collected foreach array or object.

> **Syntax note:** In the current implementation, `update` is a member of the logic element, alongside `foreach`, not a member inside the `foreach` object.

### Summing values

```json
{
  "$": true,
  "set": {
    "total": 0
  },
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": "$=item.price * item.quantity"
  },
  "update": {
    "total": "$=total + _"
  },
  "out": "$total"
}
```

During each iteration:

1. foreach `out` is evaluated.
2. Its result becomes the current value `_`.
3. The result is added to the foreach collection.
4. `update` expressions run and may read `_` and existing accumulator variables.

The outer `out` runs only after foreach completes. It sees the completed accumulator variables and the collected foreach result as the current value.

### Counting accepted items

```json
{
  "$": true,
  "set": {
    "count": 0
  },
  "foreach": {
    "in": "$.items",
    "value": "item",
    "if": "$=item.enabled",
    "out": "$item"
  },
  "update": {
    "count": "$=count + 1"
  },
  "out": "$count"
}
```

`update` runs only for items that pass foreach `if` and are not skipped. It therefore naturally counts emitted results.

### Multiple accumulators

```json
{
  "$": true,
  "set": {
    "count": 0,
    "total": 0
  },
  "foreach": {
    "in": "$.values",
    "value": "value",
    "out": "$value"
  },
  "update": {
    "count": "$=count + 1",
    "total": "$=total + _"
  },
  "out": {
    "count": "$count",
    "total": "$total",
    "average": "$=total / count if count else None"
  }
}
```

Updates are evaluated in declaration order. A later update can use the value assigned by an earlier update in the same iteration.

### Building an aggregate object

```json
{
  "$": true,
  "set": {
    "summary": {}
  },
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": {
      "name": "$item.name",
      "amount": "$item.amount"
    }
  },
  "update": {
    "summary": "$={**summary, _.name: _.amount}"
  },
  "out": "$summary"
}
```

This example depends on an expression engine that supports dictionary construction and unpacking. The same reduction structure can be used with any registered expression engine.

### Returning both collected and reduced results

After foreach, `_` is the complete foreach collection. Accumulators remain available as variables. The outer `out` can therefore return both:

```json
{
  "$": true,
  "set": {
    "total": 0
  },
  "foreach": {
    "in": "$.values",
    "value": "value",
    "out": "$value"
  },
  "update": {
    "total": "$=total + _"
  },
  "out": {
    "values": "$",
    "total": "$total"
  }
}
```

Inside `update`, `_` means the current item's emitted output. In the outer `out`, `$` and `_` mean the complete foreach result.

### Reduction order and skipped values

For each selected input item, processing occurs in this order:

1. Assign `key`, `value`, and `index` variables.
2. Evaluate foreach `if`.
3. Evaluate foreach `case` / `out`.
4. Make that output the current value.
5. Ignore it if it equals `_skip`.
6. Add it to the foreach result.
7. Evaluate `update` assignments.
8. Count it toward `limit`.

Consequences:

- Rejected or skipped items do not update accumulators.
- `update` can use the transformed per-item output through `_`.
- `limit` stops after the requested number of updates and collected outputs.
- The outer `out` can discard, summarize, or combine the collected foreach result.

---

## 5. Transform

`transform` applies a named structural transformation after the outer `case` / `out` stage.

```json
{
  "$": true,
  "foreach": {
    "in": "$.groups",
    "value": "group",
    "out": "$group.items"
  },
  "transform": "flatten"
}
```

A transform receives one completed value. It does not evaluate expressions and does not receive loop variables directly.

Transforms run after the outer `out`. This makes it possible to reshape either the direct foreach result or a value created by the outer output stage.

### `flatten`

Converts an array of arrays into one array.

```json
{
  "$": true,
  "data": [
    [1, 2],
    [3, 4]
  ],
  "transform": "flatten"
}
```

Result:

```json
[1, 2, 3, 4]
```

`null` subarrays are ignored. Every other element must be an array.

Typical foreach use:

```json
{
  "$": true,
  "foreach": {
    "in": "$.departments",
    "value": "department",
    "out": "$department.employees"
  },
  "transform": "flatten"
}
```

### `merge`

Converts an array of objects into one object. Later objects overwrite earlier values for duplicate keys.

```json
{
  "$": true,
  "data": [
    {"a": 1, "b": 2},
    {"b": 20, "c": 30}
  ],
  "transform": "merge"
}
```

Result:

```json
{
  "a": 1,
  "b": 20,
  "c": 30
}
```

`null` entries are ignored. Every other item must be an object.

`merge` can create an object with computed keys from foreach output:

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": "$={item.name: item.value}"
  },
  "transform": "merge"
}
```

### `to_pairs`

Converts an object into an array of `[key, value]` pairs.

```json
{
  "$": true,
  "data": {
    "a": 1,
    "b": 2
  },
  "transform": "to_pairs"
}
```

Result:

```json
[
  ["a", 1],
  ["b", 2]
]
```

The input must be an object.

### `from_pairs`

Converts an array of `[key, value]` pairs into an object.

```json
{
  "$": true,
  "data": [
    ["a", 1],
    ["b", 2]
  ],
  "transform": "from_pairs"
}
```

Result:

```json
{
  "a": 1,
  "b": 2
}
```

Each retained key must be a string. Pairs whose value is missing are omitted. Empty placeholder pairs such as `[null, null]` or `[false, null]` are also ignored.

This transform is useful when foreach must compute output keys:

```json
{
  "$": true,
  "foreach": {
    "in": "$.items",
    "value": "item",
    "out": [
      "$item.name",
      "$item.value"
    ]
  },
  "transform": "from_pairs"
}
```

### `drop_missing`

Removes direct missing members from an array or object.

```json
{
  "$": true,
  "out": {
    "name": "$.name",
    "email": "$.email",
    "phone": "$.phone"
  },
  "transform": "drop_missing"
}
```

For objects, properties whose values are missing are removed. For arrays, missing elements are removed. The transform is shallow: it does not recursively remove missing values from nested containers.

A missing or `null` input is converted to `null`.

### `concat`

Converts an array of scalar values into one string with no separator.

```json
{
  "$": true,
  "data": ["A", 10, true, null],
  "transform": "concat"
}
```

The result is the concatenation of the scalar string representations. `null` becomes the text `null`.

For formatted strings, interpolation is usually clearer. `concat` is useful when a preceding foreach or output stage naturally produces an array of fragments.

```json
{
  "$": true,
  "foreach": {
    "in": "$.parts",
    "value": "part",
    "out": "$part"
  },
  "transform": "concat"
}
```

### Transform errors

A transform returns an error when its input has the wrong shape. The logic element's `error` member can handle that error:

```json
{
  "$": true,
  "data": "$.possibly_nested",
  "transform": "flatten",
  "error": []
}
```

Transforms are not applied to a missing result. A missing result proceeds directly to `default` handling.

---

## Complete Shape

The complete implemented structure is:

```json
{
  "$": true,

  "set": {
    "variable": "expression"
  },
  "if": "condition",
  "data": "expression",

  "foreach": {
    "in": "expression",
    "value": "item_variable",
    "key": "key_variable",
    "index": "index_variable",
    "start": "expression",
    "stop": "expression",
    "limit": "expression",
    "if": "condition",
    "case": [
      {
        "when": "condition",
        "then": "expression"
      }
    ],
    "out": "expression"
  },

  "update": {
    "accumulator": "expression"
  },

  "case": [
    {
      "when": "condition",
      "then": "expression"
    }
  ],
  "out": "expression",

  "transform": "flatten | merge | to_pairs | from_pairs | drop_missing | concat",

  "default": "expression",
  "error": "expression"
}
```

All members are optional except `"$": true`. Their meaning depends on the stage in which they appear: foreach `if`, `case`, and `out` operate once per iteration, while the outer `case` and `out` operate once after foreach completes.
