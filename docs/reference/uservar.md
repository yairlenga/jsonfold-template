# User Variables

This page describes how JFTL stores and resolves user-defined variables at
render time: the namespace concept, how a Logic Statement creates a new
namespace, the three ways to put a variable into it, and the two ways to
read it back.

---

## 1. Namespaces (a.k.a. Frames)

At render time, every point in the template tree is evaluated against a
**Frame** (`RuntimeContext` in `model.py` / `Frame` in `core.py`). A Frame
is a namespace: it holds a `vars` dict, and a link (`parent`) to the Frame
it was created from. Frames form a chain all the way back to the root
Frame created for the top-level `render()` call.

```
root Frame  (vars: _input, _top, _datasets, ...)
   └── child Frame  (vars: whatever "set"/"foreach" added)
          └── child Frame  ...
```

**Resolution rule:** looking up a variable named `foo` starts at the
*current* Frame and walks up the parent chain, stopping at the first
Frame whose `vars` contains `foo`. The value found there — closest scope
wins — is the result; if no Frame in the chain defines it, the lookup
resolves to `Missing`.

This is exactly the same rule used by the `pyrun`/`pyeval`/`py`
expression engines: they build their evaluation namespace by walking the
same Frame chain from the root down, letting closer scopes overwrite
farther ones (`_build_env` in `py_run.py`, `_build_env` in `py_expr.py`).

A Frame is *not* created for every statement — only specific constructs
create one. Everything else (plain literals, navigation, interpolation,
`check`/`data` inside a Logic Statement, etc.) evaluates against the Frame it
was given.

---

## 2. A Logic Statement (`"$": true`) creates a new namespace

Every time a Logic element (`{"$": true, ...}`) is evaluated, it calls
`child_state()` on its enclosing Frame, producing a **new child Frame**
before Stage 1 (`set`/`check`) runs:

- The new Frame's `vars` starts essentially empty (just internal
  bookkeeping entries like `_parent`/`_local`).
- Its `parent` is the Frame the Logic Statement was evaluated in.
- Any variables it defines live **only** in this new Frame — they are
  local to that Logic Statement and disappear once it finishes; they do
  not leak into the enclosing scope.
- A *nested* Logic Statement (e.g. as the value of a `set` entry) creates
  yet another child Frame, whose parent is this one — so it can still
  read everything the outer Logic Statement defined, via the chain.

---

## 3. Adding variables to the namespace

Within one Logic Statement's Frame, variables can be added in three ways.
All three write into the **same** Frame — the one created for that Logic
Statement — not into separate per-iteration sub-Frames.

### (1) `set`

```json
"set": { "VAR_NAME": "EXPR" }
```

Each entry is evaluated once, in Stage 1, and assigned into the current
Frame's `vars`.

### (2) `foreach` — `var` and `key`

```json
"foreach": {
  "in": "$.items",
  "var": "item",
  "key": "idx"
}
```

- `var` names the variable bound to **each item's value** on every
  iteration. If omitted, the item is not bound to a name at all — it
  simply becomes the current value (`$`/`_`) for that iteration.
- `key` names the variable bound to the **item's key or index**. If
  omitted, it still defaults to `_key` — the loop always exposes the
  current key/index under that name unless you override it.

Both are (re)assigned on every iteration, in the same Frame, so later
iterations overwrite earlier ones — they hold the *current* item/key, not
a per-iteration snapshot.

### (3) `foreach` → `update`

```json
"foreach": {
  "in": "$.items",
  "var": "item",
  "out": "EXPR",
  "update": { "VAR_NAME": "EXPR" }
}
```

`update` is nested *inside* the `foreach` object. Each entry is
(re-)evaluated **after** the per-item `out`, once per iteration, and
assigned into the same Frame's `vars` — making it the standard way to
build a running accumulator across iterations (the accumulator can then
be read by later iterations, or by the outer `out`/`case` stage once the
loop finishes).

---

## 4. Variable naming — the "id" format

Variable names (`set` keys, `foreach` `var`/`key` names) must look like an
identifier:

```
^[A-Za-z]\w*$
```

— a letter, followed by any number of letters/digits/underscores. This is
enforced for `foreach`'s `var`/`key` names, and matters generally because
the same name is used both for `$name` navigation and as a literal Python
variable name inside `$py=`/`$pyeval=`/`$pyrun=` expressions — so it must
be a legal identifier in both worlds.

---

## 5. Reading variables back

### Via navigation

```
$foo         → lookup_var("foo") on the current Frame chain
$foo.bar[0]  → same lookup, then walks .bar / [0] on the result
```

Note the distinction from data access: `$.foo` reads a field of the
*current data value* (`_`), while `$foo` (no dot) reads the *variable*
named `foo` from the namespace chain. `$^` reads the original top-level
input; `$<` reads the parent's current data; `$%` reads the Frame itself.

### Via Python expressions (`$py=`, `$pyeval=`, `$pyrun=`)

Every variable visible on the Frame chain (root to current, closest wins)
is exposed as an ordinary Python variable in the expression's evaluation
namespace, alongside `_` (current value) and `_input`:

```json
"$py=foo + 1"
```

---

## 6. Examples

### 6.1 Set a variable to a constant

```json
{
  "$": true,
  "set": { "greeting": "hello" },
  "out": "$greeting"
}
```

Input: (any) → Output: `"hello"`

### 6.2 Set a variable to a composite value

```json
{
  "$": true,
  "set": {
    "profile": { "name": "$.name", "id": "$.id" }
  },
  "out": "$profile"
}
```

Input: `{"name": "Ada", "id": 7}`
Output: `{"name": "Ada", "id": 7}`

### 6.3 Set a variable via an arithmetic Python expression

```json
{
  "$": true,
  "set": {
    "x": "$.a",
    "y": "$.b",
    "sum": "$py=x + y"
  },
  "out": "$sum"
}
```

Input: `{"a": 3, "b": 4}` → Output: `7`

(`x` and `y` were themselves just set via `set`, and are visible inside
`$py=` as plain Python names because they live in the same Frame.)

### 6.4 Set a variable to the result of another Logic Statement

```json
{
  "$": true,
  "set": {
    "label": {
      "$": true,
      "check": "$.active",
      "out": "Active",
      "fallback": "Inactive"
    }
  },
  "out": "$label"
}
```

Input: `{"active": true}` → Output: `"Active"`
Input: `{"active": false}` → Output: `"Inactive"`

The inner `{"$": true, ...}` gets its own child Frame (a child of the
outer Logic Statement's Frame) while it evaluates; only its final result
— not any variables it might itself define — is assigned to `label` in
the outer namespace.

### 6.5 `foreach` `var`/`key` plus `update` accumulator

```json
{
  "$": true,
  "set": { "running": 0 },
  "foreach": {
    "in": "$.nums",
    "var": "n",
    "key": "idx",
    "out": "$py=f'{idx}:{n}'",
    "update": { "running": "$py=running + n" }
  },
  "out": "$running"
}
```

Input: `{"nums": [1, 2, 3]}` → Output: `6`

`n` and `idx` are rebound each iteration; `running` is updated after each
item's `out` and still holds its final value once the loop ends — which
is what the outer `out` returns, overriding the loop's own collected
per-item output.