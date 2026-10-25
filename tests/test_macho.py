import struct
import tempfile
import unittest
from pathlib import Path

from archshift_lator.macho import MachOError, inspect_macho


def thin64(cpu: int, kind: int = 2) -> bytes:
    return b"\xcf\xfa\xed\xfe" + struct.pack("<iiIII", cpu, 0, kind, 0, 0) + struct.pack("<II", 0, 0)


class MachOTests(unittest.TestCase):
    def test_thin_arm64(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binary"
            path.write_bytes(thin64(0x0100000C))
            info = inspect_macho(path)
            self.assertEqual(info.architectures, ["arm64"])
            self.assertTrue(info.has_arm64)
            self.assertEqual(info.file_type_name, "executable")

    def test_thin_x86_64(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binary"
            path.write_bytes(thin64(0x01000007))
            info = inspect_macho(path)
            self.assertTrue(info.has_x86_64)
            self.assertFalse(info.has_arm64)

    def test_rejects_non_macho(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "text"
            path.write_text("not a Mach-O")
            with self.assertRaises(MachOError):
                inspect_macho(path)


if __name__ == "__main__":
    unittest.main()
