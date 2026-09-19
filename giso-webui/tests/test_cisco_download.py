import hashlib
import json
import os
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from cisco_download import (
    DOWNLOAD_URL,
    EULA_URL,
    METADATA_URL,
    CiscoDownloadError,
    CiscoSoftwareClient,
    secret_value,
)


class _JsonResponse:
    """Fake urllib response for _json_request(), mirroring its context-manager use."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size):
        value, self._data = self._data, b""
        return value


class CiscoDownloadTests(unittest.TestCase):
    def client(self):
        return CiscoSoftwareClient("id", "secret", resolver=lambda host: ["8.8.8.8"])

    def test_credentials_can_be_loaded_from_docker_secret_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            path.write_text("private\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"CISCO_CLIENT_SECRET": "wrong", "CISCO_CLIENT_SECRET_FILE": str(path)},
            ):
                self.assertEqual(secret_value("CISCO_CLIENT_SECRET"), "private")

    def test_constructor_rejects_missing_credentials(self):
        with self.assertRaisesRegex(CiscoDownloadError, "not configured"):
            CiscoSoftwareClient("", "secret")
        with self.assertRaisesRegex(CiscoDownloadError, "not configured"):
            CiscoSoftwareClient("id", "")

    def test_access_token_request_without_a_token_is_rejected(self):
        client = self.client()
        client._json_request = lambda *args, **kwargs: {"expires_in": 3600}
        with self.assertRaisesRegex(
            CiscoDownloadError, "did not return an access token"
        ):
            client._access_token()

    def test_access_token_falls_back_to_a_default_lifetime_when_expires_in_is_malformed(
        self,
    ):
        client = self.client()
        client._json_request = lambda *args, **kwargs: {
            "access_token": "tok",
            "expires_in": "not-a-number",
        }
        self.assertEqual(client._access_token(), "tok")
        self.assertAlmostEqual(client._token[1], time.monotonic() + 3600, delta=5)

    def test_token_is_cached_until_close_to_expiry(self):
        client = self.client()
        calls = []
        client._json_request = lambda *args, **kwargs: (
            calls.append(args) or {"access_token": "token", "expires_in": 3600}
        )
        self.assertEqual(client._access_token(), "token")
        self.assertEqual(client._access_token(), "token")
        self.assertEqual(len(calls), 1)

    def test_expiring_token_is_renewed(self):
        client = self.client()
        client._token = ("old", 0)
        client._json_request = lambda *args, **kwargs: {
            "access_token": "new",
            "expires_in": 3600,
        }
        self.assertEqual(client._access_token(), "new")

    def test_private_and_unapproved_download_destinations_are_rejected(self):
        with self.assertRaises(CiscoDownloadError):
            self.client()._validate_download_url("https://example.com/file.iso")
        client = CiscoSoftwareClient(
            "id", "secret", resolver=lambda host: ["127.0.0.1"]
        )
        with self.assertRaises(CiscoDownloadError):
            client._validate_download_url("https://download.cisco.com/file.iso")

    def test_contract_error_is_not_returned_as_a_download(self):
        with self.assertRaisesRegex(CiscoDownloadError, "CONTRACT_REJECTED"):
            self.client()._check_errors(
                {"exception": {"code": "CONTRACT_REJECTED", "message": "sensitive"}}
            )

    def test_download_checks_size_and_all_hashes(self):
        content = b"licensed fixture placeholder"
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, size):
                nonlocal content
                value, content = content, b""
                return value

        client._opener.open = lambda request, timeout: Response()
        payload = b"licensed fixture placeholder"
        with tempfile.TemporaryDirectory() as directory:
            progress = []
            result = client.download(
                "https://download.cisco.com/file.iso",
                Path(directory) / "file.iso",
                expected_size=len(payload),
                max_bytes=1024,
                expected_md5=hashlib.md5(payload, usedforsecurity=False).hexdigest(),
                expected_sha512=hashlib.sha512(payload).hexdigest(),
                progress=lambda written, total: progress.append((written, total)),
            )
            self.assertEqual(result.sha256, hashlib.sha256(payload).hexdigest())
            self.assertEqual(progress, [(len(payload), len(payload))])

    def test_stale_partial_file_from_a_previous_crashed_attempt_is_overwritten(self):
        content = b"licensed fixture placeholder"
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, size):
                nonlocal content
                value, content = content, b""
                return value

        client._opener.open = lambda request, timeout: Response()
        payload = b"licensed fixture placeholder"
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "file.iso"
            destination.with_name(".file.iso.part").write_bytes(
                b"leftover from a crashed attempt"
            )
            result = client.download(
                "https://download.cisco.com/file.iso",
                destination,
                expected_size=len(payload),
                max_bytes=1024,
            )
            self.assertEqual(result.size, len(payload))
            self.assertEqual(destination.read_bytes(), payload)

    def test_partial_file_is_removed_after_size_mismatch(self):
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, size):
                return b""

        client._opener.open = lambda request, timeout: Response()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "file.iso"
            with self.assertRaises(CiscoDownloadError):
                client.download(
                    "https://download.cisco.com/file.iso",
                    destination,
                    expected_size=1,
                    max_bytes=1024,
                )
            self.assertFalse(destination.with_name(".file.iso.part").exists())

    def test_interrupted_download_is_redacted_and_partial_file_is_removed(self):
        client = self.client()
        client._access_token = lambda: "token"
        client._validate_download_url = lambda url: None

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, size):
                raise TimeoutError("private upstream detail")

        client._opener.open = lambda request, timeout: Response()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "file.iso"
            with self.assertRaisesRegex(CiscoDownloadError, "interrupted") as raised:
                client.download(
                    "https://download.cisco.com/file.iso",
                    destination,
                    expected_size=1,
                    max_bytes=1024,
                )
            self.assertNotIn("private upstream detail", str(raised.exception))
            self.assertFalse(destination.with_name(".file.iso.part").exists())

    def test_redirect_is_revalidated_before_download(self):
        content = b"x"
        client = self.client()
        client._access_token = lambda: "token"
        checked = []
        client._validate_download_url = checked.append

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, size):
                nonlocal content
                value, content = content, b""
                return value

        calls = 0

        def open_request(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    302,
                    "redirect",
                    {"Location": "https://dl.cisco.com/final.iso"},
                    None,
                )
            return Response()

        client._opener.open = open_request
        with tempfile.TemporaryDirectory() as directory:
            client.download(
                "https://download.cisco.com/file.iso",
                Path(directory) / "file.iso",
                expected_size=1,
                max_bytes=1024,
            )
        self.assertEqual(len(checked), 2)
        self.assertEqual(checked[1], "https://dl.cisco.com/final.iso")

    def test_json_request_returns_the_parsed_response_on_success(self):
        client = self.client()
        client._opener.open = lambda request, timeout: _JsonResponse(
            json.dumps({"ok": True}).encode()
        )
        self.assertEqual(
            client._json_request(METADATA_URL, b"{}", authenticated=False), {"ok": True}
        )

    def test_json_request_wraps_a_network_failure(self):
        client = self.client()

        def open_request(request, timeout):
            raise urllib.error.URLError("connection refused")

        client._opener.open = open_request
        with self.assertRaisesRegex(CiscoDownloadError, "Cisco API request failed"):
            client._json_request(METADATA_URL, b"{}", authenticated=False)

    def test_json_request_rejects_an_oversized_response(self):
        client = self.client()
        oversized = json.dumps({"data": "x" * (2 * 1024 * 1024)}).encode()
        client._opener.open = lambda request, timeout: _JsonResponse(oversized)
        with self.assertRaisesRegex(CiscoDownloadError, "too large"):
            client._json_request(METADATA_URL, b"{}", authenticated=False)

    def test_json_request_rejects_invalid_json(self):
        client = self.client()
        client._opener.open = lambda request, timeout: _JsonResponse(b"not json")
        with self.assertRaisesRegex(CiscoDownloadError, "invalid response"):
            client._json_request(METADATA_URL, b"{}", authenticated=False)

    def test_json_request_rejects_a_non_object_json_response(self):
        client = self.client()
        client._opener.open = lambda request, timeout: _JsonResponse(
            json.dumps([1, 2, 3]).encode()
        )
        with self.assertRaisesRegex(CiscoDownloadError, "invalid response"):
            client._json_request(METADATA_URL, b"{}", authenticated=False)

    def test_json_request_authenticates_with_the_access_token(self):
        client = self.client()
        client._access_token = lambda: "the-token"
        seen = {}

        def open_request(request, timeout):
            seen["authorization"] = request.get_header("Authorization")
            return _JsonResponse(json.dumps({}).encode())

        client._opener.open = open_request
        client._json_request(METADATA_URL, b"{}")
        self.assertEqual(seen["authorization"], "Bearer the-token")

    def test_exceptions_are_found_inside_a_list(self):
        # _check_errors()'s recursive walk had only ever been exercised
        # through a dict-nested error; Cisco's real response shape can also
        # carry errors inside a JSON array (e.g. {"errors": [{...}]}).
        with self.assertRaisesRegex(CiscoDownloadError, "LOGIN_REQD"):
            self.client()._check_errors(
                {"errors": [{"code": "LOGIN_REQD", "message": "sensitive"}]}
            )

    def test_blocked_code_without_a_contract_prefix_is_also_rejected(self):
        with self.assertRaisesRegex(CiscoDownloadError, "K9_REJECTED"):
            self.client()._check_errors(
                {"exception": {"code": "K9_REJECTED", "message": "sensitive"}}
            )

    def test_search_posts_the_expected_payload_to_the_metadata_endpoint(self):
        client = self.client()
        captured = {}
        client._json_request = lambda url, body, **kwargs: (
            captured.update(url=url, body=json.loads(body)) or {"metadataTransId": "tx"}
        )
        result = client.search("NCS-5500", "25.1.1", "25.1.2")
        self.assertEqual(captured["url"], METADATA_URL)
        self.assertEqual(
            captured["body"],
            {
                "pid": "NCS-5500",
                "currentReleaseVersion": "25.1.1",
                "outputReleaseVersion": "25.1.2",
                "pageIndex": 1,
                "perPage": 25,
            },
        )
        self.assertEqual(result["metadataTransId"], "tx")

    def test_search_raises_on_a_blocked_response(self):
        client = self.client()
        client._json_request = lambda url, body, **kwargs: {
            "exception": {"code": "CONTRACT_REJECTED", "message": "sensitive"}
        }
        with self.assertRaises(CiscoDownloadError):
            client.search("NCS-5500", "25.1.1", "25.1.2")

    def test_request_download_rejects_zero_or_too_many_images(self):
        client = self.client()
        client._json_request = lambda *args, **kwargs: {}
        with self.assertRaisesRegex(CiscoDownloadError, "one and five"):
            client.request_download("pid", "mdf", "tx", [])
        with self.assertRaisesRegex(CiscoDownloadError, "one and five"):
            client.request_download("pid", "mdf", "tx", ["g"] * 6)

    def test_request_download_posts_the_expected_payload(self):
        client = self.client()
        captured = {}
        client._json_request = lambda url, body, **kwargs: (
            captured.update(url=url, body=json.loads(body)) or {}
        )
        client.request_download("PID1", "mdf-1", "tx-1", ["guid-1", "guid-2"])
        self.assertEqual(captured["url"], DOWNLOAD_URL)
        self.assertEqual(
            captured["body"],
            {
                "pid": "PID1",
                "mdfId": "mdf-1",
                "metadataTransId": "tx-1",
                "imageGuids": ["guid-1", "guid-2"],
            },
        )

    def test_accept_eula_posts_a_comma_joined_file_list(self):
        client = self.client()
        captured = {}
        client._json_request = lambda url, body, **kwargs: (
            captured.update(url=url, body=json.loads(body)) or {}
        )
        client.accept_eula(["a.iso", "b.iso"])
        self.assertEqual(captured["url"], EULA_URL)
        self.assertEqual(captured["body"]["fileNames"], "a.iso,b.iso")
        self.assertEqual(captured["body"]["status"], "Accepted")

    def test_accept_k9_requires_both_declarations(self):
        client = self.client()
        client._json_request = lambda *args, **kwargs: {}
        with self.assertRaisesRegex(CiscoDownloadError, "must be confirmed"):
            client.accept_k9(
                "a.iso", commercial_or_civil=False, not_government_or_military=True
            )
        with self.assertRaisesRegex(CiscoDownloadError, "must be confirmed"):
            client.accept_k9(
                "a.iso", commercial_or_civil=True, not_government_or_military=False
            )

    def test_accept_k9_posts_the_expected_payload_when_confirmed(self):
        client = self.client()
        captured = {}
        client._json_request = lambda url, body, **kwargs: (
            captured.update(url=url, body=json.loads(body)) or {}
        )
        client.accept_k9(
            "a.iso", commercial_or_civil=True, not_government_or_military=True
        )
        self.assertEqual(captured["body"]["fileNames"], "a.iso")
        self.assertEqual(captured["body"]["busFunction"], "COMM_OR_CIVIL")


if __name__ == "__main__":
    unittest.main()
