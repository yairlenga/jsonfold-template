# JFTL Navigation Rules

This document summarizes the navigation grammar and the reserved-name
conventions used to reach data, frame state, and datasets from within a
JFTL template. It reflects design decisions made during development,
including several deliberate simplifications — the reasoning is included
so these decisions aren't re-litigated later without a reason.

## Sigils

Every navigation expression starts with a sigil that says *where* to begin
looking, followed by an ordinary path (dot-separated bare keys, or
bracket-quoted keys for names with spaces/special characters, or `[N]`
for array indices).

| Sigil | Meaning |
|---|---|
| `$.` | Current data (`current` / `_` of the active frame) |
| `$^` | Absolute document root |
| `$<` | Parent frame's current data (**one hop only** — see below) |
| `$%` | Variable lookup, starting from the current frame |

Examples:
```
$.user.name
$.items[0].qty
$.user["first name"]
$/config.version
$^.total
$%orders.subtotal
```

## Bracket vs. dot notation

- A bare word segment requires a leading `.`: `$.foo.bar`
- A bracket segment (`[0]`, `["key with space"]`, `['key']`) is
  self-delimiting and needs **no** leading dot: `$.items[0]`,
  `$.user["first name"]`

Both single- and double-quoted bracket keys are supported and treated
identically — this exists mainly so JSON-embedded templates can avoid
escaping (`['key']` needs no backslash-escaping inside a JSON string;
`["key"]` does, if the key itself contains a double quote).

## `^` is single-hop only — no counted multi-hop

`$^` moves to the immediate parent frame's `current`. There is **no**
`$^^^` / multi-caret form. This was a deliberate simplification:

- Counted multi-hop navigation (`^^^`) is fragile — it silently points at
  the wrong frame the moment a nesting level is inserted or removed
  anywhere in between, with no error, just a different (wrong) value.
- Anything beyond one hop should be reached by **naming** the frame you
  want and referencing it directly (see below), not by counting.
- We do not add any special limit or lint warning against chaining
  (`_parent._parent...`, see below) beyond one hop. It's possible, and
  it's discouraged, but it isn't specially restricted — the general
  execution time/node limits (which bound *all* processing, including
  runaway loops and recursion) are considered sufficient. This is a
  correctness-education problem, not a resource-exhaustion problem, and
  there's no generic runtime guard against an author's navigation not
  meaning what they think it means.

## `$%` — variable lookup and frame vars

Every frame has a `vars` dict: the frame's own local bindings (from
`set`/`define`), plus a handful of **reserved** entries seeded
automatically at frame-creation time (see below).

`$%name` looks up `name`:
1. In the *current* frame's `vars`.
2. If not found, walks up the parent chain (result is cached along the
   way once resolved).

Naming a `LogicStatement`/`foreach` (via an `id`/name field) has **no
special mechanism** — it's sugar for registering a variable, under that
name, pointing at that frame's `vars` dict. From there, ordinary
navigation (`$%myframe.foo`) reaches into that dict like any other data.
This deliberately reuses machinery that already exists (variable lookup +
plain-value navigation) rather than introducing a second, parallel way to
address frames.

## Reserved names (all start with `_`)

**User-defined variable names may never start with `_`.** This is
enforced at compile time (`set`/`define` bindings with a leading
underscore are rejected). This turns "these names are reserved" into a
structural guarantee rather than a convention someone could accidentally
violate.

| Name | Resolves to | Notes |
|---|---|---|
| `_` | The current frame's `current` value | Fast path: never walked, never cached — always exactly one hop (the frame itself). Seeded fresh in every frame. |
| `_input` | The absolute input document | Only ever seeded at the root frame; every descendant reaches it via the ordinary walk (or a direct fast path to `top`, since its location is always statically known). |
| `_global` | The dataset namespace (template-embedded + runtime-injected datasets, merged, runtime overriding template on collision) | Same treatment as `_input` — seeded once at root, inherited everywhere. Naming it this way means datasets need **no separate mechanism at all** — they're reachable through the exact same `$%`/`get_var` path as any other variable. |
| `_parent` | The parent frame's `vars` dict | A dict, not a chainable frame object — see below. |
| `_top` | The root frame's `vars` dict | Same shape as `_parent`, but always the root regardless of current depth. |
| `_depth` | The current frame's nesting level (integer) | Exposed as a plain value, mirrors the internal `level` field. |
| `_local` | Forces a lookup to check **only** the current frame's own `vars`, with no walk up the parent chain | Opt-out of the normal scope-walk, for when you specifically want "is this bound *here*, not anywhere above." |

### Reserved names resolve to dicts, not chainable frames

`_parent` and `_top` resolve to a **plain `vars` dict** — inert data, not
a further-navigable frame object. This distinction matters:

- `_parent._` → the parent's current data (works: `_` is a normal key
  inside that dict, seeded like any other frame's).
- `_parent._parent._parent...` → **also works**, mechanically, since each
  frame's `vars` dict does contain its own `_parent` entry pointing at
  the next one up. This is the "single-hop only" rule resurfacing via a
  different door — it's allowed, not specially blocked (see the
  discussion above), but it carries the same fragility as counted `^^^`
  ever did. Prefer naming a specific ancestor and referencing it directly
  wherever the intent is "I need a specific frame," rather than counting
  hops through `_parent`.

### `_input` / `_global` never require the general walk-and-cache path

Because their location is always statically known (root only), lookups
for these two names skip the general recursive parent-walk entirely —
they resolve directly via the frame's `top` reference. `_` skips the walk
for the opposite reason: it's always local, never anywhere else. Neither
is cached, because neither benefits from caching — both are already O(1).

## Fixed vocabulary, not a general plugin surface

Navigation (`$.`/`$/`/`$^`/`$%`) is one specific `ExprEngine`
implementation among possibly several (alongside `$pyrun:` and, later,
CEL). Its sigil grammar is closed and specific to this one engine — other
engines are free to have entirely different syntax; there's no
requirement that `$.`/`$^`/`$%` mean anything to any other expression
engine.
