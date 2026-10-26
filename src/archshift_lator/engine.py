"""Maclator-override and bundled native-engine dispatch.

The bundled runtime is an attributed native backend under native/. If it is not
built, the Python front end falls back to diagnostics and the optional raw-code
emulator; it never reports an app launch as successful without process exit 0.
"""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess


@dataclass
class EngineResult:
    configured: bool
    success: bool
    message: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


def _native_candidates() -> list[str]:
    candidates = []
    override = os.environ.get("ARCHSHIFT_LATOR_NATIVE_ENGINE", "").strip()
    if override:
        candidates.append(override)
    project_root = Path(__file__).resolve().parents[2]
    candidates.append(str(project_root / "native" / "target" / "release" / "archshift-lator-native"))
    on_path = shutil.which("archshift-lator-native")
    if on_path:
        candidates.append(on_path)
    # De-duplicate while retaining preference order.
    return list(dict.fromkeys(candidates))


def _run(argv: list[str], label: str) -> EngineResult:
    try:
        timeout = float(os.environ.get(
            "ARCHSHIFT_LATOR_ENGINE_TIMEOUT",
            os.environ.get("ARCHSHIFT_MACLATOR_TIMEOUT", "900")
        ))
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            check=False, shell=False
        )
    except subprocess.TimeoutExpired:
        return EngineResult(True, False, f"{label} timed out.")
    except OSError as exc:
        return EngineResult(True, False, f"Could not start {label}: {exc}")
    success = completed.returncode == 0
    message = (
        f"{label} exited successfully."
        if success else f"{label} exited with status {completed.returncode}."
    )
    return EngineResult(
        True, success, message, completed.returncode,
        completed.stdout[-12000:], completed.stderr[-12000:]
    )


def _run_native(target: str | Path) -> EngineResult:
    for candidate in _native_candidates():
        expanded = Path(candidate).expanduser()
        executable = shutil.which(candidate)
        if executable is None and expanded.is_file():
            executable = str(expanded.resolve())
        if executable is None:
            continue
        argv = [executable]
        dyld = os.environ.get("ARCHSHIFT_LATOR_DYLD", "").strip()
        sysroot = os.environ.get("ARCHSHIFT_LATOR_SYSROOT", "").strip()
        if dyld:
            argv.extend(["--dyld", str(Path(dyld).expanduser().resolve())])
        if sysroot:
            argv.extend(["--sysroot", str(Path(sysroot).expanduser().resolve())])
        argv.append(str(Path(target).expanduser().resolve()))
        return _run(argv, "ArchShift-lator native engine")
    return EngineResult(
        False, False,
        "Bundled native engine is not built or not found. Build it with "
        "'cd native && cargo build --release -p maclator'."
    )


def try_external_engine(target: str | Path) -> EngineResult:
    """Try an explicitly configured engine, then the bundled ArchShift engine."""
    target_path = str(Path(target).expanduser().resolve())
    failures: list[str] = []
    captured_out: list[str] = []
    captured_err: list[str] = []

    raw = os.environ.get("ARCHSHIFT_MACLATOR_COMMAND", "").strip()
    if raw:
        try:
            template = shlex.split(raw)
        except ValueError as exc:
            failures.append(f"Invalid ARCHSHIFT_MACLATOR_COMMAND: {exc}")
            template = []
        if template:
            if not any("{target}" in item for item in template):
                failures.append("External command template must include the {target} placeholder.")
            else:
                executable = shutil.which(template[0])
                if executable is None and Path(template[0]).expanduser().is_file():
                    executable = str(Path(template[0]).expanduser().resolve())
                if executable is None:
                    failures.append(f"External engine executable not found: {template[0]}")
                else:
                    argv = [item.replace("{target}", target_path) for item in template]
                    argv[0] = executable
                    external = _run(argv, "Configured external engine")
                    if external.success:
                        return external
                    failures.append(external.message)
                    if external.stdout:
                        captured_out.append(external.stdout)
                    if external.stderr:
                        captured_err.append(external.stderr)

    native = _run_native(target)
    if native.success:
        if failures:
            native.message = "; ".join(failures) + "; bundled native engine succeeded."
            native.stdout = "\n".join(captured_out + ([native.stdout] if native.stdout else []))[-12000:]
            native.stderr = "\n".join(captured_err + ([native.stderr] if native.stderr else []))[-12000:]
        return native
    failures.append(native.message)
    if native.stdout:
        captured_out.append(native.stdout)
    if native.stderr:
        captured_err.append(native.stderr)
    return EngineResult(
        bool(raw) or native.configured, False,
        "No execution engine succeeded: " + " ".join(failures),
        native.returncode,
        "\n".join(captured_out)[-12000:],
        "\n".join(captured_err)[-12000:]
    )
