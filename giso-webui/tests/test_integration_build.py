"""Synthetic end-to-end build integration: the real job pipeline, a fake engine.

Everything from POST /api/jobs onward is the real code - BuildPlan,
build_command(), run_job()'s pull/run/stream loop, artifact discovery,
archive and cleanup, persisted job state, the post-failure dependency
parser. Only the docker CLI is replaced, by a small executable that answers
`inspect`, `ps` and `pull` like Docker and, for `run`, behaves like
gisobuild: it records its arguments, prints gisobuild-style output and
either writes a Golden ISO to the requested output directory or fails the
RPM dependency check. No container, image, network or Cisco content is used.
"""

import hashlib
import io
import itertools
import json
import os
import stat
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as module

FAKE_DOCKER = r"""#!__PYTHON__
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
command = args[0] if args else ""
if command == "inspect":
    print(json.dumps([{"Mounts": [
        {"Type": "volume", "Name": "giso-uploads", "Destination": "/uploads"},
        {"Type": "volume", "Name": "giso-output", "Destination": "/output"},
        {"Type": "bind", "Source": "/srv/gisobuild", "Destination": "/tool"},
        {"Type": "volume", "Name": "giso-work", "Destination": "/work"},
    ]}]))
elif command == "ps":
    pass  # no build container running
elif command == "pull":
    if os.environ.get("FAKE_PULL") == "fail":
        print("Error response from daemon: registry unreachable")
        sys.exit(1)
    print("Status: Image is up to date for " + args[-1])
elif command == "image" and args[1:2] == ["inspect"]:
    if os.environ.get("FAKE_IMAGE_CACHED", "1") == "0":
        print("Error: No such image: " + args[-1], file=sys.stderr)
        sys.exit(1)
    print("sha256:" + "c0" * 32)
elif command == "stop":
    with open(os.environ["FAKE_DOCKER_STOPS"], "a") as handle:
        handle.write(args[-1] + "\n")
elif command == "run":
    with open(os.environ["FAKE_DOCKER_ARGS"], "w") as handle:
        json.dump(args, handle)
    script = args.index("/tool/src/gisobuild.py")
    engine_args = args[script + 1:]
    out_dir = engine_args[engine_args.index("--out-directory") + 1]
    output = Path(os.environ["FAKE_OUTPUT_ROOT"]) / Path(out_dir).relative_to("/output")
    print("Gisobuild starting", flush=True)
    print("Validating inputs and RPM dependencies", flush=True)
    if os.environ.get("FAKE_GISOBUILD_MODE") == "slow":
        import time
        time.sleep(60)
    if os.environ.get("FAKE_GISOBUILD_MODE") == "dependency-failure":
        print("error: Failed dependencies:")
        print("\tncs5500-dpa = 1.0.0.5 is needed by "
              "ncs5500-routing-1.0.0.2-r2512.CSCtest00001.x86_64")
        sys.exit(1)
    output.mkdir(parents=True, exist_ok=True)
    label = engine_args[engine_args.index("--label") + 1] if "--label" in engine_args else "golden"
    (output / f"ncs5500-golden-x-25.1.2-{label}.iso").write_bytes(b"synthetic golden iso")
    (output / "gisobuild.log").write_text("build complete\n")
    print("Golden ISO build complete", flush=True)
else:
    sys.exit(f"fake docker: unsupported command {command!r}")
"""


