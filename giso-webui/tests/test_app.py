import hashlib
import io
import json
import os
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as module


class GisoWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "uploads"
        self.output = Path(self.temp.name) / "output"
        self.data.mkdir()
        self.output.mkdir()
        module.DATA = self.data.resolve()
        module.OUTPUT = self.output.resolve()
        module.WORK = (Path(self.temp.name) / "work").resolve()
        module.WORK.mkdir()
        module.ARCHIVE = (Path(self.temp.name) / "archive").resolve()
        module.ARCHIVE.mkdir()
        module.uploads.clear()
        module.jobs.clear()
        module.archive_policy_checked = 0.0
        self.docker_running = patch("app.docker_build_running", return_value=False)
        self.docker_running.start()
        self.disk_usage = patch("app.shutil.disk_usage", return_value=SimpleNamespace(free=100 * 1024**3))
        self.disk_usage.start()
        self.client = module.app.test_client()

    def tearDown(self):
        self.disk_usage.stop()
        self.docker_running.stop()
        self.temp.cleanup()

    def upload(self, name, content):
        response = self.client.post("/api/uploads/init", json={"name": name, "size": len(content)})
        self.assertEqual(response.status_code, 200)
        upload_id = response.get_json()["id"]
        response = self.client.put(f"/api/uploads/{upload_id}?offset=0", data=content)
        self.assertEqual(response.status_code, 200)
        return self.client.post(f"/api/uploads/{upload_id}/complete")

    def test_chunked_upload_and_safe_tar_extraction(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"rpm"
            info = tarfile.TarInfo("smu/package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        response = self.upload("cisco-smu.tar", stream.getvalue())
        self.assertEqual(response.status_code, 200)
        self.assertTrue((self.data / "cisco-smu/smu/package.rpm").is_file())

    def test_tar_path_traversal_is_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"bad"
            info = tarfile.TarInfo("../outside.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        response = self.upload("unsafe.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Tar archive rejected", response.get_json()["error"])
        self.assertFalse((Path(self.temp.name) / "outside.rpm").exists())
        self.assertFalse((self.data / "unsafe.tar").exists())

    def test_reupload_does_not_overwrite_existing_extracted_directory(self):
        existing = self.data / "cisco-smu"
        existing.mkdir()
        (existing / "keep.rpm").write_bytes(b"keep")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"new"
            info = tarfile.TarInfo("new.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        response = self.upload("cisco-smu.tar", stream.getvalue())
        self.assertEqual(response.status_code, 200)
        self.assertEqual((existing / "keep.rpm").read_bytes(), b"keep")
        self.assertEqual(len(list(self.data.glob("cisco-smu-*"))), 2)

    def test_upload_offset_must_be_sequential(self):
        upload_id = self.client.post("/api/uploads/init", json={"name": "x.rpm", "size": 3}).get_json()["id"]
        response = self.client.put(f"/api/uploads/{upload_id}?offset=2", data=b"abc")
        self.assertEqual(response.status_code, 409)

    def test_empty_upload_chunk_is_rejected(self):
        upload_id = self.client.post("/api/uploads/init", json={"name": "x.rpm", "size": 3}).get_json()["id"]
        response = self.client.put(f"/api/uploads/{upload_id}?offset=0", data=b"")
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.get_json()["error"].lower())

    def test_invalid_upload_size_returns_json_error(self):
        response = self.client.post("/api/uploads/init", json={"name": "x.rpm", "size": "many"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, "application/json")

    def test_oversized_request_returns_json_error(self):
        previous = module.app.config["MAX_CONTENT_LENGTH"]
        module.app.config["MAX_CONTENT_LENGTH"] = 4
        try:
            response = self.client.put("/api/uploads/missing?offset=0", data=b"12345")
        finally:
            module.app.config["MAX_CONTENT_LENGTH"] = previous
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.content_type, "application/json")

    def test_cross_site_mutation_is_rejected(self):
        response = self.client.post("/api/cleanup", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 403)

    def test_build_payload_types_are_validated(self):
        response = self.client.post("/api/jobs", json={"iso": ["base.iso"], "pkglist": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("iso must be a string", response.get_json()["error"])

    def test_job_api_hides_internal_command_and_payload(self):
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "log": "safe", "command": ["secret"],
                              "payload": {"key_request": "sensitive-name"},
                              "container_pid": 123, "artifacts": []}
        detail = self.client.get("/api/jobs/job").get_json()
        summary = self.client.get("/api/jobs").get_json()[0]
        self.assertNotIn("command", detail)
        self.assertNotIn("payload", detail)
        self.assertNotIn("container_pid", detail)
        self.assertNotIn("payload", summary)

    def test_only_one_build_can_run_at_a_time(self):
        module.jobs["active"] = {"id": "active", "status": "running", "created": 1}
        response = self.client.post("/api/jobs", json={"iso": "base.iso", "pkglist": []})
        self.assertEqual(response.status_code, 409)
        self.assertIn("already running", response.get_json()["error"])

    def test_log_is_bounded(self):
        module.jobs["job"] = {"log": "", "updated": 0, "progress": 0, "phase": ""}
        with patch.object(module, "MAX_LOG_BYTES", 32):
            module.append_log("job", "a" * 100)
        self.assertIn("truncated", module.jobs["job"]["log"])
        self.assertLess(len(module.jobs["job"]["log"]), 100)

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            module.safe_data_path("../secret.iso")

    def test_uppercase_extensions_are_discovered(self):
        (self.data / "BASE.ISO").write_bytes(b"iso")
        files = module.discover()["files"]
        self.assertEqual(files[0]["type"], ".iso")

    @patch("app.subprocess.run")
    def test_build_mounts_exclude_docker_socket(self, run):
        iso = self.data / "base.iso"
        iso.write_bytes(b"iso")
        run.return_value.stdout = json.dumps([{"Mounts": [
            {"Type": "bind", "Source": "/host/uploads", "Destination": "/uploads"},
            {"Type": "bind", "Source": "/host/output", "Destination": "/output"},
            {"Type": "bind", "Source": "/host/tool", "Destination": "/tool"},
            {"Type": "volume", "Name": "work", "Destination": "/work"},
            {"Type": "bind", "Source": "/var/run/docker.sock", "Destination": "/var/run/docker.sock"},
        ]}])
        command = module.build_command({"iso": "base.iso", "pkglist": []}, "job")
        self.assertNotIn("/var/run/docker.sock:/var/run/docker.sock", command)
        self.assertIn("/host/uploads:/uploads:ro", command)

    @patch("app.child_mount_args", return_value=[])
    def test_exr_xrv9k_options_are_forwarded(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        command = module.build_command({"iso": "base.iso", "pkglist": [], "optimize": True, "full_iso": True}, "xrv")
        self.assertIn("--optimize", command)
        self.assertIn("--full-iso", command)

    def test_build_progress_follows_real_log_milestones(self):
        module.jobs["job"] = {"log": "", "updated": 0, "progress": 3, "phase": "Preparing"}
        module.append_log("job", "Scanning repository [/work/repo]...\n")
        self.assertEqual(module.jobs["job"]["progress"], 28)
        self.assertEqual(module.jobs["job"]["phase"], "Scanning update packages")
        module.append_log("job", "Building Golden ISO...\n")
        self.assertEqual(module.jobs["job"]["progress"], 72)

    @patch("app.child_mount_args", return_value=[])
    def test_identical_duplicate_rpms_are_accepted(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        (self.data / "one").mkdir()
        (self.data / "two").mkdir()
        (self.data / "one/package.rpm").write_bytes(b"same rpm")
        (self.data / "two/package.rpm").write_bytes(b"same rpm")
        command = module.build_command({"iso": "base.iso", "pkglist": ["package.rpm"]}, "duplicate")
        self.assertIn("package.rpm", command)

    @patch("app.child_mount_args", return_value=[])
    def test_different_duplicate_rpms_are_rejected(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        (self.data / "one").mkdir()
        (self.data / "two").mkdir()
        (self.data / "one/package.rpm").write_bytes(b"first")
        (self.data / "two/package.rpm").write_bytes(b"second")
        with self.assertRaises(ValueError):
            module.build_command({"iso": "base.iso", "pkglist": ["package.rpm"]}, "conflict")

    def test_cleanup_keeps_uploads_and_completed_images(self):
        (self.data / "base.iso").write_bytes(b"keep")
        (self.output / "finished.iso").write_bytes(b"keep")
        (self.data / ".parts").mkdir()
        (self.data / ".parts/upload.part").write_bytes(b"remove")
        (module.WORK / "old-job").mkdir()
        (module.WORK / "old-job/temp").write_bytes(b"remove")
        response = self.client.post("/api/cleanup")
        self.assertEqual(response.status_code, 200)
        self.assertTrue((self.data / "base.iso").exists())
        self.assertTrue((self.output / "finished.iso").exists())
        self.assertFalse((module.WORK / "old-job").exists())

    def test_success_archive_is_verified_before_sources_are_removed(self):
        (self.data / "source.rpm").write_bytes(b"source")
        job_dir = self.output / "job"
        job_dir.mkdir()
        (job_dir / "router-goldenk9.iso").write_bytes(b"golden image")
        (job_dir / "checksums.json").write_bytes(b"remove")
        (module.WORK / "job").mkdir()
        artifacts = module.archive_golden_iso_and_cleanup("job", job_dir)
        self.assertEqual(len(artifacts), 1)
        self.assertTrue((module.ARCHIVE / "job/router-goldenk9.iso").exists())
        self.assertFalse((self.data / "source.rpm").exists())
        self.assertFalse(job_dir.exists())

    def test_usb_boot_image_is_archived_with_golden_iso(self):
        job_dir = self.output / "usb-job"
        job_dir.mkdir()
        (job_dir / "router-goldenk9.iso").write_bytes(b"golden image")
        (job_dir / "router-usb_boot.zip").write_bytes(b"usb image")
        artifacts = module.archive_giso_artifacts_and_cleanup("usb-job", job_dir)
        self.assertEqual({item["path"] for item in artifacts},
                         {"router-goldenk9.iso", "router-usb_boot.zip"})
        self.assertTrue((module.ARCHIVE / "usb-job/router-usb_boot.zip").exists())

    def test_symlink_build_artifact_is_rejected(self):
        job_dir = self.output / "unsafe-job"
        job_dir.mkdir()
        outside = self.output / "outside.iso"
        outside.write_bytes(b"not a build artifact")
        (job_dir / "router-goldenk9.iso").symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "Unsafe build artifact"):
            module.archive_giso_artifacts_and_cleanup("unsafe-job", job_dir)
        self.assertTrue(outside.exists())
        self.assertTrue(job_dir.exists())

    def test_archive_lists_and_checksums_usb_boot_image(self):
        archive_dir = module.ARCHIVE / "usb-job"
        archive_dir.mkdir()
        content = b"usb image"
        (archive_dir / "router-usb_boot.zip").write_bytes(content)
        items = self.client.get("/api/archive").get_json()
        self.assertEqual(items[0]["name"], "router-usb_boot.zip")
        response = self.client.get("/api/archive/usb-job/router-usb_boot.zip/checksums")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["sha256"], hashlib.sha256(content).hexdigest())

    def test_archive_retention_removes_complete_expired_job(self):
        old_job = module.ARCHIVE / "old-job"
        old_job.mkdir()
        (old_job / "golden.iso").write_bytes(b"iso")
        (old_job / "usb.zip").write_bytes(b"usb")
        old_time = time.time() - 31 * 86400
        os.utime(old_job, (old_time, old_time))
        current_job = module.ARCHIVE / "current-job"
        current_job.mkdir()
        (current_job / "golden.iso").write_bytes(b"current")
        with patch.object(module, "ARCHIVE_RETENTION_DAYS", 30), \
                patch.object(module, "MAX_ARCHIVE_BYTES", 1024):
            removed = module.enforce_archive_policy()
        self.assertIn("old-job", removed)
        self.assertFalse(old_job.exists())
        self.assertTrue(current_job.exists())

    def test_archive_quota_removes_oldest_complete_job(self):
        old_job = module.ARCHIVE / "old-job"
        old_job.mkdir()
        (old_job / "golden.iso").write_bytes(b"123456")
        old_time = time.time() - 60
        os.utime(old_job, (old_time, old_time))
        new_job = module.ARCHIVE / "new-job"
        new_job.mkdir()
        (new_job / "golden.iso").write_bytes(b"abcdef")
        with patch.object(module, "ARCHIVE_RETENTION_DAYS", 30), \
                patch.object(module, "MAX_ARCHIVE_BYTES", 10):
            removed = module.enforce_archive_policy()
        self.assertEqual(removed, ["old-job"])
        self.assertFalse(old_job.exists())
        self.assertTrue(new_job.exists())

    def test_oversized_new_archive_is_rejected_without_cleanup(self):
        job_dir = self.output / "large-job"
        job_dir.mkdir()
        (job_dir / "golden.iso").write_bytes(b"large")
        with patch.object(module, "MAX_ARCHIVE_BYTES", 4), \
                self.assertRaisesRegex(RuntimeError, "exceed"):
            module.archive_giso_artifacts_and_cleanup("large-job", job_dir)
        self.assertTrue(job_dir.exists())

    def test_lnt_output_name_without_golden_is_archived(self):
        job_dir = self.output / "lnt-job"
        job_dir.mkdir()
        (job_dir / "8000-x64-custom.iso").write_bytes(b"lnt giso")
        artifacts = module.archive_golden_iso_and_cleanup("lnt-job", job_dir)
        self.assertEqual(artifacts[0]["path"], "8000-x64-custom.iso")
        self.assertTrue((module.ARCHIVE / "lnt-job/8000-x64-custom.iso").exists())

    def test_archive_iso_can_be_deleted_without_touching_other_files(self):
        archive_dir = module.ARCHIVE / "job"
        archive_dir.mkdir()
        (archive_dir / "golden.iso").write_bytes(b"delete")
        other = module.ARCHIVE / "keep.txt"
        other.write_bytes(b"keep")
        response = self.client.delete("/api/archive/job/golden.iso")
        self.assertEqual(response.status_code, 200)
        self.assertFalse((archive_dir / "golden.iso").exists())
        self.assertTrue(other.exists())

    def test_archive_delete_rejects_path_traversal(self):
        outside = Path(self.temp.name) / "outside.iso"
        outside.write_bytes(b"keep")
        response = self.client.delete("/api/archive/job/../../outside.iso")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(outside.exists())

    def test_archive_checksums_returns_md5_and_sha256(self):
        archive_dir = module.ARCHIVE / "job"
        archive_dir.mkdir()
        content = b"golden iso content"
        (archive_dir / "golden.iso").write_bytes(content)
        response = self.client.get("/api/archive/job/golden.iso/checksums")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["md5"], hashlib.md5(content).hexdigest())
        self.assertEqual(result["sha256"], hashlib.sha256(content).hexdigest())


if __name__ == "__main__":
    unittest.main()
