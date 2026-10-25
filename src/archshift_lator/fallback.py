"""Fallback analysis and Maclator-first orchestration."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os

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
    engine = try_external_engine(p)
    if engine.success:
        return RouteReport(str(p), engine, None, "The configured external engine reported success.")
    inspection = inspect_target(p)
    if inspection.has_x86_64:
        detail = "An x86_64 slice exists; native launch selection is not implemented by this prototype."
    elif inspection.has_arm64:
        detail = "ARM64 Mach-O detected. The Python fallback can inspect it, but cannot yet run or convert arbitrary apps."
    else:
        detail = "No supported architecture was identified by fallback inspection."
    message = f"{engine.message} Fallback result: {detail}"
    return RouteReport(str(p), engine, inspection, message)
