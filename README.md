# ArchShift-lator

**ArchShift-lator** is a hybrid Python + native macOS runtime project for running ARM64 macOS programs on Intel Macs. The Python CLI/GUI handles inspection, routing, and diagnostics. The project now bundles an attributed native execution engine derived from [linuxkid473/maclator](https://github.com/linuxkid473/maclator), with upstream MIT licensing and NOTICE retained under `native/`.

This is a working engine integration project, not yet a guarantee that every ARM64 app will launch. The imported native engine was documented and tested on Intel Macs running macOS 26. **macOS 15 support remains unverified**, and the engine may require a guest arm64e dyld and matching system cache.

## What is included

- Python CLI and optional Tkinter GUI.
- Native AArch64 interpreter/JIT, Mach-O loader, syscall/trap emulation, AOT cache, and threading/workqueue runtime under `native/`.
- Automatic discovery of the bundled `archshift-lator-native` binary once it has been built.
- Optional override to try a separately installed Maclator command first; if it fails, ArchShift-lator tries its bundled engine and then reports fallback diagnostics.
- Read-only Mach-O architecture inspection and .app bundle scanning.
- Optional Unicorn ARM64 raw-code emulator and a small Python instruction lab.
- A small ARM64-to-x86-64 assembly translator for NOP, MOVZ, ADD/SUB-immediate, RET X30 (a development prototype, not a Mach-O application converter).
- Python tests and a native-engine build workflow.

## Build and install

Requirements: Python 3.10+, Rust/Cargo, and Xcode Command Line Tools on an Intel Mac. Tkinter is needed for the desktop GUI.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[runtime]"
cd native
cargo build --release -p maclator
cd ..
archshift-lator --help
archshift-lator run /Applications/Example.app
```

The native executable is built as `native/target/release/archshift-lator-native`. The Python command auto-discovers that file, or an installed `archshift-lator-native` on `PATH`. To install it under `~/bin`, run:

```bash
./native/scripts/install-archshift-lator.sh
```

## Older macOS / guest system files

The native engine's documented test target is macOS 26; other host versions are not established as supported. On an Intel Mac where `/usr/lib/dyld` does not contain an arm64e slice, the engine may need a compatible guest dyld and a matching Apple Silicon shared cache:

```bash
export ARCHSHIFT_LATOR_DYLD="/path/to/arm64e/dyld"
export ARCHSHIFT_LATOR_SYSROOT="/path/to/guest/sysroot"
archshift-lator run /path/to/Example.app
```

The guest dyld/sysroot must come from an Apple macOS image you are licensed to use. A matching sysroot alone does not guarantee success: guest syscalls and Mach traps must also be compatible with the Intel host kernel. When the native engine exits unsuccessfully, ArchShift-lator reports that failure and the inspection fallback; it does not claim the app ran.

## External-engine fallback

By default, the bundled native engine is attempted. To try an existing Maclator installation first, set a command template with an explicit `{target}` placeholder using the syntax supported by that installation:

```bash
export ARCHSHIFT_MACLATOR_COMMAND='maclator --your-supported-options {target}'
archshift-lator run /path/to/Example.app
```

The external command is invoked without a shell. If it is unavailable or exits nonzero, the bundled ArchShift-lator engine is attempted next.

## Developer commands

```text
archshift-lator inspect TARGET
archshift-lator run TARGET
archshift-lator lab d28000a0 91000400 d65f03c0
archshift-lator translate-code raw-arm64.bin -o translated.s
archshift-lator emulate-code raw-arm64.bin
archshift-lator gui
```

The `translate-code` prototype converts only a tiny straight-line subset to x86-64 assembly. `emulate-code` uses optional Unicorn to execute a raw ARM64 blob with a small Darwin `exit`/`write` shim. Neither command is a replacement for Mach-O loading and macOS runtime compatibility.

## What remains for broad compatibility

Even with the native runtime bundled, many apps can fail due to host-OS version mismatch, missing guest userland files, unsupported syscalls/Mach traps, code-signing policy, sandboxing, IOKit, audio, Metal/CAMetalLayer paths, JIT restrictions, or unimplemented instructions. Native source builds are now part of the repository, but app-by-app compatibility and macOS 15 testing remain necessary.

## Licensing

The Python glue and project-specific code are in this repository. The native engine source under `native/` is derived from Maclator and retains its upstream [MIT license](native/LICENSE) and [NOTICE](native/NOTICE). See those files and the upstream project for attribution and terms.
