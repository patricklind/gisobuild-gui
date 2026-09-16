import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app as module

ISOINFO_AVAILABLE = shutil.which("genisoimage") is not None and Path(module.ISOINFO_BIN).exists()


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
        module.STATE = (Path(self.temp.name) / "state").resolve()
        module.JOB_DB = module.STATE / "jobs.sqlite3"
        module.store_initialized = False
        module.uploads.clear()
        module.cisco_searches.clear()
        module.cisco_download_jobs.clear()
        module.cisco_api_client = None
        module.jobs.clear()
        module.job_processes.clear()
        module.job_persisted_at.clear()
        module.archive_policy_checked = 0.0
        self.docker_running = patch("app.docker_build_running", return_value=False)
        self.docker_running.start()
        self.disk_usage = patch("app.shutil.disk_usage", return_value=SimpleNamespace(free=100 * 1024**3))
        self.disk_usage.start()
        self.client = module.app.test_client()

    def tearDown(self):
        self.disk_usage.stop()
        self.docker_running.stop()
        module.store_initialized = False
        self.temp.cleanup()

    def upload(self, name, content):
        response = self.client.post("/api/uploads/init", json={"name": name, "size": len(content)})
        self.assertEqual(response.status_code, 200)
        upload_id = response.get_json()["id"]
        response = self.client.put(f"/api/uploads/{upload_id}?offset=0", data=content)
        self.assertEqual(response.status_code, 200)
        return self.client.post(f"/api/uploads/{upload_id}/complete")

    def test_version_reports_none_commit_when_tool_is_not_a_git_checkout(self):
        with patch.object(module, "TOOL", Path(self.temp.name)):  # not a git repo
            response = self.client.get("/api/version")
        body = response.get_json()
        self.assertEqual(body["app_version"], module.APP_VERSION)
        self.assertEqual(body["gisobuild_image"], module.IMAGE)
        self.assertIsNone(body["gisobuild_commit"])

    def test_version_reports_the_real_commit_of_a_git_checkout(self):
        # Point TOOL at this very repository (mounted read-only into the test
        # container) to prove gisobuild_commit() actually reads a real git
        # commit rather than always degrading to None.
        repo_root = Path(module.__file__).resolve().parents[1]
        if not (repo_root / ".git").exists():
            self.skipTest("test container was not given a git checkout")
        with patch.object(module, "TOOL", repo_root):
            response = self.client.get("/api/version")
        commit = response.get_json()["gisobuild_commit"]
        self.assertIsNotNone(commit)
        self.assertRegex(commit, r"^[0-9a-f]{7,40}$")

    @patch.dict(os.environ, {"CISCO_CLIENT_ID": "id", "CISCO_CLIENT_SECRET": "secret"})
    def test_cisco_config_only_exposes_availability(self):
        response = self.client.get("/api/cisco/config")
        self.assertEqual(response.get_json(), {"enabled": True})
        self.assertNotIn("secret", response.get_data(as_text=True))

    @patch.dict(os.environ, {"CISCO_CLIENT_ID_FILE": "/missing/client-id",
                             "CISCO_CLIENT_SECRET_FILE": "/missing/client-secret"})
    def test_cisco_config_is_disabled_when_secret_files_are_absent(self):
        response = self.client.get("/api/cisco/config")
        self.assertEqual(response.get_json(), {"enabled": False})

    @patch("app.cisco_client")
    def test_cisco_search_returns_safe_normalized_metadata(self, client):
        client.return_value.search.return_value = {
            "metadataTransId": "transaction",
            "metadata": [{"products": [{"mdfId": 42, "releases": [{
                "version": "26.1.2", "images": [{
                "imageGuid": "A" * 40, "name": "ncs5500-mini-x-26.1.2.iso",
                "size": "100", "md5": "b" * 32, "sha512": "c" * 128,
            }]}],
            }]}],
            "access_token": "must-not-leak",
        }
        response = self.client.post("/api/cisco/search", json={
            "pid": "NCS-5501-SE", "current_release": "25.1.2", "target_release": "26.1.2",
        })
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["images"][0]["mdf_id"], "42")
        self.assertEqual(body["images"][0]["release"], "26.1.2")
        self.assertEqual(body["images"][0]["size"], 100)
        self.assertNotIn("must-not-leak", response.get_data(as_text=True))

    @patch("app.threading.Thread")
    @patch("app.cisco_client")
    def test_cisco_download_link_stays_server_side(self, client, thread):
        guid = "A" * 40
        module.cisco_searches["search"] = {
            "created": time.time(), "pid": "NCS-5501-SE", "transaction_id": "transaction",
            "images": {guid: {"guid": guid, "name": "image.iso", "size": 100,
                              "release": "26.1.2", "mdf_id": "42", "md5": "", "sha512": ""}},
        }
        client.return_value.request_download.return_value = {
            "downloads": [{"imageGuid": guid, "url": "https://download.cisco.com/private?token=secret"}]
        }
        response = self.client.post("/api/cisco/downloads", json={
            "search_id": "search", "image_guids": [guid],
        })
        self.assertEqual(response.status_code, 202)
        self.assertNotIn("download.cisco.com", response.get_data(as_text=True))
        self.assertEqual(response.get_json()["status"], "downloading")
        thread.return_value.start.assert_called_once()

    @patch("app.cisco_client")
    def test_cisco_download_reports_nested_eula_and_k9_requirements(self, client):
        guid = "A" * 40
        module.cisco_searches["search"] = {
            "created": time.time(), "pid": "NCS-5501-SE", "transaction_id": "transaction",
            "images": {guid: {"guid": guid, "name": "image.iso", "size": 100,
                              "release": "26.1.2", "mdf_id": "42", "md5": "", "sha512": ""}},
        }
        client.return_value.request_download.return_value = {
            "response": {"acceptanceForm": {"eulaContent": "terms", "k9Content": "notice"}}
        }
        response = self.client.post("/api/cisco/downloads", json={
            "search_id": "search", "image_guids": [guid],
        })
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["agreement"], {"eula": True, "k9": True})
        self.assertNotIn("terms", response.get_data(as_text=True))

    @patch("app.shutil.disk_usage")
    def test_cisco_download_rejects_insufficient_disk_space(self, disk_usage):
        disk_usage.return_value = shutil._ntuple_diskusage(1000, 999, 1)
        guid = "A" * 40
        module.cisco_searches["search"] = {
            "created": time.time(), "pid": "NCS-5501-SE", "transaction_id": "transaction",
            "images": {guid: {"guid": guid, "name": "image.iso", "size": 100,
                              "release": "26.1.2", "mdf_id": "42", "md5": "", "sha512": ""}},
        }
        response = self.client.post("/api/cisco/downloads", json={
            "search_id": "search", "image_guids": [guid],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("free disk space", response.get_json()["error"])

    def test_cisco_download_is_blocked_during_upload_or_build(self):
        guid = "A" * 40
        module.cisco_searches["search"] = {
            "created": time.time(), "pid": "NCS-5501-SE", "transaction_id": "transaction",
            "images": {guid: {"guid": guid, "name": "image.iso", "size": 100,
                              "release": "26.1.2", "mdf_id": "42", "md5": "", "sha512": ""}},
        }
        module.uploads["active"] = {"updated": time.time(), "temp": ""}
        response = self.client.post("/api/cisco/downloads", json={
            "search_id": "search", "image_guids": [guid],
        })
        self.assertEqual(response.status_code, 409)
        self.assertIn("upload", response.get_json()["error"])
        module.uploads.clear()
        module.jobs["active"] = {"status": "running"}
        response = self.client.post("/api/cisco/downloads", json={
            "search_id": "search", "image_guids": [guid],
        })
        self.assertEqual(response.status_code, 409)
        self.assertIn("build", response.get_json()["error"])

    def test_cisco_download_rejects_duplicate_file_selection(self):
        guid = "A" * 40
        module.cisco_searches["search"] = {
            "created": time.time(), "pid": "NCS-5501-SE", "transaction_id": "transaction",
            "images": {guid: {"guid": guid, "name": "image.iso", "size": 100}},
        }
        response = self.client.post("/api/cisco/downloads", json={
            "search_id": "search", "image_guids": [guid, guid],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("unique", response.get_json()["error"])

    @patch("app.cisco_client")
    def test_failed_multi_file_cisco_download_removes_partial_results(self, client):
        first = self.data / "first.iso"

        def download(_url, target, **_kwargs):
            if target.name == "first.iso":
                target.write_bytes(b"verified")
                return SimpleNamespace(path=target, size=8, sha256="sha256")
            raise module.CiscoDownloadError("second file failed")

        client.return_value.download.side_effect = download
        selected = [
            {"guid": "A", "name": "first.iso", "size": 8, "md5": "", "sha512": ""},
            {"guid": "B", "name": "second.iso", "size": 8, "md5": "", "sha512": ""},
        ]
        downloads = [
            {"imageGuid": "A", "url": "https://download.cisco.com/first.iso"},
            {"imageGuid": "B", "url": "https://download.cisco.com/second.iso"},
        ]
        module.cisco_download_jobs["job"] = {
            "id": "job", "status": "downloading", "created": time.time(),
            "progress": 0, "files": [], "error": "",
        }
        module.run_cisco_download("job", {}, selected, downloads)
        self.assertEqual(module.cisco_download_jobs["job"]["status"], "failed")
        self.assertEqual(module.cisco_download_jobs["job"]["files"], [])
        self.assertFalse(first.exists())

    @patch("app.threading.Thread")
    @patch("app.cisco_client")
    def test_cisco_k9_only_flow_does_not_require_eula(self, client, thread):
        guid = "A" * 40
        selected = [{"guid": guid, "name": "image.iso", "size": 100,
                     "release": "26.1.2", "mdf_id": "42", "md5": "", "sha512": ""}]
        module.cisco_download_jobs["job"] = {
            "id": "job", "status": "eula-required", "progress": 0, "files": [],
            "error": "", "created": time.time(), "pending": {
                "search": {"pid": "NCS-5501-SE", "transaction_id": "transaction"},
                "selected": selected, "downloads": [], "eula_required": False,
                "k9_required": True,
            },
        }
        client.return_value.request_download.return_value = {
            "downloads": [{"imageGuid": guid, "url": "https://download.cisco.com/file.iso"}]
        }
        response = self.client.post("/api/cisco/downloads/job/accept", json={
            "commercial_or_civil": True, "not_government_or_military": True,
        })
        self.assertEqual(response.status_code, 202)
        client.return_value.accept_eula.assert_not_called()
        client.return_value.accept_k9.assert_called_once()
        thread.return_value.start.assert_called_once()

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

    def test_upload_progress_is_available_in_activity_log(self):
        upload_id = self.client.post(
            "/api/uploads/init", json={"name": "private.iso", "size": 10}
        ).get_json()["id"]
        self.client.put(f"/api/uploads/{upload_id}?offset=0", data=b"12345")
        activity = self.client.get("/api/activity").get_json()["log"]
        self.assertIn("Upload started: 10 bytes expected", activity)
        self.assertIn("Upload progress: 50%", activity)
        self.assertNotIn("private.iso", activity)

    def test_build_output_is_redacted_and_written_to_service_log(self):
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "progress": 0, "phase": "Starting",
                              "log": "", "artifacts": []}
        with self.assertLogs(module.app.logger.name, level="INFO") as captured:
            module.append_log(
                "job", "Scanning /uploads/private/base.iso, update.rpm and "
                "'/output/private matrix.json'\n"
            )
        self.assertIn("[artifact]", module.jobs["job"]["log"])
        self.assertNotIn("base.iso", module.jobs["job"]["log"])
        self.assertNotIn("private matrix.json", module.jobs["job"]["log"])
        service_log = "\n".join(captured.output)
        self.assertIn("event=build_output", service_log)
        self.assertNotIn("update.rpm", service_log)

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

    def test_tar_symlink_member_is_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            info = tarfile.TarInfo("escape-link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            archive.addfile(info)
        response = self.upload("unsafe-symlink.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Links are not accepted", response.get_json()["error"])
        self.assertFalse((self.data / "unsafe-symlink.tar").exists())

    def test_tar_hardlink_member_is_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"rpm"
            target_info = tarfile.TarInfo("package.rpm")
            target_info.size = len(payload)
            archive.addfile(target_info, io.BytesIO(payload))
            link_info = tarfile.TarInfo("hardlink-to-package")
            link_info.type = tarfile.LNKTYPE
            link_info.linkname = "package.rpm"
            archive.addfile(link_info)
        response = self.upload("unsafe-hardlink.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Links are not accepted", response.get_json()["error"])
        self.assertFalse((self.data / "unsafe-hardlink.tar").exists())

    # extract_cisco_archive() duplicates upload_complete()'s tar safety checks
    # for the Cisco-download path, but nothing exercised it directly - every
    # test above only reaches upload_complete()'s copy of this logic.
    def test_cisco_archive_extraction_rejects_path_traversal(self):
        archive_path = self.data / "cisco-bundle.tar"
        with tarfile.open(archive_path, "w") as archive:
            info = tarfile.TarInfo("../escape.rpm")
            info.size = 3
            archive.addfile(info, io.BytesIO(b"rpm"))
        with self.assertRaisesRegex(module.CiscoDownloadError, "unsafe path"):
            module.extract_cisco_archive(archive_path)
        self.assertFalse((self.data / "cisco-bundle").exists())

    def test_cisco_archive_extraction_rejects_symlink_members(self):
        archive_path = self.data / "cisco-symlink.tar"
        with tarfile.open(archive_path, "w") as archive:
            info = tarfile.TarInfo("link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            archive.addfile(info)
        with self.assertRaisesRegex(module.CiscoDownloadError, "unsafe path"):
            module.extract_cisco_archive(archive_path)
        self.assertFalse((self.data / "cisco-symlink").exists())

    def test_cisco_archive_extraction_enforces_member_count_limit(self):
        archive_path = self.data / "cisco-many-members.tar"
        with tarfile.open(archive_path, "w") as archive:
            for index in range(3):
                info = tarfile.TarInfo(f"package{index}.rpm")
                info.size = 0
                archive.addfile(info, io.BytesIO(b""))
        with patch.object(module, "MAX_TAR_MEMBERS", 2), \
                self.assertRaisesRegex(module.CiscoDownloadError, "too many files"):
            module.extract_cisco_archive(archive_path)
        self.assertFalse((self.data / "cisco-many-members").exists())

    def test_cisco_archive_extraction_succeeds_for_a_safe_archive(self):
        archive_path = self.data / "cisco-safe.tar"
        with tarfile.open(archive_path, "w") as archive:
            payload = b"rpm contents"
            info = tarfile.TarInfo("package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        extracted = module.extract_cisco_archive(archive_path)
        self.assertEqual(extracted, 1)
        self.assertEqual((self.data / "cisco-safe/package.rpm").read_bytes(), b"rpm contents")

    def test_tar_absolute_path_member_is_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"bad"
            info = tarfile.TarInfo("/etc/cron.d/evil")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        response = self.upload("unsafe-abs.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("Tar archive rejected", response.get_json()["error"])
        self.assertFalse(Path("/etc/cron.d/evil").exists())
        self.assertFalse((self.data / "unsafe-abs.tar").exists())

    def test_tar_expansion_size_limit_is_enforced(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"x" * 100
            info = tarfile.TarInfo("package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        with patch.object(module, "MAX_EXTRACTED_BYTES", 10):
            response = self.upload("too-big.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", response.get_json()["error"])
        self.assertFalse((self.data / "too-big.tar").exists())

    def test_tar_member_count_limit_is_enforced(self):
        # MAX_TAR_MEMBERS has protective code in upload_complete() but,
        # unlike the size/traversal/symlink checks nearby, nothing exercised
        # it - a tar bomb with many tiny/empty members would pass the byte
        # size limit while still being expensive to iterate/extract.
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for index in range(3):
                info = tarfile.TarInfo(f"package{index}.rpm")
                info.size = 0
                archive.addfile(info, io.BytesIO(b""))
        with patch.object(module, "MAX_TAR_MEMBERS", 2):
            response = self.upload("too-many-members.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("too many files", response.get_json()["error"])
        self.assertFalse((self.data / "too-many-members.tar").exists())

    def test_tar_extraction_requires_reserved_free_space(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"rpm"
            info = tarfile.TarInfo("package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        free_space = [SimpleNamespace(free=100 * 1024**3),
                      SimpleNamespace(free=module.MIN_FREE_BYTES)]
        with patch("app.shutil.disk_usage", side_effect=free_space):
            response = self.upload("no-space.tar", stream.getvalue())
        self.assertEqual(response.status_code, 400)
        self.assertIn("free disk space", response.get_json()["error"])
        self.assertFalse((self.data / "no-space.tar").exists())

    def test_build_waits_for_tar_extraction_to_finish(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"rpm"
            info = tarfile.TarInfo("package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        upload_id = self.client.post(
            "/api/uploads/init", json={"name": "package.tar", "size": len(stream.getvalue())}
        ).get_json()["id"]
        self.client.put(f"/api/uploads/{upload_id}?offset=0", data=stream.getvalue())
        build_responses = []

        def attempt_build(*_args, **_kwargs):
            with module.app.test_client() as client:
                build_responses.append(client.post("/api/jobs", json={"iso": "base.iso", "pkglist": []}))

        with patch("app.tarfile.TarFile.extractall", side_effect=attempt_build):
            response = self.client.post(f"/api/uploads/{upload_id}/complete")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(build_responses[0].status_code, 409)
        self.assertIn("uploads", build_responses[0].get_json()["error"])
        self.assertNotIn(upload_id, module.uploads)

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

    def test_deleting_archive_removes_its_extraction_directory(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"rpm"
            info = tarfile.TarInfo("package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        response = self.upload("vendor-bundle.tar", stream.getvalue())
        self.assertEqual(response.status_code, 200)
        self.assertTrue((self.data / "vendor-bundle").is_dir())
        self.assertTrue((self.data / "vendor-bundle" / "package.rpm").exists())

        response = self.client.delete("/api/uploads/vendor-bundle.tar")

        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.data / "vendor-bundle.tar").exists())
        self.assertFalse((self.data / "vendor-bundle").exists())

    def test_deleting_plain_upload_does_not_touch_unrelated_directory(self):
        (self.data / "vendor-bundle").mkdir()
        (self.data / "vendor-bundle" / "keep.rpm").write_bytes(b"keep")
        unrelated = self.data / "standalone.rpm"
        unrelated.write_bytes(b"standalone")

        response = self.client.delete("/api/uploads/standalone.rpm")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(unrelated.exists())
        self.assertTrue((self.data / "vendor-bundle" / "keep.rpm").exists())

    def test_inventory_reports_extracted_from_source_archive(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            payload = b"rpm"
            info = tarfile.TarInfo("package.rpm")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        self.upload("vendor-bundle.tar", stream.getvalue())

        files = module.inventory_files()

        extracted = next(item for item in files if item["basename"] == "package.rpm")
        self.assertEqual(extracted["extracted_from"], "vendor-bundle.tar")
        archive_entry = next(item for item in files if item["basename"] == "vendor-bundle.tar")
        self.assertIsNone(archive_entry["extracted_from"])

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

    def test_upload_size_rejects_boolean_and_fraction(self):
        for size in (True, 1.5):
            with self.subTest(size=size):
                response = self.client.post("/api/uploads/init",
                                            json={"name": "x.rpm", "size": size})
                self.assertEqual(response.status_code, 400)

    def test_upload_filename_rejects_paths_and_control_characters(self):
        for name in ("../x.rpm", "folder/x.rpm", "bad\nx.rpm"):
            with self.subTest(name=name):
                response = self.client.post("/api/uploads/init",
                                            json={"name": name, "size": 3})
                self.assertEqual(response.status_code, 400)

    def test_upload_session_can_be_cancelled_and_part_is_removed(self):
        response = self.client.post("/api/uploads/init", json={"name": "x.rpm", "size": 3})
        upload_id = response.get_json()["id"]
        part = Path(module.uploads[upload_id]["temp"])
        self.assertTrue(part.exists())
        response = self.client.delete(f"/api/uploads/session/{upload_id}")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(upload_id, module.uploads)
        self.assertFalse(part.exists())

    def test_expired_upload_session_is_removed_before_request(self):
        parts = self.data / ".parts"
        parts.mkdir()
        part = parts / "expired.part"
        part.write_bytes(b"partial")
        module.uploads["expired"] = {"name": "x.rpm", "size": 3, "received": 1,
                                     "temp": str(part), "updated": 0}
        response = self.client.get("/api/inputs")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("expired", module.uploads)
        self.assertFalse(part.exists())

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

    def test_browser_security_headers_are_complete(self):
        response = self.client.get("/")
        policy = response.headers["Content-Security-Policy"]
        self.assertIn("connect-src 'self'", policy)
        self.assertIn("form-action 'self'", policy)
        self.assertIn("worker-src 'none'", policy)
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(response.headers["X-Permitted-Cross-Domain-Policies"], "none")

    @patch("app.build_command", side_effect=RuntimeError("/secret/internal/path"))
    def test_build_setup_error_does_not_expose_internal_details(self, _build):
        (self.data / "base.iso").write_bytes(b"iso")
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")
        response = self.client.post("/api/jobs", json={
            "iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
            "automatic_smu_selection": False, "auto_repo": True,
        })
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("/secret", response.get_json()["error"])

    def test_tar_read_error_does_not_expose_internal_details(self):
        response = self.client.post(
            "/api/uploads/init", json={"name": "bundle.tar", "size": 3}
        )
        upload_id = response.get_json()["id"]
        self.client.put(f"/api/uploads/{upload_id}?offset=0", data=b"bad")
        with patch("app.tarfile.open", side_effect=OSError("/secret/internal/path")):
            response = self.client.post(f"/api/uploads/{upload_id}/complete")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Tar archive could not be read safely")

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

    def test_job_history_survives_store_reload(self):
        module.jobs["saved"] = {"id": "saved", "status": "success", "created": 1,
                                "updated": 2, "finished": 2,
                                "log": "completed /uploads/private.iso",
                                "artifacts": [{"path": "golden.iso", "size": 3}],
                                "command": ["private"], "payload": {"iso": "private.iso"}}
        module.persist_job("saved")
        module.jobs.clear()
        module.store_initialized = False
        module.initialize_job_store()
        self.assertEqual(module.jobs["saved"]["status"], "success")
        self.assertEqual(module.jobs["saved"]["log"], "completed [artifact]")
        self.assertNotIn("command", module.jobs["saved"])
        self.assertNotIn("payload", module.jobs["saved"])

    def test_active_job_is_marked_interrupted_after_restart(self):
        module.jobs["active"] = {"id": "active", "status": "running", "created": 1,
                                 "updated": 2, "log": "building", "artifacts": []}
        module.persist_job("active")
        module.jobs.clear()
        module.store_initialized = False
        module.initialize_job_store()
        self.assertEqual(module.jobs["active"]["status"], "interrupted")
        self.assertIn("restarted", module.jobs["active"]["error"])

    def test_job_history_is_bounded(self):
        with patch.object(module, "MAX_JOB_HISTORY", 2):
            for index in range(3):
                job_id = f"job-{index}"
                module.jobs[job_id] = {"id": job_id, "status": "success", "created": index,
                                       "updated": index, "log": "", "artifacts": []}
                module.persist_job(job_id)
            module.jobs.clear()
            module.store_initialized = False
            module.initialize_job_store()
        self.assertEqual(set(module.jobs), {"job-1", "job-2"})

    def test_only_one_build_can_run_at_a_time(self):
        module.jobs["active"] = {"id": "active", "status": "running", "created": 1}
        response = self.client.post("/api/jobs", json={"iso": "base.iso", "pkglist": []})
        self.assertEqual(response.status_code, 409)
        self.assertIn("already running", response.get_json()["error"])

    def test_cancelling_job_blocks_new_uploads(self):
        module.jobs["active"] = {"id": "active", "status": "cancelling", "created": 1}
        response = self.client.post("/api/uploads/init", json={"name": "x.rpm", "size": 3})
        self.assertEqual(response.status_code, 409)

    def test_cancel_during_pull_terminates_tracked_process(self):
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "log": "", "progress": 3,
                              "phase": "Preparing", "process_phase": "pulling"}
        process = MagicMock()
        process.poll.return_value = None
        module.job_processes["job"] = process
        response = self.client.delete("/api/jobs/job")
        self.assertEqual(response.status_code, 200)
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=20)
        self.assertEqual(module.jobs["job"]["status"], "cancelled")

    @patch("app.subprocess.run")
    def test_cancel_running_build_stops_container_after_client_process(self, run):
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "log": "", "progress": 50,
                              "phase": "Building", "process_phase": "building"}
        process = MagicMock()
        process.poll.return_value = None
        module.job_processes["job"] = process

        response = self.client.delete("/api/jobs/job")

        self.assertEqual(response.status_code, 200)
        process.terminate.assert_called_once_with()
        run.assert_called_once()
        self.assertIn("giso-build-job", run.call_args.args[0])
        self.assertEqual(module.jobs["job"]["status"], "cancelled")

    def test_cleanup_rejects_active_upload(self):
        module.uploads["active"] = {"name": "x.rpm", "size": 3, "received": 0}
        response = self.client.post("/api/cleanup")
        self.assertEqual(response.status_code, 409)
        self.assertIn("upload", response.get_json()["error"])

    def test_cleanup_rejects_running_build(self):
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1, "updated": 1}
        response = self.client.post("/api/cleanup")
        self.assertEqual(response.status_code, 409)
        self.assertIn("build is running", response.get_json()["error"])

    def test_cleanup_rejects_active_cisco_download(self):
        module.cisco_download_jobs["job"] = {
            "id": "job", "status": "downloading", "progress": 10, "created": time.time(),
        }
        response = self.client.post("/api/cleanup")
        self.assertEqual(response.status_code, 409)
        self.assertIn("Cisco download", response.get_json()["error"])

    def test_docker_image_reference_cannot_be_an_option(self):
        with self.assertRaisesRegex(RuntimeError, "Docker image reference"):
            module.validate_image_reference("--privileged")

    def test_negative_archive_retention_days_is_rejected(self):
        # A negative value pushes enforce_archive_policy()'s cutoff into the
        # future, which would delete every archive - including one just
        # created - on the very next policy check. A misconfiguration typo
        # must fail fast at startup, not silently destroy every artifact.
        with self.assertRaisesRegex(RuntimeError, "ARCHIVE_RETENTION_DAYS must not be negative"):
            module.validate_archive_retention_days(-1)

    def test_zero_archive_retention_days_is_accepted(self):
        self.assertEqual(module.validate_archive_retention_days(0), 0)

    def test_non_positive_max_archive_bytes_is_rejected(self):
        for value in (0, -1):
            with self.assertRaisesRegex(RuntimeError, "MAX_ARCHIVE_BYTES must be a positive number"):
                module.validate_max_archive_bytes(value)

    def test_log_is_bounded(self):
        module.jobs["job"] = {"log": "", "updated": 0, "progress": 0, "phase": ""}
        with patch.object(module, "MAX_LOG_BYTES", 32):
            module.append_log("job", "a" * 100)
        self.assertIn("truncated", module.jobs["job"]["log"])
        self.assertLess(len(module.jobs["job"]["log"]), 100)

    def test_quoted_artifact_path_with_spaces_is_fully_redacted(self):
        redacted = module.safe_log_text("$ docker run --iso '/uploads/customer router.iso'")
        self.assertEqual(redacted, "$ docker run --iso [artifact]")
        self.assertNotIn("customer", redacted)

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
        command = module.build_command({"iso": "base.iso", "platform": "asr9k",
                                        "pkglist": []}, "job")
        self.assertNotIn("/var/run/docker.sock:/var/run/docker.sock", command)
        self.assertIn("/host/uploads:/uploads:ro", command)

    @patch("app.child_mount_args", return_value=[])
    def test_exr_xrv9k_options_are_forwarded(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        command = module.build_command({"iso": "base.iso", "platform": "xrv9k", "pkglist": [],
                                        "optimize": True, "full_iso": True,
                                        "skip_usb_image": True}, "xrv")
        self.assertIn("--optimize", command)
        self.assertIn("--full-iso", command)

    def test_platform_matrix_is_exposed(self):
        response = self.client.get("/api/platforms")
        self.assertEqual(response.status_code, 200)
        self.assertIn("asr9k", {item["id"] for item in response.get_json()})
        ncs5500 = next(item for item in response.get_json() if item["id"] == "ncs5500")
        self.assertEqual(ncs5500["engine"], "exr")
        self.assertTrue(ncs5500["capabilities"]["optimize"])
        self.assertFalse(ncs5500["capabilities"]["remove_packages"])

    def test_compatibility_api_checks_smu_and_uploaded_upgrade_matrix(self):
        matrix = self.data / "compatibility_matrix_test.json"
        matrix.write_text(json.dumps({"permitted": {"25.1.2": {"26.1.2": [{
            "platform": "ncs5500", "bridge_smus": ["bridge-placeholder.rpm"],
            "caveats": [],
        }]}}}), encoding="utf-8")
        response = self.client.post("/api/compatibility", json={
            "iso": "ncs5500-mini-x-26.1.2.iso",
            "packages": ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"],
            "matrix": matrix.name, "source_release": "25.1.2",
            "target_release": "26.1.2", "platform": "ncs5500",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["smu"]["compatible"])
        self.assertTrue(response.get_json()["upgrade"]["permitted"])
        self.assertEqual(response.get_json()["upgrade"]["missing_bridge_smus"],
                         ["bridge-placeholder.rpm"])

    def test_smu_recommendation_api_selects_matching_packages_automatically(self):
        (self.data / "ncs5500-mini-x-26.1.2.iso").write_bytes(b"iso")
        matching = "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"
        wrong_release = "ncs5500-bgp-1.0.0.1-r2512.CSCtest00002.x86_64.rpm"
        (self.data / matching).write_bytes(b"rpm")
        (self.data / wrong_release).write_bytes(b"rpm")

        response = self.client.post("/api/smu/recommendation", json={
            "iso": "ncs5500-mini-x-26.1.2.iso",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["selected"], [matching])
        self.assertEqual(response.get_json()["excluded"][0]["name"], wrong_release)

    def test_superseded_rpm_is_excluded_with_a_reason_not_silently_dropped(self):
        # active_rpm_names() already removes superseded RPMs from the
        # automatic candidate list before selection ever runs. Without
        # add_superseded_exclusions() they simply vanished from the response
        # instead of appearing in "excluded" with a reason, leaving the
        # operator unable to tell an SMU was superseded rather than just
        # missing from the upload.
        (self.data / "ncs5500-mini-x-26.1.2.iso").write_bytes(b"iso")
        current = "ncs5500-bgp-2.0.0.1-r2612.CSCnew00001.x86_64.rpm"
        (self.data / current).write_bytes(b"new")
        old_dir = self.data / "ncs5500-bgp-1.0.0.1.CSCold00001"
        old_dir.mkdir()
        old_rpm = old_dir / "ncs5500-bgp-1.0.0.1-r2612.CSCold00001.x86_64.rpm"
        old_rpm.write_bytes(b"old")
        (self.data / "supersedence-notes.txt").write_text(
            "ncs5500-bgp-1.0.0.1.CSCold00001 Full\n"
        )

        response = self.client.get("/api/inputs")

        recommendation = response.get_json()["recommendation"]
        self.assertIn(current, recommendation["selected"])
        excluded_by_name = {item["name"]: item["reason"] for item in recommendation["excluded"]}
        self.assertIn(old_rpm.name, excluded_by_name)
        self.assertIn("Superseded", excluded_by_name[old_rpm.name])

    def test_oversized_text_is_not_loaded_as_supersedence_metadata(self):
        rpm = "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"
        (self.data / rpm).write_bytes(b"rpm")
        metadata = self.data / "oversized.txt"
        with metadata.open("wb") as handle:
            handle.truncate(module.MAX_SUPERSEDENCE_FILE_BYTES + 1)
        with patch("pathlib.Path.read_text", side_effect=AssertionError("must not be read")):
            packages, superseded = module.active_rpm_names()
        self.assertEqual(packages, [rpm])
        self.assertEqual(superseded, set())

    def test_discover_pauses_automatic_selection_when_multiple_isos_exist(self):
        (self.data / "ncs5500-mini-x-26.1.2.iso").write_bytes(b"iso")
        (self.data / "ncs5500-mini-x-26.1.3.iso").write_bytes(b"iso")
        (self.data / "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm").write_bytes(b"rpm")

        response = self.client.get("/api/inputs")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["recommendation"]["ready"])

    def test_discover_tolerates_file_removed_during_scan(self):
        disappearing = self.data / "disappearing.rpm"
        disappearing.write_bytes(b"rpm")
        original_stat = Path.stat

        def concurrent_stat(path, *args, **kwargs):
            if path == disappearing:
                raise FileNotFoundError(path)
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", new=concurrent_stat):
            response = self.client.get("/api/inputs")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("disappearing.rpm", {item["path"] for item in response.get_json()["files"]})
        self.assertEqual(response.get_json()["recommended"], [])

    def test_inventory_exposes_stable_identity_without_absolute_path(self):
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"rpm content")

        first = self.client.get("/api/inputs").get_json()["files"][0]
        second = self.client.get("/api/inputs").get_json()["files"][0]

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["sha256"], hashlib.sha256(b"rpm content").hexdigest())
        self.assertEqual(first["relative_path"], "package.rpm")
        self.assertEqual(first["lifecycle"], "READY")
        self.assertNotIn("absolute_path", first)
        self.assertNotIn(str(self.data), json.dumps(first))

    def test_identical_duplicate_inventory_keeps_provenance(self):
        for directory in ("one", "two"):
            (self.data / directory).mkdir()
            (self.data / directory / "package.rpm").write_bytes(b"same")

        rpms = self.client.get("/api/inputs").get_json()["files"]

        self.assertEqual(len(rpms), 2)
        self.assertEqual(len({item["id"] for item in rpms}), 2)
        self.assertEqual({item["duplicate_kind"] for item in rpms}, {"identical"})
        self.assertEqual(rpms[0]["provenance"], ["one/package.rpm", "two/package.rpm"])

    def test_different_duplicate_inventory_is_a_visible_conflict(self):
        for directory, content in (("one", b"first"), ("two", b"second")):
            (self.data / directory).mkdir()
            (self.data / directory / "package.rpm").write_bytes(content)

        rpms = self.client.get("/api/inputs").get_json()["files"]

        self.assertEqual({item["duplicate_kind"] for item in rpms}, {"conflict"})
        self.assertEqual(len({item["sha256"] for item in rpms}), 2)

    @patch("app.child_mount_args", return_value=[])
    def test_platform_is_inferred_and_invalid_option_rejected(self, _mounts):
        (self.data / "ncs5500-mini-x.iso").write_bytes(b"iso")
        with self.assertRaisesRegex(ValueError, "Full ISO"):
            module.build_command({"iso": "ncs5500-mini-x.iso", "pkglist": [],
                                  "full_iso": True}, "invalid")

    @patch("app.child_mount_args", return_value=[])
    def test_build_recalculates_automatic_smu_selection_server_side(self, _mounts):
        iso = "ncs5500-mini-x-26.1.2.iso"
        matching = "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"
        wrong_release = "ncs5500-bgp-1.0.0.1-r2512.CSCtest00002.x86_64.rpm"
        for name in (iso, matching, wrong_release):
            (self.data / name).write_bytes(b"input")

        command = module.build_command({
            "iso": iso, "pkglist": [wrong_release], "automatic_smu_selection": True,
            "auto_repo": True,
        }, "automatic")

        pkglist_index = command.index("--pkglist")
        self.assertIn(matching, command[pkglist_index + 1:])
        self.assertNotIn(wrong_release, command[pkglist_index + 1:])

    @patch("app.child_mount_args", return_value=[])
    def test_unknown_iso_requires_platform_selection(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        with self.assertRaisesRegex(ValueError, "Select the platform"):
            module.build_command({"iso": "base.iso", "pkglist": []}, "unknown")

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
        command = module.build_command({"iso": "base.iso", "platform": "asr9k",
                                        "pkglist": ["package.rpm"]}, "duplicate")
        self.assertIn("package.rpm", command)

    @patch("app.child_mount_args", return_value=[])
    def test_verbose_dep_check_is_passed_through_for_lnt_platforms(self, _mounts):
        # verbose_dep_check now defaults to checked in the UI (2026-09-16);
        # this confirms the backend actually includes --verbose-dep-check
        # in the real build command when the payload requests it.
        (self.data / "base.iso").write_bytes(b"iso")
        command = module.build_command({"iso": "base.iso", "platform": "ncs57",
                                        "pkglist": [], "verbose_dep_check": True}, "job")
        self.assertIn("--verbose-dep-check", command)

    @patch("app.child_mount_args", return_value=[])
    def test_verbose_dep_check_is_omitted_when_not_requested(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        command = module.build_command({"iso": "base.iso", "platform": "ncs57",
                                        "pkglist": []}, "job")
        self.assertNotIn("--verbose-dep-check", command)

    @patch("app.child_mount_args", return_value=[])
    def test_different_duplicate_rpms_are_rejected(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        (self.data / "one").mkdir()
        (self.data / "two").mkdir()
        (self.data / "one/package.rpm").write_bytes(b"first")
        (self.data / "two/package.rpm").write_bytes(b"second")
        with self.assertRaises(ValueError):
            module.build_command({"iso": "base.iso", "platform": "asr9k",
                                  "pkglist": ["package.rpm"]}, "conflict")

    @patch("app.child_mount_args", return_value=[])
    def test_inventory_id_selects_exact_rpm(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        (self.data / "one").mkdir()
        (self.data / "two").mkdir()
        first = self.data / "one/package.rpm"
        second = self.data / "two/package.rpm"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        selected = next(item for item in module.inventory_files()
                        if item["relative_path"] == "two/package.rpm")

        module.build_command({"iso": "base.iso", "platform": "asr9k",
                              "pkglist": [selected["id"]]}, "identity")

        self.assertEqual((module.WORK / "identity/repo/package.rpm").read_bytes(), b"second")

    def test_build_plan_is_backend_owned_and_checksum_fingerprinted(self):
        (self.data / "base.iso").write_bytes(b"iso")
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"first")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")
        payload = {"iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
                   "automatic_smu_selection": False, "auto_repo": True}

        first = self.client.post("/api/build-plan", json=payload).get_json()
        rpm.write_bytes(b"second")
        second_item = next(entry for entry in module.inventory_files()
                           if entry["type"] == ".rpm")
        payload["pkglist"] = [second_item["id"]]
        second = self.client.post("/api/build-plan", json=payload).get_json()

        self.assertTrue(first["ready"])
        self.assertEqual(first["selected_packages"][0]["id"], item["id"])
        self.assertNotEqual(first["inventory_revision"], second["inventory_revision"])
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_build_plan_returns_blockers_instead_of_enabling_invalid_build(self):
        response = self.client.post("/api/build-plan", json={
            "iso": "missing.iso", "platform": "asr9k", "pkglist": [],
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["ready"])
        self.assertIn("current inventory", response.get_json()["blockers"][0])

    def test_build_plan_confidence_is_unknown_when_no_iso_is_selected(self):
        # Nothing has been detected yet, so every confidence entry must say so
        # rather than defaulting to a value that looks like a real answer.
        response = self.client.post("/api/build-plan", json={
            "iso": "missing.iso", "platform": "", "pkglist": [],
        })

        confidence = response.get_json()["confidence"]
        self.assertEqual(confidence["platform"]["value"], "UNKNOWN")
        self.assertEqual(confidence["release"]["value"], "UNKNOWN")
        self.assertEqual(confidence["iso_architecture"]["value"], "UNKNOWN")
        self.assertEqual(confidence["dependency_closure"]["value"], "UNKNOWN")

    def test_build_plan_confidence_marks_filename_derived_fields_as_inferred(self):
        # Platform, release and CSC grouping all come from filename regexes,
        # not from parsing the artifact itself, so none of them may be
        # reported as VERIFIED - only genuine content inspection earns that.
        (self.data / "asr9k-x64-7.3.2.iso").write_bytes(b"iso")
        rpm = self.data / "asr9k-x64-routing-1.0.0.1-r732.CSCtest00001.x86_64.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")

        response = self.client.post("/api/build-plan", json={
            "iso": "asr9k-x64-7.3.2.iso", "platform": "", "pkglist": [item["id"]],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        confidence = response.get_json()["confidence"]
        self.assertEqual(confidence["platform"], {
            "value": "INFERRED",
            "source": "iso-filename-pattern",
            "detail": confidence["platform"]["detail"],
        })
        self.assertEqual(confidence["release"]["value"], "INFERRED")
        self.assertEqual(confidence["release"]["source"], "iso-filename-pattern")
        self.assertEqual(confidence["package_architecture"]["value"], "INFERRED")
        self.assertEqual(confidence["csc_groups"]["value"], "INFERRED")
        self.assertEqual(confidence["dependency_closure"]["value"], "UNKNOWN")

    def test_build_plan_confidence_marks_manual_platform_as_operator_selected(self):
        (self.data / "base.iso").write_bytes(b"iso")

        response = self.client.post("/api/build-plan", json={
            "iso": "base.iso", "platform": "asr9k", "pkglist": [],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        confidence = response.get_json()["confidence"]
        self.assertEqual(confidence["platform"]["value"], "INFERRED")
        self.assertEqual(confidence["platform"]["source"], "operator-selected")

    def test_build_plan_warns_when_only_ownership_vouchers_are_set(self):
        # Mirrors _validate_ovs_and_oc() in gisobuild's own _coordinate.py:
        # it rejects a final image carrying one of ownership vouchers/
        # certificate without the other. A warning, not a blocker, since the
        # base ISO might already carry the missing one from an earlier build.
        (self.data / "base.iso").write_bytes(b"iso")
        response = self.client.post("/api/build-plan", json={
            "iso": "base.iso", "platform": "8000", "pkglist": [],
            "automatic_smu_selection": False, "auto_repo": True,
            "ownership_vouchers": "vouchers.tar",
        })
        warnings = response.get_json()["warnings"]
        self.assertTrue(any("ownership" in warning.lower() for warning in warnings), warnings)

    def test_build_plan_warns_when_only_ownership_certificate_is_set(self):
        (self.data / "base.iso").write_bytes(b"iso")
        response = self.client.post("/api/build-plan", json={
            "iso": "base.iso", "platform": "8000", "pkglist": [],
            "automatic_smu_selection": False, "auto_repo": True,
            "ownership_certificate": "certificate.pem",
        })
        warnings = response.get_json()["warnings"]
        self.assertTrue(any("ownership" in warning.lower() for warning in warnings), warnings)

    def test_build_plan_does_not_warn_when_both_or_neither_ownership_fields_are_set(self):
        (self.data / "base.iso").write_bytes(b"iso")
        neither = self.client.post("/api/build-plan", json={
            "iso": "base.iso", "platform": "8000", "pkglist": [],
            "automatic_smu_selection": False, "auto_repo": True,
        }).get_json()
        both = self.client.post("/api/build-plan", json={
            "iso": "base.iso", "platform": "8000", "pkglist": [],
            "automatic_smu_selection": False, "auto_repo": True,
            "ownership_vouchers": "vouchers.tar", "ownership_certificate": "certificate.pem",
        }).get_json()
        self.assertFalse(any("ownership" in w.lower() for w in neither["warnings"]), neither["warnings"])
        self.assertFalse(any("ownership" in w.lower() for w in both["warnings"]), both["warnings"])

    def test_build_plan_automatic_selection_explains_superseded_exclusions(self):
        # create_build_plan()'s automatic_smu_selection path pulls candidates
        # straight from active_rpm_names(), which already drops superseded
        # RPMs - without add_superseded_exclusions() they disappeared from
        # excluded_packages entirely instead of being explained.
        (self.data / "ncs5500-mini-x-26.1.2.iso").write_bytes(b"iso")
        current = "ncs5500-bgp-2.0.0.1-r2612.CSCnew00001.x86_64.rpm"
        (self.data / current).write_bytes(b"new")
        old_dir = self.data / "ncs5500-bgp-1.0.0.1.CSCold00001"
        old_dir.mkdir()
        old_rpm = old_dir / "ncs5500-bgp-1.0.0.1-r2612.CSCold00001.x86_64.rpm"
        old_rpm.write_bytes(b"old")
        (self.data / "supersedence-notes.txt").write_text(
            "ncs5500-bgp-1.0.0.1.CSCold00001 Full\n"
        )

        response = self.client.post("/api/build-plan", json={
            "iso": "ncs5500-mini-x-26.1.2.iso", "pkglist": [],
            "automatic_smu_selection": True, "auto_repo": True,
        })

        plan = response.get_json()
        self.assertTrue(plan["ready"], plan)
        excluded_by_name = {item["name"]: item["reason"] for item in plan["excluded_packages"]}
        self.assertIn(old_rpm.name, excluded_by_name)
        self.assertIn("Superseded", excluded_by_name[old_rpm.name])

    @unittest.skipUnless(
        ISOINFO_AVAILABLE,
        "genisoimage and isoinfo are only available inside the giso-webui container image",
    )
    def test_build_plan_confidence_reports_verified_iso_architecture_from_real_iso(self):
        # inspect_iso_architecture() reads the ISO's own contents, so this is
        # the one field this endpoint can honestly call VERIFIED.
        source = Path(self.temp.name) / "iso-src-confidence"
        source.mkdir()
        (source / "iosxr_image_mdata.yml").write_text(
            "x86_64 supported arch list: corei7_64\narm supported arch list:\n"
        )
        iso_path = self.data / "verified.iso"
        subprocess.run(
            ["genisoimage", "-quiet", "-R", "-o", str(iso_path), str(source)],
            check=True, capture_output=True,
        )

        response = self.client.post("/api/build-plan", json={
            "iso": "verified.iso", "platform": "asr9k", "pkglist": [],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        confidence = response.get_json()["confidence"]
        self.assertEqual(confidence["iso_architecture"]["value"], "VERIFIED")
        self.assertEqual(confidence["iso_architecture"]["source"], "iso-contents")

    @unittest.skipUnless(
        ISOINFO_AVAILABLE,
        "genisoimage and isoinfo are only available inside the giso-webui container image",
    )
    def test_build_plan_blocks_rpm_architecture_mismatch_against_real_iso(self):
        # create_build_plan() must apply the same iso_architectures check that
        # discover(), /api/smu-recommendation, /api/compatibility, and
        # build_command() already apply - otherwise /api/build-plan can show
        # "ready" for a build that build_command() would reject afterward,
        # defeating the point of one authoritative preflight.
        source = Path(self.temp.name) / "iso-src"
        source.mkdir()
        (source / "iosxr_image_mdata.yml").write_text(
            "x86_64 supported arch list: corei7_64\narm supported arch list:\n"
        )
        iso_path = self.data / "base.iso"
        subprocess.run(
            ["genisoimage", "-quiet", "-R", "-o", str(iso_path), str(source)],
            check=True, capture_output=True,
        )
        rpm = self.data / "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.aarch64.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")

        response = self.client.post("/api/build-plan", json={
            "iso": "base.iso", "platform": "ncs5500", "pkglist": [item["id"]],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        plan = response.get_json()
        self.assertFalse(plan["ready"])
        self.assertTrue(any("architecture" in blocker.lower() for blocker in plan["blockers"]),
                        plan["blockers"])

    @patch("app.run_job")
    @patch("app.child_mount_args", return_value=[])
    def test_created_job_records_authoritative_build_plan(self, _mounts, _run_job):
        (self.data / "base.iso").write_bytes(b"iso")
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")

        response = self.client.post("/api/jobs", json={
            "iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        self.assertEqual(response.status_code, 202)
        job = module.jobs[response.get_json()["id"]]
        self.assertEqual(job["plan_fingerprint"], job["build_plan"]["fingerprint"])
        self.assertEqual(job["inventory_revision"], job["build_plan"]["inventory_revision"])

    def test_command_preview_strips_docker_wrapper_and_shows_basenames(self):
        real_command = [
            "/usr/bin/docker", "run", "--rm", "-v", "/home/alice/secret-project:/uploads:ro",
            "-v", "giso-webui_giso-output:/output:rw", "ciscogisobuild/cisco-xr-gisobuild:2.3.4",
            "/tool/src/gisobuild.py", "--iso", "/uploads/base.iso",
            "--pkglist", "/uploads/one/package.rpm", "--label", "MYLABEL",
            "--out-directory", "/output/job-1", "--clean",
        ]
        preview = module.command_preview(real_command)
        self.assertNotIn("docker", preview)
        self.assertNotIn("/home/alice", preview)
        self.assertNotIn("giso-webui_giso-output", preview)
        self.assertTrue(preview.startswith("gisobuild.py --iso base.iso"))
        self.assertIn("package.rpm", preview)
        self.assertNotIn("/uploads", preview)

    def test_command_preview_returns_empty_string_for_a_yaml_only_command(self):
        # build_command() still points at gisobuild.py even for --yamlfile
        # builds, so this only exercises the "script not found" fallback
        # directly, since it can't otherwise occur from build_command().
        self.assertEqual(module.command_preview(["docker", "run", "some-image"]), "")

    @patch("app.run_job")
    @patch("app.child_mount_args", return_value=[])
    def test_created_job_exposes_a_safe_command_preview_but_not_the_real_command(self, _mounts, _run_job):
        (self.data / "base.iso").write_bytes(b"iso")
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")

        response = self.client.post("/api/jobs", json={
            "iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["id"]
        api_job = self.client.get(f"/api/jobs/{job_id}").get_json()
        self.assertIn("command_preview", api_job)
        self.assertTrue(api_job["command_preview"].startswith("gisobuild.py --iso base.iso"))
        self.assertNotIn("command", api_job)
        internal_job = module.jobs[job_id]
        self.assertIn("command", internal_job)
        self.assertEqual(internal_job["command_preview"], api_job["command_preview"])

    @patch("app.run_job")
    @patch("app.child_mount_args", return_value=[])
    def test_cleanup_paths_do_not_include_an_unselected_duplicate_basename(self, _mounts, _run_job):
        # create_job() resolves pkglist by opaque inventory ID, so two RPMs
        # with the same basename but different content can coexist and be
        # selected precisely (resolve_rpm_identifiers()). build_command()
        # then overwrites payload["pkglist"] with basenames as a side effect;
        # if build_cleanup_paths() re-derives files to delete by globbing for
        # that basename across all of DATA, it deletes every file sharing the
        # name, including one that was never selected for this build.
        (self.data / "base.iso").write_bytes(b"iso")
        (self.data / "one").mkdir()
        (self.data / "two").mkdir()
        selected_rpm = self.data / "one/package.rpm"
        other_rpm = self.data / "two/package.rpm"
        selected_rpm.write_bytes(b"selected content")
        other_rpm.write_bytes(b"a different upload that happens to share this filename")
        item = next(entry for entry in module.inventory_files()
                    if entry["relative_path"] == "one/package.rpm")

        response = self.client.post("/api/jobs", json={
            "iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
            "automatic_smu_selection": False, "auto_repo": True,
        })

        self.assertEqual(response.status_code, 202)
        cleanup_paths = {Path(p) for p in module.jobs[response.get_json()["id"]]["cleanup_paths"]}
        self.assertIn(selected_rpm.resolve(), cleanup_paths)
        self.assertNotIn(other_rpm.resolve(), cleanup_paths)

    @patch("app.run_job")
    @patch("app.child_mount_args", return_value=[])
    def test_stale_confirmed_plan_is_rejected_when_inventory_changes(self, _mounts, _run_job):
        (self.data / "base.iso").write_bytes(b"iso")
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")
        payload = {"iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
                   "automatic_smu_selection": False, "auto_repo": True}
        reviewed = self.client.post("/api/build-plan", json=payload).get_json()

        (self.data / "other.rpm").write_bytes(b"unrelated new upload")
        payload["confirmed_plan_fingerprint"] = reviewed["fingerprint"]
        response = self.client.post("/api/jobs", json=payload)

        self.assertEqual(response.status_code, 409)
        self.assertIn("Inventory changed", response.get_json()["error"])
        self.assertEqual(module.jobs, {})

    @patch("app.run_job")
    @patch("app.child_mount_args", return_value=[])
    def test_confirmed_plan_matching_current_inventory_is_accepted(self, _mounts, _run_job):
        (self.data / "base.iso").write_bytes(b"iso")
        rpm = self.data / "package.rpm"
        rpm.write_bytes(b"rpm")
        item = next(entry for entry in module.inventory_files() if entry["type"] == ".rpm")
        payload = {"iso": "base.iso", "platform": "asr9k", "pkglist": [item["id"]],
                   "automatic_smu_selection": False, "auto_repo": True}
        reviewed = self.client.post("/api/build-plan", json=payload).get_json()

        payload["confirmed_plan_fingerprint"] = reviewed["fingerprint"]
        response = self.client.post("/api/jobs", json=payload)

        self.assertEqual(response.status_code, 202)

    def test_manual_package_ui_uses_ids_and_renders_duplicate_conflicts(self):
        source = (Path(module.__file__).parent / "static/manual-packages.js").read_text()
        self.assertIn("box.value = file.id", source)
        self.assertIn("same filename but different content", source)
        self.assertIn("identical copies deduplicated", source)
        self.assertNotIn("new Map(rpms.map(file => [basename(file.path), file]))", source)

    @patch("app.child_mount_args", return_value=[])
    def test_package_glob_characters_cannot_select_unintended_files(self, _mounts):
        (self.data / "base.iso").write_bytes(b"iso")
        (self.data / "package-one.rpm").write_bytes(b"rpm")

        with self.assertRaisesRegex(ValueError, "exact filename"):
            module.build_command({"iso": "base.iso", "platform": "asr9k",
                                  "pkglist": ["package-*.rpm"]}, "glob")

    def test_cleanup_removes_workspace_but_keeps_archive(self):
        (self.data / "base.iso").write_bytes(b"remove")
        (self.output / "finished.iso").write_bytes(b"remove")
        (self.data / ".parts").mkdir()
        (self.data / ".parts/upload.part").write_bytes(b"remove")
        (module.WORK / "old-job").mkdir()
        (module.WORK / "old-job/temp").write_bytes(b"remove")
        archive_dir = module.ARCHIVE / "finished-job"
        archive_dir.mkdir()
        archived = archive_dir / "golden.iso"
        archived.write_bytes(b"keep")
        with self.assertLogs(module.app.logger.name, level="INFO") as captured:
            response = self.client.post("/api/cleanup")
        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.data / "base.iso").exists())
        self.assertFalse((self.output / "finished.iso").exists())
        self.assertFalse((module.WORK / "old-job").exists())
        self.assertTrue(archived.exists())
        self.assertEqual(response.get_json()["removed"],
                         {"output": 1, "uploads": 2, "work": 1})
        self.assertTrue(any("event=workspace_cleanup" in line for line in captured.output))

    def test_cleanup_clears_failed_output_links_but_keeps_archive_links(self):
        failed_id = "failed-job"
        module.jobs[failed_id] = {
            "id": failed_id, "status": "failed", "created": 1, "updated": 1,
            "log": "", "artifacts": [
                {"path": "logs/gisobuild.log", "size": 3},
                {"path": "upgrade_matrix/matrix.json", "size": 4,
                 "url": f"/download/{failed_id}/upgrade_matrix/matrix.json"},
                {"path": "golden.iso", "size": 5,
                 "url": f"/archive/{failed_id}/golden.iso"},
            ],
        }
        module.persist_job(failed_id)
        (self.output / failed_id / "logs").mkdir(parents=True)
        (self.output / failed_id / "logs/gisobuild.log").write_bytes(b"log")

        response = self.client.post("/api/cleanup")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["cleared_artifacts"], 2)
        self.assertEqual(module.jobs[failed_id]["artifacts"], [{
            "path": "golden.iso", "size": 5,
            "url": f"/archive/{failed_id}/golden.iso",
        }])
        with module.sqlite3.connect(module.JOB_DB) as database:
            stored = json.loads(database.execute(
                "SELECT data FROM jobs WHERE id = ?", (failed_id,),
            ).fetchone()[0])
        self.assertEqual(len(stored["artifacts"]), 1)
        self.assertTrue(stored["artifacts"][0]["url"].startswith("/archive/"))

    def test_request_log_uses_endpoint_and_safe_correlation_id(self):
        with self.assertLogs(module.app.logger.name, level="INFO") as captured:
            response = self.client.get("/api/inputs", headers={"X-Request-ID": "request-123"})
        self.assertEqual(response.headers["X-Request-ID"], "request-123")
        log = "\n".join(captured.output)
        self.assertIn("endpoint=inputs", log)
        self.assertIn("request_id=request-123", log)

    def test_cross_process_archive_lock_blocks_a_separate_os_process(self):
        # archive_lock is a threading.RLock, which only ever coordinates
        # threads inside this one Python process. The archive-maintenance
        # container calls enforce_archive_policy() from a genuinely separate
        # OS process on the same ARCHIVE volume, so only a real cross-process
        # primitive (flock on a shared file) can prove this actually works -
        # a same-process threading test would pass even with no fix at all.
        module.ARCHIVE.mkdir(parents=True, exist_ok=True)
        lock_path = module.ARCHIVE / ".lock"
        script = (
            "import fcntl, sys, time\n"
            "handle = open(sys.argv[1], 'w')\n"
            "fcntl.flock(handle, fcntl.LOCK_EX)\n"
            "print('locked', flush=True)\n"
            "time.sleep(1.5)\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", script, str(lock_path)],
                                stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "locked")
            start = time.monotonic()
            with module.cross_process_archive_lock():
                elapsed = time.monotonic() - start
            self.assertGreater(elapsed, 1.0,
                              "cross_process_archive_lock() did not wait for the other process")
        finally:
            proc.wait(timeout=5)
            proc.stdout.close()

    def test_success_archive_is_verified_before_sources_are_removed(self):
        (self.data / "source.rpm").write_bytes(b"source")
        job_dir = self.output / "job"
        job_dir.mkdir()
        (job_dir / "router-goldenk9.iso").write_bytes(b"golden image")
        (job_dir / "checksums.json").write_bytes(b"remove")
        (module.WORK / "job").mkdir()
        artifacts = module.archive_golden_iso_and_cleanup(
            "job", job_dir, [self.data / "source.rpm"]
        )
        self.assertEqual(len(artifacts), 1)
        self.assertTrue((module.ARCHIVE / "job/router-goldenk9.iso").exists())
        self.assertFalse((self.data / "source.rpm").exists())
        self.assertFalse(job_dir.exists())

    def test_archived_artifacts_report_their_sha256(self):
        job_dir = self.output / "job"
        job_dir.mkdir()
        (job_dir / "router-goldenk9.iso").write_bytes(b"golden image")
        artifacts = module.archive_golden_iso_and_cleanup("job", job_dir, [])
        self.assertEqual(artifacts[0]["sha256"], hashlib.sha256(b"golden image").hexdigest())

    def test_build_report_captures_version_plan_and_output_checksums(self):
        job = {
            "id": "job-1", "created": 100.0, "finished": 200.0,
            "payload": {"label": "my-build"},
            "command_preview": "gisobuild.py --iso base.iso",
            "build_plan": {"fingerprint": "abc123", "platform": "ncs5500"},
        }
        artifacts = [{"path": "golden.iso", "size": 5, "sha256": "deadbeef"}]
        with patch.object(module, "gisobuild_commit", return_value="cafef00d"):
            report = module.build_report(job, artifacts)
        self.assertEqual(report["job_id"], "job-1")
        self.assertEqual(report["label"], "my-build")
        self.assertEqual(report["web_ui_version"], module.APP_VERSION)
        self.assertEqual(report["gisobuild_image"], module.IMAGE)
        self.assertEqual(report["gisobuild_commit"], "cafef00d")
        self.assertEqual(report["generated_command"], "gisobuild.py --iso base.iso")
        self.assertEqual(report["build_plan"], job["build_plan"])
        self.assertEqual(report["output_artifacts"], artifacts)

    def test_write_build_report_persists_json_next_to_archived_artifacts(self):
        (module.ARCHIVE / "job-2").mkdir(parents=True)
        job = {"id": "job-2", "payload": {}, "build_plan": {}}
        module.write_build_report("job-2", job, [{"path": "golden.iso"}])
        report = json.loads((module.ARCHIVE / "job-2" / "build-report.json").read_text())
        self.assertEqual(report["job_id"], "job-2")

    def test_write_build_report_does_not_raise_when_archive_dir_is_missing(self):
        module.write_build_report("missing-job", {"id": "missing-job", "payload": {}}, [])

    def test_archive_list_reports_has_report_only_when_the_file_exists(self):
        job_dir = self.output / "job"
        job_dir.mkdir()
        (job_dir / "router-goldenk9.iso").write_bytes(b"golden image")
        module.archive_golden_iso_and_cleanup("job", job_dir, [])
        without_report = self.client.get("/api/archive").get_json()
        self.assertFalse(without_report[0]["has_report"])
        (module.ARCHIVE / "job" / "build-report.json").write_text("{}")
        with_report = self.client.get("/api/archive").get_json()
        self.assertTrue(with_report[0]["has_report"])

    def test_successful_build_preserves_inputs_not_owned_by_job(self):
        owned = self.data / "selected.rpm"
        unrelated = self.data / "future-build.iso"
        owned.write_bytes(b"selected")
        unrelated.write_bytes(b"keep")
        job_dir = self.output / "scoped-job"
        job_dir.mkdir()
        (job_dir / "router-golden.iso").write_bytes(b"golden image")

        module.archive_giso_artifacts_and_cleanup("scoped-job", job_dir, [owned])

        self.assertFalse(owned.exists())
        self.assertTrue(unrelated.exists())

    def test_successful_build_removes_emptied_extraction_directory_and_source_archive(self):
        archive = self.data / "vendor-bundle.tar"
        archive.write_bytes(b"tar contents")
        extraction_dir = self.data / "vendor-bundle"
        extraction_dir.mkdir()
        owned = extraction_dir / "selected.rpm"
        owned.write_bytes(b"selected")
        job_dir = self.output / "extracted-job"
        job_dir.mkdir()
        (job_dir / "router-golden.iso").write_bytes(b"golden image")

        module.archive_giso_artifacts_and_cleanup("extracted-job", job_dir, [owned])

        self.assertFalse(owned.exists())
        self.assertFalse(extraction_dir.exists())
        self.assertFalse(archive.exists())

    def test_successful_build_preserves_extraction_directory_with_remaining_files(self):
        archive = self.data / "vendor-bundle.tar"
        archive.write_bytes(b"tar contents")
        extraction_dir = self.data / "vendor-bundle"
        extraction_dir.mkdir()
        owned = extraction_dir / "selected.rpm"
        owned.write_bytes(b"selected")
        remaining = extraction_dir / "unused.rpm"
        remaining.write_bytes(b"still needed by another build")
        job_dir = self.output / "partial-job"
        job_dir.mkdir()
        (job_dir / "router-golden.iso").write_bytes(b"golden image")

        module.archive_giso_artifacts_and_cleanup("partial-job", job_dir, [owned])

        self.assertFalse(owned.exists())
        self.assertTrue(remaining.exists())
        self.assertTrue(extraction_dir.exists())
        self.assertTrue(archive.exists())

    def test_cancellation_during_finalization_preserves_inputs(self):
        owned = self.data / "selected.rpm"
        owned.write_bytes(b"selected")
        job_dir = self.output / "cancel-finalize"
        job_dir.mkdir()
        (job_dir / "router-golden.iso").write_bytes(b"golden image")

        with self.assertRaises(module.BuildCancelled):
            module.archive_giso_artifacts_and_cleanup(
                "cancel-finalize", job_dir, [owned],
                lambda: (_ for _ in ()).throw(module.BuildCancelled("cancelled")),
            )

        self.assertTrue(owned.exists())
        self.assertTrue(job_dir.exists())
        self.assertFalse((module.ARCHIVE / "cancel-finalize").exists())

    def test_archive_retention_starts_when_old_source_is_archived(self):
        job_dir = self.output / "old-source-job"
        job_dir.mkdir()
        source = job_dir / "router-golden.iso"
        source.write_bytes(b"golden image")
        old_time = time.time() - 31 * 86400
        os.utime(source, (old_time, old_time))

        module.archive_giso_artifacts_and_cleanup("old-source-job", job_dir)

        archived = module.ARCHIVE / "old-source-job/router-golden.iso"
        self.assertGreater(archived.stat().st_mtime, time.time() - 60)

    def test_expired_orphan_partial_upload_is_removed_after_restart(self):
        parts = self.data / ".parts"
        parts.mkdir()
        orphan = parts / "orphan.part"
        orphan.write_bytes(b"partial")
        old_time = time.time() - module.UPLOAD_SESSION_TTL - 1
        os.utime(orphan, (old_time, old_time))

        module.expire_upload_sessions()

        self.assertFalse(orphan.exists())

    def test_upload_init_reserves_space_for_concurrent_sessions(self):
        with patch("app.shutil.disk_usage", return_value=SimpleNamespace(
                free=module.MIN_FREE_BYTES + 15)):
            first = self.client.post("/api/uploads/init", json={"name": "one.rpm", "size": 10})
            second = self.client.post("/api/uploads/init", json={"name": "two.rpm", "size": 10})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 507)

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
        os.utime(old_job / "golden.iso", (old_time, old_time))
        os.utime(old_job / "usb.zip", (old_time, old_time))
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

    def test_archive_directory_change_does_not_extend_artifact_retention(self):
        old_job = module.ARCHIVE / "old-job"
        old_job.mkdir()
        iso = old_job / "golden.iso"
        usb = old_job / "usb.zip"
        iso.write_bytes(b"iso")
        usb.write_bytes(b"usb")
        old_time = time.time() - 31 * 86400
        os.utime(iso, (old_time, old_time))
        os.utime(usb, (old_time, old_time))
        os.utime(old_job, None)
        with patch.object(module, "ARCHIVE_RETENTION_DAYS", 30), \
                patch.object(module, "MAX_ARCHIVE_BYTES", 1024):
            removed = module.enforce_archive_policy()
        self.assertEqual(removed, ["old-job"])
        self.assertFalse(old_job.exists())

    def test_archive_quota_removes_oldest_complete_job(self):
        old_job = module.ARCHIVE / "old-job"
        old_job.mkdir()
        (old_job / "golden.iso").write_bytes(b"123456")
        old_time = time.time() - 60
        os.utime(old_job / "golden.iso", (old_time, old_time))
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

    def test_new_archive_is_protected_when_quota_evicts_existing_job(self):
        existing_job = module.ARCHIVE / "existing-job"
        existing_job.mkdir()
        existing_iso = existing_job / "golden.iso"
        existing_iso.write_bytes(b"123456")
        job_dir = self.output / "new-job"
        job_dir.mkdir()
        new_iso = job_dir / "new-golden.iso"
        new_iso.write_bytes(b"abcdef")
        old_time = time.time() - 31 * 86400
        os.utime(new_iso, (old_time, old_time))
        with patch.object(module, "ARCHIVE_RETENTION_DAYS", 30), \
                patch.object(module, "MAX_ARCHIVE_BYTES", 10):
            artifacts = module.archive_giso_artifacts_and_cleanup("new-job", job_dir)
        self.assertEqual(artifacts[0]["path"], "new-golden.iso")
        self.assertTrue((module.ARCHIVE / "new-job/new-golden.iso").exists())
        self.assertFalse(existing_job.exists())

    @patch("app.subprocess.run")
    def test_health_returns_service_unavailable_when_dependency_is_down(self, run):
        run.side_effect = module.subprocess.TimeoutExpired([module.DOCKER_BIN, "info"], 5)
        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["ok"])
        self.assertNotIn("image", response.get_json())

    @patch("app.subprocess.run")
    def test_health_is_pure_liveness_and_ignores_dependency_state(self, run):
        run.side_effect = module.subprocess.TimeoutExpired([module.DOCKER_BIN, "info"], 5)
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_ready_reports_database_and_disk_checks(self):
        response = self.client.get("/api/ready")
        payload = response.get_json()
        self.assertIn("database", payload)
        self.assertIn("disk", payload)

    def test_storage_reports_real_disk_and_archive_usage(self):
        archive_dir = module.ARCHIVE / "job-1"
        archive_dir.mkdir(parents=True)
        (archive_dir / "golden.iso").write_bytes(b"x" * 1000)

        payload = self.client.get("/api/storage").get_json()

        self.assertEqual(payload["archive_used_bytes"], 1000)
        self.assertEqual(payload["archive_quota_bytes"], module.MAX_ARCHIVE_BYTES)
        self.assertEqual(payload["archive_retention_days"], module.ARCHIVE_RETENTION_DAYS)
        self.assertEqual(payload["disk_free_bytes"], 100 * 1024**3)

    def test_storage_reports_zero_archive_usage_before_any_archive_exists(self):
        payload = self.client.get("/api/storage").get_json()
        self.assertEqual(payload["archive_used_bytes"], 0)

    def test_file_preview_returns_text_content_of_a_small_config_file(self):
        (self.data / "router.cfg").write_text("hostname router1\n")
        payload = self.client.get("/api/file-preview?path=router.cfg").get_json()
        self.assertTrue(payload["previewable"])
        self.assertEqual(payload["text"], "hostname router1\n")

    def test_file_preview_refuses_a_file_that_is_too_large(self):
        (self.data / "big.cfg").write_bytes(b"x" * (module.MAX_FILE_PREVIEW_BYTES + 1))
        payload = self.client.get("/api/file-preview?path=big.cfg").get_json()
        self.assertFalse(payload["previewable"])
        self.assertIn("too large", payload["reason"])

    def test_file_preview_refuses_a_binary_file(self):
        (self.data / "voucher.bin").write_bytes(b"\xff\xfe\x00\x01binary")
        payload = self.client.get("/api/file-preview?path=voucher.bin").get_json()
        self.assertFalse(payload["previewable"])
        self.assertIn("not plain text", payload["reason"])

    def test_file_preview_rejects_a_path_outside_the_upload_directory(self):
        response = self.client.get("/api/file-preview?path=../outside.cfg")
        self.assertEqual(response.status_code, 400)

    def test_file_preview_rejects_a_directory(self):
        (self.data / "a-dir").mkdir()
        response = self.client.get("/api/file-preview?path=a-dir")
        self.assertEqual(response.status_code, 400)

    @patch("app.subprocess.Popen")
    def test_build_events_are_logged_with_inventory_revision_and_plan_fingerprint(self, popen):
        pull = MagicMock(returncode=0, args=[module.DOCKER_BIN, "pull"])
        pull.communicate.return_value = ("", None)
        job_dir = self.output / "job"
        job_dir.mkdir()
        (job_dir / "router-golden.iso").write_bytes(b"golden image")
        build = SimpleNamespace(pid=123, stdout=[], wait=lambda: 0)
        popen.side_effect = [pull, build]
        module.jobs["job"] = {"id": "job", "status": "running", "created": time.time(),
                              "updated": time.time(), "log": "", "progress": 3,
                              "phase": "Preparing", "artifacts": [],
                              "inventory_revision": "rev-1", "plan_fingerprint": "fp-1"}
        with patch.object(module, "gisobuild_commit", return_value=None), \
             self.assertLogs(module.app.logger.name, level="INFO") as captured:
            module.run_job("job", [module.DOCKER_BIN, "run"])
        log = "\n".join(captured.output)
        self.assertIn("event=build_started", log)
        self.assertIn("inventory_revision=rev-1", log)
        self.assertIn("plan_fingerprint=fp-1", log)
        self.assertIn("event=build_finished", log)
        self.assertIn("duration_ms=", log)

    @patch("app.subprocess.Popen")
    def test_image_pull_timeout_marks_build_failed(self, popen):
        pull = MagicMock()
        pull.communicate.side_effect = module.subprocess.TimeoutExpired(
            [module.DOCKER_BIN, "pull"], 10
        )
        popen.return_value = pull
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "log": "", "progress": 3,
                              "phase": "Preparing", "artifacts": []}
        with patch.object(module, "GISO_PULL_TIMEOUT_SECONDS", 10):
            module.run_job("job", [module.DOCKER_BIN, "run"])
        self.assertEqual(module.jobs["job"]["status"], "failed")
        pull.terminate.assert_called_once_with()
        pull.wait.assert_called_once_with(timeout=20)

    @patch("app.subprocess.Popen")
    def test_run_job_honors_cancellation_during_image_pull(self, popen):
        pull = MagicMock()
        pull.returncode = -15
        pull.args = [module.DOCKER_BIN, "pull"]

        def complete_pull(**_kwargs):
            module.jobs["job"]["status"] = "cancelling"
            return "", None

        pull.communicate.side_effect = complete_pull
        popen.return_value = pull
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "log": "", "progress": 3,
                              "phase": "Preparing", "artifacts": []}

        module.run_job("job", [module.DOCKER_BIN, "run"])

        self.assertEqual(module.jobs["job"]["status"], "cancelled")
        self.assertNotIn("error", module.jobs["job"])

    @patch("app.subprocess.Popen")
    def test_zero_exit_without_iso_is_not_reported_complete(self, popen):
        pull = MagicMock(returncode=0, args=[module.DOCKER_BIN, "pull"])
        pull.communicate.return_value = ("", None)
        build = SimpleNamespace(pid=123, stdout=[], wait=lambda: 0)
        popen.side_effect = [pull, build]
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "log": "", "progress": 3,
                              "phase": "Preparing", "artifacts": []}
        module.run_job("job", [module.DOCKER_BIN, "run"])
        self.assertEqual(module.jobs["job"]["status"], "failed")
        self.assertEqual(module.jobs["job"]["phase"], "Build failed")
        self.assertEqual(module.jobs["job"]["progress"], 3)

    @patch("app.subprocess.Popen")
    def test_background_build_error_is_safe_for_job_api(self, popen):
        popen.side_effect = RuntimeError("/internal/customer-router.iso")
        module.jobs["job"] = {"id": "job", "status": "running", "created": 1,
                              "updated": 1, "log": "", "progress": 3,
                              "phase": "Preparing", "artifacts": []}
        module.run_job("job", [module.DOCKER_BIN, "run"])
        response = self.client.get("/api/jobs/job")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("internal", response.get_json()["error"])
        self.assertNotIn("customer-router", response.get_json()["error"])

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

    def test_nested_golden_output_is_recognized_and_archived(self):
        job_dir = self.output / "nested-job"
        nested = job_dir / "results"
        nested.mkdir(parents=True)
        (nested / "router-golden.iso").write_bytes(b"nested giso")
        self.assertEqual([path.name for path in module.giso_artifact_candidates(job_dir)],
                         ["router-golden.iso"])
        artifacts = module.archive_giso_artifacts_and_cleanup("nested-job", job_dir)
        self.assertEqual(artifacts[0]["path"], "router-golden.iso")

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
        self.assertEqual(
            result["md5"], hashlib.md5(content, usedforsecurity=False).hexdigest()
        )
        self.assertEqual(result["sha256"], hashlib.sha256(content).hexdigest())


@unittest.skipUnless(
    ISOINFO_AVAILABLE,
    "genisoimage and isoinfo are only available inside the giso-webui container image",
)
class IsoArchitectureInspectionTests(unittest.TestCase):
    """Regression coverage for inspect_iso_architecture() against real ISO9660 images.

    These build tiny synthetic ISOs with genisoimage; no Cisco content is
    involved. They must run only inside the giso-webui container, which is
    the sole place isoinfo/genisoimage are installed (see AGENTS.md).
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        module.iso_architecture_cache.clear()

    def tearDown(self):
        self.temp.cleanup()

    def _build_iso(self, files: dict[str, str]) -> Path:
        source = Path(self.temp.name) / "iso-src"
        source.mkdir()
        for name, content in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        iso_path = Path(self.temp.name) / "test.iso"
        subprocess.run(
            ["genisoimage", "-quiet", "-R", "-o", str(iso_path), str(source)],
            check=True, capture_output=True,
        )
        return iso_path

    def test_detects_x86_64_only_exr_image_from_metadata(self):
        iso_path = self._build_iso({
            "iosxr_image_mdata.yml": "x86_64 supported arch list: corei7_64\narm supported arch list:\n",
        })
        self.assertEqual(module.inspect_iso_architecture(iso_path), frozenset({"x86_64"}))

    def test_detects_dual_arch_exr_image_from_metadata(self):
        iso_path = self._build_iso({
            "iosxr_image_mdata.yml": "x86_64 supported arch list: corei7_64\narm supported arch list: armv7l\n",
        })
        self.assertEqual(module.inspect_iso_architecture(iso_path), frozenset({"x86_64", "aarch64"}))

    def test_falls_back_to_rpm_repository_listing_for_lnt_image(self):
        iso_path = self._build_iso({"repo/foo-1.0-r0.x86_64.rpm": ""})
        self.assertEqual(module.inspect_iso_architecture(iso_path), frozenset({"x86_64"}))

    def test_unreadable_iso_reports_unknown_rather_than_raising(self):
        bogus = Path(self.temp.name) / "not-an-iso.iso"
        bogus.write_bytes(b"not a real iso9660 image")
        self.assertEqual(module.inspect_iso_architecture(bogus), frozenset())

    def test_result_is_cached_by_path_size_and_mtime(self):
        iso_path = self._build_iso({"repo/foo-1.0-r0.x86_64.rpm": ""})
        first = module.inspect_iso_architecture(iso_path)
        with patch("app.subprocess.run") as run:
            second = module.inspect_iso_architecture(iso_path)
        run.assert_not_called()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
