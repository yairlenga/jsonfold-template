# JFTL — JSONFold Template Language

## Vision

JFTL is a **safe JSON-to-JSON transformation language** in which **templates are themselves valid JSON documents**. There is no new syntax outside of JSON — transformation, control flow, and expression evaluation are expressed through a small set of reserved object shapes and string prefixes.

JFTL aims to be for JSON roughly what XSLT is for XML — but deliberately smaller, more predictable, and closer in spirit to a compact orchestration language (à la AWS Step Functions / ASL) than to a general-purpose functional pipeline language (jq) or a text-templating engine (Handlebars/Mustache).

Goals:

* Templates remain readable, diffable, and editable as plain JSON.
* Portable across host languages — tier-1 targets are **Python, JavaScript/Node, and Java**; Go and .NET are tier-2; other languages may follow.
* Deterministic, side-effect-free, sandboxed execution.
* A strict separation between the **template language** (control flow, structure) and the **expression engine** (value computation).
* Reusable, isolated components (macros / partials).

### Positioning relative to prior art

| Compared to | JFTL's departure |
|---|---|
| **jq** | Trades jq's terse, bespoke pipe-grammar for JSON-native syntax — optimizing for tooling (diffs, validation, editing, generation) over keystroke economy. |
| **awk** | "Awk for JSON" in spirit (input → template → output), but JFTL is a whole-document tree transformation, not an implicit per-line/per-record processor. Streaming/record-oriented processing is out of scope for now. |
| **XSLT / XQuery** | JFTL uses explicit macro invocation (like `xsl:call-template`), not pattern-matched template dispatch (`xsl:apply-templates`) — trading some declarative power for predictability and a simpler mental model. |
| **Handlebars / Mustache** | JFTL covers the same logical operators (if, each, partials) but has no string-interpolation form (`{{name}}` inside literal strings) yet — values are computed via whole-string expression prefixes, not embedded substitution. |
| **AWS Step Functions (ASL)** | Direct inspiration for "small closed set of primitives; everything else is a Task (macro)." JFTL drops `Parallel` (unneeded — macros are pure, so independent branches are parallelizable by the host without a language construct) and `Wait`/`Succeed`/`Fail` (no orchestration-time concepts apply to a pure transform). |
| **TAL (Zope)** | Source of the fixed, order-independent execution sequence for a single logic object (see below), rather than depending on written key order. |

---

## Template Structure

```json
{
  "body": { "...": "TEMPLATE-BODY" },
  "macro": {
    "macro1": { "...": "MACRO-BODY" },
    "macro2": { "...": "MACRO-BODY" }
  },
  "data": {
    "item1": { "...": "JSON-DATA" }
  }
}
```

* **`body`** — the root of the transformation, evaluated to produce the output document.
* **`macro`** — named, reusable sub-templates (partials), invoked explicitly by name. Templates are **self-contained**: there is no cross-file import/export mechanism. Macro reuse across templates is a host-application concern (e.g. assembling a shared macro library into a template before invocation), not a language feature.
* **`data`** — optional embedded static data available to the template, distinct from the external input document.

---

## Processing Model

Each JSON node in the template body is processed according to its shape:

