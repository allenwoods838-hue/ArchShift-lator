# ArchShift-lator

ArchShift lator is a Python-first compatibility frontend for ARM64 macOS apps on Intel Macs. It tries a configured Maclator installation first, then falls back to ArchShift-lator diagnostics and an experimental ARM64 instruction lab when Maclator is unavailable or fails.

**Status: experimental developer foundation. It is not yet a drop-in Rosetta 2 replacement.** The fallback inspects Mach-O files and interprets a small, explicit subset of AArch64 instructions. It does not yet translate arbitrary ARM64 macOS applications, bridge Apple frameworks, or make every ARM64 .app runnable.

## Included

- Python CLI and optional Tkinter GUI.
- Thin and fat/universal Mach-O architecture detection, linked dylibs, and code-signature metadata.
- Tiny AArch64 lab for NOP, MOVZ, ADD/SUB immediate, and RET.
- Configurable Maclator command adapter; missing configuration or failure routes to fallback diagnostics.
- Unit tests and GitHub Actions CI.

## Install

Python 3.10+ is required. The CLI has no third-party runtime dependency. Tkinter is required for the GUI.

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[runtime]"
    archshift-lator --help

## Maclator-first fallback

Configure the exact CLI invocation supported by your Maclator build. Include {target} where the target path belongs:

    export ARCHSHIFT_MACLATOR_COMMAND='maclator --your-supported-options {target}'
    archshift-lator run /path/to/Example.app

Replace the illustrative options with ones supported by your installed build. ArchShift-lator does not guess undocumented Maclator syntax. The command is invoked without a shell. If it is not configured, its executable is missing, or it exits unsuccessfully, fallback diagnostics run.

The fallback does not silently execute an ARM64 app, rewrite the bundle, remove signatures, or claim conversion succeeded. It reports whether an x86_64 slice exists and what the current fallback can actually do.

## Commands

    archshift-lator inspect TARGET
    archshift-lator run TARGET
    archshift-lator lab d28000a0 91000400 d65f03c0
    archshift-lator emulate-code raw-arm64.bin
    archshift-lator gui


## Expanded CPU execution prototype

Install the optional Unicorn runtime with `python -m pip install -e ".[runtime]"`. The `emulate-code` command can execute a **raw little-endian ARM64 machine-code blob** and provides a small Darwin SVC shim for `exit` and `write`. This uses an established ARM64 emulator as a CPU backend; it is not yet a dynamic binary translator and does not load or run a full `.app` bundle. The existing `lab` command remains a tiny pure-Python interpreter useful for debugging a few instructions.

Example: assemble or otherwise produce a raw ARM64 instruction blob, then run:

    archshift-lator emulate-code ./program.arm64.bin

The runtime is deliberately strict: unknown Darwin syscalls stop execution; it does not fake success for missing OS services. Use only trusted guest code.

## Safety and roadmap

Inspection is read-only. Configure only trusted Maclator executables; do not use untrusted binaries. Test on copies and retain backups.

The remaining work for a real Maclator replacement includes broad instruction coverage, JIT/native code generation, guest memory, Mach-O loading and relocations, exceptions, runtime/syscall boundaries, ABI bridging, and macOS framework compatibility. This project is a foundation for those components, not a claim that arbitrary ARM64 apps already run on Intel.
