"""Cisco Automated Software Distribution client with strict download controls."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TOKEN_URL = "https://id.cisco.com/oauth2/default/v1/token"  # noqa: S105 - an endpoint URL, not a secret
METADATA_URL = "https://apix.cisco.com/software/v4.0/metadata/pidrelease"
DOWNLOAD_URL = "https://apix.cisco.com/software/v4.0/download/pidimage"
EULA_URL = "https://apix.cisco.com/software/v4.0/compliance/eula"
K9_URL = "https://apix.cisco.com/software/v4.0/compliance/k9"
ALLOWED_DOWNLOAD_HOSTS = ("cisco.com",)
BLOCKED_CODES = {
    "CONTRACT_NOT_AUTH",
    "CONTRACT_REJECTED",
    "CONTRACT_ACCESS",
    "IMG_CONTRACT_REQD",
    "LOGIN_REQD",
    "LOGIN_IMG_DWLD",
    "IP_CHECK_FAIL",
    "K9_REJECTED",
}


class CiscoDownloadError(RuntimeError):
    """Safe error suitable for returning to the local UI."""


def secret_value(name: str) -> str:
    """Read a secret from NAME_FILE first, then NAME, without logging either."""
    secret_file = os.getenv(f"{name}_FILE", "").strip()
    if secret_file:
        try:
            return Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CiscoDownloadError(f"Cannot read {name}_FILE") from exc
    return os.getenv(name, "").strip()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    size: int
    sha256: str
    md5: str
    sha512: str


class CiscoSoftwareClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        timeout: int = 60,
        allowed_hosts: tuple[str, ...] = ALLOWED_DOWNLOAD_HOSTS,
        resolver: Callable[[str], list[str]] | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise CiscoDownloadError("Cisco API credentials are not configured")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.allowed_hosts = tuple(host.lower().rstrip(".") for host in allowed_hosts)
        self.resolver = resolver or self._resolve
        self._opener = urllib.request.build_opener(_NoRedirect)
        self._token: tuple[str, float] | None = None
        self._token_lock = threading.Lock()

    @staticmethod
    def _resolve(host: str) -> list[str]:
        return list(
            {
                item[4][0]
                for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        )

    def _access_token(self) -> str:
        with self._token_lock:
            if self._token and self._token[1] > time.monotonic() + 60:
                return self._token[0]
            body = urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }
            ).encode()
            result = self._json_request(
                TOKEN_URL,
                body,
                authenticated=False,
                content_type="application/x-www-form-urlencoded",
            )
            token = str(result.get("access_token", ""))
            if not token:
                raise CiscoDownloadError(
                    "Cisco authentication did not return an access token"
                )
            try:
                lifetime = max(120, int(result.get("expires_in", 3600)))
            except (TypeError, ValueError):
                lifetime = 3600
            self._token = (token, time.monotonic() + lifetime)
            return token

    def _json_request(
        self,
        url: str,
        body: bytes,
        *,
        authenticated: bool = True,
        content_type: str = "application/json",
    ) -> dict:
        headers = {"Accept": "application/json", "Content-Type": content_type}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._access_token()}"
        # url is always one of the https Cisco API constants above.
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = response.read(2 * 1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise CiscoDownloadError("Cisco API request failed") from exc
        if len(data) > 2 * 1024 * 1024:
            raise CiscoDownloadError("Cisco API response is too large")
        try:
            value = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CiscoDownloadError("Cisco API returned an invalid response") from exc
        if not isinstance(value, dict):
            raise CiscoDownloadError("Cisco API returned an invalid response")
        return value

    @staticmethod
    def _exceptions(value: object) -> list[dict]:
        found: list[dict] = []
        if isinstance(value, dict):
            if "code" in value and "message" in value:
                found.append(value)
            for nested in value.values():
                found.extend(CiscoSoftwareClient._exceptions(nested))
        elif isinstance(value, list):
            for nested in value:
                found.extend(CiscoSoftwareClient._exceptions(nested))
        return found

    def _check_errors(self, response: dict) -> None:
        for item in self._exceptions(response):
            code = str(item.get("code", ""))
            if code in BLOCKED_CODES or code.startswith("CONTRACT_"):
                raise CiscoDownloadError(f"Cisco authorization failed: {code}")

    def search(self, pid: str, current_release: str, output_release: str) -> dict:
        payload = {
            "pid": pid,
            "currentReleaseVersion": current_release,
            "outputReleaseVersion": output_release,
            "pageIndex": 1,
            "perPage": 25,
        }
        response = self._json_request(METADATA_URL, json.dumps(payload).encode())
        self._check_errors(response)
        return response

    def request_download(
        self, pid: str, mdf_id: str, transaction_id: str, image_guids: list[str]
    ) -> dict:
        if not 1 <= len(image_guids) <= 5:
            raise CiscoDownloadError("Select between one and five Cisco images")
        payload = {
            "pid": pid,
            "mdfId": mdf_id,
            "metadataTransId": transaction_id,
            "imageGuids": image_guids,
        }
        response = self._json_request(DOWNLOAD_URL, json.dumps(payload).encode())
        self._check_errors(response)
        return response

    def accept_eula(self, file_names: list[str]) -> dict:
        payload = {"status": "Accepted", "fileNames": ",".join(file_names)}
        return self._json_request(EULA_URL, json.dumps(payload).encode())

    def accept_k9(
        self,
        file_name: str,
        *,
        commercial_or_civil: bool,
        not_government_or_military: bool,
    ) -> dict:
        if not commercial_or_civil or not not_government_or_military:
            raise CiscoDownloadError("Cisco K9 declarations must be confirmed")
        payload = {
            "status": "Accepted",
            "fileNames": file_name,
            "confirm": "CONFIRM_CHECKED",
            "busFunction": "COMM_OR_CIVIL",
            "govMilCountries": "GOV_OR_MIL_COUNTRIES_NO",
        }
        return self._json_request(K9_URL, json.dumps(payload).encode())

    def _validate_download_url(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise CiscoDownloadError("Cisco returned an unsafe download URL")
        if not any(
            host == suffix or host.endswith(f".{suffix}")
            for suffix in self.allowed_hosts
        ):
            raise CiscoDownloadError("Cisco returned an unapproved download host")
        try:
            addresses = self.resolver(host)
        except OSError as exc:
            raise CiscoDownloadError(
                "Cisco download host could not be resolved"
            ) from exc
        if not addresses or any(
            not ipaddress.ip_address(address).is_global for address in addresses
        ):
            raise CiscoDownloadError(
                "Cisco download host resolved to an unsafe address"
            )

    def download(
        self,
        url: str,
        destination: Path,
        *,
        expected_size: int,
        max_bytes: int,
        cloud_token: str = "",
        expected_md5: str = "",
        expected_sha512: str = "",
        progress: Callable[[int, int], None] | None = None,
    ) -> DownloadResult:
        if expected_size <= 0 or expected_size > max_bytes:
            raise CiscoDownloadError("Cisco file exceeds the configured size limit")
        token = self._access_token()
        if cloud_token:
            body = urllib.parse.urlencode(
                {"X-Authentication-Control": cloud_token}
            ).encode()
            method, headers = (
                "POST",
                {"Content-Type": "application/x-www-form-urlencoded"},
            )
        else:
            parsed = urllib.parse.urlsplit(url)
            query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            query.append(("access_token", token))
            url = urllib.parse.urlunsplit(
                parsed._replace(query=urllib.parse.urlencode(query))
            )
            body, method, headers = None, "GET", {}
        temporary = destination.with_name(f".{destination.name}.part")
        # A previous attempt that crashed mid-download (killed process, host
        # restart) can leave this file behind; only one Cisco download runs
        # at a time (see cisco_download_running()), so it is never a
        # concurrent writer to guard against - remove it before the
        # exclusive-create open below, or a stale leftover would fail this
        # attempt too, one retry too many.
        temporary.unlink(missing_ok=True)
        current = url
        digests = {name: hashlib.new(name) for name in ("sha256", "md5", "sha512")}
        written = 0
        try:
            for _ in range(6):
                self._validate_download_url(current)
                # Validated just above: https, allowlisted host, global IPs only.
                request = urllib.request.Request(  # noqa: S310
                    current, data=body, headers=headers, method=method
                )
                try:
                    response = self._opener.open(request, timeout=self.timeout)
                except urllib.error.HTTPError as exc:
                    if exc.code not in (301, 302, 303, 307, 308) or not exc.headers.get(
                        "Location"
                    ):
                        raise CiscoDownloadError("Cisco download failed") from exc
                    current = urllib.parse.urljoin(current, exc.headers["Location"])
                    if exc.code in (301, 302, 303):
                        body, method, headers = None, "GET", {}
                    continue
                except (urllib.error.URLError, TimeoutError) as exc:
                    raise CiscoDownloadError("Cisco download failed") from exc
                with response, temporary.open("xb") as output:
                    while chunk := response.read(1024 * 1024):
                        written += len(chunk)
                        if written > max_bytes or written > expected_size:
                            raise CiscoDownloadError(
                                "Cisco download exceeded its declared size"
                            )
                        output.write(chunk)
                        for digest in digests.values():
                            digest.update(chunk)
                        if progress:
                            progress(written, expected_size)
                break
            else:
                raise CiscoDownloadError("Cisco download redirected too many times")
            if written != expected_size:
                raise CiscoDownloadError(
                    "Cisco download size did not match its metadata"
                )
            if (
                expected_md5
                and digests["md5"].hexdigest().lower() != expected_md5.lower()
            ):
                raise CiscoDownloadError("Cisco MD5 checksum did not match")
            if (
                expected_sha512
                and digests["sha512"].hexdigest().lower() != expected_sha512.lower()
            ):
                raise CiscoDownloadError("Cisco SHA-512 checksum did not match")
            temporary.replace(destination)
            return DownloadResult(
                destination,
                written,
                *(digests[name].hexdigest() for name in ("sha256", "md5", "sha512")),
            )
        except CiscoDownloadError:
            temporary.unlink(missing_ok=True)
            raise
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            temporary.unlink(missing_ok=True)
            raise CiscoDownloadError("Cisco download was interrupted") from exc
