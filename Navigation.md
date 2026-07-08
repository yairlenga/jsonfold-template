# JFTL Navigation Rules

This document summarizes the navigation grammar used to reach data, frame state, and datasets from within a JFTL template.

Navigation is one specific expression engine among several (see
`Expression.md` for how engines are selected and registered). The Logic elements use expression to dynamically resolve values at rendering time, and is covered in `Logic.md`.

- Every navigation expression starts with a head reference.
- The navigation expression may be followed by 1 or more segments

It is possible to identify navigation element by the following rules if it starts with the following regex (white spaces in this pattern are for readablity only, and are not significant, similar to python re.VERBOSE or Perl/PCRE `/x`)

> `\$   ( | ^ | < | \w+ )   ( $ | \[ | \. )`

## Heads — how a navigation path starts

Every navigation expression starts with a head reference.

| Head | Symbol | Examples | Meaning |
|---|---|---|---|
| Current | `$.` | `$.foo`, `$[...]` | Current frame's data |
| Root | `$^` | `$^.foo`, `$^[...]` | Absolute document root. |
| Parent | `$<` | `$<.foo`, `$<[...]` | Parent frame data
| Variable | `$foo` | `$foo.bar`, `$foo[...]` | Start at variable `foo`

The head symbols `$.`, `$^`, `$<`, and `$foo` can be used as the complete navigation expression, as the segment list can be of zero length.

## Segments — the grammar for everything after the head

Every step of a path — whether it's the first thing after `$.`/`$^`/`$<`,
or any subsequent step in a longer path — is one of these four forms:

| Form | Meaning |
|---|---|
| `.foo` | Plain key, bare word. Requires the leading `.`. |
| `["a@b c.d"]` | Quoted key — for names with spaces or characters that can't appear in a bare word. Both quote styles are accepted and treated identically. |
| `[2]` | Array index. Including negative indices |
| `[$xyz]` | Dynamic key or index — dereferences variable `xyz` at render time and uses its value as the segment.|

Note: Segments are connected with a `.` or with bracket `[`. Therefore, the expression `$.[...]` (dot immediately before a bracket) is **not**
valid — a bracket segment never follows a dot, matching standard
JSONPath.

### Array Indices

When referencing arrays, negative indices will be computed based on the current array length, meaning `-1` will reference the last element. It is an error to reference an array with non-integer index. Indexes which are out of range will result in `MISSING`. Using array indexing on `MISSING`, `null` will result in `MISSING`, and provides null-safe navigation.

### Object indices

When referencing an object, the key must be a string. It is an error to reference an object with non-string index. Non-existing keys will result in `MISSING`. Using object indexing on `MISSING`, `null` will result in `MISSING`, and provide for null-safe navigation.

### `[$xyz]` — Variable Reference

`[$xyz]` is a variable dereference. If `xyz` isn't a bound variable, it will resolve to a `MISSING` value, consistent with how any other failed lookup is handled.
This mirrors SQL/JSON-path dynamic member access (Postgres,
Oracle SQL/JSON)

Whether this behaves as a key or an index depends on that value's runtime type (string vs. integer). Accessing an array with non-integer index, or accessing an object with non-string index are errors.
