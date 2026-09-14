import hashlib
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from cisco_download import CiscoDownloadError, CiscoSoftwareClient, secret_value


class CiscoDownloadTests(unittest.TestCase):
    def client(self):
        return CiscoSoftwareClient("id", "secret", resolver=lambda host: ["8.8.8.8"])

    def test_credentials_can_be_loaded_from_docker_secret_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.write_text("private\n", encoding="utf-8")
            with patch.dict(os.environ, {"CISCO_CLIENT_SECRET": "wrong", "CISCO_CLIENT_SECRET_FILE": str(path)}):
                self.assertEqual(secret_value("CISCO_CLIENT_SECRET"), "private")

    def test_token_is_cached_until_close_to_expiry(self):
        client = self.client()
        calls = []
        client._json_request = lambda *args, **kwargs: calls.append(args) or {"access_token": "token", "expires_in": 3600}
        self.assertEqual(client._access_token(), "token")
        self.assertEqual(client._access_token(), "token")
        self.assertEqual(len(calls), 1)

    def test_expiring_token_is_renewed(self):
        client = self.client()
        client._token = ("old", 0)
        client._json_request = lambda *args, **kwargs: {"access_token": "new", "expires_in": 3600}
        self.assertEqual(client._access_token(), "new")

    def test_private_and_unapproved_download_destinations_are_rejected(self):
        with self.assertRaises(CiscoDownloadError):
            self.client()._validate_download_url("https://example.com/file.iso")
        client = CiscoSoftwareClient("id", "secret", resolver=lambda host: ["127.0.0.1"])
        with self.assertRaises(CiscoDownloadError):
            client._validate_download_url("https://download.cisco.com/file.iso")

    def test_contract_error_is_not_returned_as_a_download(self):
        with self.assertRaisesRegex(CiscoDownloadError, "CONTRACT_REJECTED"):
            self.client()._check_errors({"exception": {"code": "CONTRACT_REJECTED", "message": "sensitive"}})

    def test_download_checks_size_and_all_hashes(self):
        content = b"licensed fixture placeholder"
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, size):
                nonlocal content
                value, content = content, b""
                return value

        client._opener.open = lambda request, timeout: Response()
        payload = b"licensed fixture placeholder"
        with tempfile.TemporaryDirectory() as directory:
            progress = []
            result = client.download(
                "https://download.cisco.com/file.iso", Path(directory) / "file.iso",
                expected_size=len(payload), max_bytes=1024,
                expected_md5=hashlib.md5(payload).hexdigest(),
                expected_sha512=hashlib.sha512(payload).hexdigest(),
                progress=lambda written, total: progress.append((written, total)),
            )
            self.assertEqual(result.sha256, hashlib.sha256(payload).hexdigest())
            self.assertEqual(progress, [(len(payload), len(payload))])

    def test_partial_file_is_removed_after_size_mismatch(self):
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, size): return b""

        client._opener.open = lambda request, timeout: Response()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "file.iso"
            with self.assertRaises(CiscoDownloadError):
                client.download("https://download.cisco.com/file.iso", destination,
                                expected_size=1, max_bytes=1024)
            self.assertFalse(destination.with_name(".file.iso.part").exists())

    def test_interrupted_download_is_redacted_and_partial_file_is_removed(self):
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, size): raise TimeoutError("private upstream detail")

        client._opener.open = lambda request, timeout: Response()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "file.iso"
            with self.assertRaisesRegex(CiscoDownloadError, "interrupted") as raised:
                client.download("https://download.cisco.com/file.iso", destination,
                                expected_size=1, max_bytes=1024)
            self.assertNotIn("private upstream detail", str(raised.exception))
            self.assertFalse(destination.with_name(".file.iso.part").exists())

    def test_redirect_is_revalidated_before_download(self):
        content = b"x"
        client = self.client()
        client._access_token = lambda: "token"
        checked = []
        client._validate_download_url = checked.append

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, size):
                nonlocal content
                value, content = content, b""
                return value

        calls = 0
        def open_request(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.HTTPError(request.full_url, 302, "redirect", {
                    "Location": "https://dl.cisco.com/final.iso"
                }, None)
            return Response()

        client._opener.open = open_request
        with tempfile.TemporaryDirectory() as directory:
            client.download("https://download.cisco.com/file.iso", Path(directory) / "file.iso",
                            expected_size=1, max_bytes=1024)
        self.assertEqual(len(checked), 2)
        self.assertEqual(checked[1], "https://dl.cisco.com/final.iso")


if __name__ == "__main__":
    unittest.main()
