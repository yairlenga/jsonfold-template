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

from collections.abc import Set
from enum import IntEnum
import sys
import argparse
import json
import time
import traceback
import re

from pathlib import Path
from typing import Any, Iterator, Optional, TextIO

# --- make ../src importable when run directly from a sibling tests/ dir ---
sys.path.insert(0, str((Path(__file__).resolve().parent / ".." / "src").resolve()))

from core import CompileError, RenderError
from template import JFTLError, Missing, create_engine, Engine  # noqa: E402

class ExitCode(IntEnum):
    SUCCESS = 0
    # Codes 1-9 reserved for the CLI
    READ_ERROR = 1               # Unable to read inputs
    BAD_SYNTAX = 2               # Invocation errors, bad CLI, ...
    TEMPLATE_IO = 3              # Error reading/processing template
    GENERAL_ERROR = 4            # Unexpected error
    OUTPUT_ERROR = 5             # Error writing results
    PARTIAL = 6                  # Some failures occured, engine runing in "ignore error"

    # Codes 10-19 classify engine errors
    COMPILE_ERROR = 11           # Compiler failed
    RENDER_ERROR = 13            # Engine intenal error
    USER_ERROR = 14              # Template raise error
    PY_EXCEPTION = 16            # Python runtime exception
    PLUGIN_ERROR = 18            # Plugin raised an error

class ProcessingException(Exception):
    def __init__(self, code: int, message: Optional[str] = None):
        super().__init__(message)
        self.code = code

args: Any
out_record_count = 0
out_files = set()

def info(msg: str) -> None:
    if not args.quiet:
        print(msg, file=sys.stderr)

def error(msg: str) -> None:
    print(msg, file=sys.stderr)  # errors always print, even under -q

def _read_text(path: str) -> tuple[str, str]:
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


def _exception_summary(exc: BaseException, verbose: bool) -> str:
    if verbose:
        return traceback.format_exc()
    return f"{type(exc).__name__}: {exc}"


def _text_desc(text: str) -> str:
    return f"{len(text)} characters, {_count_lines(text)} lines"

def _write_json_result(args, dest: TextIO, result: Any, input_label: str, input_desc: str, output_label: str) -> tuple[bool, Any]:

    json_out = _format_output(result, args.indent, args.raw)
    bytes = len(json_out.encode('utf-8'))
    lines = _count_lines(json_out)

    if args.sections:
        desc = f"{bytes} characters, {lines} lines"

        comment = f"output: '{output_label}' ({desc}), Input: {input_label} ({input_desc})"
        print("// " + comment, file=dest)
    
    print(json_out, file=dest)
    return True, { "lines": lines, "bytes": bytes, "doc_count": 1 }

def _write_json_file(args, out_file: str, result: Any, input_label: str, input_desc: str, output_id: str) -> tuple[bool, Any]:
    with open(out_file, mode="w", encoding="utf-8") as dest:
        ok, result = _write_json_result(args, dest, result, input_label, input_desc, output_id)
    result = { "output": output_id } | result
    return ok, result

    # Read single json record from the input stream

def _normalize_out_name(output_id: Optional[str]) -> str:
    global out_record_count
    global out_files
    new_name = output_id
    if not new_name or new_name in out_files or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", new_name):
        out_record_count += 1
        new_name = f"{out_record_count:06d}.out"    
    out_files.add(new_name)
    return new_name        


def _write_one_result(args, doc: Any, dest: TextIO, *, input_label: str = "", input_desc: str = "", output_id: str = "") -> tuple[bool, Any]:
    try:
        if args.target:
            item_dest = str(Path(args.target) / output_id)
            return _write_json_file(args, item_dest, doc, input_label, input_desc, output_id)
        else:
            return _write_json_result(args, dest, doc, input_label, input_desc, output_id)
    except RenderError as ex:
        raise ex
    except Exception as ex:
        raise ProcessingException(ExitCode.OUTPUT_ERROR) from ex


