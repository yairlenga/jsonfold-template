# `jf-template` Command-Line Reference

`jf-template` compiles a JFTL template and applies it to zero or more JSON input documents. A template is compiled once, then reused for every supplied input file or input record.

## General usage

```text
jf-template [OPTIONS] [TEMPLATE] [FILE ...]
```

The usual form is:

```bash
jf-template template.json input1.json input2.json
```

`TEMPLATE` is the path to a JSON template file. Each `FILE` is processed independently, in command-line order.

When no input files are supplied, the template is rendered once with no input value; the input is JSON `null`, and is identified as `(none)` in diagnostic output and in the manifest.

When `TEMPLATE` is omitted, the template is read from standard input. Because standard input is then consumed by the template, that form also renders the template once with no input value:

```bash
jf-template < template.json
```

Use `-` as an explicit input filename to read an input document or record stream from standard input:

```bash
jf-template template.json -
```

A template can also be read explicitly from standard input by using `-` as `TEMPLATE`, but the same standard-input stream cannot then also supply an input file.

By default, rendered JSON is written to standard output. Informational messages and errors are written to standard error. With `--target`, rendered documents are written to files under the target directory.

## Option summary

| Option | Argument | Default | Description |
|---|---:|---:|---|
| `-f`, `--input-format` | `json`, `stream`, or `jsonl` | `json` | Select how each input source is parsed. |
| `-D`, `--data` | `KEY=VALUE` | none | Define a named dataset from inline JSON or `@file`. Repeatable. |
| `-F`, `--dataset` | `NAME PATH` | none | Load a named dataset from a JSON file. Repeatable. |
| `--split` | — | off | Split each top-level result into separate output documents. |
| `-t`, `--target` | `DIR` | stdout | Write results under `DIR` instead of standard output. |
| `-s`, `--sections` | — | off | Add a `//` metadata line before each JSON document. |
| `-m`, `--map` | `FILE` | automatic with `--target` | Write a JSON manifest; use `-` for standard output. |
| `--nomap` | — | off | Suppress manifest generation, including the automatic target manifest. |
| `-k`, `--keep-going` | — | off | Continue with later input files after an input fails. |
| `-q`, `--quiet` | — | off | Suppress informational messages on standard error. |
| `-v`, `--verbose` | — | off | Include traceback details in reported exceptions. |
| `--indent` | `N` | `2` | Set pretty-print indentation width. |
| `--raw` | — | off | Produce compact, single-line JSON. Overrides `--indent`. |
| `-N`, `--no-plugins` | — | off | Start the engine without its normally registered plugins. |
| `-A`, `--all-plugins` | — | off | Register all built-in plugins, including trusted Python engines. |
| `--enable` | `PLUGIN` | none | Parsed as an optional-plugin request; currently not applied by the CLI. |
| `-e`, `--entry` | `NAME` | main entry | Parsed as a macro entry point; not operational with the current engine implementation. |
| `-h`, `--help` | — | — | Show command help and exit. |

## Input options

### `-f`, `--input-format`

```text
-f {json,stream,jsonl}
--input-format {json,stream,jsonl}
```

Selects how every input file is decoded. The option applies to all input files in the invocation.

#### `json`

Reads the entire input source as one JSON document. This is the default.

```bash
jf-template template.json input.json
```

Whitespace before or after the document is accepted by the JSON parser. Any additional non-whitespace content makes the input invalid.

#### `stream`

Reads a sequence of adjacent JSON values from one input source. Values may be separated by arbitrary JSON whitespace and may span multiple lines.

```text
{"id": 1}
{"id": 2}
[3, 4]
```

Each decoded value is rendered independently. This format is not limited to one value per line.

```bash
jf-template --input-format stream template.json records.jsons
```

#### `jsonl`

Reads JSON Lines input. Each nonblank physical line must contain one complete JSON value. Blank lines are ignored.

```text
{"id": 1}
{"id": 2}
{"id": 3}
```

```bash
jf-template --input-format jsonl template.json records.jsonl
```

A JSONL record cannot span multiple lines.

For `stream` and `jsonl`, every record is rendered separately. Without `--split`, each rendered result is emitted as one JSON document. With `--split`, each record's result may produce multiple documents.

