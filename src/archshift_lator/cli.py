"""Command-line interface."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from . import __version__
from .arm64 import UnsupportedInstruction, run_words
from .fallback import inspect_target, run_with_fallback


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
