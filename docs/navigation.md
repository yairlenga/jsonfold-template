# `navigation.md` — Navigation Expressions Reference

## Introduction

JFTL navigation implement a subset of the JSONPath grammar, extended with variables inspired by the SQL/JSON standard.

Every navigation expression in JFTL resolve to a single JSON Value (from the original document, from the template, from external data, or calculated) — like a street address, customer object. If you need to work over many items — filtering, selecting, looping — that's what `foreach`, `if`, and `case` are for (see logic.md).

Tactically, JFTL navigation expressions are singular queries, in the sense defined by the JSONPath standard (RFC 9535 §2.3.5.1): the grammar is restricted so that every valid expression is guaranteed, by construction, to resolve to at most one value — never a list of matches. There is no filtering, recursive descent, wildcards, slices, or unions; navigation is not a general query language, and isn't intended as one.

If any path component cannot be resolved, the result is `Missing`.

JFTL navigation does not support filters, recursive descent, wildcards, slices, unions, or any other JSONPath constructs that may select multiple nodes. Conditional logic and iteration are instead provided by JFTL's `if`, `case`, and `foreach` constructs (see `logic.md`).

Every navigation expression resolves to **exactly one value**:

* the referenced JSON value, if the path exists;
* `Missing`, if any component of the path cannot be resolved.

Navigation expressions never return lists of matching nodes. More complex selection and filtering are performed using JFTL's `foreach`, `if`, and `case` constructs (see `logic.md`).

---

## Navigation Roots

Every navigation expression begins with one of the following roots.

| Root   | Description                                                       |
| ------ | ----------------------------------------------------------------- |
| `$`    | Current data.                                                |
| `$foo` | User-defined variable named `foo`.                                |
| `$%`   | Variable namespace.                                               |
| `$<`   | Current data of the enclosing logic element.                      |
| `$^`   | The input document. |

The following sections describe each navigation root in detail.

---

### `$` — Current Data

`$` refers to the current data.

Examples:

```text
$
$.customer
$.items[42]
```

Within a logic element, the current data may be replaced by the `data` statement or by each iteration of `foreach`.

---

### `$foo` — Named Variable

`$foo` references a user-defined variable named `foo`.

Variables are introduced by `set` or by `foreach`.

Examples:

```text
$user
$order.customer
$item.price
```

`$foo` is equivalent to `$%.foo`.

Variable scoping rules are described in `variables.md`.

---

3## `$%` — Variable Namespace

`$%` exposes the current variable scope as an object whose members are variables.

Like any other object, variables may be accessed using identifier notation, quoted keys, or computed keys.

Examples:

```text
$%.customer
$%["customer id"]
$%[$name]
```

This makes it possible to reference variables whose names are determined at runtime or whose names are not valid identifiers.

The variable namespace participates in normal navigation, so additional path segments may follow the selected variable.

Examples:

```text
$%.customer.address
$%[$name].zip
```

Variable scoping rules are described in `variables.md`.

---

### `$<` — Parent Frame

`$<` refers to the **current data** of the enclosing logic element.

Unlike JSON navigation, the enclosing logic element is determined by the evaluation structure rather than by the structure of the JSON document. Consequently, the current data of the enclosing logic element may be:

* The same JSON value as the current logic element;
* a parent of the current value;
* a descendant of the current value; or
* a completely unrelated JSON value.

The relationship depends entirely on how each logic element selected its current data (for example, using `data` or `foreach.in`).

A common case is nested `foreach` loops. When each `foreach` iterates over a child collection of its current data, and neither logic element explicitly replaces its current data using `data`, the enclosing logic element's current data is the direct parent of the current value.

Examples:

```text
$<
$<.customer
```

Use `$<` whenever a nested logic element needs to access the current data of its enclosing logic element.

---

### `$^` — The input document (The "Top" of the document)

