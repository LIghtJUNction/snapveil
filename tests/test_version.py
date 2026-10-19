"""Version transitions and rollback matter because one code is shared with an APK."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("snapveil_bump", ROOT / "tools/bump.py")
bump = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump)


class VersionTests(unittest.TestCase):
    def test_semantic_transitions_and_canonical_prefix(self):
        for requested, expected in (("patch", "v1.2.4"), ("minor", "v1.3.0"),
                                    ("major", "v2.0.0"), ("1.9.0", "v1.9.0")):
            with self.subTest(requested=requested):
                self.assertEqual(bump.next_version("v1.2.3", requested), expected)

    def test_same_lower_and_malformed_versions_are_rejected(self):
        for requested in ("v1.2.3", "1.2.2", "1.02.4", "v1.2.4\n", "1.2", "1.2.4;echo bad"):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                bump.next_version("v1.2.3", requested)

    def make_project(self, folder):
        root = Path(folder)
        (root / "tools").mkdir()
        (root / "src/snapveil").mkdir(parents=True)
        shutil.copy(ROOT / "tools/bump.py", root / "tools/bump.py")
        shutil.copy(ROOT / "kam.toml", root / "kam.toml")
        (root / "src/snapveil/module.prop").write_text("previous metadata\n")
        return root

    @unittest.skipUnless(shutil.which("kam"), "real Kam is required for the export integration")
    def test_real_kam_export_keeps_name_and_code_together(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_project(folder)
            initial = tomllib.loads((root / "kam.toml").read_text())["prop"]
            subprocess.run(["python3", "tools/bump.py", "patch"], cwd=root,
                           check=True, capture_output=True, text=True)
            prop = tomllib.loads((root / "kam.toml").read_text())["prop"]
            self.assertEqual(prop["versionCode"], initial["versionCode"] + 1)
            metadata = (root / "src/snapveil/module.prop").read_text()
            self.assertIn(f"version={prop['version']}\n", metadata)
            self.assertIn(f"versionCode={prop['versionCode']}\n", metadata)

    def test_export_failure_restores_both_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_project(folder)
            before = (root / "kam.toml").read_bytes()
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "kam"
            fake.write_text("#!/bin/sh\nprintf 'partial' > src/snapveil/module.prop\nexit 1\n")
            fake.chmod(0o755)
            result = subprocess.run(["python3", "tools/bump.py", "patch"], cwd=root,
                                    env=dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}"),
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "kam.toml").read_bytes(), before)
            self.assertEqual((root / "src/snapveil/module.prop").read_text(), "previous metadata\n")


if __name__ == "__main__":
    unittest.main()
