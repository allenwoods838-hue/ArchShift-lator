import ctypes
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from archshift_lator.arm64 import UnsupportedInstruction
from archshift_lator.translator import translate_words


class TranslatorTests(unittest.TestCase):
    def test_emits_x86_64_prologue_and_arithmetic(self):
        assembly = translate_words([0xD28000A0, 0x91000400, 0xD65F03C0])
        self.assertIn(".intel_syntax noprefix", assembly)
        self.assertIn("add rax, 1", assembly)
        self.assertIn("ret", assembly)

    def test_rejects_unknown_instructions(self):
        with self.assertRaises(UnsupportedInstruction):
            translate_words([0xFFFFFFFF])

    def test_rejects_branchless_blocks_without_return(self):
        with self.assertRaises(UnsupportedInstruction):
            translate_words([0xD503201F])

    @unittest.skipUnless(shutil.which("cc"), "a C compiler is required to assemble generated code")
    def test_generated_code_compiles_and_runs_on_x86_64(self):
        machine = platform.machine().lower()
        if machine not in ("x86_64", "amd64"):
            self.skipTest("generated code can only be loaded in an x86-64 test process")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "translated.s"
            library = folder / ("translated.dylib" if sys.platform == "darwin" else "translated.so")
            source.write_text(translate_words([0xD28000A0, 0x91000400, 0xD65F03C0]), encoding="utf-8")
            if sys.platform == "darwin":
                command = ["cc", "-arch", "x86_64", "-dynamiclib", str(source), "-o", str(library)]
            else:
                command = ["cc", "-shared", "-fPIC", str(source), "-o", str(library)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            loaded = ctypes.CDLL(str(library))
            function = loaded.archshift_guest
            function.argtypes = []
            function.restype = ctypes.c_uint64
            self.assertEqual(function(), 6)


if __name__ == "__main__":
    unittest.main()
