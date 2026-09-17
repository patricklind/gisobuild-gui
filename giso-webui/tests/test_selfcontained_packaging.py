"""Static guards for the self-contained deployment (docker/selfcontained.Dockerfile).

These read the packaging files as text so they run anywhere the unit tests
run; the image itself is exercised by building and running it (see
docs/todo/03-DOCKER-SELF-CONTAINED-TODO.md for that evidence).
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO / "docker" / "selfcontained.Dockerfile"
COMPOSE = REPO / "giso-webui" / "compose.selfcontained.yaml"


class SelfContainedPackagingTests(unittest.TestCase):
    def setUp(self):
        if not DOCKERFILE.exists() or not COMPOSE.exists():
            self.skipTest("repository root is not mounted alongside giso-webui")
        self.dockerfile = DOCKERFILE.read_text()
        self.compose = COMPOSE.read_text()

    def test_compose_never_mounts_the_docker_socket_or_a_host_gisobuild_checkout(self):
        for forbidden in ("docker.sock", ".gisobuild-tool", "/tool", "privileged"):
            self.assertNotIn(forbidden, self.compose)
        self.assertIn("no-new-privileges:true", self.compose)
        self.assertIn("read_only: true", self.compose)

    def test_image_pins_one_exact_gisobuild_commit_and_uses_the_local_runner(self):
        commits = set(re.findall(r"^ARG GISOBUILD_COMMIT=(\S+)$", self.dockerfile, re.MULTILINE))
        self.assertEqual(len(commits), 1, commits)
        self.assertRegex(commits.pop(), r"^[0-9a-f]{40}$")
        self.assertIn('test "$(git -C /src rev-parse HEAD)" = "$GISOBUILD_COMMIT"', self.dockerfile)
        self.assertIn("GISO_RUNNER=local", self.dockerfile)
        self.assertIn("TOOL_ROOT=/opt/gisobuild", self.dockerfile)

    def test_image_verifies_and_records_one_sha256_of_the_gisobuild_source(self):
        pins = set(re.findall(r"^ARG GISOBUILD_SOURCE_SHA256=(\S+)$", self.dockerfile, re.MULTILINE))
        self.assertEqual(len(pins), 1, pins)
        self.assertRegex(pins.pop(), r"^[0-9a-f]{64}$")
        self.assertIn('sha256sum -c -', self.dockerfile)
        self.assertIn("COPY --from=source /gisobuild.sha256sums /opt/gisobuild.sha256sums", self.dockerfile)
        self.assertIn("GISOBUILD_SOURCE_MANIFEST=/opt/gisobuild.sha256sums", self.dockerfile)

    def test_every_base_image_is_pinned_by_digest(self):
        bases = re.findall(r"^FROM\s+(\S+)", self.dockerfile, re.MULTILINE)
        self.assertEqual(len(bases), 2)
        for base in bases:
            self.assertRegex(base, r"@sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
