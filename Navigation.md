# JFTL Navigation Rules

This document summarizes the navigation grammar and the reserved-name
conventions used to reach data, frame state, and datasets from within a
JFTL template. It reflects design decisions made during development,
including several deliberate simplifications — the reasoning is included
so these decisions aren't re-litigated later without a reason.

Navigation is one specific expression engine among several (see
`EXPRESSION.md` for how engines are selected and registered). Logic
statements — `set`/`if`/`data`/`foreach`/`case`/`body`/`transform`/
`error` — are covered in `LOGIC.md`, not here; this document is only
about reaching a value once you're inside an expression.

## Sigils

Every expression begins with `$`. If nothing follows that matches an
`<engine>=` prefix (see `EXPRESSION.md`), the expression is a
**navigation path**, handled by the built-in navigation engine.

| Sigil | Meaning |
|---|---|
| `$foo` | Current scope, checked as a variable first, falling back to a key on current data. **First segment only** — see below. |
| `$^` | Absolute document root (structural hop only — see below) |
| `$<` | Parent frame's current data, one hop only (structural shortcut for `_.parent` — nothing more, nothing less) |
| `[$foo]` | Dynamic key/index lookup — dereferences variable `foo` and uses its runtime value as the next path segment (SQL/JSON-path style) |

Bare `$` with nothing following is **invalid** — a compile error, not
"current data with no navigation."

Examples:
```
$foo.bar
$user.name
$orders[0].price
$^.total
$<.customer.id
$items[$idx]
```

## Bracket vs. dot notation

- A bare word segment requires a leading `.`: `.foo.bar`
- A bracket segment (`[0]`, `["key with space"]`, `['key']`, `[$var]`) is
  self-delimiting and needs **no** leading dot: `$foo.items[0]`,
  `$foo.user["first name"]`

Both single- and double-quoted bracket keys are supported and treated
identically — this exists mainly so JSON-embedded templates can avoid
escaping (`['key']` needs no backslash-escaping inside a JSON string;
`["key"]` does, if the key itself contains a double quote).

## Bare `$foo` — first-segment variable resolution

The first segment only of a bare `$foo...` path is checked against the
frame's variable scope (`vars`, parent-chain-walk-and-caching) before
falling back to a key on the current frame's data.

- `$foo` → is `foo` a variable in scope? If yes, that. If no, `foo` as a
  key on current data.
- `$foo.bar` → `foo` resolved as above; `.bar` is **always** a plain data
  key on whatever `foo` resolved to — no further var-checking past the
  first segment.

> **Open question — not yet decided:** on collision (a variable *and* a
> data key both named `foo` are available), which wins? This needs an
> explicit rule before implementation, since it changes observable
> behavior silently depending on scope contents. Pick one and record it
> here before building this.

## `[$foo]` — dynamic key/index lookup

Inside brackets, `$foo` dereferences a variable and uses its runtime
value as the path segment — same convention as SQL/JSON path dynamic
member access (Postgres, Oracle SQL/JSON).

- **Strict, var-only** — no fallback to a data key literally named
  `foo`. If `foo` isn't a bound variable, this is an error (or MISSING,
  consistent with how a bad key lookup is already handled — TBD which).
- **Type-resolved at eval time** — the variable's runtime value decides
  whether this behaves as a key (string) or index (int) segment. This
  requires a segment type that defers the key-vs-index decision to
  render time, rather than deciding it at compile time.

## `$^` and `$<` — structural hops only, no variable semantics

Both are **pure frame-hop shortcuts** — "nothing more, nothing less."
Neither checks variables; both always mean "jump to this frame's current
data," full stop.

- `$^` → absolute document root
- `$<` → parent frame's current data, **one hop only**

What follows `$^`/`$<` must be `.`, `[`, or nothing at all — **never** a
bare word. `$^foo` is invalid; the correct form is `$^.foo`. This is
consistent with the bracket-vs-dot rule above (bare words always require
a leading dot); it's called out explicitly here because bare `$foo` (no
`^`/`<` prefix) behaves differently — it *is* allowed to start with a
bare word, since it does its own variable check first. `$^`/`$<`
deliberately don't get that treatment, to keep structural navigation
predictable and free of scope-dependent surprises.

## `^` and `<` are single-hop only — no counted multi-hop

There is **no** `$^^^` / multi-caret form, and no counted multi-`<` form.
This is a deliberate simplification:

- Counted multi-hop navigation is fragile — it silently points at the
  wrong frame the moment a nesting level is inserted or removed anywhere
  in between, with no error, just a different (wrong) value.
- Anything beyond one hop should be reached by **naming** the frame you
  want and referencing it directly (see below), not by counting.
- There is no special limit or lint warning against chaining
  (`_parent._parent...`, see below) beyond one hop. It's possible, and
  it's discouraged, but it isn't specially restricted — the general
  execution time/node limits (which bound *all* processing, including
  runaway loops and recursion) are considered sufficient. This is a
  correctness-education problem, not a resource-exhaustion problem, and
  there's no generic runtime guard against an author's navigation not
  meaning what they think it means.

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
| `_global` | The dataset namespace (template-embedded + runtime-injected datasets, merged, runtime overriding template on collision) | Same treatment as `_input` — seeded once at root, inherited everywhere. Naming it this way means datasets need **no separate mechanism at all** — they're reachable through the exact same bare-`$name` path as any other variable. |
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

Navigation's sigil grammar (bare `$foo`, `$^`, `$<`, `[$foo]`) is closed
and specific to this one engine. Other engines are free to have entirely
different internal syntax after their `$<engine>=` prefix; there's no
requirement that navigation's sigils mean anything to any other
expression engine. See `EXPRESSION.md` for how other engines are invoked
and registered.