class SyntheticBuildIntegrationTests(unittest.TestCase):
    ISO = "ncs5500-x64-25.1.2.iso"
    ROUTING = "ncs5500-routing-1.0.0.2-r2512.CSCtest00001.x86_64.rpm"
    OTHER_RELEASE = "ncs5500-bgp-1.0.0.1-r2612.CSCtest00002.x86_64.rpm"

    def setUp(self):
        # run_job() runs in a fire-and-forget daemon thread that keeps doing
        # real work (verification, archiving, cleanup, the final status
        # update) well after it drops out of module.job_processes - the only
        # thing the old tearDown() waited for. A test's own assertions run
        # fast enough to never notice, but tearDown() returning early let the
        # *next* test's setUp() reset module.DATA/WORK/jobs while a build
        # thread from the previous test was still reading and writing them,
        # a cross-test race a slower/more loaded CI runner hit for real.
        self._threads_before_test = {t.ident for t in threading.enumerate()}
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        for name in ("uploads", "output", "work", "archive", "state", "bin"):
            (root / name).mkdir()
        module.DATA = (root / "uploads").resolve()
        module.OUTPUT = (root / "output").resolve()
        module.WORK = (root / "work").resolve()
        module.ARCHIVE = (root / "archive").resolve()
        module.STATE = (root / "state").resolve()
        module.JOB_DB = module.STATE / "jobs.sqlite3"
        module.store_initialized = False
        for registry in (
            module.uploads,
            module.jobs,
            module.job_processes,
            module.job_persisted_at,
            module.cisco_download_jobs,
        ):
            registry.clear()
        docker = root / "bin" / "docker"
        docker.write_text(FAKE_DOCKER.replace("__PYTHON__", sys.executable))
        docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
        self.args_file = root / "docker-run-args.json"
        self.stops_file = root / "docker-stops.txt"
        self.patches = [
            patch.object(module, "DOCKER_BIN", str(docker)),
            patch.dict(
                os.environ,
                {
                    "FAKE_DOCKER_ARGS": str(self.args_file),
                    "FAKE_DOCKER_STOPS": str(self.stops_file),
                    "FAKE_OUTPUT_ROOT": str(module.OUTPUT),
                    "HOSTNAME": "giso-webui",
                },
            ),
            patch("app.gisobuild_tool_available", return_value=True),
            patch("app.is_iso9660_image", return_value=True),
            patch(
                "app.shutil.disk_usage",
                return_value=SimpleNamespace(free=100 * 1024**3),
            ),
        ]
        for active in self.patches:
            active.start()
        self.client = module.app.test_client()

    def tearDown(self):
        deadline = time.monotonic() + 10
        while module.job_processes and time.monotonic() < deadline:
            time.sleep(0.05)
        # The subprocess handle above is gone well before run_job()'s own
        # thread finishes (verification, archiving, cleanup, the final
        # status update all happen after it) - wait for the thread itself,
        # not just the process, so the next test's setUp() never resets
        # module.DATA/WORK/jobs out from under still-running work.
        stray = [
            t for t in threading.enumerate() if t.ident not in self._threads_before_test
        ]
        for thread in stray:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        for active in reversed(self.patches):
            active.stop()
        module.store_initialized = False
        self.temp.cleanup()

    def write(self, name, content=None):
        path = module.DATA / name
        path.write_bytes(content if content is not None else name.encode())
        return path

    def upload(self, name, content):
        """The real browser upload protocol: init, chunked PUT, complete."""
        started = self.client.post(
            "/api/uploads/init", json={"name": name, "size": len(content)}
        )
        self.assertEqual(started.status_code, 200, started.get_json())
        upload_id = started.get_json()["id"]
        self.assertEqual(
            self.client.put(
                f"/api/uploads/{upload_id}?offset=0", data=content
            ).status_code,
            200,
        )
        completed = self.client.post(f"/api/uploads/{upload_id}/complete")
        self.assertEqual(completed.status_code, 200, completed.get_json())
        return completed.get_json()

    @staticmethod
    def smu_tar(smu, rpms):
        """A Cisco-style SMU tar: the RPMs plus a README whose RPMS block lists them."""
        listing = "".join(
            f"\t{name} {hashlib.md5(body, usedforsecurity=False).hexdigest()}\n"
            for name, body in rpms.items()
        )
        readme = (
            f"Name:                    {smu}\n\nRPMS: \n{listing}\t\n"
            "Pre-requisites:          \n"
        ).encode()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name, body in {**rpms, f"{smu}.txt": readme}.items():
                info = tarfile.TarInfo(name)
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))
        return buffer.getvalue()

    def start_build(self, payload):
        response = self.client.post("/api/jobs", json=payload)
        self.assertEqual(response.status_code, 202, response.get_json())
        return response.get_json()["id"]

    def wait_for_job(self, job_id, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").get_json()
            if job["status"] not in module.ACTIVE_JOB_STATUSES:
                return job
            time.sleep(0.05)
        self.fail(f"job {job_id} did not finish: {job}")

    def test_exr_build_runs_the_plan_archives_the_image_and_cleans_inputs(self):
        # upload -> extract -> inspect -> inventory -> BuildPlan -> engine ->
        # output verification -> archive, through the same endpoints the page uses.
        self.upload(self.ISO, b"synthetic base iso")
        extracted = self.upload(
            "ncs5500-25.1.2.CSCtest00001.tar",
            self.smu_tar("ncs5500-25.1.2.CSCtest00001", {self.ROUTING: b"routing rpm"}),
        )
        self.assertEqual(extracted["extracted"], 2)
        self.write(self.OTHER_RELEASE)
        inputs = self.client.get("/api/inputs").get_json()
        self.assertEqual(inputs["recommended"], [self.ROUTING])
        iso = next(
            module.DATA / item["relative_path"]
            for item in inputs["files"]
            if item["type"] == ".iso"
        )
        rpm = next(
            module.DATA / item["relative_path"]
            for item in inputs["files"]
            if item["basename"] == self.ROUTING
        )
        job_id = self.start_build(
            {
                "iso": iso.name,
                "automatic_smu_selection": True,
                "pkglist": [],
                "label": "INTEGRATION",
            }
        )
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "success", job.get("log"))
        self.assertEqual(job["exit_code"], 0)
        self.assertEqual(module.jobs[job_id]["builder_image"]["source"], "registry")
        # Every pipeline step is recorded in order with its own timing.
        stages = module.jobs[job_id]["stages"]
        self.assertEqual(
            [entry["stage"] for entry in stages],
            [
                "preflight",
                "preparing_builder",
                "building",
                "verifying",
                "archiving",
                "complete",
            ],
        )
        self.assertEqual(job["stage"], "complete")
        for earlier, later in itertools.pairwise(stages):
            self.assertLessEqual(earlier["started"], earlier["ended"])
            self.assertEqual(earlier["ended"], later["started"])
        self.assertIn("Gisobuild starting", job["log"])
        self.assertIn("Golden ISO build complete", job["log"])

        # The engine received exactly the reviewed plan: the base ISO, a
        # staged repository holding only the compatible RPM, the label and
        # the per-job output directory.
        args = json.loads(self.args_file.read_text())
        engine = args[args.index("/tool/src/gisobuild.py") + 1 :]
        self.assertEqual(engine[engine.index("--iso") + 1], str(iso))
        repo = Path(engine[engine.index("--repo") + 1])
        self.assertEqual(repo, module.WORK / job_id / "repo")
        self.assertEqual(engine[engine.index("--label") + 1], "INTEGRATION")
        self.assertEqual(
            engine[engine.index("--out-directory") + 1], f"/output/{job_id}"
        )
        self.assertIn("-v", args)
        self.assertIn("giso-output:/output:rw", args)
        self.assertNotIn("/var/run/docker.sock", " ".join(args))
        plan = module.jobs[job_id]["build_plan"]
        self.assertEqual(
            [item["basename"] for item in plan["selected_packages"]], [self.ROUTING]
        )
        self.assertIn(
            self.OTHER_RELEASE, {item["name"] for item in plan["excluded_packages"]}
        )

        # Finalization: the image is archived and the consumed inputs removed.
        archived = sorted(path.name for path in (module.ARCHIVE / job_id).iterdir())
        self.assertIn("ncs5500-golden-x-25.1.2-INTEGRATION.iso", archived)
        self.assertTrue(any(item["path"].endswith(".iso") for item in job["artifacts"]))
        self.assertFalse(rpm.exists())
        self.assertFalse(iso.exists())

        # Job state is persisted, not only held in memory: a fresh process
        # (simulated by dropping memory and re-initializing the store) sees it.
        module.jobs.clear()
        module.store_initialized = False
        restored = self.client.get(f"/api/jobs/{job_id}").get_json()
        self.assertEqual(restored["status"], "success")

    def test_exr_dependency_failure_is_reported_and_inputs_are_kept(self):
        iso = self.write(self.ISO)
        rpm = self.write(self.ROUTING)
        with patch.dict(os.environ, {"FAKE_GISOBUILD_MODE": "dependency-failure"}):
            job_id = self.start_build(
                {"iso": self.ISO, "automatic_smu_selection": True, "pkglist": []}
            )
            job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["exit_code"], 1)
        self.assertEqual(job["failure"]["code"], "DEPENDENCY_ERROR")
        self.assertEqual(
            [e["stage"] for e in module.jobs[job["id"]]["stages"]],
            ["preflight", "preparing_builder", "building", "verifying", "failed"],
        )
        # Scratch space (staged repo copies) is gone; gisobuild's output dir is not touched.
        self.assertFalse((module.WORK / job["id"]).exists())
        self.assertEqual(
            job["missing_dependencies"],
            [
                {
                    "requirement": "ncs5500-dpa = 1.0.0.5",
                    "required_by": "ncs5500-routing-1.0.0.2-r2512.CSCtest00001.x86_64",
                }
            ],
        )
        self.assertFalse((module.ARCHIVE / job_id).exists())
        self.assertTrue(iso.exists())
        self.assertTrue(rpm.exists())

    def test_work_directory_is_gone_before_status_becomes_externally_visible_as_failed(
        self,
    ):
        # A synthetic-integration run on a slower/more loaded CI runner
        # failed exactly the assertion above (module.WORK / job_id gone)
        # intermittently, while never failing locally: run_job() used to
        # publish status="failed" to the jobs dict *before* calling
        # discard_job_work_directory(), so a client polling GET /api/jobs
        # (as wait_for_job() does) could observe "failed" and still find the
        # scratch directory there for a moment. This pins the real ordering
        # directly, rather than relying on winning a timing race to notice a
        # regression.
        seen_status_at_cleanup = []
        real_discard = module.discard_job_work_directory

        def spy(job_id):
            with module.job_lock:
                seen_status_at_cleanup.append(module.jobs[job_id]["status"])
            real_discard(job_id)

        self.write(self.ISO)
        self.write(self.ROUTING)
        with (
            patch.dict(os.environ, {"FAKE_GISOBUILD_MODE": "dependency-failure"}),
            patch.object(module, "discard_job_work_directory", side_effect=spy),
        ):
            job_id = self.start_build(
                {"iso": self.ISO, "automatic_smu_selection": True, "pkglist": []}
            )
            job = self.wait_for_job(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(seen_status_at_cleanup, ["running"])

    def test_lnt_build_passes_lnt_only_options_to_the_engine(self):
        self.write("8000-x86_64-24.2.11.iso")
        self.write("router.cfg", b"hostname lnt\n")
        job_id = self.start_build(
            {
                "iso": "8000-x86_64-24.2.11.iso",
                "platform": "8000",
                "pkglist": [],
                "automatic_smu_selection": False,
                "xrconfig": "router.cfg",
                "remove_packages": ["xr-telnet"],
                "label": "LNT_SYNTH",
            }
        )
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "success", job.get("log"))
        args = json.loads(self.args_file.read_text())
        engine = args[args.index("/tool/src/gisobuild.py") + 1 :]
        self.assertEqual(
            engine[engine.index("--xrconfig") + 1], str(module.DATA / "router.cfg")
        )
        self.assertEqual(engine[engine.index("--remove-packages") + 1], "xr-telnet")
        self.assertNotIn("--repo", engine)  # nothing selected, nothing staged
        self.assertEqual(module.jobs[job_id]["build_plan"]["engine"], "lnt")
        self.assertTrue(
            (module.ARCHIVE / job_id / "ncs5500-golden-x-25.1.2-LNT_SYNTH.iso").exists()
        )

    def test_cancelling_a_running_build_stops_the_container_and_keeps_inputs(self):
        iso = self.write(self.ISO)
        rpm = self.write(self.ROUTING)
        with patch.dict(os.environ, {"FAKE_GISOBUILD_MODE": "slow"}):
            job_id = self.start_build(
                {"iso": self.ISO, "automatic_smu_selection": True, "pkglist": []}
            )
            deadline = time.monotonic() + 10
            while "Validating inputs" not in module.jobs[job_id]["log"]:
                self.assertLess(time.monotonic(), deadline, module.jobs[job_id]["log"])
                time.sleep(0.05)
            self.assertEqual(
                self.client.get(f"/api/jobs/{job_id}").get_json()["status"], "running"
            )
            response = self.client.delete(f"/api/jobs/{job_id}")
            self.assertEqual(response.status_code, 200, response.get_json())
            job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "cancelled")
        self.assertIn("Build cancelled by user.", job["log"])
        self.assertEqual(job["stage"], "cancelled")
        self.assertFalse((module.WORK / job_id).exists())
        self.assertNotIn("verifying", [e["stage"] for e in job["stages"]])
        self.assertEqual(self.stops_file.read_text().split(), [f"giso-build-{job_id}"])
        self.assertFalse((module.ARCHIVE / job_id).exists())
        self.assertTrue(iso.exists())
        self.assertTrue(rpm.exists())
        # A second cancel is refused rather than re-stopping anything.
        self.assertEqual(self.client.delete(f"/api/jobs/{job_id}").status_code, 409)

    def test_consecutive_builds_use_only_their_own_inventory(self):
        self.write(self.ISO)
        self.write(self.ROUTING)
        first = self.wait_for_job(
            self.start_build(
                {
                    "iso": self.ISO,
                    "automatic_smu_selection": True,
                    "pkglist": [],
                    "label": "FIRST",
                }
            )
        )
        self.assertEqual(first["status"], "success", first.get("log"))

        # The first build consumed its inputs; the second starts from what is
        # in the workspace now, not from anything the first one used.
        self.write(self.ISO, b"second base iso")
        second_rpm = "ncs5500-bgp-1.0.0.1-r2512.CSCtest00002.x86_64.rpm"
        self.write(second_rpm)
        second_id = self.start_build(
            {
                "iso": self.ISO,
                "automatic_smu_selection": True,
                "pkglist": [],
                "label": "SECOND",
            }
        )
        second = self.wait_for_job(second_id)
        self.assertEqual(second["status"], "success", second.get("log"))

        plan = module.jobs[second_id]["build_plan"]
        self.assertEqual(
            [item["basename"] for item in plan["selected_packages"]], [second_rpm]
        )
        self.assertNotEqual(
            plan["iso"]["sha256"],
            module.jobs[first["id"]]["build_plan"]["iso"]["sha256"],
        )
        self.assertEqual(
            sorted(path.name for path in (module.ARCHIVE / first["id"]).glob("*.iso")),
            ["ncs5500-golden-x-25.1.2-FIRST.iso"],
        )
        self.assertEqual(
            sorted(path.name for path in (module.ARCHIVE / second_id).glob("*.iso")),
            ["ncs5500-golden-x-25.1.2-SECOND.iso"],
        )

    def test_registry_outage_builds_with_the_cached_builder_image(self):
        self.write(self.ISO)
        self.write(self.ROUTING)
        with (
            patch.dict(os.environ, {"FAKE_PULL": "fail"}),
            patch.object(
                module, "IMAGE", "ciscogisobuild/cisco-xr-gisobuild@sha256:" + "be" * 32
            ),
        ):
            job = self.wait_for_job(
                self.start_build(
                    {"iso": self.ISO, "automatic_smu_selection": True, "pkglist": []}
                )
            )
        self.assertEqual(job["status"], "success", job.get("log"))
        self.assertIn("registry unreachable", job["log"])
        self.assertIn("digest-pinned, so it is identical", job["log"])
        self.assertEqual(module.jobs[job["id"]]["builder_image"]["source"], "cache")
        self.assertEqual(
            module.jobs[job["id"]]["builder_image"]["id"], "sha256:" + "c0" * 32
        )

    def test_registry_outage_without_a_cached_image_fails_clearly(self):
        iso = self.write(self.ISO)
        rpm = self.write(self.ROUTING)
        with patch.dict(os.environ, {"FAKE_PULL": "fail", "FAKE_IMAGE_CACHED": "0"}):
            job = self.wait_for_job(
                self.start_build(
                    {"iso": self.ISO, "automatic_smu_selection": True, "pkglist": []}
                )
            )
        self.assertEqual(job["status"], "failed")
        self.assertIn(
            "could not be pulled (exited with status 1) and is not cached", job["log"]
        )
        self.assertEqual(
            [e["stage"] for e in job["stages"]],
            ["preflight", "preparing_builder", "failed"],
        )
        self.assertFalse(self.args_file.exists())  # the engine never ran
        self.assertTrue(iso.exists())
        self.assertTrue(rpm.exists())


