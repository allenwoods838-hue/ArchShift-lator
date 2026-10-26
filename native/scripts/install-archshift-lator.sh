#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust/Cargo is required. Install a Rust toolchain and rerun this script." >&2
  exit 1
fi
cargo build --release -p maclator
install -d "$HOME/bin"
install -m 755 "target/release/archshift-lator-native" "$HOME/bin/archshift-lator-native"
echo "Installed native engine to $HOME/bin/archshift-lator-native"
echo "Set ARCHSHIFT_LATOR_DYLD and ARCHSHIFT_LATOR_SYSROOT if required."
