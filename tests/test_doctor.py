import unittest

from archshift_lator.doctor import collect_diagnostics


class DoctorTests(unittest.TestCase):
    def test_reports_host_and_runtime_status(self):
        diagnostics = dict(collect_diagnostics())
        self.assertIn("Host", diagnostics)
        self.assertIn("Python", diagnostics)
        self.assertIn("Native runtime", diagnostics)
        self.assertIn("Guest dyld", diagnostics)
        self.assertIn("Guest sysroot", diagnostics)


if __name__ == "__main__":
    unittest.main()
