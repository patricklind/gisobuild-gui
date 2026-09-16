import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


def load_real_iso_runner():
    path = Path(__file__).parents[2] / "scripts/e2e_real_iso.py"
    spec = spec_from_file_location("e2e_real_iso", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildScriptTests(unittest.TestCase):
    def test_browser_prompts_use_the_in_app_dialog(self):
        web_root = Path(__file__).parents[1]
        script = (web_root / "static" / "app.js").read_text()
        template = (web_root / "templates" / "index.html").read_text()

        self.assertNotRegex(script, r"\b(?:alert|confirm)\s*\(")
        self.assertIn("showAppDialog", script)
        self.assertIn('id="app-dialog"', template)
        self.assertIn('aria-describedby="app-dialog-message"', template)

    def test_cisco_theme_is_loaded_last(self):
        web_root = Path(__file__).parents[1]
        template = (web_root / "templates" / "index.html").read_text()
        theme = (web_root / "static" / "cisco-theme.css").read_text()

        self.assertLess(template.index("compact.css"), template.index("cisco-theme.css"))
        self.assertIn("--navy: #0d2740", theme)
        self.assertIn("@media (prefers-reduced-motion: reduce)", theme)

    def test_cleanup_resets_failed_artifacts_in_the_ui(self):
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()
        cleanup_handler = script[script.index("$('#cleanup').onclick"):]
        self.assertIn("$('#artifacts').replaceChildren()", cleanup_handler)
        self.assertIn("result.cleared_artifacts", cleanup_handler)
        self.assertIn("currentJob = null", cleanup_handler)

    def test_archive_list_supports_filtering_by_filename(self):
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()
        template = (Path(__file__).parents[1] / "templates" / "index.html").read_text()
        self.assertIn('id="archive-filter"', template)
        load_archive = script[script.index("async function loadArchive()"):]
        self.assertIn("row.dataset.name=item.name.toLowerCase()", load_archive)
        self.assertIn("applyArchiveFilter()", load_archive)
        filter_fn = script[script.index("function applyArchiveFilter()"):]
        filter_fn = filter_fn[:filter_fn.index("\n}\n")]
        self.assertIn("row.dataset.name.includes(query)", filter_fn)

    def test_cisco_search_results_support_filtering_by_filename(self):
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()
        template = (Path(__file__).parents[1] / "templates" / "index.html").read_text()
        self.assertIn('id="cisco-results-filter"', template)
        # The filter must not live inside <form id="cisco-results-form">,
        # which has its own submit button ("Download selected files") -
        # pressing Enter while typing a filter would otherwise submit it.
        form_start = template.index('id="cisco-results-form"')
        filter_start = template.index('id="cisco-results-filter"')
        self.assertLess(filter_start, form_start)
        search_handler = script[script.index("$('#cisco-search-form').addEventListener"):]
        self.assertIn("label.dataset.name=image.name.toLowerCase()", search_handler)
        self.assertIn("applyCiscoResultsFilter()", search_handler)
        filter_fn = script[script.index("function applyCiscoResultsFilter()"):]
        filter_fn = filter_fn[:filter_fn.index("\n}\n")]
        self.assertIn("label.dataset.name.includes(query)", filter_fn)

    def test_system_status_pill_uses_the_deep_readiness_check(self):
        # /api/health only proves the Flask process is responding; it does
        # not check Docker, the mounted gisobuild checkout, storage, the job
        # database or disk space the way /api/ready (and the container's own
        # HEALTHCHECK) does. Showing "System ready" from the weaker check
        # would be a false all-clear on a deployment that can never actually
        # complete a build.
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()
        health_fn = script[script.index("async function health()"):]
        health_fn = health_fn[:health_fn.index("\n}\n")]
        self.assertIn("fetch('/api/ready')", health_fn)
        self.assertNotIn("api('/api/health')", health_fn)
        self.assertNotIn("api('/api/ready')", health_fn)
        for check in ("docker", "tool", "storage", "database", "disk"):
            self.assertIn(f"{check}:", script[:script.index("async function health()")])

    def test_manual_package_mode_renders_uploaded_rpms_as_choices(self):
        # renderManualPackages()/selectedManualPackages()/syncManualPackageValue()
        # used to be defined in app.js too, with an older implementation that
        # used box.value = file.path (a raw workspace path). manual-packages.js
        # (loaded after app.js) always overwrote those globals before they
        # were ever called, so that copy was dead code - but this test used to
        # assert on literal source substrings that only existed in the dead
        # copy, meaning it verified nothing about what actually runs. The dead
        # code has been removed from app.js; this now checks the real,
        # executing implementation in manual-packages.js.
        web_root = Path(__file__).parents[1]
        app_script = (web_root / "static" / "app.js").read_text()
        manual_script = (web_root / "static" / "manual-packages.js").read_text()
        template = (web_root / "templates" / "index.html").read_text()

        self.assertIn('id="manual-package-list"', template)
        self.assertIn("files.filter(file => file.type === '.rpm')", manual_script)
        self.assertIn("box.type = 'checkbox';", manual_script)
        self.assertIn("box.value = file.id;", manual_script)
        self.assertIn("syncManualPackageValue", app_script)
        self.assertIn("window.syncManualPackageValue", manual_script)
        self.assertNotIn("function renderManualPackages", app_script)
        self.assertNotIn('name="pkglist_override" rows=', template)

    def test_start_build_button_names_exactly_what_is_missing(self):
        # Previously the disabled hint always said "Waiting for an ISO and a
        # customization", even once one of those two was already satisfied -
        # an operator who had already uploaded an ISO and just needed to add
        # a package was wrongly told the ISO was still missing too.
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()
        fn = script[script.index("function updateBuildAvailability()"):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn("Waiting for an ISO and a customization", fn)
        self.assertIn("Waiting for an ISO…", fn)
        self.assertIn("Waiting for a customization", fn)

    def test_manual_package_list_supports_compatible_and_selected_only_toggles(self):
        web_root = Path(__file__).parents[1]
        manual_script = (web_root / "static" / "manual-packages.js").read_text()
        template = (web_root / "templates" / "index.html").read_text()

        self.assertIn('id="manual-package-compatible-only"', template)
        self.assertIn('id="manual-package-selected-only"', template)
        filter_fn = manual_script[manual_script.index("function applyManualPackageFilter()"):]
        filter_fn = filter_fn[:filter_fn.index("\n  }\n")]
        self.assertIn("compatibleOnly", filter_fn)
        self.assertIn("option.classList.contains('incompatible')", filter_fn)
        self.assertIn("selectedOnly", filter_fn)
        self.assertIn(".manual-rpm-checkbox').checked", filter_fn)
        self.assertIn("applyManualPackageFilter()", manual_script[manual_script.index("window.syncManualPackageValue"):])

    def test_lnt_only_defaults_do_not_block_exr_builds(self):
        # verbose_dep_check defaults to checked in the template (gisobuild's
        # dependency check always runs regardless of this flag - it only
        # controls whether that check's own output is verbose - so there is
        # no reason to make an operator opt in to more diagnostic detail).
        # The safety property this test actually guards is that
        # updatePlatformControls() forces it back to unchecked, along with
        # every other LNT-only control, whenever the detected/selected
        # platform is not LNT - never the HTML default itself.
        web_root = Path(__file__).parents[1]
        template = (web_root / "templates" / "index.html").read_text()
        script = (web_root / "static" / "app.js").read_text()

        self.assertIn('id="lnt-controls"', template)
        self.assertIn('name="verbose_dep_check" checked', template)
        self.assertIn("profile.architecture !== 'lnt'", script)
        reset_for_unsupported = script[script.index("Object.entries(capabilityNames)"):]
        self.assertIn("control.checked=false", reset_for_unsupported)
        self.assertIn("verbose_dep_check:'verbose_dependency_check'", script)

    def test_expert_controls_follow_server_capabilities(self):
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()

        self.assertIn("profile.capabilities?.[capability]", script)
        self.assertIn("wrapper.hidden=!supported", script)
        self.assertIn("control.disabled=!supported", script)
        self.assertIn("profile.capabilities?.usb_image", script)

    def test_multiple_isos_block_automatic_selection_and_release_is_refreshed(self):
        script = (Path(__file__).parents[1] / "static" / "app.js").read_text()

        self.assertIn("isoFiles.length === 1", script)
        self.assertIn("Select one base ISO in Expert settings", script)
        self.assertIn("updateAutomaticTargetRelease", script)
        self.assertIn("targetReleaseIsAutomatic=false", script)

    def test_clean_rejects_traversal_outside_standard_output(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("Bash is not installed in the minimal runtime image")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            script = root / "build-giso.sh"
            shutil.copy2(Path(__file__).parents[2] / "build-giso.sh", script)
            iso = root / "base.iso"
            iso.write_bytes(b"iso")
            (root / "output_gisobuild_safe").mkdir()
            victim = root.parent / f"{root.name}-victim"
            victim.mkdir()
            (victim / "keep.txt").write_text("keep")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            docker = bin_dir / "docker"
            docker.write_text("#!/bin/sh\nexit 0\n")
            docker.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            try:
                result = subprocess.run(
                    [bash, str(script), "--iso", str(iso), "--output",
                     f"output_gisobuild_safe/../../{victim.name}", "--clean"],
                    capture_output=True, text=True, env=environment, check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Refusing to clean", result.stderr)
                self.assertTrue((victim / "keep.txt").exists())
            finally:
                shutil.rmtree(victim, ignore_errors=True)

    def test_build_container_does_not_mount_entire_project(self):
        script = (Path(__file__).parents[2] / "build-giso.sh").read_text()
        self.assertNotIn('-v "$SCRIPT_DIR:/workspace"', script)

    def test_build_script_uses_unique_staging_and_rejects_option_like_images(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("Bash is not installed in the minimal runtime image")
        script = (Path(__file__).parents[2] / "build-giso.sh").read_text()
        self.assertIn("mktemp -d", script)
        result = subprocess.run(
            [bash, str(Path(__file__).parents[2] / "build-giso.sh"),
             "--iso", "missing.iso", "--image", "--privileged"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Docker image must not start with a dash", result.stderr)

    def test_real_iso_upload_uses_server_assigned_path(self):
        runner = load_real_iso_runner()
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "base image.iso"
            source.write_bytes(b"iso")
            responses = [{"id": "abc"}, {"received": 3}, {"path": "base image-a1b2.iso"}]
            with patch.object(runner, "request", side_effect=responses) as call:
                uploaded = runner.upload_path("http://127.0.0.1:8080", source)
        self.assertEqual(uploaded, "base image-a1b2.iso")
        self.assertIn("/api/uploads/abc/complete", call.call_args_list[-1].args[0])

    def test_real_iso_runner_url_encodes_archive_names(self):
        script = (Path(__file__).parents[2] / "scripts/e2e_real_iso.py").read_text()
        self.assertIn('quote(item["name"], safe="")', script)

    def test_real_iso_runner_rejects_non_local_url(self):
        with tempfile.TemporaryDirectory() as temp_name:
            iso = Path(temp_name) / "base.iso"
            iso.write_bytes(b"synthetic test marker")
            script = Path(__file__).parents[2] / "scripts/e2e_real_iso.py"
            result = subprocess.run(
                [sys.executable, str(script), str(iso), "--platform", "ncs5500",
                 "--url", "file:///tmp/fake-api"],
                capture_output=True, text=True, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP(S) origin", result.stderr)


if __name__ == "__main__":
    unittest.main()
