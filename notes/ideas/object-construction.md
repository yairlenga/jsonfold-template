# JFTL Constructor Grammar Proposal

## Motivation

The goal is to make JFTL templates resemble the JSON they produce, similarly to how TAL keeps HTML visible and adds attributes to control evaluation.

Instead of writing generic logic statements everywhere:

```json5
{
    $: true,
    if: "...",
    foreach: { ... },
    out: {
        ...
    }
}
```

the common cases become structural constructors.

The existing logic statement remains the canonical internal representation and the escape hatch for advanced cases.

---

# Three Construction Forms

## 1. Object Constructor

Produces a single object.

```json5
{
    $: {
        if: "$.active",
        set: {
            full_name: "${$.first} ${$.last}"
        }
    },

    name: "$full_name",
    city: "$.address.city"
}
```

Equivalent to:

```json5
{
    $: true,
    if: "$.active",
    set: {
        full_name: "${$.first} ${$.last}"
    },
    out: {
        name: "$full_name",
        city: "$.address.city"
    }
}
```

### Rules

- `$` must be the first property.
- Object must contain at least one additional property.
- `foreach` is **not allowed**.
- If `case` exists:
    - sibling properties become the implicit `else`
    - explicit `else` is forbidden.
- If `case` does not exist:
    - sibling properties become `out`.
- `out` is not allowed.

---

## 2. Array Constructor

Produces an array of objects.

```json5
[
    {
        $: {
            foreach: {
                in: "$.customers"
            },
            set: {
                country: "$^.country"
            }
        }
    },

    {
        name: "$.name",
        city: "$.city",
        country: "$country"
    }
]
```

Equivalent to:

```json5
{
    $: true,

    foreach: {
        in: "$.customers"
    },

    set: {
        country: "$^.country"
    },

    out: {
        name: "$.name",
        city: "$.city",
        country: "$country"
    }
}
```

### Rules

The shortcut is recognized only when:

- node is an array
- exactly two elements
- first element is an object
- first object's **only** property is `$`
- `$` contains `foreach`
- second element is an object

Otherwise it is either:

- a normal array
- or a compile-time error (if it partially matches the shortcut)

---

## 3. Generic Statement

Used for everything else.

```json5
{
    $: true,

    case: [
        { when: "$.raw", then: "$.value" },
        { else: null }
    ]
}
```

Examples:

- scalar output
- explicit `out`
- explicit `case`
- transforms
- reductions
- advanced logic

---

# Compiler Architecture

No preprocessing pass.

Compilation simply recognizes two constructor patterns.

```
compile(node)

    object constructor?
        ↓
        synthesize canonical LogicStatement
        ↓
        compile logic

    array constructor?
        ↓
        synthesize canonical LogicStatement
        ↓
        compile logic

    otherwise
        compile normally
```

The canonical logic representation remains unchanged.

---

# Validation Rules

## General

- `$` must always be the first property.
- `$` appearing elsewhere is a compile-time error.

---

## Object Constructor

Allowed

```json5
{
    $: { ... },
    foo: ...
}
```

Rejected

```json5
{
    foo: ...,
    $: { ... }
}
```

Rejected

```json5
{
    $: { ... }
}
```

(no implicit empty object)

Rejected

```json5
{
    $: {
        foreach: ...
    },

    foo: ...
}
```

Rejected

```json5
{
    $: {
        out: ...
    },

    foo: ...
}
```

Rejected

```json5
{
    $: {
        case: [
            ...
            { else: ... }
        ]
    },

    foo: ...
}
```

---

## Array Constructor

Allowed

```json5
[
    { $: { foreach: ... } },
    { foo: ... }
]
```

Rejected

```json5
[
    { $: { foreach: ... } }
]
```

Rejected

```json5
[
    { $: { foreach: ... } },
    { foo: ... },
    { bar: ... }
]
```

Rejected

```json5
[
    { foo: ..., $: { foreach: ... } },
    { ... }
]
```

Rejected

```json5
[
    { $: { if: ... } },
    { ... }
]
```

(no foreach)

---

# Transforms

Constructors intentionally guarantee output shape.

Therefore transforms are **not allowed** inside constructors.

Reasons:

- compiler cannot determine whether a transform changes shape
- plugins may reshape output
- keeps constructor semantics simple

Use the generic statement whenever a transform is required.

---

# Design Principles

1. Templates should look like the JSON they produce.

2. `$` contains only execution directives.

3. Everything outside `$` is output.

4. Constructors guarantee output shape.

5. Generic statements remain available for advanced scenarios.

6. Constructors are preferred syntax.

7. Generic statements become the escape hatch.

---

# Documentation Structure

1. Object Constructor
2. Array Constructor
3. Generic Logic Statement

The tutorial should introduce constructors first, and explain later that they are syntactic sugar over the canonical logic statement.