# JFTL 0.3 Release TODO

Scope: current Logic element, Navigation expressions, simpleeval-tier Python expressions, CLI. Recursive navigation, string interpolation beyond nav-only `${...}`, streaming TOML, and streaming-output-to-files are the only items explicitly deferred past this release; everything else below is in scope.

---

## 1. Engine Bugs (fix before anything else)

**Compile errors aren't caught.** `JFTLEngine.compile()` never wraps `self._compile(...)` in a try/except for `CompileError`, so a malformed template raises an exception instead of returning `list[Error]` as the `Engine` ABC promises. This needs to be fixed first since several other items below (exit codes, error reporting) depend on compile errors surfacing cleanly rather than crashing the process.

**Only `$.` navigation head is dispatched.** `$^` (root), `$<` (parent), and `$foo` (variable head) are documented in `Navigation.md` but not wired into `_compile()` — they currently fall into the generic `else` branch and produce a misleading "lambda expressions are not allowed" error. All four heads need to route to `NavigationExprNode` before nav expressions can be called complete.

**`Up` segment parsing doesn't match the locked head model.** `runtime.py`'s leading-`^`-count parsing predates the `$^`/`$<` head split in `Navigation.md`. Needs to be reconciled: `$<` = exactly one parent hop, `$^` = absolute root, no multi-`^` chaining implied by the regex anymore.

**`foreach` shape/transform mixups in `logic.py`.** `do_dict = self._transform == "OBJECT"` should key off shape, not transform (transform is `MERGE|FLATTEN|REMOVE_MISSING`, shape is a different axis entirely — see §2). `start`/`stop`/`limit` are compiled via `compiler.condition(...)` but are numeric expressions, not booleans. The `stop_index` computation has an operator-precedence bug that only works by accident in the current multiply-table test. `foreach.shape` is compared as lowercase `"range"` in code against the uppercase convention (`RANGE`/`ARRAY`/`OBJECT`) locked elsewhere — code, docs, and `multiply_jftl.json` currently disagree with each other.

**`MISSING` isn't dropped from `OBJECT`-shaped foreach results.** `_eval_foreach`'s dict branch assigns `dict_result[new_key] = new_val` unconditionally, even when `new_val` is `Missing`. This must be fixed as a prerequisite for the `_skip`/`REMOVE_MISSING` work in §2.

**`$pyrun=` has no trust gate.** It's dispatched unconditionally in `engine.py` today, contradicting the three-tier design (`$py=` always on, `$pyeval=`/`$pyrun=` opt-in via `--trust`). Needs an actual check before release — this is the one bug with real security weight.

**Misc `core.py` issues:** `Frame.child_frame` has a mutable default argument (`vars: dict = {}`); `Frame.__exit__(self)` has the wrong signature and calls `self.reset(self)` against a `reset(self)` that takes no extra arg — will crash on first real use as a context manager; `create_engine(strict=True)` never passes `strict` into `JFTLEngine()`, and its docstring contradicts its own default.

---

## 2. Sentinel & Missing-Value Semantics

**Rename constants for consistency.** `MISSING`/error constants become `_missing`/`_error`, injected into Python-tier eval environments alongside `_`/`_input`, matching the existing reserved-name convention. `_error` stays a bare, unparameterized sentinel for v1 — no `_error("message")` constructor yet.

**New `_skip` sentinel.** Unconditionally removed from both arrays and objects when used as a statement/body result — distinct from `MISSING`, which is *kept* (and converted to `null` only at final serialization). Applies anywhere a statement body can resolve to a value, not just inside `foreach`.

**Defer null conversion to the render boundary.** This is an architecture change, not just a rename: `ArrayStatement.eval()` currently converts `Missing → None` eagerly, inline. That has to stop — `MISSING` must survive as a live sentinel all the way up the tree. Conversion to JSON `null` happens only at serialization (`render_to()` / JSON emission), not in `render()`'s return value — API consumers get the raw tree with `MISSING` distinguishable from `null`. This must land before `REMOVE_MISSING` (§3) can work, since that transform needs to inspect elements for "was this missing" before they've been nulled out.

