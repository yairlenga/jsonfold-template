# JFTL Variable Reference

This document covers variable scope and the reserved `_`-prefixed names
available in every frame. Path syntax for reaching a variable or a data
key (`$foo`, `$.foo`, segment forms) is covered in `NAVIGATION.md`, not
here — this document is about what's bound, not how to spell a
reference to it.

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
| `_global` | The dataset namespace (template-embedded + runtime-injected datasets, merged, runtime overriding template on collision) | Same treatment as `_input` — seeded once at root, inherited everywhere. Naming it this way means datasets need **no separate mechanism at all** — they're reachable through the exact same `$name` path as any other variable. |
| `_parent` | The parent frame's `vars` dict | A dict, not a chainable frame object — see below. |
| `_top` | The root frame's `vars` dict | Same shape as `_parent`, but always the root regardless of current depth. |
| `_depth` | The current frame's nesting level (integer) | Exposed as a plain value, mirrors the internal `level` field. |
| `_local` | Forces a lookup to check **only** the current frame's own `vars`, with no walk up the parent chain | Opt-out of the normal scope-walk, for when you specifically want "is this bound *here*, not anywhere above." |

## Reserved names resolve to dicts, not chainable frames

`_parent` and `_top` resolve to a **plain `vars` dict** — inert data, not
a further-navigable frame object. This distinction matters:

- `_parent._` → the parent's current data (works: `_` is a normal key
  inside that dict, seeded like any other frame's).
- `_parent._parent._parent...` → **also works**, mechanically, since each
  frame's `vars` dict does contain its own `_parent` entry pointing at
  the next one up. This is allowed, not specially blocked, but counting
  hops this way is fragile — it silently points at the wrong frame the
  moment a nesting level is inserted or removed anywhere in between, with
  no error, just a different (wrong) value. Prefer naming a specific
  ancestor and referencing it directly wherever the intent is "I need a
  specific frame," rather than counting hops through `_parent`.

## `_input` / `_global` never require the general walk-and-cache path

Because their location is always statically known (root only), lookups
for these two names skip the general recursive parent-walk entirely —
they resolve directly via the frame's `top` reference. `_` skips the walk
for the opposite reason: it's always local, never anywhere else. Neither
is cached, because neither benefits from caching — both are already O(1).