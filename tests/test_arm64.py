import unittest

from archshift_lator.arm64 import UnsupportedInstruction, run_words


class ARM64LabTests(unittest.TestCase):
    def test_movz_add_ret(self):
        state, trace = run_words([0xD28000A0, 0x91000400, 0xD65F03C0])
        self.assertEqual(state.x[0], 6)
        self.assertTrue(state.halted)
        self.assertEqual([row.mnemonic for row in trace], ["MOVZ", "ADD", "RET"])

    def test_unknown_instruction_is_not_guessed(self):
        with self.assertRaises(UnsupportedInstruction):
            run_words([0xFFFFFFFF])


if __name__ == "__main__":
    unittest.main()
