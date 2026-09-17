"""Real-browser tests of the operator UI, driven by Playwright/Chromium.

Run only inside docker/browser-tests.Dockerfile (see docs/testing.md). The
Flask app runs in-process against temporary directories with synthetic
placeholder files - no Cisco content, no Docker, no gisobuild. Only the
parts that need a real host (Docker, gisobuild, free disk space) are
patched; every selection, validation and BuildPlan decision is the real
backend code, and every assertion is on what the page actually renders.
"""

import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ALLOWED_HOSTS", "127.0.0.1,localhost")

import app as module
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

TIMEOUT_MS = 10000


class OperatorFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        for name in ("uploads", "work", "output", "archive", "state"):
            (root / name).mkdir()
        module.DATA = (root / "uploads").resolve()
        module.WORK = (root / "work").resolve()
        module.OUTPUT = (root / "output").resolve()
        module.ARCHIVE = (root / "archive").resolve()
        module.STATE = (root / "state").resolve()
        module.JOB_DB = module.STATE / "jobs.sqlite3"
        module.store_initialized = False
        cls.patches = [
            patch("app.docker_build_running", return_value=False),
            patch("app.build_environment_blockers", side_effect=lambda: ([], [])),
            patch("app.is_iso9660_image", return_value=True),
            patch("app.shutil.disk_usage", return_value=SimpleNamespace(
                free=500 * 1024**3, total=1000 * 1024**3, used=500 * 1024**3)),
        ]
        for active in cls.patches:
            active.start()
        cls.server = make_server("127.0.0.1", 0, module.app, threaded=True)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        for active in cls.patches:
            active.stop()
        cls.temp.cleanup()

    def setUp(self):
        for child in module.DATA.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        module.uploads.clear()
        module.jobs.clear()
        module.rpm_metadata_cache.clear()
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(TIMEOUT_MS)
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.console_errors.append(str(error)))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.console_errors, [], "the page raised JavaScript errors")

    # -- helpers ---------------------------------------------------------

    def write(self, relative, content=None):
        path = module.DATA / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if content is not None else relative.encode())
        return path

    def open(self):
        self.page.goto(self.base_url)
        self.page.wait_for_function("() => renderedInventoryRevision !== null")

    def open_expert(self, group_summary):
        self.page.locator("details.advanced > summary").click()
        self.page.locator("details.expert-group > summary", has_text=group_summary).click()

    def use_manual_mode(self):
        self.open_expert("2. SMU compatibility")
        self.page.locator("[name=package_selection_mode][value=manual]").check()
        expect(self.page.locator("#manual-package-override")).to_be_visible()

    def rpm_box(self, name):
        option = self.page.locator(".manual-package-option", has=self.page.locator("b", has_text=name))
        return option.locator(".manual-rpm-checkbox")

    ISO = "asr9k-x64-7.3.2.iso"
    ROUTING = "asr9k-x64-routing-1.0.0.1-r732.CSCtest00001.x86_64.rpm"
    BGP = "asr9k-x64-bgp-1.0.0.1-r732.CSCtest00001.x86_64.rpm"
    OSPF = "asr9k-x64-ospf-1.0.0.1-r732.CSCtest00002.x86_64.rpm"
    OTHER_RELEASE = "asr9k-x64-isis-1.0.0.1-r733.CSCtest00003.x86_64.rpm"

    # -- scenarios -------------------------------------------------------

    def test_automatic_selection(self):
        for name in (self.ISO, self.ROUTING, self.BGP, self.OTHER_RELEASE):
            self.write(name)
        self.open()
        expect(self.page.locator("#smu-plan-state")).to_have_text("Calculated")
        expect(self.page.locator("#smu-auto-plan-title")).to_have_text("2 matching RPMs selected")
        expect(self.page.locator("#rpm-check p")).to_have_text("2 compatible RPMs selected · 1 excluded")
        # The summary counts by the backend status codes, and every row carries
        # its own status so a large package set can be read at a glance.
        excluded = self.page.locator("#smu-plan-details details summary",
                                     has_text="excluded automatically")
        expect(excluded).to_have_text("1 RPM excluded automatically (1 wrong release)")
        excluded.click()
        expect(self.page.locator(".excluded-package")).to_have_text(
            f"wrong release{self.OTHER_RELEASE} — Different IOS XR release")
        self.assertEqual(self.page.locator(".excluded-package").get_attribute("data-status"),
                         "WRONG_RELEASE")
        self.assertEqual(self.page.input_value("[name=pkglist]").splitlines(),
                         sorted([self.BGP, self.ROUTING]))

    def test_unsatisfiable_fix_is_left_out_and_names_the_smu_to_download(self):
        for name in (self.ISO, self.ROUTING, self.BGP, self.OSPF):
            self.write(name)
        # RPM headers need the rpm binary, which this image does not carry; the
        # dependency facts are unit-tested, this checks what the operator sees.
        missing = [{"requirement": "asr9k-x64-dpa = 1.0.0.5", "required_by": [self.ROUTING],
                    "base_image_has": "1.0.0.0", "prerequisite_smu": "asr9k-x64-7.3.2.CSCtest00099",
                    "listed_by": "asr9k-x64-7.3.2.CSCtest00001"}]

        def unsatisfied(_iso, names):
            return missing if self.ROUTING in names else []

        with patch("app.unsatisfied_dependencies_for_recommendation", side_effect=unsatisfied):
            self.open()
        expect(self.page.locator("#smu-plan-state")).to_have_text("Calculated")
        expect(self.page.locator("#smu-auto-plan-title")).to_have_text("1 matching RPM selected")
        expect(self.page.locator("#smu-plan-message")).to_contain_text(
            "2 left out because their dependencies cannot be satisfied "
            "(download asr9k-x64-7.3.2.CSCtest00099 to include them)")
        self.page.locator("#smu-plan-details details summary", has_text="excluded automatically").click()
        excluded = self.page.locator(".excluded-package")
        expect(excluded.filter(has_text=self.ROUTING)).to_contain_text(
            "download Cisco SMU asr9k-x64-7.3.2.CSCtest00099")
        expect(excluded.filter(has_text=self.BGP)).to_contain_text(
            "Part of CSCTEST00001, left out because another RPM of the same fix cannot be installed")
        expect(self.page.locator("#start-build")).to_be_enabled()
        # A Cisco search that returns the missing SMU pre-selects and labels it.
        self.page.route("**/api/cisco/search", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps({"id": "s1", "images": [
                {"guid": "G1", "name": "asr9k-x64-7.3.2.CSCtest00099.tar", "release": "7.3.2", "size": 1048576},
                {"guid": "G2", "name": "asr9k-x64-7.3.2.CSCtest00100.tar", "release": "7.3.2", "size": 1048576}]})))
        self.page.evaluate("""() => { document.querySelector('#cisco-download').hidden = false;
                                     document.querySelector('#cisco-download').open = true; }""")
        form = self.page.locator("#cisco-search-form")
        form.locator("[name=pid]").fill("ASR-9901")
        form.locator("[name=current_release]").fill("7.3.2")
        form.locator("[name=target_release]").fill("7.3.2")
        form.locator("button[type=submit]").click()
        needed = self.page.locator("#cisco-results label.needed-by-plan")
        expect(needed).to_have_count(1)
        expect(needed).to_contain_text("CSCtest00099.tar · 7.3.2 · 1.0 MB · needed by the current package plan")
        expect(needed.locator("input")).to_be_checked()
        expect(self.page.locator("#cisco-results input[value=G2]")).not_to_be_checked()
        callout = self.page.locator(".left-out-fixes")
        expect(callout).to_contain_text("2 RPMs left out: a required package is missing")
        expect(callout).to_contain_text("Download asr9k-x64-7.3.2.CSCtest00099 from Cisco and upload it")

    def test_build_report_shows_a_cached_builder_fallback(self):
        self.write(self.ISO)
        module.jobs["done"] = {
            "id": "done", "status": "success", "created": 1, "updated": 2, "finished": 2,
            "progress": 100, "phase": "Complete", "log": "", "artifacts": [],
            "stages": [{"stage": "preflight", "started": 100, "ended": 100.4},
                       {"stage": "preparing_builder", "started": 100.4, "ended": 102},
                       {"stage": "building", "started": 102, "ended": 327},
                       {"stage": "verifying", "started": 327, "ended": 327.2},
                       {"stage": "archiving", "started": 327.2, "ended": 339},
                       {"stage": "complete", "started": 339, "ended": 339}],
            "builder_image": {"reference": "ciscogisobuild/cisco-xr-gisobuild:2.3.4",
                              "id": "sha256:" + "be" * 32, "source": "cache"},
            "build_plan": {"iso": {"relative_path": self.ISO, "sha256": "0" * 64},
                           "platform": "asr9k", "engine": "exr", "release": "7.3.2",
                           "selected_packages": [], "inventory_revision": "rev",
                           "fingerprint": "f" * 64},
        }
        self.open()
        report = self.page.locator("#build-report")
        expect(report).to_be_visible()
        report.locator("summary").first.click()
        expect(report).to_contain_text(
            "Builder ciscogisobuild/cisco-xr-gisobuild:2.3.4 · cached copy on this host "
            "(registry unreachable) · sha256:bebebebebebe")
        expect(report).to_contain_text(
            "Time per step: Preflight 0.4s · Builder 1.6s · gisobuild 3m 45s · Verify 0.2s · Archive 11.8s")

    def test_failed_build_says_what_went_wrong_and_what_to_do(self):
        module.jobs["broken"] = {
            "id": "broken", "status": "failed", "created": 1, "updated": 2, "finished": 2,
            "progress": 40, "phase": "Build failed", "exit_code": 1, "artifacts": [],
            "log": "error: Failed dependencies:\n\tncs5500-dpa = 1.0.0.5 is needed by "
                   "ncs5500-routing-1.0.0.2-r2512.CSCtest00001.x86_64\n",
        }
        self.open()
        status = self.page.locator("#friendly-status")
        expect(status).to_contain_text("A selected package needs a package version that nothing provides.")
        expect(status).to_contain_text("Download the Cisco SMU named in the message")

    def test_blocked_start_names_the_problem_and_the_fix(self):
        self.write(self.ISO)
        self.write(self.ROUTING)
        self.open()
        # The workspace changes after review: the ISO disappears before Start.
        (module.DATA / self.ISO).unlink()
        self.page.locator("#start-build").click()
        expect(self.page.locator("#error")).to_contain_text(
            "A selected input is not in the workspace. Check files again and reselect the base ISO")

    def test_readiness_badge_names_a_failing_self_test_check(self):
        self.write(self.ISO)
        ready = {"ok": False, "docker": True, "tool": True, "storage": True, "database": True,
                 "disk": True, "self_test": {
                     "database_schema": {"ok": False, "required": True,
                                         "detail": "schema version 3, expected 2"},
                     "isoinfo": {"ok": False, "required": False, "detail": "isoinfo missing"}}}
        self.page.route("**/api/ready", lambda route: route.fulfill(
            status=503, content_type="application/json", body=json.dumps(ready)))
        self.open()
        expect(self.page.locator("#health")).to_have_text(
            "⚠ the job database schema is not usable (schema version 3, expected 2)")

    def test_manual_csc_selection(self):
        for name in (self.ISO, self.ROUTING, self.BGP, self.OSPF):
            self.write(name)
        self.open()
        self.use_manual_mode()
        group = self.page.locator(".manual-csc-checkbox[data-csc=CSCtest00001 i]")
        summary = self.page.locator("#manual-package-summary")
        expect(summary).to_have_text("3 of 3 RPM packages selected.")
        group.uncheck()
        expect(self.rpm_box(self.ROUTING)).not_to_be_checked()
        expect(self.rpm_box(self.BGP)).not_to_be_checked()
        expect(summary).to_have_text("1 of 3 RPM packages selected.")
        # One member back on its own leaves the group visibly partial.
        self.rpm_box(self.BGP).check()
        self.assertTrue(group.evaluate("box => box.indeterminate"))
        group.check()
        expect(summary).to_have_text("3 of 3 RPM packages selected.")

    def test_upload_while_manual_mode_is_open_keeps_the_manual_selection(self):
        for name in (self.ISO, self.ROUTING, self.BGP):
            self.write(name)
        self.open()
        self.use_manual_mode()
        self.rpm_box(self.ROUTING).uncheck()
        expect(self.page.locator("#manual-package-summary")).to_have_text("1 of 2 RPM packages selected.")
        self.page.set_input_files("#file-upload", files=[{
            "name": self.OSPF, "mimeType": "application/x-rpm", "buffer": b"ospf"}])
        expect(self.page.locator(".upload-row.done")).to_have_count(1)
        expect(self.rpm_box(self.OSPF)).to_have_count(1)
        # The operator's explicit choice survives the refresh the upload causes.
        expect(self.page.locator("[name=package_selection_mode][value=manual]")).to_be_checked()
        expect(self.rpm_box(self.ROUTING)).not_to_be_checked()
        expect(self.rpm_box(self.BGP)).to_be_checked()

    def test_upload_retries_a_dropped_chunk_and_finishes(self):
        self.open()
        puts = []

        def flaky(route):
            puts.append(route.request.url)
            if len(puts) == 1:
                route.abort("connectionreset")  # the network drops the first chunk
            else:
                route.continue_()

        self.page.route("**/api/uploads/*?offset=*", flaky)
        self.page.set_input_files("#file-upload", files=[{
            "name": "router.cfg", "mimeType": "text/plain", "buffer": b"hostname r1\n"}])
        expect(self.page.locator(".upload-row.done")).to_have_count(1, timeout=15000)
        self.assertGreaterEqual(len(puts), 2)
        self.assertEqual((module.DATA / "router.cfg").read_bytes(), b"hostname r1\n")

    def test_selecting_the_same_file_again_resumes_where_the_server_stopped(self):
        self.open()
        started = self.page.evaluate("""async () => {
          const init = await fetch('/api/uploads/init', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: 'resume.cfg', size: 8})});
          const {id} = await init.json();
          await fetch(`/api/uploads/${id}?offset=0`, {method: 'PUT', body: 'host'});
          return id;
        }""")
        offsets = []
        self.page.route("**/api/uploads/*?offset=*",
                        lambda route: (offsets.append(route.request.url.split("offset=")[1]), route.continue_()))
        # Same name, size and modification time as the interrupted upload.
        self.page.evaluate("""async id => {
          const file = new File(['hostname'], 'resume.cfg', {lastModified: 1000});
          localStorage.setItem('giso-upload:resume.cfg:8:1000', id);
          await uploadFiles([file]);
        }""", started)
        expect(self.page.locator(".upload-row.done")).to_have_count(1)
        self.assertEqual(offsets, ["4"])  # only the missing half was sent
        self.assertEqual((module.DATA / "resume.cfg").read_bytes(), b"hostname")
        self.assertIsNone(self.page.evaluate("() => localStorage.getItem('giso-upload:resume.cfg:8:1000')"))

    def test_manual_to_automatic(self):
        for name in (self.ISO, self.ROUTING, self.BGP, self.OSPF):
            self.write(name)
        self.open()
        self.use_manual_mode()
        self.rpm_box(self.OSPF).uncheck()
        self.assertEqual(len(self.page.input_value("[name=pkglist_override]").splitlines()), 2)
        self.page.locator("#use-automatic-packages").click()
        expect(self.page.locator("[name=package_selection_mode][value=automatic]")).to_be_checked()
        expect(self.page.locator("#manual-package-override")).to_be_hidden()
        self.assertEqual(self.page.input_value("[name=pkglist_override]"), "")
        expect(self.page.locator("#smu-auto-plan-title")).to_have_text("3 matching RPMs selected")
        self.assertEqual(len(self.page.input_value("[name=pkglist]").splitlines()), 3)

    def test_inventory_refresh(self):
        self.write(self.ISO)
        self.open()
        expect(self.page.locator("#rpm-check p")).not_to_have_text("1 compatible RPM selected")
        self.write(self.ROUTING)  # arrives without this page doing anything
        self.page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
        expect(self.page.locator("#rpm-check p")).to_have_text("1 compatible RPM selected")

    def test_no_rpm_state(self):
        self.write(self.ISO)
        self.open()
        expect(self.page.locator("#iso-check p")).to_have_text("Found and ready")
        expect(self.page.locator("#start-build")).to_be_disabled()
        expect(self.page.locator("#start-build")).to_have_text(
            "Waiting for a customization (packages, config files, or bridging fixes)…")
        self.use_manual_mode()
        expect(self.page.locator(".manual-package-empty p")).to_contain_text(
            "No RPM files are available in the workspace")

    def test_failed_compatibility(self):
        # Two different versions of the same component in one fix: automatic
        # selection picks both, and the backend check must block them.
        self.write(self.ISO)
        self.write("asr9k-x64-routing-1.0.0.1-r732.CSCtest00001.x86_64.rpm")
        self.write("asr9k-x64-routing-1.0.0.2-r732.CSCtest00001.x86_64.rpm")
        self.open()
        expect(self.page.locator("#smu-plan-state")).to_have_text("Blocked")
        self.open_expert("2. SMU compatibility")
        self.page.locator("#check-compatibility").click()
        result = self.page.locator("#compatibility-result")
        expect(result).to_have_class("compatibility-result bad")
        expect(result.locator(".compatibility-summary")).to_contain_text("Blocked")

    def test_successful_preflight(self):
        for name in (self.ISO, self.ROUTING, self.BGP):
            self.write(name)
        self.open()
        expect(self.page.locator("#start-build")).to_be_enabled()
        self.page.locator("#start-build").click()
        dialog = self.page.locator("#app-dialog")
        expect(dialog).to_be_visible()
        expect(self.page.locator("#app-dialog-title")).to_have_text("Start Golden ISO build?")
        expect(self.page.locator("#app-dialog-message")).to_contain_text(
            "Start the verified plan with 2 updates?")
        expect(self.page.locator("#app-dialog-message")).to_contain_text("Platform: ASR9K")
        # Stop here: confirming would start a real build container.
        self.page.locator("#app-dialog-cancel").click()
        expect(dialog).to_be_hidden()
        self.assertEqual(module.jobs, {})

    def test_build_button_enable_disable(self):
        button = self.page.locator("#start-build")
        self.open()
        expect(button).to_be_disabled()
        expect(button).to_have_text("Waiting for an ISO and a customization…")
        self.write(self.ROUTING)
        self.page.locator("#refresh").click()
        expect(button).to_have_text("Waiting for an ISO…")
        self.write(self.ISO)
        self.page.locator("#refresh").click()
        expect(button).to_be_enabled()
        expect(button).to_have_text("Start build")

    def test_unknown_platform_presentation(self):
        self.write("customer-golden-base.iso")
        self.write(self.ROUTING)
        self.open()
        expect(self.page.locator("#smu-plan-state")).to_have_text("Needs input")
        expect(self.page.locator("#smu-auto-plan-title")).to_have_text("Automatic selection paused")
        expect(self.page.locator("#smu-plan-message")).to_have_text(
            "The ISO platform could not be detected; select it in Expert settings")
        expect(self.page.locator("#lnt-controls-help")).to_have_text(
            "Select a platform or base ISO to determine whether these controls apply.")

    def test_multiple_iso_ambiguity_blocks_build(self):
        self.write(self.ISO)
        self.write("asr9k-x64-7.3.3.iso")
        self.write(self.ROUTING)
        self.open()
        expect(self.page.locator("#iso-check p")).to_have_text("Select one base ISO in Expert settings")
        expect(self.page.locator("#start-build")).to_be_disabled()
        expect(self.page.locator("#start-build")).to_have_text("Waiting for an ISO…")

    def test_duplicate_rpm_basename_conflict_is_visible(self):
        self.write(self.ISO)
        self.write(f"one/{self.ROUTING}", b"first")
        self.write(f"two/{self.ROUTING}", b"second")
        self.open()
        self.use_manual_mode()
        options = self.page.locator(".manual-package-option", has=self.page.locator("b", has_text=self.ROUTING))
        expect(options).to_have_count(2)
        for index in range(2):
            expect(options.nth(index)).to_have_class("manual-package-option incompatible")
            expect(options.nth(index).locator("input")).to_be_disabled()
            expect(options.nth(index).locator("small")).to_contain_text(
                "another RPM has the same filename but different content")
        digests = sorted(hashlib.sha256(content).hexdigest()[:12] for content in (b"first", b"second"))
        shown = options.locator("small").all_inner_texts()
        for digest in digests:
            self.assertTrue(any(digest in text for text in shown), shown)

    def test_iso_switch_refreshes_auto_derived_release(self):
        self.write(self.ISO)
        self.write("asr9k-x64-7.3.3.iso")
        self.open()
        self.open_expert("1. Image identity")
        self.page.locator("details.expert-group > summary", has_text="2. SMU compatibility").click()
        target = self.page.locator("#upgrade-compatibility-fields [name=target_release]")
        iso_override = self.page.locator("[name=iso_override]")
        iso_override.fill(self.ISO)
        iso_override.dispatch_event("change")
        self.page.locator("[name=compatibility_mode][value=upgrade]").check()
        expect(target).to_have_value("7.3.2")
        iso_override.fill("asr9k-x64-7.3.3.iso")
        iso_override.dispatch_event("change")
        expect(target).to_have_value("7.3.3")
        # A release the operator typed is theirs; switching ISO must not overwrite it.
        target.fill("7.3.9")
        iso_override.fill(self.ISO)
        iso_override.dispatch_event("change")
        expect(target).to_have_value("7.3.9")


if __name__ == "__main__":
    unittest.main()