1. **Scalars** — passed through as-is.
2. **Arrays** — each element is processed; any element whose result is `NONE` is dropped; the output is an array of the remaining elements (this is how filtering is expressed — see [NONE and Truthiness](#none-and-truthiness)).
3. **Objects without an execution tag** (no `$` key) — the *default constructor*:
   * Each keyword is evaluated; if it is `NONE` or not a string, the pair is dropped.
   * Each value is evaluated; if the result is `NONE`, the pair is dropped.
   * Remaining key/value pairs are added, **in evaluation order**, to the output object.
4. **Objects with `$`** — dispatched to a processor:
   * `"$": true` → the **logic engine** (below).
   * `"$": false` → **literal subtree** — copied unchanged, no evaluation. Useful for static JSON and performance.
   * `"$": "macroName"` → **macro invocation** — the named macro runs in a fully isolated context, receiving only the parameters explicitly supplied at the call site.

### Escaping

Because `$` and expression prefixes (`expr:`, `sel:`, …) are reserved, templates need an escape for real data that happens to collide with them (e.g. a literal key named `$`, or a string value that legitimately starts with `expr:`). *(Exact escape syntax — e.g. `$$`, backslash-escaping — is an open item; see [Open Items](#open-items).)*

---

## The Logic Engine

```json
{
  "$": true,
  "set": {
    "var1": "EXPR-1",
    "var2": "EXPR-2"
  },
  "if": "EXPR",
  "data": "EXPR",
  "foreach": {
    "key": "KEY-VAR",
    "item": "ITEM-VAR",
    "in": "EXPR"
  },
  "case": [
    { "when": "COND-1", "then": "EXPR-1" },
    { "when": "COND-2", "then": "EXPR-2" }
  ],
  "body": "EXPR",
  "transform": "MERGE | FLATTEN | ... | NONE",
  "error": "EXPR"
}
```

### Fixed execution order

Regardless of the order keys are written in the JSON (JSON object key order is not part of the JSON spec, and JFTL does not rely on it *here* — see the contrast with `set`, below), a logic object is always evaluated in this order:

1. **`set`** — bind local variables. Assignments are evaluated **in author-written order**, so later variables may reference earlier ones (this is the one place JFTL *does* rely on JSON object key order — see [Ordering Guarantees](#ordering-guarantees)).
2. **`if`** — a guard. If the expression's result is falsy (see below), the entire node immediately evaluates to `NONE` and steps 3–7 are skipped entirely — including `error` (a false guard is a normal outcome, not a failure).
3. **`data`** — if provided, sets the "current" node (`_ctx.self`) for the new child context.
4. **`foreach`** — if present, iterates the `in` expression, binding `item` (and optionally `key`) per element, and re-runs steps 5–7 once per element, producing an array of per-element results.
5. **`case` / `body`** — `case` evaluates each `when` in order and uses the first matching `then`; if none match (or `case` is absent), `body` is used as the value.
6. The resulting value is combined with the context (parent context + newly bound variables) established in steps 1–4.
7. **`transform`** — optional post-processing of a `foreach` result array (see [Transform](#transform)).
8. **`error`** — if any error occurred during steps 1–7 (including errors propagated from nested macro calls or logic objects), this expression is evaluated and returned as the node's result. If `error` has no expression, a special `ERROR` sentinel is returned. *(Exact `ERROR` sentinel semantics — propagation vs. filtering — are an open item.)*

### NONE and Truthiness

* **`NONE`** is an engine-internal sentinel meaning "this value/pair does not exist in the output." It is **distinct from JSON `null`** — an expression that legitimately evaluates to `null` is preserved in the output; only `NONE` triggers omission.
* Falsy values for `if`, evaluated by JFTL **after** the underlying expression engine returns a value (CEL itself is strictly typed and does not coerce truthiness — this coercion is a JFTL-level rule applied to whatever CEL returns): `false`, `null`, `0`, `[]`, `{}`. *(Whether empty string `""` is falsy is an open item — current lean is to treat it as truthy, since JFTL otherwise treats "present but empty" as meaningfully different from "absent.")*
* **Idiomatic empty-collection omission**: rather than a dedicated `omitIfEmpty` flag, reuse `if` against a `set`-bound variable:
  ```json
  {
    "$": true,
    "set": { "items": "expr: some.expression" },
    "if": "expr: items",
    "foreach": { "item": "item", "in": "expr: items" },
    "body": "expr: item"
  }
  ```
  This works because `[]`/`{}` are already falsy — no new primitive needed, for either arrays or constructed objects.

### Transform

`transform` is a **string**, deliberately left open-ended (not a boolean, not initially a closed enum) to allow future growth toward Mongo-aggregation-style shape conversions (e.g. array↔object). Currently anticipated values:

* `NONE` — no post-processing (default).
* `MERGE` — combine an array of objects into a single object. Requires the `foreach` result to actually be an array of objects; applying it to a mismatched shape is a template error, not a silent no-op.
* `FLATTEN` — combine an array of arrays into a single array. Same shape-matching requirement as `MERGE`.

Design notes:

* `transform` values are a **spec-defined, shared vocabulary** — implementations must not invent non-standard values; new operations are added via the shared spec and conformance test suite, the same way new CEL host functions would be.
* Only one transform is applied per node. Chained transforms (e.g. flatten-then-merge) are expressed by nesting another logic object, not by a multi-step `transform` value.
* `MERGE` is likely to remain a core JFTL primitive (it's how array-of-key-value-results becomes a constructed object — a shape change the default object constructor doesn't otherwise support). `FLATTEN` is a more generic data operation and could plausibly be deferred to a CEL/host function instead, similar to `sort` (below).

### Macro invocation and isolation

* Macros always execute in a **fully isolated context**. The only things visible inside a macro body are:
  1. Explicitly supplied parameters from the call site.
  2. A fixed, spec-defined **global environment** (`_ctx.global`) — see below.
* There is **no ambient access** to the caller's tree, no implicit inheritance of `_ctx.parent`/`_ctx.top` from the call site. If a macro needs data from the caller's context, it must be passed explicitly as a parameter — this is a deliberate design choice (closures vs. pure functions): a macro's parameter list is its complete, auditable contract.
* This makes macros deterministic, cacheable, and — since they are side-effect-free — safely parallelizable by a host implementation without any `Parallel` construct in the language itself.

### Global (environment) values — `_ctx.global`

To avoid "parameter drilling" (threading a config value through many nested macro calls) without reintroducing mutable shared state:

* `_ctx.global` is assembled **once, before evaluation begins**, from:
  1. Host-injected constants (locale, tenant config, feature flags, etc., supplied by the embedding application at invocation time), plus
  2. Explicitly exported root-level bindings *(exact mechanism — e.g. a dedicated `global` block distinct from root `let`/`set` — is an open item; leaning toward requiring explicit export rather than making all root `set` bindings automatically global, to keep a macro's dependency surface fully declared).*
* `_ctx.global` is **immutable** for the duration of the run. There is no "put" operation. JFTL has no mutable global state — cross-iteration accumulation (running totals, dedup sets, etc.) is expressed as a fold/reduce over a `foreach` result, not as side-effecting writes during iteration.

### Context model (`_ctx`)

Every executable node runs within a context. A child context contains all visible parent variables, its own locally defined (`set`) variables, and runtime metadata:

```
_ctx.top      the input document root
_ctx.self     the "current" node (alias: _, shadowable by user variables; _ctx itself is reserved)
_ctx.parent   the enclosing node
_ctx.global   the immutable environment object (see above)
_ctx.index    current index (inside foreach)
_ctx.key      current key (inside foreach)
_ctx.depth    nesting depth
```

Contexts are immutable after creation — "moving current" through the tree (e.g. via `data`, or per-`foreach`-element) is modeled as descending into a **new** child context, never as mutating a pointer in place.

### Path navigation

* `sel:` paths are relative to `_ctx.self` by default (e.g. `sel:a.b`, `sel:a[1]`, `sel:a["special key"]`).
* Absolute access to the document root uses `_ctx.top` (e.g. `sel:_ctx.top.config.locale`).
* **Ascent** ("go up") is supported explicitly — via `_ctx.parent` chains or `../`-style relative syntax — to support join-like patterns that JSONPath/JMESPath cannot express (they have no parent axis).
  * Ascent past `_ctx.top` is a hard error, not silent clamping.
  * **Ascent inside an isolated macro stops at the macro's own parameter boundary** — a macro body cannot use `../` to reach into the caller's tree. This is essential; without it, macro isolation would be silently violated.
  * Two idioms, for two different join shapes: relative ascent (`../discounts`) for sibling access within a stable substructure; absolute paths from `_ctx.top` for reference-table lookups that shouldn't break if a template is refactored to add another nesting level.
* `sel:` is intentionally simpler than JSONPath/JMESPath (no wildcards, no recursive descent, no slicing) — escalate to `jmes:`/`jsonpath:` prefixes for advanced queries.

---

## Expression Model

Strings without a recognized prefix are literals. Recognized prefixes select an expression engine:

```
expr:   default expression engine
cel:    Common Expression Language
sel:    built-in lightweight selector
jmes:   JMESPath
jsonpath: JSONPath
```

* **CEL is the recommended default engine.** It is non-Turing-complete, side-effect-free, and guaranteed to terminate — the basis for JFTL's "secure evaluation" claim.
* The template language is independent of the expression engine; other engines (JMESPath, JSONPath, custom) may be registered per host implementation.
* CEL engine status across tier-1/tier-2 targets:

  | Language | Status |
  |---|---|
  | Java | Official (`cel-java`) |
  | Go | Official, reference implementation (`cel-go`) |
  | Python | Official as of March 2026 (`cel-expr-python`), plus a mature community fallback (`cel-python`/`celpy`) |
  | JavaScript/Node | **Community only** (e.g. `cel-js`) — the current open risk, since Node is tier-1 |
  | .NET | Community only (`cel.net`, `cel-net`) |

* **CEL is expression evaluation only** — it has no concept of `NONE`, no side effects, and no built-in `sort`. JFTL deliberately does not build its own expression language on top of it:
  * Functions like `first` are expressed via CEL composition (`list.filter(x, cond)[0]`), not a JFTL builtin.
  * Missing capabilities (e.g. `sort`) are deferred until real templates reveal the actual required shape, then added as **host-registered CEL functions** rather than new JFTL syntax. Host-registered functions inherit CEL's safety guarantees only if the host implementer preserves purity/termination — this is a documented responsibility, not automatic.
  * Chaining/composition happens either through CEL's own method-chaining within a single expression, or through named, nested JFTL stages (see below) — **not** through a JFTL-level pipe operator.

### Sequential composition ("pipelines")

JFTL deliberately has no flow-level pipe operator. The idiomatic way to express a multi-stage transformation is nested, named `set` stages:

```json
{
  "$": true,
  "set": {
    "stage1": { "$": true, "...": "..." },
    "stage2": { "$": true, "data": "expr: stage1", "...": "..." },
    "stage3": { "$": true, "data": "expr: stage2", "...": "..." }
  },
  "body": "expr: stage3"
}
```

This is strictly more expressive than a linear `|` pipe (any stage can reference any earlier stage — a DAG, not a line) and self-documenting (every intermediate value has a name), at the cost of verbosity relative to `|`. This trade is deliberate: unreadable pipe/stream chains (jq, complex Java streams) were an explicit anti-goal for this design.

---

## Ordering Guarantees

JFTL treats JSON object key order as **semantically meaningful** in two specific, deliberately scoped places — not generally:

1. **`set` bindings** are evaluated in author-written order, so later variables may reference earlier ones.
2. **Output object key order** is insertion order — following template-authoring order for constructed content, and source-document order for pass-through content. This is a conformance requirement, not best-effort, because gratuitous key reordering breaks golden-file/snapshot tests and produces noisy diffs in real-world API tooling.

The fixed execution *step* order of a logic object (`set` → `if` → `data` → `foreach` → `case`/`body` → `transform` → `error`) is **spec-defined and independent of written key order** — this is the TAL precedent, and it avoids depending on JSON ordering for structural sequencing.

Implementation requirements:

* All conformant parsers/serializers must preserve JSON object key order.
* This is well-supported by default in JavaScript (ES2015+, except integer-like keys), Python (`dict`, guaranteed since 3.7), and Java *if* an order-preserving library is used (e.g. Jackson or Gson defaults — plain `HashMap`-backed parsing is non-conformant).
* Secondary/tier-2 implementations (e.g. Perl) must use order-preserving parsing and storage throughout (e.g. `Tie::IxHash` / `Hash::Ordered`, plus a decoder that reads keys in document order) for **both template and input data parsing** — not just the template.
* The shared conformance test suite must include explicit ordering tests: dependent `set` variables, and round-tripping a non-alphabetically-ordered document through each implementation.

---

## Repository

```
jsonfold-template/
  spec/
  examples/
  tests/
  python/
  java/
  js/
  go/
  dotnet/
  perl/
```

A shared specification and conformance test suite is used by all implementations. Tier-1 (must always be correct and current): **Python, JavaScript/Node, Java**. Tier-2 (best-effort): Go, .NET. Others (e.g. Perl) are secondary.

---

## Open Items

Tracked design decisions still to be finalized:

* Exact escaping syntax for literal `$`-prefixed keys and literal strings colliding with expression prefixes (`expr:`, `sel:`, …).
* Whether empty string `""` is falsy for `if`.
* Exact shape of `_ctx.global` export (all root `set` bindings vs. an explicit export block).
* `ERROR` sentinel semantics (propagation vs. NONE-like filtering) when `error` has no expression.
* Whether `case` matching nothing *and* no `body` present is `NONE` or a hard error (current lean: error).
* Full `transform` vocabulary beyond `MERGE`/`FLATTEN` (array↔object conversions, sort, distinct, group-by) — to be added via spec + conformance tests as real use cases emerge, likely as host-registered CEL functions where the operation is generic rather than structural.
* String interpolation (Handlebars-style `{{ }}` embedded in literal strings) — currently out of scope; JFTL only supports whole-string expression prefixes.
* Node.js CEL implementation risk — no first-party engine currently exists; requires either vetting a community port against the conformance suite or an in-house/WASM-based solution.
