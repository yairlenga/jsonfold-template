# `variables.md` — Built-in Variables Reference

## Introduction

JFTL provides a set of built-in variables and sentinel values available during template evaluation, organized into four categories based on scope — what determines when each value changes.

* **Constant** — fixed for the life of the process; language-level sentinel values, identical across every template and every render.
* **Template** — established once per render operation; constant within a single render, but different from one render to the next.
* **Scoped** — updated when execution enters a new logic element.
* **Foreach** — updated on every `foreach` iteration.

The table below groups every built-in by category; each is covered in detail in the sections that follow, in the same order.

| Variable    | Category | Type      | Description                                                                                                                                          |
| ----------- | -------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `_missing`  | Constant | sentinel  | Represents the absence of a value.                                                                                                                  |
| `_skip`     | Constant | sentinel  | Omits the current generated item and continues processing.                                                                                          |
| `_break`    | Constant | sentinel  | Terminates the current `foreach` iteration.                                                                                                         |
| `_error`    | Constant | sentinel  | Represents a processing error.                                                                                                                      |
| `_input`    | Template | json      | Complete input document supplied to the render operation.                                                                                           |
| `_datasets` | Template | namespace | Namespace containing all datasets available during rendering.                                                                                       |
| `_external` | Template | namespace | External variables supplied by the rendering environment.                                                                                           |
| `_top`      | Template | context   | Runtime context of the top-level logic element.                                                                                                     |
| `_data` | Scoped | json | Value most recently assigned by a data statement in the current logic element. || `_level`    | Scoped   | int       | Nesting level of the current logic element.                                                                                                         |
| `_local`    | Scoped   | namespace | Variables declared in the current logic-element scope.                                                                                              |
| `_global`   | Scoped   | namespace | Variables declared in the top-level logic-element scope.                                                                                            |
| `_parent`   | Scoped   | context   | Runtime context of the enclosing logic element.                                                                                                     |
| `_`         | Foreach  | json      | Current data. During `foreach`, contains the current source item. During `foreach.update`, contains the generated output for the current iteration. |
| `_key`      | Foreach  | json      | Current array index, object key, or range value.                                                                                                    |

---

## Constant Values

Constant values are immutable singletons used by JFTL to control evaluation. They are not ordinary JSON values, and they are identical across every template and every render — fixed for the life of the process.

### `_missing`

Represents the absence of a value.

Unlike JSON `null`, `_missing` indicates that no value existed or no value was produced. In the final template result they get converted to null, but until that point, they remain distinct, making it possible to distinguish between the `null` value no-value present. They are similar to the JavaScript `undefined`. The `_missing` value is treated as false in conditions (similar to `null`),

#### Examples
In the following example, both "missing" and "nonexisting" will show "Nothing" is the output. Both the $nonexisting expression, and the explicit `_missing` variable resolve to the missing value, which is converted to the string "Nothing" by the `fallback` clause. Without the `fallback` clause, they `_missing` value will be converted to `null` in the final output.

```json
// Template
{
    "main": {
        "$": true,
        "data": { "foo": "bar", "null": null, "missing": "$_missing", "nonexisting": "$nonexisting" },
        "foreach": { "out": { "$": true, "fallback": "Nothing" }}
    }
}
// Output
{
  "foo": "bar",
  "null": null,
  "missing": "Nothing",
  "nonexisting": "Nothing"
}
```

#### Common sources include:

* navigation to a nonexistent object member;
* an array index outside the array bounds;
* lookup of an undefined variable;
* navigation through a `null` or `missing` value;
* Failed `check` condition, which are used to guard complete statement;
* a `case` with no matching branch and no `else`;
* a `for` statement that iterate thru a `null` or `_missing` container;
* an explicit `$_missing`.

`Missing` is treated as false in JFTL conditions.

A logic element may replace `Missing` using `fallback`.

---

### `_skip`

Omits the current generated item.

When returned from a `foreach` item's `out` or `case` expression. It is conceptually similar to `continue` in imperative languages.

