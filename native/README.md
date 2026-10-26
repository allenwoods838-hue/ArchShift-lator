# ArchShift-lator native execution engine

This directory vendors native runtime source from [linuxkid473/maclator](https://github.com/linuxkid473/maclator), retaining its MIT license and upstream NOTICE. The Python CLI is the front end; the native component provides an AArch64 interpreter/JIT, Mach-O loader, AOT cache, syscall/trap handling, and thread/workqueue emulation.

This is an attributed, source-derived native backend, not a clean-room Python reimplementation. A performant, broad ARM64 runtime requires native code.

## Build

On an Intel Mac with Xcode Command Line Tools and Rust:

    cd native
    cargo build --release -p maclator
    ./target/release/archshift-lator-native --help

The upstream engine was documented and tested on Intel Macs running macOS 26. Older hosts, including macOS 15, are not established as supported by this import. If the host `/usr/lib/dyld` lacks an arm64e slice, set `ARCHSHIFT_LATOR_DYLD=/path/to/arm64e/dyld`; set `ARCHSHIFT_LATOR_SYSROOT=/path/to/sysroot` for the matching shared cache. A compatible guest dyld/sysroot must come from an Apple macOS image you are licensed to use.

On older host kernels, syscall and Mach-trap behavior can still prevent apps from launching. Python fallback diagnostics do not claim the guest app ran. GPU bridge integration is a later step.

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for retained upstream licensing.
