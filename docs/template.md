
# Template Structure

Every JFTL template is a JSON document. At the top level, the template may contain up to three entries:

| Entry | Required | Description |
|--------|----------|-------------|
| `main` | **Yes** | The main template to execute. |
| `datasets` | No | Defines datasets bundled with the template. |
| `config` | No | Template-wide configuration options. |

Minimal template:

```json
{
  "main": {
    "message": "Hello World"
  }
}
```

---

# main

The `main` entry is the root of the template.

It may contain:

- literal JSON
- navigation expressions
- logic elements
- expression engine invocations
- any other valid JFTL construct

Example:

```json
{
  "main": {
    "name": "$.name",
    "age": "$.age"
  }
}
```

When rendered with

```json
{
  "name": "Alice",
  "age": 42
}
```

the result is

```json
{
  "name": "Alice",
  "age": 42
}
```

The engine always starts execution from `main`.

---

# datasets

Templates may embed datasets that become available during rendering through the built-in `_datasets` variable.

The `datasets` entry must be a JSON object mapping dataset names to arbitrary JSON values.

```json
{
  "datasets": {
    "countries": {
      "US": "United States",
      "CA": "Canada"
    },

    "colors": [
      "red",
      "green",
      "blue"
    ]
  },

  "main": {
    "country": "$_datasets.countries.US"
  }
}
```

During rendering the engine combines datasets from three sources, in the following order:

1. datasets embedded in the template
2. datasets registered by the application
3. datasets supplied explicitly for the render operation

Later sources override earlier ones when the same dataset name is used.

When using the CLI options `--dataset` (also `-F`) and `--data` (also `-D`) can add data to the engine. See `CLI.md`.

---

# config

The optional `config` object controls template-wide behavior.

Current configuration options are shown below.

| Option | Type | Default | Description |
|---------|------|---------|-------------|
| `default_expr_engine` | string | `""` | Default expression engine used by `$=...` expressions. |
| `drop_null_attributes` | boolean | `false` | Omits object attributes whose final value is `null`. :contentReference[oaicite:1]{index=1} |

Example:

```json
{
  "config": {
    "default_expr_engine": "py"
  },

  "main": {
    "sum": "$=a + b"
  }
}
```

---

# default_expr_engine

Normally an expression explicitly specifies its engine:

```text
$py=a + b
$pyeval=a + b
$pyrun=
return a + b
```

When `default_expr_engine` is configured, it specify the engine that will be used when no engined is provided: 

```json
{
  "config": {
    "default_expr_engine": "py"
  },

  "main": {
    "total": "$=price * quantity"
  }
}
```

is equivalent to

```json
{
  "main": {
    "total": "$py=price * quantity"
  }
}
```

If no default engine is configured, `$=...` expressions have no engine associated with them and compilation fails unless one is specified explicitly.

---

# drop_null_attributes

By default, object members whose value evaluates to `null` remain in the output.

Template:

```json
{
  "main": {
    "name": "$.name",
    "phone": "$.phone"
  }
}
```

Input:

```json
{
  "name": "Alice",
  "phone": null
}
```

Output:

```json
{
  "name": "Alice",
  "phone": null
}
```

Setting

```json
{
  "config": {
    "drop_null_attributes": true
  }
}
```

produces

```json
{
  "name": "Alice"
}
```

Only object attributes are removed. Array elements remain in place even when their value is `null`.

---

# Complete Example

```json
{
  "config": {
    "default_expr_engine": "py",
    "drop_null_attributes": true
  },

  "datasets": {
    "currency": {
      "USD": "$",
      "EUR": "€"
    }
  },

  "main": {
    "name": "$.customer",
    "symbol": "$_datasets.currency.USD",
    "total": "$=price * quantity"
  }
}
```

This template:

- executes the `main` entry,
- exposes the `currency` dataset through `_datasets`,
- evaluates `$=...` expressions using the `py` engine by default, and
- removes object attributes whose final value is `null`.
