"""Host preflight diagnostics for the native execution engine."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess


def _native_path() -> Path | None:
    override = os.environ.get("ARCHSHIFT_LATOR_NATIVE_ENGINE", "").strip()
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path(__file__).resolve().parents[2] / "native" / "target" / "release" / "archshift-lator-native")
    path_engine = shutil.which("archshift-lator-native")
    if path_engine:
        candidates.append(Path(path_engine))
    for candidate in candidates:
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()
        except OSError:
            continue
    return None


def _dyld_architectures(path: Path) -> str:
    lipo = shutil.which("lipo")
    if not lipo or not path.is_file():
        return "not checked (lipo unavailable or dyld missing)"
    try:
        completed = subprocess.run([lipo, "-archs", str(path)], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "unable to inspect"
    if completed.returncode != 0:
        return "not a recognized universal Mach-O"
    return completed.stdout.strip() or "unknown"


def collect_diagnostics() -> list[tuple[str, str]]:
    details: list[tuple[str, str]] = []
    system = platform.system()
    machine = platform.machine().lower()
    details.append(("Host", f"{system} {platform.mac_ver()[0] or ''} ({machine})".strip()))
    details.append(("Python", platform.python_version()))

    if system != "Darwin":
        details.append(("Native runtime", "macOS-only; this host cannot launch macOS userland"))
    elif machine not in ("x86_64", "amd64"):
        details.append(("Native runtime", "unsupported host architecture for the bundled Intel runtime"))
    else:
        engine = _native_path()
        details.append(("Native engine", str(engine) if engine else "not built/found; run native/scripts/install-archshift-lator.sh"))
        version = tuple(int(part) for part in platform.mac_ver()[0].split(".")[:2] if part.isdigit())
        if version and version < (26, 0):
            details.append(("Host version", "older than the upstream tested macOS 26 target; app execution is unverified"))
        else:
            details.append(("Host version", "matches or exceeds the documented macOS 26 test generation; app compatibility is still experimental"))

    dyld_value = os.environ.get("ARCHSHIFT_LATOR_DYLD", "").strip()
    dyld_path = Path(dyld_value).expanduser() if dyld_value else Path("/usr/lib/dyld")
    details.append(("Guest dyld", str(dyld_path) if dyld_path.is_file() else f"missing: {dyld_path}"))
    details.append(("dyld slices", _dyld_architectures(dyld_path)))

    sysroot_value = os.environ.get("ARCHSHIFT_LATOR_SYSROOT", "").strip()
    if sysroot_value:
        sysroot = Path(sysroot_value).expanduser()
        has_cache = sysroot.is_file() or (
            sysroot.is_dir() and any(sysroot.glob("**/dyld_shared_cache_arm64e"))
        )
        details.append(("Guest sysroot", f"{sysroot} ({'cache/file detected' if has_cache else 'directory supplied, cache not detected'})"))
    else:
        discovered = [
            Path.home() / "maclator-sysroot",
            Path.home() / ".maclator" / "sysroot",
            Path.home() / ".archshift-lator" / "sysroot",
        ]
        found = next((p for p in discovered if p.exists()), None)
        details.append(("Guest sysroot", f"candidate found: {found}" if found else "not configured"))
    details.append(("Unicorn raw-code backend", "available" if importlib.util.find_spec("unicorn") else "optional dependency not installed"))
    return details
