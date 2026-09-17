"""Static guards for the default, self-contained deployment (docker/selfcontained.Dockerfile).

These read the packaging files as text so they run anywhere the unit tests
run; the image itself is exercised by building and running it (see
docs/todo/03-DOCKER-SELF-CONTAINED-TODO.md for that evidence).
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO / "docker" / "selfcontained.Dockerfile"
COMPOSE = REPO / "giso-webui" / "compose.yaml"
SOCKET_COMPOSE = REPO / "giso-webui" / "compose.socket.yaml"
ENV_EXAMPLE = REPO / "giso-webui" / ".env.example"


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
        self.assertIn('test "$(git rev-parse HEAD)" = "$GISOBUILD_COMMIT"', self.dockerfile)
        self.assertIn("GISO_RUNNER=local", self.dockerfile)
        self.assertIn("TOOL_ROOT=/opt/gisobuild", self.dockerfile)

    def test_image_verifies_and_records_one_sha256_of_the_gisobuild_source(self):
        pins = set(re.findall(r"^ARG GISOBUILD_SOURCE_SHA256=(\S+)$", self.dockerfile, re.MULTILINE))
        self.assertEqual(len(pins), 1, pins)
        self.assertRegex(pins.pop(), r"^[0-9a-f]{64}$")
        self.assertIn('sha256sum -c -', self.dockerfile)
        self.assertIn("COPY --from=source /gisobuild.sha256sums /opt/gisobuild.sha256sums", self.dockerfile)
        self.assertIn("GISOBUILD_SOURCE_MANIFEST=/opt/gisobuild.sha256sums", self.dockerfile)

    def test_default_compose_builds_our_image_and_the_socket_variant_is_explicit_and_pinned(self):
        self.assertIn("dockerfile: docker/selfcontained.Dockerfile", self.compose)
        # A published image can replace the local build without editing compose
        # (a real deployment ran "docker compose pull" against the local name).
        self.assertEqual(self.compose.count("image: ${GISO_WEBUI_IMAGE:-giso-webui-selfcontained}"), 2)
        self.assertIn("GISO_WEBUI_IMAGE", ENV_EXAMPLE.read_text())
        self.assertNotIn("GISO_IMAGE", self.compose)
        socket = SOCKET_COMPOSE.read_text()
        self.assertIn("/var/run/docker.sock", socket)
        images = re.findall(r"GISO_IMAGE:\s*\"\$\{GISO_IMAGE:-(\S+)\}\"", socket)
        self.assertEqual(len(images), 1, images)
        self.assertRegex(images[0], r"^ciscogisobuild/cisco-xr-gisobuild:[\w.]+@sha256:[0-9a-f]{64}$")
        # The app's own fallback is the same pinned reference.
        app_source = (REPO / "giso-webui" / "app.py").read_text()
        self.assertIn(f'"{images[0]}"', app_source)

    def test_env_example_sets_nothing_that_only_the_socket_deployment_uses(self):
        active = {line.split("=", 1)[0] for line in ENV_EXAMPLE.read_text().splitlines()
                  if "=" in line and not line.lstrip().startswith("#")}
        for socket_only in ("GISO_IMAGE", "GISO_PULL_TIMEOUT_SECONDS", "TOOL_ROOT"):
            self.assertNotIn(socket_only, active)
        for name in active:
            self.assertIn(f"${{{name}", self.compose, f"{name} in .env.example is not used by compose.yaml")

    def test_every_base_image_is_pinned_by_digest(self):
        bases = re.findall(r"^FROM\s+(\S+)", self.dockerfile, re.MULTILINE)
        self.assertEqual(len(bases), 2)
        for base in bases:
            self.assertRegex(base, r"@sha256:[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