* the item is not added to the result;
* `update` is not executed;
* the item does not count toward `limit`;
* iteration continues with the next source item.

When produced while generating an array or object outside `foreach`, the corresponding output element is omitted.

#### Examples

In the following three examples, the entries with `_skip` value are removed from the final output. The `foreach` part start with the range 0, 1, 3, ..., 9, and then convert any number that is not divisible 3 to _skip, which is then removed from the output.
```json
// Template:
{
    "main": {
        "foreach": { "$": true, "foreach": { "in": 10, "out": "$py= _skip if _ % 3 != 0 else _" }},
        "array": [ 1, 2, "$_skip", 3, 4, "$_skip" ],
        "object": { "a": 1, "b": "$_skip", "c": 3, "d": 4, "e": "$_skip" }
    }
}
// Output:
{
    "array": [ 1, 2, 3, 4 ],
    "object": { "a": 1, "c": 3, "d": 4 },
    "foreach": [ 0, 3, 6, 9 ]
}
```

---

### `_break`

Terminates the current `foreach` iteration immediately.

The current item is not added to the result, `update` is not executed, and no additional source items are processed.

`_break` is conceptually similar to `break` in an imperative language.

#### Examples

```json
// Template:
{
    "main": {
        "foreach": { "$": true, "foreach": { "in": 100, "out": "$py= _break if _*_ > 50 else _*_" }},
        "array": [ 1, 2, "$_break", 3, 4, "$_break" ],
        "object": { "a": 1, "b": "$_break", "c": 3, "d": 4, "e": "$_break" }
    }
}
// Output:
{
  "foreach": [ 0, 1, 4, 9, 16, 25, 36, 49 ],
  "array": [ 1, 2 ],
  "object": { "a": 1 }
}
```

When produced while generating an array or object outside `foreach`, the created object will not include any additional elements. 

---

### `_error`

Represents a processing error.

When an expression produces `_error`, normal evaluation stops and the logic element's `error` handler is evaluated, if one is present. Otherwise, the error propagates to the enclosing logic element.

Unlike `Missing`, `_error` represents a processing failure rather than an absent value.

Unlike `_skip` and `_break`, which only affect the array, object, or `foreach` they occur in, `_error` aborts the entire structure being built — the moment it's encountered, construction stops immediately, with no partial result, and the error propagates outward until something catches it.

#### Examples

In the following example, `_error` is unhandled. Since `main` here is a plain object with no enclosing logic element, nothing intercepts the error, and the entire render fails — there is no partial output, not even `null`; the render itself does not succeed.

```json
// Template
{
    "main": {
        "array": [ 1, 2, "$_error", 3, 4 ]
    }
}
// Output
// render fails; no JSON result is produced
[ERROR] GENERIC-ERROR: Unspecific Error
```

In the next example, the same failure occurs one level deeper — inside `data` — but this time the enclosing logic element has an `error` clause, which intercepts the error and supplies a replacement value instead. This mirrors how `fallback` recovers from `Missing`.

```json
// Template
{
    "main": {
        "$": true,
        "data": { "count": 5, "values": [ 1, 2, "$_error", 3, 4 ] },
        "error": "Could not process values"
    }
}
// Output
"Could not process values"
```

#### Common sources include:

* an explicit `$_error`;
* a runtime exception inside a `$py=`, `$pyeval=`, or `$pyrun=` expression, converted internally into a notice;
* a `transform` given input of the wrong shape (for example, `merge` given a non-list);
* an unresolvable navigation, such as `$<` used with no enclosing logic element.
* 

---

## Template Values

Template values are initialized once at the start of a render operation and remain unchanged throughout that render — but differ from one render to the next.

### `_input`

The complete input document supplied to the render operation.

This is equivalent to the navigation root `$^`.

Use `_input` from expression engines and `$^` from navigation expressions.

Unlike `$` (current data), which changes as `data` and `foreach` reassign it at each nesting level, `_input`/`$^` always refers to the original document handed to `render()` — unaffected by how deep the current logic element is nested, or what `data`/`foreach` have done to `$` along the way.