def _process_record(args, engine, compiled, record: Any, dest: TextIO, *, input_label: str = "", input_desc: str = "", output_label: str = "") -> tuple[bool, Any]:

    try:
        status, result = engine.render(compiled, record, entry=args.entry)
    except RenderError as ex:
        raise ex
    except Exception as ex:
        raise ProcessingException(ExitCode.PY_EXCEPTION) from ex

    if not status.ok:
        err = status.error
        msg = f"[{err.severity}] {err.code}: {err.message}" if err else "render failed"
        error(f"{input_label}: {msg}")
        return False, None

    if not args.split:
        return _write_one_result(args, result, dest, input_label=input_label, input_desc = input_desc, output_id=output_label)

    # Handle Splitting

    # Dict - use the ID for file name
    if isinstance(result, dict):
        manifest = {}
        all_ok = True
        for pos, [id, item] in enumerate(result.items(), start=1):
        # Write to a folder only if the file name is valid.
            ok, details = _write_one_result(args, item, dest, input_label=input_label, input_desc=f"#{pos}", output_id=_normalize_out_name(id))
            manifest[id] = details
            all_ok = all_ok and ok
        return all_ok, manifest

    # Unlikely - the top level object is scalar, just wrap it inside an array.
    if not isinstance(result, list):
        result = [ result ]

    manifest = []
    all_ok = True
    for pos, item in enumerate(result, start=1):
        ok, details = _write_one_result(args, item, dest, input_label=input_label, input_desc=f"#{pos}", output_id=_normalize_out_name(None))
        manifest.append(details)
        all_ok = all_ok and ok
    return all_ok, manifest



def _process_multi_records(args, engine, compiled, records: Iterator[tuple[Any, str]], input_label: str,  dest: TextIO, dest_label: str ) -> tuple[bool, Any, int]:

#    decoder = json.JSONDecoder()
#    input_desc = _text_desc(input) if input is not None else "(none)"
    out_count = 0
    manifest = None
    all_ok = True

    manifest = []
    while True:
        try:
            record, desc = next(records)
        except StopIteration:
            break
        except Exception as ex:
            raise ProcessingException(ExitCode.READ_ERROR) from ex
        ok, summary = _process_record(args, engine, compiled, record, dest, input_label=input_label, input_desc=desc, output_label=dest_label)

        manifest.append(summary)
        out_count += summary.get("doc_count", len(summary)) if isinstance(summary, dict) else len(summary) if isinstance(summary, list) else 0
        if not ok:
            all_ok = False

    return all_ok, manifest, out_count

def _process_single_doc(args, engine, compiled, input, input_desc, input_label: str,  dest: TextIO, dest_label: str ) -> tuple[bool, Any]:

    t1 = time.perf_counter()

    all_ok, manifest = _process_record(args, engine, compiled, input, dest, input_label=input_label, input_desc=input_desc, output_label=dest_label)
    elapsed = time.perf_counter() - t1
    out_count = len(manifest) if isinstance(manifest, list) else manifest.get("doc_count", 1)
    elapsed = time.perf_counter() - t1
    if args.target:
        if args.split:
            info(f"Input {input_label} ({input_desc}), {out_count} files, completed in {elapsed:.3f} seconds")
        else:
            info(f"Input {input_label} ({input_desc}), Output: {dest_label}, completed in {elapsed:.3f} seconds")
    else:
        if args.split:
            info(f"Input {input_label} ({input_desc}), {out_count} files, completed in {elapsed:.3f} seconds")
        else:
            info(f"Input {input_label} ({input_desc}), Output: {dest_label}, completed in {elapsed:.3f} seconds")

    return all_ok, manifest


def _read_empty_doc() -> tuple[Any, str]:
    return None, "(none)"

    # Generate single document from a file
