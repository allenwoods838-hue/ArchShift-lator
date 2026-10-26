import plistlib
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archshift_lator.fallback import resolve_app_executable, run_with_fallback
from archshift_lator.engine import EngineResult


def thin_arm64() -> bytes:
    return b"\xcf\xfa\xed\xfe" + struct.pack("<iiIII", 0x0100000C, 0, 2, 0, 0) + struct.pack("<II", 0, 0)


class AppBundleResolutionTests(unittest.TestCase):
    def make_app(self, root: Path) -> tuple[Path, Path]:
        app = root / "Sample.app"
        macos = app / "Contents" / "MacOS"
        macos.mkdir(parents=True)
        executable = macos / "Sample"
        executable.write_bytes(thin_arm64())
        info = {"CFBundleExecutable": "Sample", "CFBundleIdentifier": "test.sample"}
        with (app / "Contents" / "Info.plist").open("wb") as stream:
            plistlib.dump(info, stream)
        return app, executable

    def test_resolves_cf_bundle_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, executable = self.make_app(Path(tmp))
            self.assertEqual(resolve_app_executable(app), executable)

    def test_uses_resolved_executable_for_engine_then_inspects_bundle_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, executable = self.make_app(Path(tmp))
            failure = EngineResult(False, False, "native engine not installed")
            with patch("archshift_lator.fallback.try_external_engine", return_value=failure) as try_engine:
                report = run_with_fallback(app)
            self.assertEqual(Path(try_engine.call_args.args[0]), executable)
            self.assertEqual(report.target, str(app))
            self.assertTrue(report.inspection.has_arm64)


if __name__ == "__main__":
    unittest.main()