`$^` refers to the full input document (technically, it's **current data** of the outermost logic element). `$^` provide access to the complete input document, regardless of the current nesting level or any intermediate `data` statements.

Examples:

```text
$^
$^.customer
```

Unlike `$<`, which refers to the immediately enclosing logic element, `$^` always refers to the top-level current data (the original input document).

---

# Path Segment Types

After the root, a navigation expression consists of zero or more path segments.

Segments are evaluated from left to right. If any segment cannot be resolved, evaluation immediately returns `Missing`.

The following segment types are supported:

| Segment   | Description                                                                            |
| --------- | -------------------------------------------------------------------------------------- |
| `.name`   | Access an object member whose name is a valid identifier.                              |
| `[42]`    | Access an array element by its zero-based index.                                       |
| `[-3]`    | Access an array element counting from the end of the array (`-1` is the last element). |
| `['key']` | Access an object member using a single-quoted key.                                     |
| `["key"]` | Same as above, using double quotes. Single and double quotes are interchangeable.      |
| `[$var]` | Access an object member using a computed key |

The following sections describe each segment type in detail.

---

## Object Member (`.name`)

Object members are accessed using dot notation.

```text
$.customer
$.customer.address
$order.total
```

As in JSONPath, dot notation may be used only for member names that are valid identifiers. All other member names must use quoted notation.

Examples:

```text
$.customer["first name"]
$.customer["postal-code"]
$.customer["123"]
```

If the member does not exist, the result is `Missing`.

---

## Array Index (`[42]`, `[-3]`)

Array elements are accessed using square brackets.

```text
$.items[42]
$.orders[1].lines[3]
$.matrix[2][5]
```

Indexes are zero-based.

Negative indexes count from the end of the array.

```text
$.items[-1]    # last element
$.items[-2]    # second-to-last element
$.items[-3]    # third-to-last element
```

If the index is outside the array bounds, the result is `Missing`.

---

## Quoted Object Keys (`['key']` / `["key"]`)

Object keys that are not valid identifiers may be written inside square brackets.

Both single and double quotes are accepted and are completely interchangeable.

The following expressions are equivalent:

```text
$.customer["first name"]
$.customer['first name']
```

Unlike JSON strings, quoted member names are simple string literals and **do not support escape sequences**. If a member name contains a quote character, use the other quoting style.

Examples:

```text
$.cities["New York"]
$.config['default-value']
```

If the key does not exist, the result is `Missing`.

---

## Computed Keys (`[$var]`)

The key inside brackets may be a user-defined variables.

```text
$.countries[$country]
$.settings[$key]
```

The expression must evaluate to a string if navigating to an object member. The expression must evaluate to an integer if navigating into an array. In this case, the regular negative indexing will apply.

If the value being navigated is `Missing`, or if the key expression evaluates to `Missing`, or the resulting key does not exist, the overall navigation expression also evaluates to `Missing`.

---

# Missing Values

Navigation expressions never fail simply because a path cannot be resolved.

Instead, a missing object member, array element, variable, or computed key evaluates to `Missing`.

This allows navigation expressions to compose naturally with JFTL's `if`, `default`, `case`, and other language constructs.

---

# Built-in Variables

JFTL provides several built-in variables in addition to user-defined variables.

These include local and global variable scopes (`_local`, `_global`), the current data (`_`), and variables introduced by `foreach`.

See `variables.md` for the complete list of built-in variables and their scoping rules.

---

# Examples

| Expression                | Description                                                                       |
| ------------------------- | --------------------------------------------------------------------------------- |
| `$.customer.address.city` | Retrieve the `city` field from the current customer's address.                    |
| `$.orders[42].total`      | Retrieve the `total` field from the 43rd order.                                   |
| `$.orders[-1].total`      | Retrieve the `total` field from the last order.                                   |
| `$.cities["New York"]`    | Access an object key containing spaces using double quotes.                       |
| `$.cities['New York']`    | Same as above, using single quotes.                                               |
| `$.countries[$country]`   | Use the value of the variable `country` as the object key.                        |
| `$user.address.zip`       | Access the `zip` field of the user-defined variable `user`.                       |
| `$%[$name]`               | Access the variable whose name is stored in the variable `name`.                  |
| `$<.customer`             | Access the `customer` field from the current data of the enclosing logic element. |
| `$^.config`               | Access the `config` field from the original input document.                       |

---

# See Also

* `logic.md` — Logic elements and the execution pipeline.
* `variables.md` — Built-in variables, user-defined variables, and scoping rules.
* `expression-engines.md` — `$py=`, `$pyeval=`, `$pyrun=`, and other expression engines.
* `interpolation.md` — `${...}` string interpolation.
