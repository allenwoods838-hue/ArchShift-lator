# ArchShift-lator native execution engine

This directory vendors the native runtime from [linuxkid473/maclator](https://github.com/linuxkid473/maclator) as the execution backend for ArchShift-lator. Upstream MIT licensing and the original `NOTICE` are preserved here. It is an attributed, source-derived native backend, not a clean-room Python reimplementation; Python coordinates inspection, dispatch, diagnostics and experimental tools, while the native component executes guest instructions and emulates macOS runtime boundaries.

The imported engine includes an AArch64 interpreter, x86-64 JIT/AOT translation cache, Mach-O loader, guest dyld/sysroot integration, syscall and Mach-trap handling, child-process re-launch, thread/workqueue support and optional Metal bridge source.

## Build and install

On an Intel Mac with Xcode Command Line Tools and Rust/Cargo:

```bash
cargo build --release -p maclator
./target/release/archshift-lator-native --help
```

The Python frontend auto-discovers `native/target/release/archshift-lator-native`. To build and install the binary into `~/bin`:

```bash
./scripts/install-archshift-lator.sh
```

The upstream runtime was documented/tested on an Intel Mac running macOS 26. Older host releases, including macOS 15, are not established as supported. The current CI workflow builds on an Intel macOS runner and runs the JIT/interpreter differential smoke test; that does not prove that arbitrary apps run on every host release.

## Guest dyld and shared cache

The host needs a usable ARM64e guest dyld and Apple Silicon dyld shared cache. If the default `/usr/lib/dyld` lacks an arm64e slice, set:

```bash
export ARCHSHIFT_LATOR_DYLD="/path/to/arm64e/dyld"
export ARCHSHIFT_LATOR_SYSROOT="/path/to/sysroot"
archshift-lator doctor
archshift-lator run /path/to/Example.app
```

The `scripts/fetch-sysroot.sh` helper uses the `ipsw` tool to extract a shared cache from an Apple macOS IPSW; it does not download or redistribute Apple's OS image. See `docs/SETUP.md` and the script's own help/comments. Use only OS images you are licensed to access. You may still need to obtain the corresponding guest `dyld` binary separately, depending on the source image and host.

Guest and host releases must interoperate at the syscall/Mach-trap boundary. On older host kernels, guest processes may fail due to unavailable or different kernel services even when the cache is present.

## Metal / GPU bridge

Source for the optional Metal bridge is included under `gpu/`. It is not enabled by default. To build and install it with the native runtime:

```bash
ARCHSHIFT_BUILD_GPU=1 ./scripts/install-archshift-lator.sh
```

The bridge needs the macOS SDK and compiler toolchain. Its presence does not guarantee GPU support for all programs; apps presenting directly through `CAMetalLayer` or `MTKView` may require additional bridging. See `docs/GPU.md`.

## Troubleshooting and validation

- Run `archshift-lator doctor` to check the host, executable, dyld and sysroot configuration.
- Run `archshift-lator-native --selftest-jit dpreg 20000` to compare native JIT results against the reference interpreter.
- Start with a small ARM64 command-line executable before testing large GUI applications.
- First launches may be slow because blocks are translated and cached; later launches can benefit from AOT cache entries.
- Use copies of apps and preserve the original bundles.

## License

See [LICENSE](LICENSE) and [NOTICE](NOTICE). The original upstream notices are retained. See also [UPSTREAM_README.md](UPSTREAM_README.md) and the imported guides in `docs/`.
