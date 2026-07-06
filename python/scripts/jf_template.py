#!/usr/bin/env python3
"""
jf-template — apply a JFTL template to one or more inputs.

Usage:
    jf-template template [file1 file2 file3 ...]

  - template: path to the template JSON file.
  - file1, file2, ...: input JSON files. Each is processed independently
    (a failure on one does not stop the others).
  - No input files given -> read a single input from stdin, labeled '(stdin)'.
  - No arguments at all (not even a template) -> read the TEMPLATE from
    stdin, and render it with no input data (input = None).

Output:
  - Default: each result printed to stdout, one per file, in order.
  - -t/--target DIR: write each result to DIR/<basename(input)>.out instead
    of stdout. (If the input came from stdin and -t is given, the output
    file is named 'stdin.out' — there's no real basename to derive.)

Options:
  -s, --sections     Prepend a '//' comment line (on stdout) before each
                      result, with input/output size and timing info.
                      Sizes require the result to be fully rendered first,
                      so this disables incremental/streaming output.
  -t, --target DIR   Write each result to DIR/<basename>.out instead of
                      stdout. Uses only the basename of the input path.
  -q, --quiet        Suppress informational stderr output (the compile-time
                      line and, implicitly, anything -v would add). Error
                      messages are still always printed to stderr.
  -v, --verbose      On error, print full exception details (traceback)
                      instead of a minimal one-line summary.
  --indent N         Pretty-print indent width when not using --raw
                      (default: 2). Note: Python's json.dumps(indent=0)
                      still inserts newlines between elements — it does
                      NOT collapse to a single line. Use --raw for that.
  --raw              Fully compact, single-line output. Independent of
                      --indent; if both are given, --raw wins.
  -e, --entry NAME   Macro entry point to render (passed to engine.render).
  --strict           Use strict engine mode (see create_engine(strict=...)).

Exit code: 0 if every input succeeded, 1 if any failed.
"""
import sys
import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Any, Optional, TextIO

# --- make ../src importable when run directly from a sibling tests/ dir ---
sys.path.insert(0, str((Path(__file__).resolve().parent / ".." / "src").resolve()))

from template import create_engine, Engine  # noqa: E402


def _read_text(path: Optional[str]) -> tuple[str, str]:
    """Read raw text either from a named file or from stdin.
    Returns (text, label) where label is the filename or '(stdin)'."""
    if path is None:
        return sys.stdin.read(), "(stdin)"
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), path


def _count_lines(text: str) -> int:
    if text == "":
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _format_output(value: Any, indent: int, raw: bool) -> str:
    if raw:
        return json.dumps(value, separators=(",", ":"))
    return json.dumps(value, indent=indent)  # indent=0 is Python's own (odd but valid) behavior


def _exception_summary(exc: Exception, verbose: bool) -> str:
    if verbose:
        return traceback.format_exc()
    return f"{type(exc).__name__}: {exc}"


def _output_target(input_label: str, target_dir: Optional[str]) -> tuple[Optional[TextIO], str]:
    """Returns (file_handle_or_None, output_label).
    file_handle is None when writing to stdout."""
    if target_dir is None:
        return None, "-"
    if input_label == "(stdin)":
        out_name = "stdin.out"
    else:
        out_name = Path(input_label).name + ".out"
    out_path = Path(target_dir) / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return open(out_path, "w", encoding="utf-8"), str(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(prog="jf-template", description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("template", nargs="?", default=None,
                         help="Template JSON file (omit to read template from stdin)")
    parser.add_argument("files", nargs="*", default=None,
                         help="Input JSON files (omit to read one input from stdin)")
    parser.add_argument("-s", "--sections", action="store_true")
    parser.add_argument("-t", "--target", default=None, metavar="DIR")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--indent", type=int, default=2, metavar="N",
                         help="Pretty-print indent width when not using --raw (default: 2).")
    parser.add_argument("--raw", action="store_true",
                         help="Fully compact, single-line output. Independent of --indent; "
                              "if both are given, --raw wins.")
    parser.add_argument("-e", "--entry", default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    def info(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)

    def error(msg: str) -> None:
        print(msg, file=sys.stderr)  # errors always print, even under -q

    # --- read + compile the template ---
    template_text, template_label = _read_text(args.template)
    engine: Engine = create_engine(strict=args.strict)

    t0 = time.perf_counter()
    try:
        compiled, compile_errors = engine.compile(template_text)
    except Exception as exc:
        error(f"{template_label}: {_exception_summary(exc, args.verbose)}")
        return 1
    compile_elapsed = time.perf_counter() - t0

    if compile_errors:
        for err in compile_errors:
            error(f"{template_label}: [{err.severity}] {err.code}: {err.message}")
        if any(e.severity == "ERROR" for e in compile_errors):
            return 1

    info(f"Template {template_label} compiled in {compile_elapsed:.3f} seconds, "
         f"{len(template_text.encode('utf-8'))} bytes, {_count_lines(template_text)} lines.")

    # --- figure out which inputs to process ---
    if args.template is None and not args.files:
        # "no arguments at all" -> template from stdin already consumed above;
        # render with NO input data.
        input_sources: list[Optional[str]] = [None]
        no_input_data = True
    else:
        no_input_data = False
        input_sources = args.files if args.files else [None]  # None -> stdin

    overall_ok = True

    for input_path in input_sources:
        try:
            if no_input_data:
                input_text, input_label = "", "(none)"
                input_doc = None
            else:
                input_text, input_label = _read_text(input_path)
                input_doc = json.loads(input_text)

            t1 = time.perf_counter()
            status, result = engine.render(compiled, input_doc, entry=args.entry)
            elapsed = time.perf_counter() - t1

            if not status.ok:
                err = status.error
                msg = f"[{err.severity}] {err.code}: {err.message}" if err else "render failed"
                error(f"{input_label}: {msg}")
                overall_ok = False
                continue

            output_text = _format_output(result, args.indent, args.raw)
            out_handle, output_label = _output_target(input_label, args.target)

            if args.sections:
                comment = (
                    f"// Input: {input_label}  {_count_lines(input_text)} lines, "
                    f"{len(input_text.encode('utf-8'))} bytes, "
                    f"output: {output_label}, {_count_lines(output_text)} lines, "
                    f"{len(output_text.encode('utf-8'))} bytes "
                    f"in {elapsed:.3f} seconds"
                )
            else:
                comment = None

            dest = out_handle if out_handle is not None else sys.stdout
            if comment:
                print(comment, file=dest)
            print(output_text, file=dest)
            if out_handle is not None:
                out_handle.close()

        except Exception as exc:
            label = input_path if input_path is not None else "(stdin)"
            error(f"{label}: {_exception_summary(exc, args.verbose)}")
            overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
