# JFTL Overview

JFTL (JSON Flow Transformation Language) is a declarative language for transforming JSON documents.

A JFTL template is itself valid JSON. Ordinary JSON remains unchanged, while dynamic behavior is introduced through a small set of language constructs such as navigation expressions, logic statements, interpolation, and expression engines.

Templates are compiled once and can then be rendered repeatedly against different input documents, making JFTL suitable for command-line tools, APIs, batch processing, and streaming applications.

---

# Design Goals

JFTL was designed around several principles.

* **JSON First** — templates are valid JSON documents.
* **Declarative** — describe the desired output rather than the execution steps.
* **Safe by Default** — only safe expression engines are enabled unless explicitly requested.
* **Deterministic** — identical inputs always produce identical outputs.
* **Compiled** — templates are validated and parsed once, then rendered efficiently.
* **Composable** — simple expressions combine naturally into larger transformations.
* **Extensible** — additional expression engines and plugins can be added without changing the language itself.

---

# A First Example

Input

```json
{
  "first": "John",
  "last": "Smith",
  "salary": 120000
}
```

Template

```json
{
  "main": {
    "name": "${first} ${last}",
    "salary": "$.salary"
  }
}
```

Output

```json
{
  "name": "John Smith",
  "salary": 120000
}
```

Most templates look like ordinary JSON. Only values beginning with `$` or containing `${...}` are evaluated.

---

# Template Structure

Every template consists of a single JSON document.

```text
Template
├── main        (required)
├── datasets    (optional)
└── config      (optional)
```

* **main** contains the transformation to execute.
* **datasets** contains reusable data bundled with the template.
* **config** specifies template-wide options such as the default expression engine.

See **template.md** for the complete reference.

---

# Execution Model

Rendering follows a simple pipeline.

```text
Input JSON
      │
      ▼
Create root namespace
      │
      ▼
Evaluate template
      │
      ├── literals
      ├── navigation
      ├── expressions
      └── logic statements
      │
      ▼
Materialize result
      │
      ▼
Output JSON
```

Most templates simply evaluate expressions embedded within JSON.

Logic statements introduce additional processing such as conditionals, iteration, reductions, and transformations.

---

# Expressions and Statements

JFTL separates **expressions** from **statements**.

## Expressions

Expressions evaluate to a value.

Examples include:

* navigation
* interpolation
* Python expressions
* literals

```json
{
  "customer": "$.customer.name",
  "total": "$py=price * quantity",
  "message": "Hello ${first}"
}
```

Expressions may appear anywhere a JSON value is allowed.

---

## Statements

Statements perform structured processing.

The primary statement type is the **Logic Statement**, identified by

```json
{
  "$": true
}
```

Logic statements support:

* local variables
* conditional execution
* iteration
* aggregation
* transformations

Unlike expressions, statements execute through multiple processing stages.

See **logic.md** for details.

---

# Namespaces

Every logic statement executes inside its own **namespace**.

A namespace contains:

* the current value
* local variables
* access to the parent namespace
* access to the root input document
* access to template datasets

Nested logic statements automatically create child namespaces.

This allows expressions such as

```text
$
$<
$^
$foo
```

to access values at different levels of the execution hierarchy.

Variables follow normal lexical scoping rules: a variable defined in the current namespace hides variables with the same name in enclosing namespaces.

See **variables.md** and **navigation.md**.

---

# Navigation

Navigation expressions retrieve values from the current document or from runtime variables.

Examples include

```text
$.customer.name
$.orders[0]
$foo
$<.customer
$^.header
```

Navigation never modifies data; it simply selects values.

See **navigation.md**.

---

# Interpolation

Interpolation constructs strings by combining literal text with evaluated expressions.

```text
"${first} ${last}"
```

produces a single string by concatenating the evaluated expressions with the surrounding literal text.

Interpolation is intended for string values and is not applied inside literal blocks.

See **interpolation.md**.

---

# Expression Engines

JFTL supports multiple expression engines.

| Engine | Purpose |
|---------|---------|
| Navigation | JSON navigation |
| py | Safe Python expressions |
| pyeval | Full Python `eval()` |
| pyrun | Full Python statements |

Expressions normally specify the engine explicitly.

```text
$.name
$py=price * quantity
$pyeval=max(values)
$pyrun=...
```

Alternatively, templates may configure a default engine so that `$=...` uses that engine automatically.

See **expressions.md**.

---

# Transformations

Transformations convert one data structure into another after evaluation.

Examples include:

* flatten
* merge
* to_pairs
* to_object

Transformations are typically used after iteration or aggregation to produce the desired output format.

See **transformation.md**.

---

# Compilation and Rendering

Templates are normally compiled once.

```text
JSON Template
        │
        ▼
Compile
        │
        ▼
Compiled Template
        │
        ▼
Render
        │
Input JSON
        │
        ▼
Output JSON
```

Compilation validates the template, parses expressions, resolves plugins, and prepares efficient evaluators.

The resulting compiled template can then be rendered repeatedly against different input documents.

---

# Errors

JFTL distinguishes between compilation and rendering.

**Compilation errors** include:

* invalid template structure
* syntax errors
* unknown expression engines
* invalid navigation expressions

Compilation errors prevent the template from being rendered.

**Rendering errors** occur while processing input data and include:

* expression evaluation failures
* missing required values
* runtime plugin failures

The runtime also provides special values such as `_missing`, `_error`, and `_skip` for advanced processing.

---

# Typical Workflow

Most applications follow the same lifecycle.

```text
Create Template
        │
        ▼
Compile Once
        │
        ▼
Render Many Times
        │
        ▼
Process Results
```

Separating compilation from rendering improves performance and allows templates to be validated before they are used.

---

# Documentation Guide

| Topic | Description |
|---------|-------------|
| **template.md** | Template structure and configuration |
| **logic.md** | Logic statements |
| **navigation.md** | Navigation expressions |
| **variables.md** | Built-in variables and namespaces |
| **expressions.md** | Expression engines |
| **interpolation.md** | String interpolation |
| **transformation.md** | Built-in transformations |
| **cli.md** | Command-line interface |
| **samples/** | Complete examples |