FAKE_LOCAL_GISOBUILD = r"""
import json, os, subprocess, sys, time
from pathlib import Path

# The build environment is sanitized, so test settings come from a file next
# to this script rather than environment variables.
config = json.loads((Path(__file__).resolve().parent.parent / "fake-config.json").read_text())
args = sys.argv[1:]
Path(config["record"]).write_text(json.dumps({
    "argv": [sys.executable, __file__] + args, "env": dict(os.environ), "cwd": os.getcwd(),
}))
print("Gisobuild starting (local)", flush=True)
if config.get("mode") == "slow":
    out = Path(args[args.index("--out-directory") + 1])
    (out / "tmpextract" / "boot").mkdir(parents=True, exist_ok=True)  # like gisobuild's ISO extraction
    (out / "logs").mkdir(parents=True, exist_ok=True)
    (out / "logs" / "gisobuild.log").write_text("started\n")
    (out / "system_image.iso").write_bytes(b"inner image")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    Path(config["child_pid"]).write_text(str(child.pid))
    print("Validating inputs", flush=True)
    time.sleep(300)
out = Path(args[args.index("--out-directory") + 1])
out.mkdir(parents=True, exist_ok=True)
(out / "ncs5500-golden-x-25.1.2-LOCAL.iso").write_bytes(b"synthetic golden iso")
print("Golden ISO build complete", flush=True)
"""


