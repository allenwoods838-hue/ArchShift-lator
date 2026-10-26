import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archshift_lator.fallback import run_with_fallback


def thin_arm64() -> bytes:
    return b"\xcf\xfa\xed\xfe" + struct.pack("<iiIII", 0x0100000C, 0, 2, 0, 0) + struct.pack("<II", 0, 0)


class FallbackTests(unittest.TestCase):
    def test_unconfigured_engine_falls_back_to_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "arm64-executable"
            target.write_bytes(thin_arm64())
            with patch.dict(os.environ, {}, clear=True):
                report = run_with_fallback(target)
            self.assertFalse(report.engine.success)
            self.assertIsNotNone(report.inspection)
            self.assertTrue(report.inspection.has_arm64)
            self.assertIn("did not complete successfully", report.message)


if __name__ == "__main__":
    unittest.main()
