# Navigation Condition Suffixes

Navigation expressions may be followed by an optional condition suffix.
Conditions support standard comparison operators together with
JFTL-specific predicates introduced by `is`. This keeps navigation and
testing as separate grammar elements while providing familiar comparison
syntax, without adopting a second grammar (e.g. JSONPath filters) for it.

Notice (error) values always pass through unchanged from the underlying
nav evaluation, for every form below — a suffix never introduces a new
error condition of its own.

## Forms

```
NAV                       # bare — existing eval_bool falsy rule (Missing/null -> false)

NAV == LITERAL            # typed equality
NAV != LITERAL            # negation

NAV <  LITERAL            # ordering (planned)
NAV <= LITERAL
NAV >  LITERAL
NAV >= LITERAL

NAV is TYPE                # type check
NAV is not TYPE

NAV is empty              # array/object only
NAV is nonempty           # independent predicate, NOT the negation of `is empty`

NAV is missing             # distinguishes Missing from null
NAV is present             # independent predicate, NOT the negation of `is missing`
```

RHS is literal-only for now. `NAV`-vs-`NAV` comparison is out of scope.
Anything beyond this grammar (boolean logic, functions, regex, etc.)
routes to `$py=` / `$pyeval=`.

Scope: usable anywhere a nav expression compiles (not restricted to
`if`/`case`/`when`), so a suffix's boolean result can be captured via
`set` and reused later.

## Semantics table

| Form              | Missing | null  | `[]`/`{}` | non-empty array/object | any string (incl. `""`) | other scalar |
|-------------------|---------|-------|-----------|-------------------------|--------------------------|--------------|
| `is empty`        | true    | true  | true      | false                   | TBD (error or false)    | TBD (error or false) |
| `is nonempty`     | false   | false | true      | true                    | true                     | true         |
| `is missing`      | true    | false | false     | false                   | false                    | false        |
| `is present`      | false   | true  | true      | true                    | true                     | true         |
| `is TYPE`         | false   | false | per actual type | per actual type    | per actual type          | per actual type |

## Equality (`==` / `!=`)

- Typed comparison — `5` (int) and `5.0` (float) are distinct values.
- **Exception:** Missing and null are treated as equal to each other for
  `==`/`!=` only. `$.foo == null` is true whether `foo` is absent or
  explicitly null.
- This equivalence does **not** extend to `is TYPE`, `is empty`,
  `is missing`, or ordering — those keep Missing and null semantically
  distinct per the table above.

## `is empty` vs `is nonempty`

These are **not** a strict complementary pair:

- `is empty` is a *structural* check, scoped to array/object (plus the
  Missing/null catch-all, since both represent "nothing here").
- `is nonempty` is a *presence* check — true for anything that is not
  Missing and not null, regardless of type. `$.name is nonempty` on
  `""` is `true`, because a present-but-blank string is still present.

## Design principle: no suffix is defined as another's negation

Every form has its own standalone truth table, including its own
explicit Missing/null entry. None are defined as `not(other-form)`.
This matters because several natural-seeming negations break down once
Missing enters the picture — e.g. `>` is not simply `not(<=)`, since
Missing/null aren't comparable at all, so "not incomparable" isn't a
well-defined `true`. `is nonempty` and `is present` are named and
specified independently for the same reason, not as shorthand for
`is not empty` / `is not missing`.

## Open items

- Whether `is empty` on a string or other scalar is a compile-time
  error (loud-failure default) or silently `false`.
- **Pending evaluation against CEL** (candidate expression engine for
  the commercial server engine) before further build-out — CEL may
  already provide a better-fitting solution for some/all of the below,
  rather than maintaining a second bespoke comparator layer:
  - Ordering operators (`<`, `<=`, `>`, `>=`) — including Missing/null
    semantics, which don't obviously inherit equality's Missing≡null rule.
  - `matches RE` — regex predicate; open questions on anchoring
    (full-match vs search) and non-string NAV behavior (error vs false).
  - Integer range literals (`NAV in X..Y`, `NAV in X...Y`, Ruby-style
    inclusive/exclusive) — deliberately scoped to integers only, to
    avoid float-literal lexing ambiguity and lexicographic-vs-semantic
    ordering questions for strings/dates.
  - `LIKE PATTERN` — likely redundant with `matches` (glob is a strict
    subset of regex); if wanted, probably better as sugar over `matches`
    rather than a second independent pattern language.
  - `BETWEEN` — likely redundant once ordering operators + inclusive/
    exclusive semantics are settled; would become near-free sugar at
    that point rather than needing separate design work now.
- `NAV`-vs-`NAV` comparison: deferred, no concrete use case yet.