**Uncaught template-level errors are a distinct, deliberate outcome — not an engine failure.** If a template's own `error` value reaches the top uncaught, that's the *user's* explicit signal that downstream processing should not continue; it's different from an engine-detected `RenderError` (`NOT_ITERABLE`, `SHAPE_MISMATCH`) and different again from an unexpected Python exception. If the template author catches the error themselves (via `default`/`case`) and emits normal JSON, that's ordinary success — exit 0, error communicated only through the JSON body. `Status.error` on the existing `Status` dataclass looks like the right place for `render()` to report this distinction to the CLI.

---

## 3. Foreach & Transform Changes

**Implicit int-to-range inference.** When the resolved `in` expression (or the `frame.current` fallback when `in` is omitted) evaluates to a bare integer, `foreach` treats it as `range(0, n)` — applies even when `in` is omitted entirely. Explicitly **does not** extend to strings (no char-walking); a string in this position still hits the existing `NOT_ITERABLE` error path. Worth a dedicated test case since it's the kind of thing someone will accidentally rely on if the boundary isn't obviously enforced.

**`shape` becomes optional and assertive, not directive.** With int-inference removing the need for `shape: RANGE` to *drive* behavior, `shape` is repurposed as an optional runtime type-check: if present, the engine verifies the resolved iteration target's actual type against it (`ARRAY`, `OBJECT`, `RANGE`, extensible later) and raises a typed `SHAPE_MISMATCH` error on mismatch, rather than proceeding or silently returning `MISSING`. Omitted `shape` = accept-anything, as today. This gives template authors an explicit, fail-loud input contract without needing general type-introspection in navigation expressions. `start`/`stop`/`limit` remain unchanged and apply independently of whether `shape` is present.

**New `transform=REMOVE_MISSING`.** Filters `MISSING` elements out of arrays and out of objects with missing values, on top of the standard array/object drop rules already locked. Uppercase to match `MERGE`/`FLATTEN`. Depends on §2's deferred-null-conversion work landing first.

---

## 4. Expression Engine Selection

**Template-level default engine for `$=`.** A template can declare its default dispatch target (`py`, `pyeval`, `pyrun`; CEL later) rather than requiring every bare `$=` expression to specify one. Needs a firm answer on trust-fallback behavior: if a template declares a trusted default (`pyeval`/`pyrun`) but the engine is invoked without `--trust`, this should be a hard `CompileError` ("template requires trusted engine 'pyrun' but --trust not set"), not a silent downgrade to paranoid mode — silent semantic changes based on invocation flags are exactly the failure mode this design should avoid.

---

## 5. Nav-Only String Interpolation

**Scoped-down `${...}` interpolation, in scope for 0.3.** Embedded spans inside otherwise-literal strings (`"Hello, ${user.name}!"`), checked only on strings that don't already match an existing whole-string `$`-prefix form. Reuses the existing `$$` sigil as the literal-dollar escape — no new escape mechanism. Content inside `${...}` is navigation-expression-only (no `$py=`/`$pyrun=` dispatch), with an implicit current-data head so `${user.name}` reads the same as every other templating engine's interpolation; explicit heads (`${^.foo}`, `${<.bar}`, `${myvar.baz}`) remain available. Multiple spans per string are allowed.

**Strict, not clever, type coercion.** Only scalars (`str`/`int`/`float`/`bool`) are stringified; `null` becomes empty string. A `MISSING` or `Error` value resolving inside `${...}` is a **runtime error**, not silently empty-stringed — forces authors to add a `default` upstream rather than producing output with a silent hole. Non-scalar (object/array) results are also a runtime error rather than auto-JSON-stringified; anyone wanting that can reach for `$py=` explicitly. This scoping deliberately excludes embedded engine dispatch and container auto-stringification — the parts that would otherwise turn this into a new expression-engine surface instead of a bounded grammar extension.

---

## 6. CLI Input Formats

**JSONL input.** Mostly already validated via the test-corpus notes (`for line in f`); needs to be exposed as a CLI input-format flag, routing each line through `render()` as a separate top-level input.

**Concatenated multi-document input.** A distinct parser from JSONL (whitespace/concatenation-delimited JSON values, no newline requirement) — needs its own detection/flag rather than being merged with JSONL, to avoid confusing failures on input that's one format but not the other.

