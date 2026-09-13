import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BuildScriptTests(unittest.TestCase):
    def test_browser_prompts_use_the_in_app_dialog(self):
        web_root = Path(__file__).parents[1]
        script = (web_root / "static" / "app.js").read_text()
        template = (web_root / "templates" / "index.html").read_text()

        self.assertNotRegex(script, r"\b(?:alert|confirm)\s*\(")
        self.assertIn("showAppDialog", script)
        self.assertIn('id="app-dialog"', template)
        self.assertIn('aria-describedby="app-dialog-message"', template)

    def test_cisco_theme_is_loaded_last(self):
        web_root = Path(__file__).parents[1]
        template = (web_root / "templates" / "index.html").read_text()
        theme = (web_root / "static" / "cisco-theme.css").read_text()

        self.assertLess(template.index("compact.css"), template.index("cisco-theme.css"))
        self.assertIn("--navy: #0d2740", theme)
        self.assertIn("@media (prefers-reduced-motion: reduce)", theme)

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

    def test_real_iso_runner_rejects_non_local_url(self):
        with tempfile.TemporaryDirectory() as temp_name:
            iso = Path(temp_name) / "base.iso"
            iso.write_bytes(b"synthetic test marker")
            script = Path(__file__).parents[2] / "scripts/e2e_real_iso.py"
            result = subprocess.run(
                [sys.executable, str(script), str(iso), "--platform", "ncs5500",
                 "--url", "file:///tmp/fake-api"],
                capture_output=True, text=True, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP(S) origin", result.stderr)


if __name__ == "__main__":
    unittest.main()