### `-D`, `--data`

```text
-D KEY=VALUE
--data KEY=VALUE
```

Defines a runtime dataset available to the template through the engine's dataset collection. The option may be repeated.

`VALUE` is parsed as JSON, not as an unquoted shell string. Strings therefore require JSON quotes:

```bash
jf-template \
  -D 'region="EMEA"' \
  -D 'limit=20' \
  -D 'enabled=true' \
  -D 'labels=["new","reviewed"]' \
  template.json input.json
```

To load a dataset from a JSON file, prefix the path with `@`:

```bash
jf-template -D customers=@customers.json template.json input.json
```

The text after `@` is treated as a path and the complete file is parsed as one JSON document.

Dataset names must be non-empty and unique across all `-D` and `-F` options. A duplicate name is a command syntax error. Invalid inline JSON is also a syntax error. A missing, unreadable, or invalid `@file` is an input read error.

Because shells may interpret quotes and special characters, quoting the complete `KEY=VALUE` argument is recommended.

### `-F`, `--dataset`

```text
-F NAME PATH
--dataset NAME PATH
```

Loads a named dataset from a JSON file. The option takes two separate arguments and may be repeated:

```bash
jf-template \
  --dataset customers data/customers.json \
  --dataset rates data/rates.json \
  template.json input.json
```

This is equivalent in purpose to `-D NAME=@PATH`, but avoids embedding the name, equals sign, and path in one argument.

The file must contain one valid JSON document. Dataset names must be unique across both dataset options.

## Output options

### `--split`

Splits the top-level rendered result into multiple output documents.

The behavior depends on the result type:

- **Object:** each property value becomes an output document. The property key is used as the preferred output filename when writing to a target directory.
- **Array or tuple:** each item becomes an output document.
- **Scalar:** the scalar is treated as a one-item array and produces one output document.

Without `--target`, split documents are printed consecutively to standard output. They are separate JSON texts, not a surrounding JSON array. Use `--sections` when human-readable boundaries are needed.

With `--target`, every split document is written to a separate file. For object results, a key is accepted as a filename only when it:

1. starts with an ASCII letter or digit;
2. otherwise contains only ASCII letters, digits, `.`, `_`, or `-`;
3. has not already been used by an earlier output in the same process.

Invalid, empty, or duplicate names are replaced by generated names such as:

```text
000001.out
000002.out
```

Generated numbering and filename uniqueness apply across the complete command invocation, not separately to each input file.

When splitting an object, the manifest remains keyed by the original object key even when the physical filename has been normalized or replaced.

### `-t`, `--target`

```text
-t DIR
--target DIR
```

Writes rendered output to files under `DIR` rather than to standard output.

The directory must already exist. The CLI does not create it.

Without `--split`, output filenames are derived as follows:

| Input | Output filename |
|---|---|
| `orders.json` | `orders.out` |
| `orders.jsonl` | `orders.out` |
| `orders.yaml` | `orders.out` |
| `orders.toml` | `orders.out` |
| another filename | basename plus `.out` after the implemented extension handling |
| standard input (`-`) | `stdin.out` |
| no input file | no target filename is derived by the current implementation |

With `--split`, filenames come from result-object keys when valid; otherwise generated six-digit `.out` names are used.

Specifying `--target` also enables a manifest by default. Unless overridden with `--map FILE` or disabled with `--nomap`, that manifest is written to standard output.

### `-s`, `--sections`

Adds a JavaScript-style comment line before every rendered JSON document:

```text
// output: 'orders.out' (142 characters, 9 lines), Input: orders.json (318 characters, 18 lines)
{
  ...
}
```

The line identifies the output label, output size, input label, and input description. Despite the current command help mentioning timing, the section line itself does not include elapsed time.

Because `//` comments are not valid JSON, output produced with `--sections` is intended for inspection or concatenated text workflows, not direct consumption by strict JSON parsers.

When output is written to files, the comment is written inside each output file.

### `-m`, `--map`

```text
-m FILE
--map FILE
```

Writes a JSON manifest describing the inputs and generated outputs.

Use `-` to write the manifest to standard output:

```bash
jf-template --map - template.json input.json
```

