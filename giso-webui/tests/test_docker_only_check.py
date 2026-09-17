"""The Docker-only documentation guard (scripts/check_docker_only.py)."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_docker_only.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_docker_only", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DockerOnlyCheckTests(unittest.TestCase):
    def setUp(self):
        if not SCRIPT.exists():
            self.skipTest("repository root is not mounted alongside giso-webui")
        self.checker = load_checker()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def commit(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        subprocess.run(["git", "-C", str(self.root), "add", name], check=True)

    def test_host_commands_are_flagged_and_containerised_ones_are_not(self):
        self.commit("README.md", (
            "Never run `python -m unittest` on the host.\n"
            "```bash\n"
            "python3 staging/rehearse.py\n"
            "docker run --rm -v \"$PWD:/project:ro\" gisobuild-tooling \\\n"
            "  python -B scripts/check_docker_only.py\n"
            "docker compose exec giso-webui python -c 'print(1)'\n"
            "pip install ruff  # docker-only: allow documenting the old way\n"
            "```\n"
            "```text\n"
            "PASS: rehearsal\n"
            "```\n"
        ))
        self.commit("tool.sh", "#!/bin/bash\n# python3 in a comment is fine\nruff check .\n")
        self.commit("docs/todo/old.md", "```bash\npytest\n```\n")

        found = self.checker.violations(self.root)

        self.assertEqual(len(found), 2, found)
        self.assertTrue(found[0].startswith("README.md:3: `python3`"), found)
        self.assertTrue(found[1].startswith("tool.sh:3: `ruff`"), found)

    def test_this_repository_passes(self):
        self.assertEqual(self.checker.violations(SCRIPT.parents[1]), [])


if __name__ == "__main__":
    unittest.main()