### Examples

In the following example, the top-level `data` replaces `$` with the `orders` array, and a nested `foreach` replaces it again with each individual order. From inside that nested loop, `$` can no longer reach the original document — but `$^` still can, letting each order look up a value (the customer's `region`) that lives outside the array being iterated.

```json
// Template
{
    "main": {
        "$": true,
        "data": "$.orders",
        "foreach": {
            "var": "order",
            "out": {
                "id": "$order.id",
                "amount": "$order.amount",
                "region": "$^.customer.region"
            }
        }
    }
}
// Input
{
    "customer": { "id": 42, "region": "EMEA" },
    "orders": [
        { "id": 1001, "amount": 250 },
        { "id": 1002, "amount": 75 }
    ]
}
// Output
[
    { "id": 1001, "amount": 250, "region": "EMEA" },
    { "id": 1002, "amount": 75, "region": "EMEA" }
]
```

Without `$^`, this value would be unreachable from inside the `foreach` — `$` no longer points at the top-level document once `data` and `foreach` have replaced it, and `$<` (the *enclosing* logic element's current data) would only reach as far as the `orders` array, not the original document above it.

---

### `_datasets`

Namespace containing all datasets available during rendering.

Datasets may originate from:

* the template;
* the rendering environment;
* the render request.

Datasets are accessed as object members.

Example:

```text
$_datasets.exchange_rates
```

---

## `_external`

Namespace containing external variables supplied by the rendering environment.

Unlike `_global`, external variables are read-only and remain constant throughout the render.

Example:

```text
$_external.environment
$_external.today
```

---

## `_top`

Runtime context of the top-level logic element.

It provides access to the top-level variable scope and runtime state.

For access to the original input document, prefer `$^` or `_input`.

---

# Scoped Values

Scoped values are updated whenever execution enters a new logic element.

Good addition — this closes a real gap. Worth tracing the code first since there's a subtlety: `_data` and the navigation root `$` share an internal name coincidentally, but they are not the same mechanism, and the doc should be careful not to blur them.

`core.py`'s `Frame.set_state_data`:
```python
def set_state_data(self, current: Any):
    self.vars["_data"] = current
```
is called from exactly one place — `logic.py`'s `LogicStatement._eval`, Stage 2 (`data`):
```python
if (v_set_current := self._set_current) is not JSON_UNSET:
    v_data = ctx.eval_value(v_set_current)
    ...
    ctx.set_state_data(current)
    ctx.set_current(current)
```
`foreach`'s per-item assignment (`_eval_foreach`) only calls `ctx.set_current(item)` — never `set_state_data` — so `_data` is untouched by iteration. That's the exact distinction you're asking for: `_` moves every iteration, `_data` stays fixed at whatever `data` last assigned, for the life of that logic element.

*(Aside, not for the doc: `navigation.py` separately uses the string `"_data"` as `NavigationStatement`'s internal marker for the `$` root — `if start == "_data": value = ctx.current`. That's an unrelated internal implementation detail, not the same as this `vars["_data"]` entry; worth knowing so a future code reader doesn't conflate the two, but not something to expose in the doc itself.)*

Here's the new section:

---

## `_data`

The value most recently assigned by a `data` statement in the current logic element.

Unlike `_`, which is reassigned on every `foreach` iteration, `_data` is set only when `data` runs — once, at Stage 2 of the logic element's evaluation — and is **not** touched by `foreach`, however many iterations follow. This makes `_data` useful for reaching back to the value `data` selected, from inside a loop where `_` (and `$`) now refer to the current item instead.

If the current logic element has no `data` statement of its own, `_data` is inherited from the nearest enclosing logic element that set one, via normal variable lookup.

### Examples

```json
// Template
{
    "main": {
        "$": true,
        "data": "$.customer",
        "foreach": {
            "in": "$.orders",
            "out": {
                "customer_id": "$_data.id",
                "customer_name": "$_data.name",
                "amount": "$_"
            }
        }
    }
}
// Input
{
    "customer": {
        "id": 42,
        "name": "Ada",
        "orders": [ 100, 250, 75 ]
    }
}
// Output
[
    { "customer_id": 42, "customer_name": "Ada", "amount": 100 },
    { "customer_id": 42, "customer_name": "Ada", "amount": 250 },
    { "customer_id": 42, "customer_name": "Ada", "amount": 75 }
]
```

`data` selects the customer object once, before the loop starts. Inside `foreach`, `_` (and `$`) change on every iteration to the current order amount — but `$_data` still refers to the customer object throughout, letting every iteration reach `customer_id`/`customer_name` without needing `$<` or a `var`-bound reference back to the outer scope.

---

## `_level`

Current nesting level of the active logic element.

The outermost logic element has level `0`. Each nested logic element increases the level by one.

This variable is primarily intended for diagnostics and advanced templates.

---

## `_local`

Namespace containing variables declared in the current logic-element scope.

Unlike normal variable lookup, `_local` does not search enclosing scopes.

---

## `_global`

Namespace containing variables declared in the top-level logic element.

All nested logic elements share the same global namespace.

Unlike `_external`, the global namespace is created by the template itself and is unique to the current top-level evaluation.

---

## `_parent`

Runtime context of the enclosing logic element.

Unlike `$<`, which refers to the enclosing logic element's current data, `_parent` exposes the entire runtime context.

---

# Scoping Rules

This section explains how variable lookup works across nested logic elements — the mechanism referenced from `navigation.md`'s `$foo`, `$%`, and `$<` sections.

Every logic element evaluates inside its own scope. When a logic element is nested inside another, its scope is a **child** of the enclosing element's scope.

**Normal lookup** (`$foo`, `$%.foo`) starts in the current scope and searches outward through each enclosing scope in turn, stopping at the first match:

* A variable declared with `set` in the current logic element is found immediately.
* A variable declared with `set` in an *enclosing* logic element is visible to nested elements, unless a nested element declares a variable with the same name — which shadows the outer one for the remainder of that nested scope.
* If no scope in the chain declares the variable, lookup resolves to `Missing`.

Three built-ins deliberately bypass this walk, each in a different way:

* **`_local`** narrows the search to the *current* scope only — no outward walk. A variable that exists but only in an enclosing scope will not appear in `_local`.
* **`_global`** jumps directly to the *top-level* scope, regardless of how deeply nested the current logic element is — skipping every intermediate scope rather than walking through them.
* **`_parent`** does not perform a lookup at all — it hands back the entire enclosing runtime context as a value, so a nested element can inspect (or navigate into) its parent's state directly rather than relying on name resolution.

Use plain `$foo` / `$%.foo` for everyday variable access. Reach for `_local`, `_global`, or `_parent` only when you specifically need to bypass the normal chain — for example, to guarantee you're reading a render-wide value (`_global`) rather than whatever a nearer scope happens to shadow it with.

---

## Foreach Values


# Foreach Values

Foreach values are updated for each iteration.

## `_`

Current data.

Outside `foreach`, `_` contains the current data of the active logic element — this is what `data` assigns.

Inside `foreach`, whether `_` tracks the source item depends on whether `var` is specified:

* **No `var` given** — each source item becomes `_` (and `$`) directly for that iteration.
* **`var` given** — the source item is bound to `$var` instead; `_` and `$` are *not* updated to the item, and continue referring to whatever the enclosing logic element's current data was (e.g. whatever `data` set, or the parent's current data if no `data` was used).

In both cases, once `out` is evaluated, `_` (and `$`) is updated to hold the **result of `out`** — this is what `foreach.update` reads.

Navigation expressions use `$` to reference the same value as `_`.

### Examples

**`data` sets `_` for the whole logic element:**

```json
// Template
{
    "main": {
        "$": true,
        "data": "$.customer",
        "out": "$_.name"
    }
}
// Input
{ "customer": { "name": "Ada", "id": 7 }, "other": 1 }
// Output
"Ada"
```

After `data`, `_` (and `$`) refer to the customer object — not the original input document. (Use `$^` to still reach the original input; see `_input`.)

**`foreach` with no `var` — the source item becomes `_` directly:**

```json
// Template
{
    "main": {
        "$": true,
        "foreach": {
            "in": "$.scores",
            "out": "$py= _ * 2"
        }
    }
}
// Input
{ "scores": [ 1, 2, 3 ] }
// Output
[ 2, 4, 6 ]
```

No named variable is needed — each score is available as `_` (or `$`) for the duration of that iteration.

**`foreach` with `var` — `_` does *not* track the item, only `$var` does:**

```json
// Template
{
    "main": {
        "$": true,
        "data": "$.label",
        "foreach": {
            "var": "score",
            "in": "$.scores",
            "out": "$py= score * 2",
            "update": { "history": "$py= _local.get('history', []) + [_]" }
        }
    }
}
// Input
{ "label": "round-1", "scores": [ 1, 2, 3 ] }
```

Inside `out`, `$score` gives the source item (`1`, `2`, `3`) — `_` here still refers to `"round-1"` (from `data`), *not* the current score, because `var` was given. After `out` runs, `_` is reassigned to the `out` result (`2`, `4`, `6`), which is what `update` sees and accumulates into `history`.

---

## `_key`

Current iteration key.

Its value depends on the iteration source:

* array — zero-based array index;
* object — member name;
* integer range — current integer value.

The value is updated for every iteration, using the name given by `foreach.key`, or `_key` if none is specified.

### Examples

**Iterating an array — `_key` is the index:**

```json
// Template
{
    "main": {
        "$": true,
        "foreach": {
            "in": "$.items",
            "out": { "index": "$_key", "value": "$_" }
        }
    }
}
// Input
{ "items": [ "a", "b", "c" ] }
// Output
[
    { "index": 0, "value": "a" },
    { "index": 1, "value": "b" },
    { "index": 2, "value": "c" }
]
```

**Iterating an object — `_key` is the member name:**

```json
// Template
{
    "main": {
        "$": true,
        "foreach": {
            "in": "$.prices",
            "out": { "currency": "$_key", "amount": "$_" }
        }
    }
}
// Input
{ "prices": { "USD": 10, "EUR": 9 } }
// Output
{
    "USD": { "currency": "USD", "amount": 10 },
    "EUR": { "currency": "EUR", "amount": 9 }
}
```

# Missing versus `null`

`Missing` and JSON `null` are distinct values.

| Value     | Meaning                                   |
| --------- | ------------------------------------------ |
| `Missing` | No value exists or no value was produced. |
| `null`    | An explicit JSON value.                   |

Both are treated as false in JFTL conditions, but they remain semantically distinct throughout evaluation.

---

# Examples

| Expression            | Description                                                              |
| ---------------------- | ------------------------------------------------------------------------ |
| `$_input.customer`      | Access the `customer` field of the original input document.              |
| `$_datasets.exchange_rates.USD` | Look up a value from a named dataset.                             |
| `$_external.today`      | Read an environment-supplied value, constant for the whole render.       |
| `$_local.total`         | Read `total` only if declared in the current logic element's own scope.  |
| `$_global.session_id`   | Read a value declared once at the top level, from anywhere in the template. |
| `$_parent.customer`     | Reach into the enclosing logic element's full runtime context.           |
| `$_key`                 | Get the current index (array) or key (object) inside a `foreach`.        |
| `$_ == $_missing`       | Test whether the current value is `Missing`.                             |

---

# See Also

* `logic.md` — Logic elements and the execution pipeline; where `set`, `foreach`, and nested logic elements are defined.
* `navigation.md` — `$`, `$foo`, `$%`, `$<`, `$^` and how they map to the built-ins on this page.
* `expression-engines.md` — `$py=`, `$pyeval=`, `$pyrun=`, and how built-in variables are exposed to each engine's evaluation namespace.