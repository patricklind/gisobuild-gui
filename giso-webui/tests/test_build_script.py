import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class BuildScriptTests(unittest.TestCase):
    def test_clean_rejects_traversal_outside_standard_output(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("Bash is not installed in the minimal runtime image")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            script = root / "build-giso.sh"
            shutil.copy2(Path(__file__).parents[2] / "build-giso.sh", script)
            iso = root / "base.iso"
            iso.write_bytes(b"iso")
            (root / "output_gisobuild_safe").mkdir()
            victim = root.parent / f"{root.name}-victim"
            victim.mkdir()
            (victim / "keep.txt").write_text("keep")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            docker = bin_dir / "docker"
            docker.write_text("#!/bin/sh\nexit 0\n")
            docker.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            try:
                result = subprocess.run(
                    [bash, str(script), "--iso", str(iso), "--output",
                     f"output_gisobuild_safe/../../{victim.name}", "--clean"],
                    capture_output=True, text=True, env=environment, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Refusing to clean", result.stderr)
                self.assertTrue((victim / "keep.txt").exists())
            finally:
                shutil.rmtree(victim, ignore_errors=True)

    def test_build_container_does_not_mount_entire_project(self):
        script = (Path(__file__).parents[2] / "build-giso.sh").read_text()
        self.assertNotIn('-v "$SCRIPT_DIR:/workspace"', script)


if __name__ == "__main__":
    unittest.main()
