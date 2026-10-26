"""Command-line interface."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from . import __version__
from .arm64 import UnsupportedInstruction, run_words
from .fallback import inspect_target, run_with_fallback
from .unicorn_backend import RuntimeUnavailable, emulate_raw_file
from .translator import translate_raw_file


def _print_inspection(report) -> None:
    print(f"Target: {report.target}")
    print(f"Files checked: {report.files_checked}")
    if not report.binaries:
        print("Mach-O binaries: none found")
    for item in report.binaries:
        archs = ", ".join(item.architectures) or "unknown"
        print(f"\n{item.path}")
        print(f"  Architectures: {archs}")
        print(f"  Type: {item.file_type_name}; 64-bit: {item.is_64_bit}")
        print(f"  Fat/universal: {item.is_fat}; load commands: {item.load_commands}")
        print(f"  Code-signature command: {'present' if item.has_code_signature else 'not detected'}")
        if item.linked_libraries:
            print("  Linked libraries:")
            for lib in item.linked_libraries[:40]:
                print(f"    {lib}")
        for note in item.notes:
            print(f"  Note: {note}")
    for error in report.errors:
        print(f"Warning: {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archshift-lator", description="Maclator-first ARM64 compatibility tools")
    parser.add_argument("--version", action="version", version=f"ArchShift-lator {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_cmd = sub.add_parser("inspect", help="Inspect Mach-O files and .app bundles")
    inspect_cmd.add_argument("target")
    run_cmd = sub.add_parser("run", help="Try configured Maclator, then use ArchShift fallback diagnostics")
    run_cmd.add_argument("target")
    lab_cmd = sub.add_parser("lab", help="Run supported ARM64 instruction words in the lab")
    lab_cmd.add_argument("words", nargs="+", help="32-bit instruction words in hexadecimal")
    trans_cmd = sub.add_parser("translate-code", help="Translate a raw ARM64 block to x86-64 assembly (limited subset)")
    trans_cmd.add_argument("target", help="Raw little-endian ARM64 bytes, not a Mach-O file")
    trans_cmd.add_argument("-o", "--output", help="Output assembly path (defaults to TARGET.x86_64.s)")
    trans_cmd.add_argument("--function-name", default="archshift_guest")
    emu_cmd = sub.add_parser("emulate-code", help="Execute a raw AArch64 machine-code blob with Unicorn")
    emu_cmd.add_argument("target", help="Raw little-endian ARM64 code bytes (not a Mach-O file)")
    emu_cmd.add_argument("--max-instructions", type=int, default=1_000_000)
    sub.add_parser("gui", help="Open the desktop UI")
    args = parser.parse_args(argv)

    if args.command == "gui":
        from .gui import launch
        launch()
        return 0
    if args.command == "inspect":
        try:
            report = inspect_target(args.target)
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        _print_inspection(report)
        return 0 if report.binaries else 2
    if args.command == "run":
        try:
            report = run_with_fallback(args.target)
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(report.message)
        print(f"External engine: {report.engine.message}")
        if report.engine.stdout:
            print(report.engine.stdout)
        if report.engine.stderr:
            print(report.engine.stderr, file=sys.stderr)
        if report.inspection:
            _print_inspection(report.inspection)
        return 0 if report.engine.success else 3
    if args.command == "translate-code":
        try:
            assembly = translate_raw_file(args.target, function_name=args.function_name)
            output = Path(args.output) if args.output else Path(args.target).with_suffix(".x86_64.s")
            output.write_text(assembly, encoding="utf-8")
        except (FileNotFoundError, ValueError, UnsupportedInstruction, OSError) as exc:
            print(f"Translation stopped: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote x86-64 assembly: {output}")
        print("Note: only the supported straight-line instruction subset was translated; this is not a full app converter.")
        return 0
    if args.command == "emulate-code":
        try:
            report = emulate_raw_file(args.target, max_instructions=args.max_instructions)
        except (FileNotFoundError, ValueError, RuntimeUnavailable, RuntimeError) as exc:
            print(f"Emulation unavailable: {exc}", file=sys.stderr)
            return 2
        print(f"Stop reason: {report.stopped_reason}")
        print(f"Instructions: {report.instruction_count}")
        print(f"Exit code: {report.exit_code}")
        if report.stdout:
            print(report.stdout, end="")
        if report.stderr:
            print(report.stderr, end="", file=sys.stderr)
        if report.trace:
            print("\nTrace:")
            print("\\n".join(report.trace))
        return 0 if report.stopped_reason in ("returned", "guest called exit") else 3
    if args.command == "lab":
        try:
            words = [int(word, 16) for word in args.words]
            if any(word < 0 or word > 0xFFFFFFFF for word in words):
                raise ValueError("Instruction words must fit in 32 bits")
            state, trace = run_words(words)
        except (ValueError, UnsupportedInstruction, RuntimeError) as exc:
            print(f"Lab stopped: {exc}", file=sys.stderr)
            return 2
        for row in trace:
            print(f"0x{row.pc:08x}: 0x{row.word:08x}  {row.mnemonic}  {row.detail}")
        print(f"X0=0x{state.x[0]:x}; PC=0x{state.pc:x}; halted={state.halted}")
        return 0
    return 2
