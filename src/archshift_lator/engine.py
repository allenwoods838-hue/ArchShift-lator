"""Configured subprocess bridge to an optional external translation engine."""
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


def try_external_engine(target: str | Path) -> EngineResult:
    raw = os.environ.get("ARCHSHIFT_MACLATOR_COMMAND", "").strip()
    if not raw:
        return EngineResult(False, False, "ARCHSHIFT_MACLATOR_COMMAND is not configured.")
    try:
        template = shlex.split(raw)
    except ValueError as exc:
        return EngineResult(True, False, f"Invalid engine command template: {exc}")
    if not template or not any("{target}" in item for item in template):
        return EngineResult(True, False, "Command template must include the {target} placeholder.")
    executable = shutil.which(template[0])
    if executable is None and Path(template[0]).is_file():
        executable = str(Path(template[0]).expanduser().resolve())
    if executable is None:
        return EngineResult(True, False, f"Engine executable not found: {template[0]}")
    argv = [item.replace("{target}", str(Path(target).expanduser().resolve())) for item in template]
    argv[0] = executable
    try:
        timeout = float(os.environ.get("ARCHSHIFT_MACLATOR_TIMEOUT", "900"))
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False, shell=False)
    except subprocess.TimeoutExpired:
        return EngineResult(True, False, "External engine timed out; handing off to fallback diagnostics.")
    except OSError as exc:
        return EngineResult(True, False, f"Could not start external engine: {exc}")
    success = completed.returncode == 0
    message = "External engine completed successfully." if success else f"External engine exited with status {completed.returncode}; using fallback."
    return EngineResult(True, success, message, completed.returncode, completed.stdout[-12000:], completed.stderr[-12000:])
