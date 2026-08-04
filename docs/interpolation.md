# Interpolation

Interpolation allows a string to be constructed by **concatenating constant text with the results of evaluated expressions**. It provides a concise way to build messages, paths, URLs, identifiers, and other textual values without explicitly performing string concatenation.

An interpolated string consists of one or more literal text fragments mixed with `${...}` expressions. Each expression is evaluated, converted to a string, and all parts are concatenated to produce the final value.

---

## Syntax

Any string containing `${...}` is treated as an interpolated string.

```text
${EXPR}
```

Multiple interpolations may appear within the same string.

Examples:

```text
"Hello ${first} ${last}!"

"/users/${customer.id}/orders/${order}"

"https://api.example.com/${tenant}/${version}"
```

Text outside `${...}` is copied unchanged into the output.

---

## Escape Sequence

To include the literal text `${` without starting an interpolation, prefix it with an additional `$`.

```text
$${    →    ${
```

For example:

```json
{
  "$": true,
  "set": {
    "name": "Alice"
  },
  "out": "Use $${name} to refer to the variable named ${name}."
}
```

Result:

```text
Use ${name} to refer to the variable named Alice.
```

---

## Value Conversion

Each interpolated expression is converted to text before concatenation.

| Value | Result |
|--------|--------|
| String | unchanged |
| Number | decimal representation |
| Boolean | `true` or `false` |
| `null` | `null` |
| Missing | `null` |

Objects and arrays cannot be interpolated directly. Attempting to do so results in a runtime error.

---

## Examples

### Simple greeting

```json
{
  "$": true,
  "set": {
    "first": "Alice",
    "last": "Smith"
  },
  "out": "Hello ${first} ${last}!"
}
```

Result:

```text
Hello Alice Smith!
```

---

### Building a URL

```json
{
  "$": true,
  "set": {
    "tenant": "demo",
    "version": "v2",
    "customer": 12345
  },
  "out": "https://api.example.com/${tenant}/${version}/customers/${customer}"
}
```

Result:

```text
https://api.example.com/demo/v2/customers/12345
```

---

### Structured output

Interpolation works naturally together with ordinary expressions.

```json
{
  "$": true,
  "set": {
    "first": "Alice",
    "last": "Smith",
    "customer_id": 12345
  },
  "out": {
    "id": "$customer_id",
    "name": "${first} ${last}",
    "display": "Customer ${customer_id}: ${first} ${last}"
  }
}
```

Result:

```json
{
  "id": 12345,
  "name": "Alice Smith",
  "display": "Customer 12345: Alice Smith"
}
```

Notice that `"id"` is produced by an ordinary expression, so it remains an integer. The `"name"` and `"display"` fields use interpolation and therefore produce strings.

---

### Reusing computed values

Interpolation can be used to build intermediate values that are later referenced by ordinary expressions.

Input:

```json
{
  "first": "Alice",
  "last": "Smith",
  "customer_id": 12345
}
```

Template:

```json
{
  "$": true,
  "set": {
    "full_name": "${$.first} ${$.last}"
  },
  "out": {
    "id": "$.customer_id",
    "name": "$full_name",
    "message": "Welcome ${full_name}!"
  }
}
```

Result:

```json
{
  "id": 12345,
  "name": "Alice Smith",
  "message": "Welcome Alice Smith!"
}
```
---

### Referencing values from an outer frame

Interpolation can reference values from the current frame as well as values from parent frames using normal navigation expressions.

Input:

```json
{
  "department": "Technology",
  "employees": [
    {
      "name": "Alice",
      "skills": ["Python", "SQL"]
    },
    {
      "name": "Bob",
      "skills": ["Java"]
    }
  ]
}
```

Template:

```json
{
  "$": true,
  "foreach": {
    "in": "$.employees",
    "out": {
      "$": true,
      "foreach": {
        "in": "$.skills",
        "out": "${$<.name} (${^.department}) - ${_}"
      }
    }
  },
  "transform": "flatten"
}
```

Result:

```json
[
  "Alice (Technology) - Python",
  "Alice (Technology) - SQL",
  "Bob (Technology) - Java"
]
```

In the innermost interpolation:

- `${_}` refers to the current skill.
- `${$<.name}` navigates to the parent frame (the current employee).
- `${$^.department}` navigates to the top-level input document.

---

## Summary

- Interpolation constructs strings by concatenating literal text with evaluated expressions.
- Any string containing `${...}` is automatically treated as an interpolated string. Exceptions:
  - Navigation Statements (`"$"`, `"$foo"`, `"$.customer.address"`)
  - Expression (`"$=..."`, `"$py=..."`)
  - Quoted strings (`"$$ ...`)
  - Strings inside literal blocks (`{ "$": false, "out": ...}`)

- Multiple interpolations may appear in the same string.
- Use `$${` to produce a string with the literal `${`.
- Interpolated values are always converted to strings before concatenation.

````
