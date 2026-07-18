#!/usr/bin/env python3
"""
jf-template — apply a JFTL template on input files.

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

from template import Error, Missing, create_engine, Engine  # noqa: E402

args: Any

def info(msg: str) -> None:
    if not args.quiet:
        print(msg, file=sys.stderr)

def error(msg: str) -> None:
    print(msg, file=sys.stderr)  # errors always print, even under -q

def _read_text(path: Optional[str]) -> tuple[str, str]:
    """Read raw text either from a named file or from stdin.
    Returns (text, label) where label is the filename or '(stdin)'."""
    if path == "-":
        return sys.stdin.read(), "(stdin)"
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), path


def _count_lines(text: str) -> int:
    if text == "":
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _json_default(obj):
    return None if isinstance(obj, Missing) else obj

def _format_output(value: Any, indent: int, raw: bool) -> str:
    if raw:
        return json.dumps(value, default=_json_default, separators=(",", ":"))
    return json.dumps(value, indent=indent, default=_json_default)  # indent=0 is Python's own (odd but valid) behavior


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


def _write_result(args, dest: TextIO | str | None, result: Any, comment: str):
    out : TextIO = dest if isinstance(dest, TextIO) else sys.stdout
    if isinstance(dest, str) and dest != "-":
        out = open(dest, "w", encoding="utf-8")

    if args.sections and comment:
        print("//" + comment, file=out)

    if args.raw:
        json.dump(result, fp=out, separators=(",", ":"))
    else:
        json.dump(result, fp=out, indent=args.indent)

    out.close()

def _process_input(args, engine, compiled, input_label, input_path):
    if not input_path:
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
        return False

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
    if output_text != "":
        print(output_text, file=dest)
    if out_handle is not None:
        out_handle.close()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(prog="jf-template", description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    # Input Options
    parser.add_argument("--stream", default=None, action="store_true",
                        help="Read multiple JSON objecs from the standard input, and apply the template for each one of them")

    parser.add_argument("-e", "--entry", default=None, metavar="NAME",
                        help="Macro entry point to render.")

    # Output Options
    parser.add_argument("--split", default=None, action="store_true",
                        help="Split the top level output into multiplle documents, potentially into different files (if --target is used)")
    parser.add_argument("-t", "--target", default=None, metavar="DIR",
                        help="Write each result to DIR/<basename>.out instead of stdout.")
    parser.add_argument("-s", "--sections", action="store_true",
                        help="Prepend a '//' comment line before each result, with "
                            "input/output size and timing info. Requires the result "
                            "to be fully rendered first (disables streaming).")

    # Logging
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress informational stderr output. Error messages "
                            "are still always printed.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="On error, print full exception details (traceback) "
                            "instead of a minimal one-line summary.")

    # Formatting
    parser.add_argument("--indent", type=int, default=2, metavar="N",
                        help="Pretty-print indent width when not using --raw (default: 2).")
    parser.add_argument("--raw", action="store_true",
                        help="Fully compact, single-line output. Wins over --indent if both given.")

    # Configuration
    parser.add_argument("--no-plugins", "-N", action="store_true",
                        help="Start with no registered plugins")
    parser.add_argument("--all-plugins", "-A", action="store_true",
                        help="Start with no registered plugins")
    parser.add_argument("--enable", action="append", default=[], metavar="PLUGIN",
                        choices=["pyrun", "pyeval", "cel", "simpleeval"],
                        help="Enable an optional plugin. May be specified multiple times.")

    parser.add_argument("template", nargs="?", default=None, metavar="TEMPLATE",
                        help="Path to the template JSON file.")
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="Input JSON files to process independently.")
    
    global args
    args = parser.parse_args()

    # --- read + compile the template ---
    template_path = args.template if args.template else "-"
    template_text, template_label = _read_text(template_path)
    engine = create_engine(all_plugins = args.all_plugins, no_plugins = args.no_plugins)

    t0 = time.perf_counter()
    try:

        template_dict = json.loads(template_text)
        compiled, compile_errors = engine.compile(template_dict)
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
    input_sources = args.files if args.files else [None]  # None -> stdin
    overall_ok = True

    for input_path in input_sources:
        input_map = { None: "(none)", "-": "(stdin)" }
        input_label = input_map.get(input_path, input_path)
        try:
            if not _process_input(args, engine, compiled, input_label, input_path):
                overall_ok = False

        except Exception as exc:
            error(f"{input_label}: {_exception_summary(exc, args.verbose)}")
            overall_ok = False

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