Use a path to write it to a file:

```bash
jf-template --map manifest.json template.json input.json
```

When `--target` is supplied and neither `--map` nor `--nomap` is specified, manifest output defaults to standard output.

When rendered output is also going to standard output, `--map -` appends the manifest to the same stream after the rendered documents. The combined stream is not one valid JSON document. For machine processing, direct the manifest to a separate file or use `--target` for rendered output.

See [Manifest output](#manifest-output) for the complete structure.

### `--nomap`

Disables manifest generation.

This is mainly useful with `--target`, which otherwise enables a manifest on standard output automatically:

```bash
jf-template --target out --nomap template.json input.json
```

If both mapping controls are supplied, normal command-line action order determines the stored value for the shared setting; avoid combining `--map` and `--nomap` in the same invocation.

## Processing and diagnostic options

### `-k`, `--keep-going`

Continues processing later input files after an input file fails.

Without this option, processing stops after the first failed input. The failure and any previously completed inputs are still represented in the manifest, and unattempted inputs contribute to its `skipped` count.

With this option, each remaining input file is attempted independently. This option applies between input files. Errors while decoding records inside one `stream` or `jsonl` input terminate processing of that input source.

When some inputs succeed and others fail, the final process status is `6` (`PARTIAL`).

### `-q`, `--quiet`

Suppresses informational progress messages written to standard error, including template compilation timing, dataset counts, and per-input completion summaries.

Errors are always printed, even in quiet mode. Rendered output and manifest output are unaffected.

### `-v`, `--verbose`

Makes exception reports include Python traceback details instead of only the exception class and message.

This option does not change the JSON result format. The current implementation's primary additional behavior is expanded exception reporting; ordinary progress messages are already emitted unless `--quiet` is used.

## JSON formatting options

### `--indent`

```text
--indent N
```

Sets the indentation width used for pretty-printed JSON. The default is `2`.

```bash
jf-template --indent 4 template.json input.json
```

The value is passed directly to Python's JSON encoder. An indent of `0` therefore uses the encoder's newline-oriented zero-indent form rather than compact JSON.

`--indent` affects rendered output only. The manifest is always written with an indentation width of `2`.

### `--raw`

Writes each rendered JSON document in compact form, with no optional spaces or pretty-print newlines:

```json
{"id":1,"active":true}
```

`--raw` overrides `--indent` when both are supplied.

Each result is still terminated by a newline when written by the CLI. In `jsonl` or stream processing, this normally produces one compact rendered result per output line, provided each result itself can be represented as one JSON value.

## Plugin configuration

### `-N`, `--no-plugins`

Creates the engine without the normally registered expression plugins.

By default, `create_engine()` registers:

- `py`, backed by the restricted SimpleEval expression engine;
- `nav`, the navigation expression engine.

With `--no-plugins`, neither is registered. Templates that rely on those engines will fail to compile unless plugins are registered through some other integration mechanism. The CLI itself does not perform additional registration after engine creation.

### `-A`, `--all-plugins`

Creates the engine with all plugins registered by `create_engine()`.

In addition to the default `py` and `nav` plugins, this enables:

- `pyeval`, which evaluates trusted Python expressions;
- `pyrun`, which executes trusted Python statements.

`pyeval` and `pyrun` are not sandboxed and must only be enabled for trusted templates.

`--all-plugins` and `--no-plugins` should not be combined. In the current engine factory, `--no-plugins` takes precedence because it prevents all registration, including the `all_plugins` branch.

### `--enable`

```text
--enable {pyrun,pyeval,cel,simpleeval}
```

May be specified multiple times and is accepted by the argument parser. In the current script, however, the collected values are never used to register plugins. The option therefore has no runtime effect.

The accepted names also do not exactly match every registered prefix: the default restricted engine is registered as `py`, while the accepted choice is `simpleeval`; `cel` is accepted but no CEL plugin is registered by `create_engine()`.

Use `--all-plugins` to enable the trusted Python plugins in this version.

## Template execution

### `-e`, `--entry`

```text
-e NAME
--entry NAME
```

Is intended to select a named macro entry point and is passed to `engine.render()`.

In the current engine implementation, a non-empty entry name prevents selection of the compiled main entry but does not resolve a named replacement. Rendering therefore fails with a `NO-MAIN` status. Named entry points are not operational in this code version; omit this option to render the template's `main` entry.

## Positional arguments

### `TEMPLATE`

Path to the template JSON file. The complete file is read as UTF-8, parsed as one JSON document, and compiled once before any input files are processed.

Use `-` to read the template from standard input. When the positional argument is omitted, `-` is assumed.

A template read or JSON parse failure returns `TEMPLATE_IO` (`3`). A compilation failure returns `COMPILE_ERROR` (`11`). Compiler notices are printed to standard error. Compilation stops when an error-severity notice is present.

### `FILE ...`

Zero or more input paths. Inputs are processed independently and in order.

Use `-` to read one input source from standard input. Only one practical standard-input consumer should be used in an invocation.

When no files are listed, the template is rendered once with `null` input rather than reading input from standard input.

## Output behavior

### Standard output

Without `--target`, rendered documents are written to standard output in input order and record order.

Multiple results are emitted as consecutive JSON texts. Pretty-printed documents are visually separated by their own trailing newline, but the overall stream is not wrapped in an array. Use `--raw` for line-oriented output or `--sections` for human-readable boundaries.

A manifest requested with `--map -` is written after all rendered output.

### Standard error

Progress information and diagnostics are written to standard error. `--quiet` suppresses only informational messages. Errors remain visible.

### Missing values

If a JFTL `Missing` value reaches JSON serialization, the CLI serializes it as JSON `null`.

## Manifest output

The manifest is a JSON object written after input processing. It summarizes the command-level result and contains one entry for every input that was actually reached before processing stopped.

Top-level structure:

```json
{
  "count": 2,
  "passed": 1,
  "failed": 1,
  "skipped": 0,
  "input": {
    "input1.json": {
      "source": "input1.json",
      "ok": true,
      "lines": 20,
      "length": 450,
      "output": {
        "lines": 8,
        "length": 120,
        "doc_count": 1
      }
    },
    "input2.json": {
      "source": "input2.json",
      "ok": false,
      "output": {
        "code": 1,
        "message": "error: ProcessingException: ..."
      }
    }
  }
}
```

### Top-level manifest fields

| Field | Type | Meaning |
|---|---|---|
| `count` | integer | Number of input sources originally selected for processing. |
| `passed` | integer | Number of input sources that completed successfully. |
| `failed` | integer | Number of input sources that were attempted and failed. |
| `skipped` | integer | Number not attempted, normally because processing stopped without `--keep-going`. |
| `input` | object | Per-input entries keyed by the original input path. |

When there are no input files, the per-input key and `source` are the empty string, representing the no-input execution. An explicit standard-input file is keyed by `-` and has `source: "-"`.

### Per-input fields

| Field | Type | Meaning |
|---|---|---|
| `source` | string | Original input path, `-`, or an empty string for no input. |
| `ok` | boolean | Whether the complete input source processed successfully. |
| `lines` | integer | Input line count, when collected by the selected reader. |
| `length` | integer | Input character count, when collected by the selected reader. |
| `doc_count` | integer | For streamed input metadata, the accumulated generated-document count as currently calculated. |
| `output` | object, array, or `null` | Output summary, split-output summaries, record summaries, or error details. |

Input size fields are present when the input reader collected them. The no-input case normally has no size fields.

### Successful non-split output summary

When output goes to standard output:

```json
{
  "lines": 8,
  "length": 120,
  "doc_count": 1
}
```

When output goes to a target file:

```json
{
  "file": "input1.out",
  "lines": 8,
  "length": 120,
  "doc_count": 1
}
```

`length` is the UTF-8 byte length of the serialized JSON text before the final newline is added. `lines` describes the serialized JSON text itself. A `--sections` comment line is not included in these counts.

### Split object output

For a top-level object, `output` is an object keyed by each original result key:

```json
{
  "customer-a": {
    "file": "customer-a",
    "lines": 5,
    "length": 72,
    "doc_count": 1
  },
  "unsafe/name": {
    "file": "000001.out",
    "lines": 4,
    "length": 51,
    "doc_count": 1
  }
}
```

The manifest key preserves the original result key. The nested `file` field reports the normalized physical filename when `--target` is used.

Without `--target`, the nested summaries omit `file`.

### Split array or scalar output

For an array result, `output` is an array of document summaries:

```json
[
  {
    "file": "000001.out",
    "lines": 3,
    "length": 25,
    "doc_count": 1
  },
  {
    "file": "000002.out",
    "lines": 6,
    "length": 91,
    "doc_count": 1
  }
]
```

A scalar result under `--split` is represented the same way as a one-item array.

### Stream and JSONL output

For `stream` and `jsonl` input, `output` is an array with one summary per successfully reached input record. Each element has the same shape as that record's non-split or split output summary.

If rendering returns an unsuccessful status for a record, the record summary is currently `null`; processing continues to later records within that source, and the containing input is marked unsuccessful.

### Error output summary

When an exception prevents a normal output summary, `output` contains:

```json
{
  "code": 1,
  "message": "error: ProcessingException: ..."
}
```

The `code` is the classified error code captured for that input. Some unsuccessful engine render statuses return no classified exception code; in that case the summary may contain code `0` and a null message in the current implementation.

## Return codes

| Code | Name | Meaning |
|---:|---|---|
| `0` | `SUCCESS` | All selected inputs succeeded. |
| `1` | `READ_ERROR` | An input or dataset file could not be read, or streamed input decoding raised an exception. |
| `2` | `BAD_SYNTAX` | CLI-level data syntax error, such as malformed `-D`, duplicate dataset names, or an unsupported internal input-format branch. Standard `argparse` usage errors also conventionally exit with `2` before `main()` returns. |
| `3` | `TEMPLATE_IO` | The template file could not be read or its text was not valid JSON. |
| `4` | `GENERAL_ERROR` | An unexpected CLI failure or an unclassified failed input. |
| `5` | `OUTPUT_ERROR` | A rendered output file or manifest could not be written. |
| `6` | `PARTIAL` | At least one input succeeded and at least one selected input failed or was not completed. |
| `11` | `COMPILE_ERROR` | Template compilation failed or produced an error-severity compiler notice. |
| `13` | `RENDER_ERROR` | A `RenderError` escaped from engine rendering. |
| `14` | `USER_ERROR` | Reserved for an error raised intentionally by a template; no direct assignment is present in this script version. |
| `16` | `PY_EXCEPTION` | An unexpected Python exception occurred while rendering or processing an input. |
| `18` | `PLUGIN_ERROR` | Reserved for plugin failures; no direct assignment is present in this script version. |

### Final status selection

After input processing, the CLI selects its final status as follows:

1. If no input succeeded, return the captured failure code.
2. If every originally selected input succeeded, return `0`.
3. If at least one input succeeded but not all succeeded, return `6`.

Without `--keep-going`, later inputs may be skipped after the first failure; this leads to `PARTIAL` when an earlier input succeeded. If no earlier input succeeded, the current script has the status-code defect described above.

Template read and compilation failures occur before input processing and return immediately with their dedicated codes. Manifest write failure also returns immediately as `OUTPUT_ERROR`.

## Examples

Render one input document to standard output:

```bash
jf-template template.json input.json
```

Render several files with compact output:

```bash
jf-template --raw template.json input1.json input2.json
```

Read JSON Lines and emit one compact result per record:

```bash
jf-template --input-format jsonl --raw template.json records.jsonl
```

Continue after file failures and write a manifest:

```bash
jf-template --keep-going --map manifest.json template.json inputs/*.json
```

Write one output file per input and suppress the automatic manifest:

```bash
mkdir -p out
jf-template --target out --nomap template.json inputs/*.json
```

Split an object or array result into separate files:

```bash
mkdir -p out
jf-template --split --target out --map manifest.json template.json input.json
```

Supply inline and file-backed datasets:

```bash
jf-template \
  -D 'run_date="2026-08-04"' \
  -D config=@config.json \
  -F customers customers.json \
  template.json input.json
```

Enable the trusted Python expression and statement engines:

```bash
jf-template --all-plugins template.json input.json
```

Only use `--all-plugins` with trusted templates.