def process_is_running(pid: int) -> bool:
    """True for a live process; a zombie (exited, not yet reaped) counts as gone."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return state != "Z"


class LocalRunnerIntegrationTests(SyntheticBuildIntegrationTests):
    """The same pipeline with GISO_RUNNER=local: gisobuild as a child process, no Docker at all."""

    def setUp(self):
        super().setUp()
        root = Path(self.temp.name)
        tool = root / "tool"
        (tool / "src").mkdir(parents=True)
        (tool / "src" / "gisobuild.py").write_text(FAKE_LOCAL_GISOBUILD)
        self.record = root / "local-run.json"
        self.child_pid = root / "child.pid"
        self.config = tool / "fake-config.json"
        self.configure(mode="success")
        local = [
            patch.object(module, "GISO_RUNNER", "local"),
            patch.object(module, "GISOBUILD_PYTHON", sys.executable),
            patch.object(module, "TOOL", tool),
            # Anything that still reached for Docker would fail loudly.
            patch.object(module, "DOCKER_BIN", str(root / "no-docker-here")),
            patch.dict(
                os.environ,
                {
                    "CISCO_CLIENT_SECRET": "must-not-leak",
                    "GISOBUILD_COMMIT": "0388af2989bb7022",
                },
            ),
        ]
        for active in local:
            active.start()
        self.patches.extend(local)

    def configure(self, **settings):
        self.config.write_text(
            json.dumps(
                {
                    "record": str(self.record),
                    "child_pid": str(self.child_pid),
                    **settings,
                }
            )
        )

    def test_local_build_runs_gisobuild_directly_with_a_sanitized_environment(self):
        iso = self.write(self.ISO)
        self.write(self.ROUTING)
        job_id = self.start_build(
            {
                "iso": self.ISO,
                "automatic_smu_selection": True,
                "pkglist": [],
                "label": "LOCAL",
            }
        )
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "success", job.get("log"))
        run = json.loads(self.record.read_text())
        engine = run["argv"][2:]
        self.assertEqual(run["argv"][0], sys.executable)
        self.assertEqual(engine[engine.index("--iso") + 1], str(iso))
        self.assertEqual(
            engine[engine.index("--out-directory") + 1], str(module.OUTPUT / job_id)
        )
        self.assertEqual(Path(run["cwd"]), module.WORK / job_id)
        self.assertEqual(run["env"]["TMPDIR"], str(module.WORK / job_id / "tmp"))
        self.assertNotIn("CISCO_CLIENT_SECRET", run["env"])
        self.assertNotIn("FAKE_DOCKER_ARGS", run["env"])
        self.assertFalse(self.args_file.exists())  # no docker run happened
        self.assertEqual(module.jobs[job_id]["builder_image"]["source"], "bundled")
        self.assertIn("0388af2989bb", module.jobs[job_id]["builder_image"]["reference"])
        self.assertTrue(
            (module.ARCHIVE / job_id / "ncs5500-golden-x-25.1.2-LOCAL.iso").exists()
        )
        version = self.client.get("/api/version").get_json()
        self.assertEqual(
            (version["runner"], version["gisobuild_image"]), ("local", None)
        )
        self.assertEqual(version["gisobuild_commit"], "0388af2989bb")

    def test_cancelling_a_local_build_leaves_no_orphan_processes(self):
        iso = self.write(self.ISO)
        self.write(self.ROUTING)
        self.configure(mode="slow")
        job_id = self.start_build(
            {"iso": self.ISO, "automatic_smu_selection": True, "pkglist": []}
        )
        deadline = time.monotonic() + 10
        while (
            not self.child_pid.exists()
            or "Validating inputs" not in module.jobs[job_id]["log"]
        ):
            self.assertLess(time.monotonic(), deadline, module.jobs[job_id]["log"])
            time.sleep(0.05)
        child = int(self.child_pid.read_text())
        leader = module.jobs[job_id]["container_pid"]
        self.assertTrue(process_is_running(child))

        started = time.monotonic()
        self.assertEqual(self.client.delete(f"/api/jobs/{job_id}").status_code, 200)
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "cancelled")
        self.assertLess(time.monotonic() - started, 15)  # SIGTERM was enough
        self.assertFalse(process_is_running(leader))
        self.assertFalse(
            process_is_running(child), "gisobuild's own child process survived"
        )
        self.assertFalse((module.OUTPUT / job_id / "tmpextract").exists())
        self.assertFalse((module.OUTPUT / job_id / "system_image.iso").exists())
        self.assertTrue((module.OUTPUT / job_id / "logs" / "gisobuild.log").exists())
        self.assertTrue(iso.exists())
        self.assertFalse((module.ARCHIVE / job_id).exists())

    # Docker-only behaviour does not apply to the local runner.
    test_cancelling_a_running_build_stops_the_container_and_keeps_inputs = None
    test_registry_outage_builds_with_the_cached_builder_image = None
    test_registry_outage_without_a_cached_image_fails_clearly = None
    test_exr_build_runs_the_plan_archives_the_image_and_cleans_inputs = None
    test_exr_dependency_failure_is_reported_and_inputs_are_kept = None
    test_work_directory_is_gone_before_status_becomes_externally_visible_as_failed = (
        None
    )
    test_lnt_build_passes_lnt_only_options_to_the_engine = None
    test_consecutive_builds_use_only_their_own_inventory = None


if __name__ == "__main__":
    unittest.main()
