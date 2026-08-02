# JFTL — JSONFold Template Language


<!-- LTeX: dictionary+=JSONata dictionary+=foreach dictionary+=py dictionary+=jq dictionary+=versionable -->
<!-- cspell:words simpleeval JSONata versionable pyeval -->

JFTL is a JSON-based template language for transforming JSON documents into other JSON documents.

Unlike text template engines, JFTL operates on structured data. Templates are themselves valid JSON, making them easy to read, validate, generate, version, and manipulate using standard JSON tooling.

JFTL is designed for data transformation, report generation, API reshaping, ETL pipelines, configuration generation, and similar tasks where the output is JSON rather than text.

---

# Features

* JSON in → JSON out
* Templates are valid JSON
* Compile once, render many
* Streaming-friendly execution
* Safe by default
* Multiple expression engines
* Built-in navigation language
* Declarative iteration and aggregation
* Extensible via plugins
* Portable template format

---

# Installation

```bash
pip install jsonfold-template
```

---

# Quick Example

Input

```json
{
  "people": [
    { "first_name": "John", "middle_name": "Q", "last_name": "Public", "street": "123 Main St", "city": "Springfield", "state": "IL", "zip": "62704", "email": "john@example.com", "mobile_phone": "555-1234", "office_phone": "555-5678" },
    { "first_name": "Jane", "last_name": "Doe", "street": "456 Oak Ave", "city": "Portland", "state": "OR", "zip": "97201", "email": "jane@example.com", "mobile_phone": "555-9999" }
  ]
}```

Template

```json
{
  "main": {
    "$": true,
    "foreach": {
      "var": "p",
      "in": "$.people",
      "out": {
        "name": {
          "first": "$p.first_name",
          "middle": "$p.middle_name",
          "last": "$p.last_name"
        },
        "address": {
          "street": "$p.street",
          "city": "$p.city",
          "state": "$p.state",
          "zip": "$p.zip"
        },
        "contact": {
          "email": "$p.email",
          "mobile": "$p.mobile_phone",
          "office": "$p.office_phone"
        }
      }
    }
  }
}
```

Output

```json
{
  "main": [
    {
      "name": { "first": "John", "middle": "Q", "last": "Public" },
      "address": { "street": "123 Main St", "city": "Springfield", "state": "IL", "zip": "62704" },
      "contact": { "email": "john@example.com", "mobile": "555-1234", "office": "555-5678" }
    },
    {
      "name": { "first": "Jane", "middle": null, "last": "Doe" },
      "address": { "street": "456 Oak Ave", "city": "Portland", "state": "OR", "zip": "97201" },
      "contact": { "email": "jane@example.com", "mobile": "555-9999", "office": null }
    }
  ]
}
```

---

# Basic Concepts

A template is compiled once and may be rendered many times against different input documents.

During rendering, JFTL evaluates a tree of expressions and logic statements that can:

* navigate the input document
* evaluate expressions
* iterate over arrays or objects
* build new JSON structures
* perform structural transformations

Templates remain ordinary JSON documents throughout.

---

# Expression Types

JFTL supports several kinds of expressions.

## Navigation

Navigation expressions look like JSONPath — $, .foo, [0], ["key"] — but are limited to direct path addressing. There's no filter syntax ([?(@.price > 10)]); JFTL uses foreach's if/case for conditional logic instead, keeping navigation simple and statically resolvable at compile time.
Examples

```text
$
$.name
$.items[0]
$.city["New York City"].population
$.state.NY.capital
$.country[$country].population
$user
```

---

## Expression Engines

JFTL doesn't invent its own expression language. Instead, it plugs into existing, well-understood engines — like Python `simpleeval` — so you write expressions in a language you already know, and choose the engine that fits your trust and complexity needs.

Expressions beginning with `$=` or `$engine=` are evaluated by an expression engine.

Examples

```text
$py=price * quantity   # Use arithmetic expressions on existing variables.
$py=_.city.upper()     # Retrieve city from the 'current' data element.
$py=len(items)         # Simple eval "safe" configuration is available by default.

```