**Datasets via `key=@filename`.** CLI sugar over the existing `Engine.add_dataset()` API. Input format for each dataset file should be inferred from its extension (`.json`, `.jsonl`, later `.toml`), so this composes with the input-format work above rather than needing a separate flag per dataset.

**TOML input — deferred, or input-only if included.** Flagging a real semantic mismatch: TOML has no `null` representation at all, and stricter typing (real dates, no mixed-type arrays in some implementations) makes round-tripping non-trivial. Combined with `MISSING` needing to survive to the serialization boundary (§2), TOML *output* especially needs a defined lossy-conversion policy that doesn't exist yet — scope to input-only if it makes the cut for 0.3, otherwise defer entirely.

---

## 7. CLI Streaming Output

**Opt-in, CLI-only, file-per-key.** Enabled via a flag (e.g. `--stream-to-files`) plus a required target folder argument — never part of the `Engine` API, never inferred. When the top-level render result is an object, each key becomes `<sanitized-key>.json` in the target folder, filenames only (no path separators honored as directories). When the top-level result isn't an object, output falls back to stdout as today.

**Invalid keys degrade gracefully, never lose data.** A key containing path separators or other unsafe characters is rejected: a one-line warning goes to stderr per bad key (e.g. `key "/a/b" not allowed`), and the value stays in the result rather than being dropped. Valid keys in the same render still get written normally.

**Stdout carries the residual object.** After streaming, stdout outputs the original top-level object minus every key successfully written to a file — naturally reduces to "just the rejected keys" in the common case. No collision detection between output files (duplicate sanitized keys, or pre-existing files in the folder) — the user owns the target folder and should point at a scratch/tmp directory if that's a concern.

**`MISSING` at the top level serializes to `null` and writes normally** — not treated as a rejected key, not folded into the stdout residual. It's just a valid JSON document like any other value at that key.

---

## 8. Exit Codes

Final table, in order of least-to-most severe / least-to-most "the engine's fault":

| Code | Meaning |
|---|---|
| 0 | Success — includes templates that catch their own `error` and emit normal output |
| 1 | IO / parse error — input or template file not found, or fails to parse as valid JSON (template JSON-syntax errors live here, *not* in compile error — they fail before JFTL semantics ever engage) |
| 2 | Invocation error — bad CLI arguments |
| 3 | Compile error (`CompileError` — valid JSON, invalid JFTL semantics) |
| 4 | Runtime error (`RenderError` — engine-detected: `NOT_ITERABLE`, `SHAPE_MISMATCH`, etc.) |
| 5 | Injected error, uncaught — the template's own `error` reached the top level unhandled |
| 6 | Unexpected Python error — genuine engine bug, uncaught exception outside the above categories |
| 7 | Partial success — streaming output rejected one or more keys |

This depends on `RenderError`/`Status.error` being able to distinguish "engine detected a problem" (4) from "template author declared a problem via `error`" (5) — currently both paths look identical at the exception level and need to be split, likely via a distinct exception subclass or a reserved `Error.code` convention for user-injected errors.

---

## 9. Documentation

**`EXPRESSION.md`** — scoped but unwritten. No longer optional now that three expression tiers plus template-level default selection (§4) are shipping together; needs to cover engine registration, dispatch (`$engine=`), and the trust-gate behavior.

**Reconcile `Navigation.md` with the actual implementation** once §1's head-dispatch and `Up`-parsing fixes land — the doc currently describes a grammar the code doesn't fully implement.

**Test corpus expansion** — the multiplication-table gold test is the only end-to-end coverage right now. Needs cases for: `default` fallback, `case`/`when`/`then`, `where`-clause filtering, `MISSING` propagating through a full nav chain, each new sentinel (`_skip`, `_missing`, `_error`), `REMOVE_MISSING`, `shape` mismatches, int-inferred `foreach`, and the interpolation coercion-error cases.

---

## Deferred Past 0.3

- **Recursive/nested variable navigation** (`[$foo.bar]`, `[$foo[$bar]]`) — explicitly out of scope, too much complexity for the time available.
- **Streaming TOML output** — no defined lossy-conversion policy for `MISSING`/`null`.
- **Full multi-span, engine-dispatching string interpolation** beyond the nav-only `${...}` scoped into §5.
- **`$sql=` expression engine** — sketched, not implemented.
- **CEL integration** — noted as a future default-engine option in §4, not started.