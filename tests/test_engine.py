import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archshift_lator.engine import try_external_engine


class EngineRoutingTests(unittest.TestCase):
    def test_configured_external_engine_runs_without_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "guest"
            target.write_text("test guest")
            script = root / "external-engine"
            script.write_text("#!/bin/sh\nprintf '%s' "$1"\n")
            script.chmod(0o755)
            env = {"ARCHSHIFT_MACLATOR_COMMAND": f"{script} {{target}}", "PATH": ""}
            with patch.dict(os.environ, env, clear=True):
                result = try_external_engine(target)
            self.assertTrue(result.success)
            self.assertIn(str(target.resolve()), result.stdout)

    def test_bundled_engine_override_is_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "guest"
            target.write_text("test guest")
            script = root / "archshift-lator-native"
            script.write_text("#!/bin/sh\nexit 0\n")
            script.chmod(0o755)
            env = {"ARCHSHIFT_LATOR_NATIVE_ENGINE": str(script), "PATH": ""}
            with patch.dict(os.environ, env, clear=True):
                result = try_external_engine(target)
            self.assertTrue(result.success)
            self.assertIn("native engine", result.message)

    def test_missing_engine_falls_back_instead_of_claiming_success(self):
        with patch.dict(os.environ, {"PATH": ""}, clear=True):
            result = try_external_engine("/tmp/nonexistent-guest")
        self.assertFalse(result.success)
        self.assertIn("not built or not found", result.message)


if __name__ == "__main__":
    unittest.main()
