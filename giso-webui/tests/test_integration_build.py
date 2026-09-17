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
import json
import os
import stat
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as module

FAKE_DOCKER = r'''#!__PYTHON__
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
'''


class SyntheticBuildIntegrationTests(unittest.TestCase):
    ISO = "ncs5500-x64-25.1.2.iso"
    ROUTING = "ncs5500-routing-1.0.0.2-r2512.CSCtest00001.x86_64.rpm"
    OTHER_RELEASE = "ncs5500-bgp-1.0.0.1-r2612.CSCtest00002.x86_64.rpm"

    def setUp(self):
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
        for registry in (module.uploads, module.jobs, module.job_processes,
                         module.job_persisted_at, module.cisco_download_jobs):
            registry.clear()
        docker = root / "bin" / "docker"
        docker.write_text(FAKE_DOCKER.replace("__PYTHON__", sys.executable))
        docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
        self.args_file = root / "docker-run-args.json"
        self.stops_file = root / "docker-stops.txt"
        self.patches = [
            patch.object(module, "DOCKER_BIN", str(docker)),
            patch.dict(os.environ, {"FAKE_DOCKER_ARGS": str(self.args_file),
                                    "FAKE_DOCKER_STOPS": str(self.stops_file),
                                    "FAKE_OUTPUT_ROOT": str(module.OUTPUT),
                                    "HOSTNAME": "giso-webui"}),
            patch("app.gisobuild_tool_available", return_value=True),
            patch("app.is_iso9660_image", return_value=True),
            patch("app.shutil.disk_usage", return_value=SimpleNamespace(free=100 * 1024**3)),
        ]
        for active in self.patches:
            active.start()
        self.client = module.app.test_client()

    def tearDown(self):
        deadline = time.monotonic() + 10
        while module.job_processes and time.monotonic() < deadline:
            time.sleep(0.05)
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
        started = self.client.post("/api/uploads/init", json={"name": name, "size": len(content)})
        self.assertEqual(started.status_code, 200, started.get_json())
        upload_id = started.get_json()["id"]
        self.assertEqual(self.client.put(f"/api/uploads/{upload_id}?offset=0", data=content).status_code, 200)
        completed = self.client.post(f"/api/uploads/{upload_id}/complete")
        self.assertEqual(completed.status_code, 200, completed.get_json())
        return completed.get_json()

    @staticmethod
    def smu_tar(smu, rpms):
        """A Cisco-style SMU tar: the RPMs plus a README whose RPMS block lists them."""
        listing = "".join(f"\t{name} {hashlib.md5(body, usedforsecurity=False).hexdigest()}\n"
                          for name, body in rpms.items())
        readme = (f"Name:                    {smu}\n\nRPMS: \n{listing}\t\n"
                  "Pre-requisites:          \n").encode()
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
        extracted = self.upload("ncs5500-25.1.2.CSCtest00001.tar", self.smu_tar(
            "ncs5500-25.1.2.CSCtest00001", {self.ROUTING: b"routing rpm"}))
        self.assertEqual(extracted["extracted"], 2)
        self.write(self.OTHER_RELEASE)
        inputs = self.client.get("/api/inputs").get_json()
        self.assertEqual(inputs["recommended"], [self.ROUTING])
        iso = next(module.DATA / item["relative_path"] for item in inputs["files"]
                   if item["type"] == ".iso")
        rpm = next(module.DATA / item["relative_path"] for item in inputs["files"]
                   if item["basename"] == self.ROUTING)
        job_id = self.start_build({"iso": iso.name, "automatic_smu_selection": True,
                                   "pkglist": [], "label": "INTEGRATION"})
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "success", job.get("log"))
        self.assertEqual(job["exit_code"], 0)
        self.assertEqual(module.jobs[job_id]["builder_image"]["source"], "registry")
        self.assertIn("Gisobuild starting", job["log"])
        self.assertIn("Golden ISO build complete", job["log"])

        # The engine received exactly the reviewed plan: the base ISO, a
        # staged repository holding only the compatible RPM, the label and
        # the per-job output directory.
        args = json.loads(self.args_file.read_text())
        engine = args[args.index("/tool/src/gisobuild.py") + 1:]
        self.assertEqual(engine[engine.index("--iso") + 1], str(iso))
        repo = Path(engine[engine.index("--repo") + 1])
        self.assertEqual(repo, module.WORK / job_id / "repo")
        self.assertEqual(engine[engine.index("--label") + 1], "INTEGRATION")
        self.assertEqual(engine[engine.index("--out-directory") + 1], f"/output/{job_id}")
        self.assertIn("-v", args)
        self.assertIn("giso-output:/output:rw", args)
        self.assertNotIn("/var/run/docker.sock", " ".join(args))
        plan = module.jobs[job_id]["build_plan"]
        self.assertEqual([item["basename"] for item in plan["selected_packages"]], [self.ROUTING])
        self.assertIn(self.OTHER_RELEASE, {item["name"] for item in plan["excluded_packages"]})

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
            job_id = self.start_build({"iso": self.ISO, "automatic_smu_selection": True,
                                       "pkglist": []})
            job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["exit_code"], 1)
        self.assertEqual(job["missing_dependencies"], [{
            "requirement": "ncs5500-dpa = 1.0.0.5",
            "required_by": "ncs5500-routing-1.0.0.2-r2512.CSCtest00001.x86_64",
        }])
        self.assertFalse((module.ARCHIVE / job_id).exists())
        self.assertTrue(iso.exists())
        self.assertTrue(rpm.exists())

    def test_lnt_build_passes_lnt_only_options_to_the_engine(self):
        self.write("8000-x86_64-24.2.11.iso")
        self.write("router.cfg", b"hostname lnt\n")
        job_id = self.start_build({
            "iso": "8000-x86_64-24.2.11.iso", "platform": "8000", "pkglist": [],
            "automatic_smu_selection": False, "xrconfig": "router.cfg",
            "remove_packages": ["xr-telnet"], "label": "LNT_SYNTH",
        })
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "success", job.get("log"))
        args = json.loads(self.args_file.read_text())
        engine = args[args.index("/tool/src/gisobuild.py") + 1:]
        self.assertEqual(engine[engine.index("--xrconfig") + 1], str(module.DATA / "router.cfg"))
        self.assertEqual(engine[engine.index("--remove-packages") + 1], "xr-telnet")
        self.assertNotIn("--repo", engine)  # nothing selected, nothing staged
        self.assertEqual(module.jobs[job_id]["build_plan"]["engine"], "lnt")
        self.assertTrue((module.ARCHIVE / job_id / "ncs5500-golden-x-25.1.2-LNT_SYNTH.iso").exists())


    def test_cancelling_a_running_build_stops_the_container_and_keeps_inputs(self):
        iso = self.write(self.ISO)
        rpm = self.write(self.ROUTING)
        with patch.dict(os.environ, {"FAKE_GISOBUILD_MODE": "slow"}):
            job_id = self.start_build({"iso": self.ISO, "automatic_smu_selection": True,
                                       "pkglist": []})
            deadline = time.monotonic() + 10
            while "Validating inputs" not in module.jobs[job_id]["log"]:
                self.assertLess(time.monotonic(), deadline, module.jobs[job_id]["log"])
                time.sleep(0.05)
            self.assertEqual(self.client.get(f"/api/jobs/{job_id}").get_json()["status"], "running")
            response = self.client.delete(f"/api/jobs/{job_id}")
            self.assertEqual(response.status_code, 200, response.get_json())
            job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "cancelled")
        self.assertIn("Build cancelled by user.", job["log"])
        self.assertEqual(self.stops_file.read_text().split(), [f"giso-build-{job_id}"])
        self.assertFalse((module.ARCHIVE / job_id).exists())
        self.assertTrue(iso.exists())
        self.assertTrue(rpm.exists())
        # A second cancel is refused rather than re-stopping anything.
        self.assertEqual(self.client.delete(f"/api/jobs/{job_id}").status_code, 409)

    def test_consecutive_builds_use_only_their_own_inventory(self):
        self.write(self.ISO)
        self.write(self.ROUTING)
        first = self.wait_for_job(self.start_build({
            "iso": self.ISO, "automatic_smu_selection": True, "pkglist": [], "label": "FIRST"}))
        self.assertEqual(first["status"], "success", first.get("log"))

        # The first build consumed its inputs; the second starts from what is
        # in the workspace now, not from anything the first one used.
        self.write(self.ISO, b"second base iso")
        second_rpm = "ncs5500-bgp-1.0.0.1-r2512.CSCtest00002.x86_64.rpm"
        self.write(second_rpm)
        second_id = self.start_build({"iso": self.ISO, "automatic_smu_selection": True,
                                      "pkglist": [], "label": "SECOND"})
        second = self.wait_for_job(second_id)
        self.assertEqual(second["status"], "success", second.get("log"))

        plan = module.jobs[second_id]["build_plan"]
        self.assertEqual([item["basename"] for item in plan["selected_packages"]], [second_rpm])
        self.assertNotEqual(plan["iso"]["sha256"], module.jobs[first["id"]]["build_plan"]["iso"]["sha256"])
        self.assertEqual(sorted(path.name for path in (module.ARCHIVE / first["id"]).glob("*.iso")),
                         ["ncs5500-golden-x-25.1.2-FIRST.iso"])
        self.assertEqual(sorted(path.name for path in (module.ARCHIVE / second_id).glob("*.iso")),
                         ["ncs5500-golden-x-25.1.2-SECOND.iso"])


    def test_registry_outage_builds_with_the_cached_builder_image(self):
        self.write(self.ISO)
        self.write(self.ROUTING)
        with patch.dict(os.environ, {"FAKE_PULL": "fail"}), \
                patch.object(module, "IMAGE", "ciscogisobuild/cisco-xr-gisobuild@sha256:" + "be" * 32):
            job = self.wait_for_job(self.start_build({"iso": self.ISO, "automatic_smu_selection": True,
                                                      "pkglist": []}))
        self.assertEqual(job["status"], "success", job.get("log"))
        self.assertIn("registry unreachable", job["log"])
        self.assertIn("digest-pinned, so it is identical", job["log"])
        self.assertEqual(module.jobs[job["id"]]["builder_image"]["source"], "cache")
        self.assertEqual(module.jobs[job["id"]]["builder_image"]["id"], "sha256:" + "c0" * 32)

    def test_registry_outage_without_a_cached_image_fails_clearly(self):
        iso = self.write(self.ISO)
        rpm = self.write(self.ROUTING)
        with patch.dict(os.environ, {"FAKE_PULL": "fail", "FAKE_IMAGE_CACHED": "0"}):
            job = self.wait_for_job(self.start_build({"iso": self.ISO, "automatic_smu_selection": True,
                                                      "pkglist": []}))
        self.assertEqual(job["status"], "failed")
        self.assertIn("could not be pulled (exited with status 1) and is not cached", job["log"])
        self.assertFalse(self.args_file.exists())  # the engine never ran
        self.assertTrue(iso.exists())
        self.assertTrue(rpm.exists())


if __name__ == "__main__":
    unittest.main()
