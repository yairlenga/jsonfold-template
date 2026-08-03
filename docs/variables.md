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
| `_level`    | Scoped   | int       | Nesting level of the current logic element.                                                                                                         |
| `_local`    | Scoped   | namespace | Variables declared in the current logic-element scope.                                                                                              |
| `_global`   | Scoped   | namespace | Variables declared in the top-level logic-element scope.                                                                                            |
| `_parent`   | Scoped   | context   | Runtime context of the enclosing logic element.                                                                                                     |
| `_`         | Foreach  | json      | Current data. During `foreach`, contains the current source item. During `foreach.update`, contains the generated output for the current iteration. |
| `_key`      | Foreach  | json      | Current array index, object key, or range value.                                                                                                    |

---

# Constant Values

Constant values are immutable singletons used by JFTL to control evaluation. They are not ordinary JSON values, and they are identical across every template and every render — fixed for the life of the process.

## `_missing`

Represents the absence of a value.

Unlike JSON `null`, `_missing` indicates that no value existed or no value was produced. In the final template result they get converted to null, but until that point, they remain distinct, making it possible to distinguish between the `null` value no-value present. They are similar to the JavaScript `undefined`. The `_missing` value is treated as false in conditions (similar to `null`),

### Examples
In the following example, both "missing" and "nonexisting" will show "Nothing" is the output. Both the $nonexisting expression, and the explicit `_missing` variable resolve to the missing value, which is converted to the string "Nothing" by the `default` clause. Without the `default` clause, they `_missing` value will be converted to `null` in the final output.

```json
// Template
{
    "main": {
        "$": true,
        "data": { "foo": "bar", "null": null, "missing": "$_missing", "nonexisting": "$nonexisting" },
        "foreach": { "out": { "$": true, "default": "Nothing" }}
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

Common sources include:

* navigation to a nonexistent object member;
* an array index outside the array bounds;
* lookup of an undefined variable;
* navigation through a `null` or `missing` value;
* Failed `if` condition, which are used to guard complete statement;
* a `case` with no matching branch and no `else`;
* a `for` statement that iterate thru a `null` or `_missing` container;
* an explicit `$_missing`.

`Missing` is treated as false in JFTL conditions.

A logic element may replace `Missing` using `default`.

---

## `_skip`

Omits the current generated item.

When returned from a `foreach` item's `out` or `case` expression. It is conceptually similar to `continue` in imperative languages.

* the item is not added to the result;
* `update` is not executed;
* the item does not count toward `limit`;
* iteration continues with the next source item.

When produced while generating an array or object outside `foreach`, the corresponding output element is omitted.

### Examples

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

## `_break`

Terminates the current `foreach` iteration immediately.

The current item is not added to the result, `update` is not executed, and no additional source items are processed.

`_break` is conceptually similar to `break` in an imperative language.

```json`
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

When produced while generating an array or object outside `foreach`, the created object will not include any additional elements. 

```

---

## `_error`

Represents a processing error.

When an expression produces `_error`, normal evaluation stops and the logic element's `error` handler is evaluated, if one is present. Otherwise, the error propagates to the enclosing logic element.

Unlike `Missing`, `_error` represents a processing failure rather than an absent value.

---

# Template Values

Template values are initialized once at the start of a render operation and remain unchanged throughout that render — but differ from one render to the next.

## `_input`

The complete input document supplied to the render operation.

This is equivalent to the navigation root `$^`.

Use `_input` from expression engines and `$^` from navigation expressions.

---

## `_datasets`

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

# Foreach Values

Foreach values are updated for each iteration.

## `_`

Current data.

Outside `foreach`, `_` contains the current data of the active logic element.

During `foreach`, it contains the current source item.

During `foreach.update`, it contains the generated output for the current iteration.

Navigation expressions use `$` to reference the same value.

---

## `_key`

Current iteration key.

Its value depends on the iteration source:

* array — zero-based array index;
* object — member name;
* integer range — current integer value.

The value is updated for every iteration.

---

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