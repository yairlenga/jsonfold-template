Full sweep of jq 1.8 manual.yml -> JFTL packed test format.
Source: jqlang/jq, docs/content/manual/v1.8/manual.yml. 93 sections, 216 program/input/output examples, all converted below (this supersedes/extends manual_conversion_batch.txt, which was the earlier curated 12-entry pass -- some overlap in content, different IDs, not de-duplicated against each other).

Files, one per manual chapter:
  manual_full_01_basic_filters.txt      - Identity through Parenthesis
  manual_full_02_types_and_values.txt   - Array/Object construction, Recursive Descent
  manual_full_03_builtins_a.txt         - Arithmetic (+ - * / %) through `in`
  manual_full_04_builtins_b.txt         - map/map_values through type-filters (arrays/objects/.../scalars)
  manual_full_05_builtins_c.txt         - empty through range
  manual_full_06_builtins_d.txt         - floor through unique_by
  manual_full_07_builtins_e.txt         - reverse through join
  manual_full_08_builtins_f.txt         - ascii_downcase/upcase through walk
  manual_full_09_builtins_g.txt         - have_literal_numbers through `builtins` (incl. interpolation, @formats, dates, SQL-style ops)
  manual_full_10_conditionals.txt       - ==/!= through Error Suppression `?`
  manual_full_11_regex.txt              - test/match/capture/scan/splits/sub/gsub

Not converted: "Advanced features > Variable / Symbolic Binding Operator" -- manual.yml gives this section 0 program/input/output examples (all its `as $x` illustrations are inline prose code blocks, not the examples: array), so there's nothing mechanical to convert.

TIER LEGEND (used in every COMMENT below instead of repeating the reasoning each time):
  NAV      = pure Navigation.md syntax ($.foo / $[n] / dotted chains). High confidence.
  STREAM   = default-shape `foreach` (no "shape" key = iterate current array) + OUT_FMT=STREAM, per your 105/107 confirmation. Only valid when iterating the CURRENT/root value -- iterating a nested field (.foo[]) is still the unresolved "106 problem" and gets BLOCKED instead.
  PYRUN    = escapes to `$pyrun= <python-expr>` against `_` as current value (per your $pyrun= note + template.py's Frame.current "_" comment). I only use PYRUN for expressions built from pure Python builtins/operators -- no `import`, since I don't know what's available inside the pyrun sandbox. Medium confidence: syntax of the escape itself (separator, "_" binding) is still your call to confirm (see 104c), and the *expression* is my best-effort Python translation of the jq semantics, not a verified equivalence.
  BLOCKED  = TODO. Either needs a JFTL mechanism I have no grounding for (path family, reduce, try/catch's MISSING redesign, label/break, nested-field foreach, native if/comparison, string interpolation, regex/date/base64/uri which need stdlib imports), or needs the same info as row 106/108/110 in the curated batch.

GOLD reshaping rule (unchanged from the curated batch): jq's `output:` list with 1 entry -> GOLD is that value. With >1 entries -> GOLD is a JSON array of all of them, OUT_FMT=STREAM set.

COMPRESSION NOTE: a handful of manual.yml sections give 4-7 near-duplicate examples that only vary a jq-internal implementation detail (e.g. the Identity section's 7 examples are all about jq's own --disable-decnum build flag and big-number literal preservation -- not a general capability; contains/inside/match give 5 near-mirror variations of the same matching rules). For those I converted one representative example and left the rest as a one-line note rather than 5-7 near-identical rows, so the file stays reviewable. Flagged inline wherever I did this -- say the word if you want the untrimmed set instead.
