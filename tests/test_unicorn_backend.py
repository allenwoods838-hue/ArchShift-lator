import struct
import unittest

from archshift_lator import unicorn_backend as backend


@unittest.skipUnless(backend.Uc is not None, "optional Unicorn dependency not installed")
class UnicornBackendTests(unittest.TestCase):
    @staticmethod
    def words(*items):
        return struct.pack("<" + "I" * len(items), *items)

    def test_executes_arm64_arithmetic_and_returns(self):
        # movz x0, #5; add x0, x0, #1; ret
        code = self.words(0xD28000A0, 0x91000400, 0xD65F03C0)
        result = backend.emulate_raw_arm64(code)
        self.assertEqual(result.instruction_count, 3)
        self.assertEqual(result.stopped_reason, "returned")
        self.assertEqual(result.exit_code, 0)

    def test_handles_darwin_exit_svc(self):
        # movz x16, #1 (SYS_exit); movz x0, #7; svc #0x80
        code = self.words(0xD2800030, 0xD28000E0, 0xD4001001)
        result = backend.emulate_raw_arm64(code)
        self.assertEqual(result.stopped_reason, "guest called exit")
        self.assertEqual(result.exit_code, 7)

    def test_rejects_unaligned_blob(self):
        with self.assertRaises(ValueError):
            backend.emulate_raw_arm64(b"abc")


if __name__ == "__main__":
    unittest.main()