def _read_json_doc(fp: TextIO) -> tuple[Any, str]:
    data = json.load(fp)
    desc = "Document"
    return data, desc

    # Generate stream of documents from json lines input
def _jsonline_record_reader(fp: TextIO) -> Iterator[tuple[Any, str]]:
    for line_no, line in enumerate(fp, start=1):
        stripped= line.strip()
        if not stripped:
            continue
        data = json.loads(stripped)
        desc = f"{_text_desc(stripped)}, at line {line_no}"
        yield data, desc    

    # Generate stream of documents from JSON objects
def _json_stream_reader(fp: TextIO) -> Iterator[tuple[Any, str]]:

    input = fp.read()
    decoder = json.JSONDecoder()

    start_line = 1
    record_count = 0
    pos = 0
    n = len(input)
    while True:
        # Skip over new lines
        start_pos = pos
        while pos < n and input[pos].isspace():
            pos += 1
        if pos >= n:
            return
        start_line += input[start_pos:pos].count("\n")
        start_pos = pos
        # Parse the next
        record_count += 1
        data, pos = decoder.raw_decode(input, pos)
        desc = f"{_text_desc(input[start_pos:pos])}, starting at line {start_line}"
        start_line += input[start_pos:pos].count("\n")
        yield data, desc


def _process_file(args, engine, compiled, input_path: Optional[str], input_label: str) -> Any:

    input_label = "(none)"
    output_path = None
    output_fp = sys.stdout
    input_fp = None
    close_input = False

    new_name = ""
    if input_path == "-":
        input_label = "(stdin)"
        input_fp = sys.stdin
        if args.target and not args.split:
            new_name = "stdin.out"
            output_path = Path(args.target) / new_name

    elif input_path is not None:
        input_label = input_path
        try:
            input_fp = open(input_path, mode="r", encoding="utf-8")
            close_input = True
        except Exception as ex:
            raise ProcessingException(ExitCode.READ_ERROR) from ex

        if args.target and not args.split:
            new_name = Path(input_path).name.removesuffix(".json") + ".out"
            output_path = Path(args.target) / new_name

    if output_path:
        output_fp = open(output_path, "w", encoding="utf-8")

    input = None
    records = None
    if input_fp:
        match args.input_format:
            case "json":
                input, desc = _read_json_doc(input_fp)

            case "stream":
                desc = ""
                records = _json_stream_reader(input_fp)

            case "jsonl":
                desc = ""
                records = _jsonline_record_reader(input_fp)

            case _:
                error(f"Unknown input_format={args.input_format}")
                raise ProcessingException(ExitCode.BAD_SYNTAX)
    else:            
        input, desc = _read_empty_doc()

    if records:
        t1 = time.perf_counter()
        status, summary, out_count = _process_multi_records(args, engine, compiled, records, input_label, output_fp, new_name)
        elapsed = time.perf_counter() - t1
        inp_count = len(summary)

        if args.split:
            info(f"Stream {input_label} ({desc}, {inp_count} records), Generated {out_count} records in {elapsed:.3f} seconds")
        else:
            info(f"Stream {input_label} ({desc}, {inp_count} records), Output: {new_name}, completed in {elapsed:.3f} seconds")

        if close_input and input_fp is not None:
            input_fp.close()
    else:
        if close_input and input_fp is not None:
            input_fp.close()
        status, summary = _process_single_doc(args, engine, compiled, input, desc, input_label, output_fp, new_name)

    if output_path:
        output_fp.close()

    return status, summary


