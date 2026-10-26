"""Fallback analysis and Maclator-first orchestration."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os
import plistlib

from .engine import EngineResult, try_external_engine
from .macho import MachOError, MachOInfo, inspect_macho


@dataclass
class InspectionReport:
    target: str
    binaries: list[MachOInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files_checked: int = 0

    @property
    def has_arm64(self) -> bool:
        return any(item.has_arm64 for item in self.binaries)

    @property
    def has_x86_64(self) -> bool:
        return any(item.has_x86_64 for item in self.binaries)


@dataclass
class RouteReport:
    target: str
    engine: EngineResult
    inspection: InspectionReport | None
    message: str


def resolve_app_executable(target: str | Path) -> Path:
    """Resolve .app bundle paths to CFBundleExecutable for the native engine."""
    p = Path(target).expanduser()
    if not (p.is_dir() and p.suffix.lower() == ".app"):
        return p
    contents = p / "Contents"
    info_path = contents / "Info.plist"
    if info_path.is_file():
        try:
            with info_path.open("rb") as stream:
                info = plistlib.load(stream)
            name = info.get("CFBundleExecutable")
            if isinstance(name, str) and name and Path(name).name == name:
                candidate = contents / "MacOS" / name
                if candidate.is_file():
                    return candidate
        except (OSError, plistlib.InvalidFileException, ValueError):
            pass
    # Damaged or nonstandard Info.plist: choose the first recognizable ARM64
    # Mach-O executable in Contents/MacOS rather than passing a directory to
    # the native loader. This fallback is inspection-only until one is found.
    macos_dir = contents / "MacOS"
    if macos_dir.is_dir():
        for candidate in sorted(macos_dir.iterdir()):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            try:
                if inspect_macho(candidate).has_arm64:
                    return candidate
            except (OSError, MachOError, ValueError):
                continue
    return p


def inspect_target(target: str | Path, max_files: int = 20000) -> InspectionReport:
    p = Path(target).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Target does not exist: {p}")
    report = InspectionReport(str(p.resolve()))
    if p.is_file():
        candidates = [p]
    elif p.is_dir():
        candidates = []
        for root, dirs, names in os.walk(p, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
            for name in names:
                item = Path(root) / name
                if item.is_file() and not item.is_symlink():
                    candidates.append(item)
                    if len(candidates) >= max_files:
                        report.errors.append(f"Scan capped at {max_files} files.")
                        break
            if len(candidates) >= max_files:
                break
    else:
        raise ValueError("Target must be a regular file or directory")

    for candidate in candidates:
        report.files_checked += 1
        try:
            info = inspect_macho(candidate)
        except (MachOError, OSError, ValueError):
            continue
        report.binaries.append(info)
    if not report.binaries:
        report.errors.append("No recognized Mach-O binaries were found in the target.")
    return report


def run_with_fallback(target: str | Path) -> RouteReport:
    p = Path(target).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Target does not exist: {p}")
    launch_target = resolve_app_executable(p)
    engine = try_external_engine(launch_target)
    if engine.success:
        return RouteReport(str(p), engine, None, "The configured or bundled native engine exited successfully.")
    inspection = inspect_target(p)
    if inspection.has_arm64:
        detail = (
            f"ARM64 Mach-O detected ({launch_target}). The native engine did not complete successfully; "
            "inspect the engine error above and check dyld/sysroot readiness with 'archshift-lator doctor'."
        )
    elif inspection.has_x86_64:
        detail = "An x86_64 slice exists. The app may have a native Intel build; no conversion was performed."
    else:
        detail = "No supported architecture was identified by fallback inspection."
    message = f"{engine.message} Fallback result: {detail}"
    return RouteReport(str(p), engine, inspection, message)