The default installation enable only the safe engines. More powerful engines are available but must be explicitly enabled (e.g. unrestricted py `eval`, or even inline Python `functions`)

---

## Logic Statements

Complex processing is expressed using a logic object.

Features include

* variable assignment
* conditional execution
* `foreach` iteration
* case selection
* aggregation
* structural transformations
* default values
* error handling

---

# Documentation

## Getting Started

* Overview
* Tutorial
* Cookbook

## Reference

* `logic.md`
* `navigation.md`
* `variables.md`
* `interpolation.md`
* `transformations.md`
* `expression-engines.md`
* `template.md`
* `cli.md`

---

# Command Line

Compile and execute a template:

```bash
jf-template template.json input.json
```

Read input from stdin:

```bash
cat input.json | jf-template template.json -
```

Process multiple files:

```bash
jf-template template.json *.json
```

See `cli.md` for the complete command reference.

---

# Design Goals

JFTL was designed around a few core principles:

* Templates should be valid JSON.
* Data transformations should be declarative.
<!-- LTeX: enabled=false --> <!-- re-parsed not accepted -->
* Templates should compile once into an efficient execution plan, not be re-parsed on every render.
<!-- LTeX: enabled=true -->
* Safe execution should be the default.
* Rendering should be efficient.
* JFTL should leverage plugins for calculations, data access, and low-level processing.
* JFTL should build on existing standards and tools rather than inventing new ones, wherever practical.
* Templates should be portable between environments.

---

# Typical Uses

* API response reshaping
* ETL pipelines
* Configuration generation
* Report generation
* Data normalization
* Static JSON generation
* Document conversion
* Client-side data transformation

---

# When to Use Something Else

JFTL isn't trying to be a "magic-bullet" to perform any JSON processing tasks. There are already few good tools our there (`jq`, `JSONata`, `JMESPath` to name a few). JFTL solves a different problem. JFTL is a good fit when you're building structured output — reshaping flat records into nested documents, traversing, aggregating, or generating the same transformation repeatedly across many inputs — and want that transformation to live in a versionable, portable JSON file. 

## Example - When to use `jq`
For a simple extraction — say, pulling every email out of a list of people — jq is the right tool:

```jq
jq '.people[].email' input.json
```
It's possible to do the same in JFTL with the template below, but jq's C implementation will outperform it for simple filtering and extractions like this.
```json
{
    "main": {
        "$": true,
        "foreach": { "in": "$.people", "out": "$p.email" }
    }
}
```

## Example - When to use JSONata

JSONata offer advanced filtering/sorting/ranking within their "expression" language. For example, you can write the below to get the 3 highest-paid employees in the engineering department.
```jsonata
employees[department='Engineering']^(>salary)[[0..2]]
```
Filter, sort descending, take the first three — all as one path expression.

JFTL template can perform the same, but require more verbose template:
```json
{
    "main": {
        "$": true,
        "foreach": {
                "var": "e",
                "in": "$.employees",
                "if": "$py=e['department'] == 'Engineering'"
        },
        "out": "$pyeval=sorted(_, key=lambda x: x.salary, reverse=True)[:3]"
    }
}
```

## Example - When to use "real" programming language is better

Sometime, the right solution is to use a "real" programming language - Python, Java, JavaScript, Rust. They will usually outperform template-based solution for complex queries. For example above (3 highest-paid employees in the engineering department) can be solved in python:

```python
result = sorted(
    [e for e in employees if e["department"] == "Engineering"],
    key=lambda e: -e["salary"]
)[:3]
```
---

# Status

JFTL is under active development.

The current release provides the core language, navigation engine, safe expression engine, iteration, transformations, interpolation, datasets, and command-line interface.

Future releases will expand the standard library, expression engines, and plugin ecosystem while maintaining backwards compatibility whenever practical.

---

# Contributing

Contributions, bug reports, feature requests, documentation improvements, and examples are welcome.

Please open an issue or submit a pull request.

---

# License

MIT License.