def main() -> int:
    parser = argparse.ArgumentParser(prog="jf-template", description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    # Input Options
    parser.add_argument("-f", "--input-format", choices=["json", "stream", "jsonl", "yaml", "toml"], default="json",
                        help="format of input records (default: json)")

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
    parser.add_argument("-k", "--keep-going", action="store_true",
                        help="Suppress informational stderr output. Error messages "
                            "are still always printed.")

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

    # Template Execution
    parser.add_argument("-e", "--entry", default=None, metavar="NAME",
                        help="Macro entry point to render.")

    parser.add_argument("template", nargs="?", default=None, metavar="TEMPLATE",
                        help="Path to the template JSON file.")
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="Input JSON files to process independently.")
    
    global args
    args = parser.parse_args()

    # --- read + compile the template ---
    template_path = args.template if args.template else "-"
    try:
        template_text, template_label = _read_text(template_path)
    except Exception as ex:
        error(f"Failed to read template '{template_path}': {_exception_summary(ex, args.verbose)}")
        return ExitCode.TEMPLATE_IO

    engine = create_engine(all_plugins = args.all_plugins, no_plugins = args.no_plugins)

    t0 = time.perf_counter()
    try:
        template_dict = json.loads(template_text)
    except Exception as ex:
        error(f"Failed to parse template '{template_path}': {_exception_summary(ex, args.verbose)}")
        return ExitCode.TEMPLATE_IO

    try:
        compiled, compile_errors = engine.compile(template_dict)
    except CompileError as exc:
        error(f"Failed to compile template '{template_path}': {_exception_summary(exc, args.verbose)}")
        return ExitCode.COMPILE_ERROR
    except Exception as ex:
        error(f"Failed during compile template '{template_path}': {_exception_summary(ex, args.verbose)}")
        error(f"{template_label}: {_exception_summary(ex, args.verbose)}")
        return ExitCode.COMPILE_ERROR

    compile_elapsed = time.perf_counter() - t0

    if compile_errors:
        for err in compile_errors:
            error(f"{template_label}: [{err.severity}] {err.code}: {err.message}")
        if any(e.severity == "ERROR" for e in compile_errors):
            return ExitCode.COMPILE_ERROR

    info(f"Template {template_label} compiled in {compile_elapsed:.3f} seconds, {_text_desc(template_text)}.")

    # None in the input list will run the template without input
    input_sources = args.files if args.files else [None]
    all_ok = True
    any_ok = False
    exit_code = 0

    manifest = {}
    for input_path in input_sources:
        input_label = "(stdin)" if input_path == "-" else input_path if input_path else "(none)"
        summary = None
        ok = False
        error_code = 0
        try:           
            ok, summary =  _process_file(args, engine, compiled, input_path, input_label)

        except RenderError as ex:
            summary = f"error: {type(ex).__name__}: {ex}"
            error(f"Error rendering: {input_label}: {_exception_summary(ex, args.verbose)}")
            error_code = ExitCode.RENDER_ERROR
        
        except ProcessingException as ex:
            summary = f"error: {type(ex).__name__}: {ex}"
            error(f"Error processing: {input_label}: {_exception_summary(ex.__cause__ or ex, args.verbose)}")
            error_code = ex.code

        except Exception as ex:
            summary = f"error: {type(ex).__name__}: {ex}"
            error(f"Exception Processing '{input_label}': {_exception_summary(ex, args.verbose)}")
            error_code = ExitCode.PY_EXCEPTION

        if ok:
            any_ok = True
        else:
            all_ok = False
            if not args.keep_going:
                break
            # Capture first error code
            if not exit_code:
                exit_code = error_code or ExitCode.GENERAL_ERROR

        manifest_id = input_path or ""
        manifest[manifest_id] = summary

    if args.target:
        try:
            json.dump(manifest, fp=sys.stdout, indent=2)
        except Exception as ex:
            error(f"Error writing manifest: {_exception_summary(ex, args.verbose)}")
            return ExitCode.OUTPUT_ERROR

    return exit_code if not any_ok else ExitCode.SUCCESS if all_ok else ExitCode.PARTIAL

if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProcessingException as ex:
        error(f"Processing error {ex}")
        sys.exit(ex.code)
    except Exception as ex:
        error(f"Unexpected error: {ex}")
        sys.exit(ExitCode.GENERAL_ERROR)

