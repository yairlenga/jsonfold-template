# Expression Engines

JFTL expressions are evaluated by **expression engines**. Each engine provides its own syntax, capabilities, and security model.

Expressions are selected using the following syntax:

```text
$ENGINE=expression
```

For example:

```text
$py=price * quantity
$pyeval=sum(values)
$pyrun=return _.upper()
```

If no engine name is specified, the template's configured default expression engine is used.

```text
$=price * quantity
```

The default engine is configured in the template's `config` section.

```json
{
  "config": {
    "default_expr_engine": "py"
  }
}
```

---

## Available Engines

| Engine | Safety | Language | Typical Use |
|---------|---------|----------|-------------|
| `nav` | Safe | JFTL Navigation | Data lookup only |
| `py` | Safe | Restricted Python (SimpleEval) | Calculations, filtering, comprehensions |
| `pyeval` | Unsafe | Full Python `eval()` | Trusted templates requiring unrestricted expressions |
| `pyrun` | Unsafe | Full Python statements | Complex logic that requires loops, assignments, or multiple statements |

---


## nav

The `nav` engine is the simplest expression engine. It performs only navigation through the current document and runtime variables. See `navigation.md` for full syntax.

Note: The Navigation engine is automatically assumed when the expression starts with '$', and follow the syntax of navigation expressions (specifically, $, $^, $foo, $["bar"], ...). Usually, there is no need to specify it explicitly.

No functions, operators, or calculations are supported.

Typical uses include:

- Reading values
- Selecting nested fields
- Looking up variables
- Dynamic object indexing

### Examples

Current object:

```text
"$nav=$"
```

Nested field:

```text
"$nav=$.customer.name"
```

Variable lookup:

```text
"$nav=$total"
```

Dynamic lookup:

```text
"$.fxrate[$currency]"
```

### Characteristics

- Safe
- No function calls
- No arithmetic
- No string manipulation
- Fastest expression engine

---

## py

The `py` engine evaluates expressions using a restricted subset of Python implemented with **SimpleEval**.

It is the recommended engine for most templates.

Supported features include:

- Arithmetic
- Comparisons
- Boolean operators
- List comprehensions
- Dictionary comprehensions
- Basic built-in functions

Access to arbitrary Python objects and methods is restricted.

### Example 1

```text
"$py=price * quantity"
```

### Example 2

```text
"$py=customer.age >= 18"
```

### Example 3

```text
"$py=[item.name for item in _.items if item.price > 100]"
```

### Built-in Functions

The default configuration provides common functions including:

- `abs`
- `all`
- `any`
- `bool`
- `chr`
- `float`
- `int`
- `len`
- `max`
- `min`
- `ord`
- `range`
- `round`
- `sorted`
- `str`
- `sum`

Strings expose a limited set of methods, including:

- `lower`
- `upper`
- `strip`
- `startswith`
- `endswith`
- `replace`
- `split`
- `join`

### Characteristics

- Safe
- Good performance
- Recommended for most templates
- Supports comprehensions
- Does not allow arbitrary Python execution

---

## pyeval

The `pyeval` engine evaluates the expression using Python's built-in `eval()`.

The expression has unrestricted access to Python language features and any objects available in the evaluation environment.

**This engine should only be enabled for trusted templates.**

### Example 1

```text
"$pyeval=sum(_.values())"
```

### Example 2

```text
"$pyeval=sorted(customers, key=lambda c: c.balance)"
```

### Example 3

```text
"$pyeval={name: value for name, value in _.items() if value > 0}"
```

### Characteristics

- Unsafe to use on untrusted templates
- Full Python expression syntax
- Lambda expressions supported
- Arbitrary function calls permitted
- Suitable only for trusted environments

---

## pyrun

The `pyrun` engine executes Python statements rather than a single expression.

Unlike the other engines, it allows:

- assignments
- loops
- conditional statements
- early returns

The result of the expression is the value returned by the `return` statement.

The engine expect a valid python program. This means that python rules must be followed: each statement should be on its own line (use "\n" to enter new lines into the JSON), and indentation rules must be followed. As an alternative, Python allows multiple statements on a single line, separated by semicolon.

**This engine should only be enabled for trusted templates.**

### Example 1

```json
{
    "main": {
        "$": true,
        "data": { "user": { "first": "Jon", "last": "Doe" }},
        "out": "$pyrun= greet='Hello'; return greet + ' ' + _['user']['first']"
    }
}
```

will print the "Hello Jon"

### Example 2

```python
"$pyrun=\n
total = 0\n
for item in _.items:\n
    total += item.price\n
return total\n
"
```

### Example 3

```python
$pyrun=
result = []

for customer in customers:
    if customer.balance > 0:
        result.append(customer.name)

return result
```

###


### Characteristics

- Unsafe
- Full Python statements
- Supports loops and assignments
- Most flexible engine
- Slower than expression engines due to execution overhead

---

# Choosing an Engine

| Requirement | Recommended Engine |
|-------------|--------------------|
| Read data | `nav` |
| Calculations | `py` |
| Filtering and comprehensions | `py` |
| Advanced Python expressions | `pyeval` |
| Multi-statement algorithms | `pyrun` |

For most templates, **`py`** provides the best balance between functionality, performance, and safety. The `pyeval` and `pyrun` engines are intended only for trusted environments where unrestricted Python execution is acceptable.