"""Representative synthetic fixtures for every platform family, through the real BuildPlan.

Filenames follow Cisco's published naming - eXR `<platform>-mini-x-<release>.iso`
with `<platform>-<component>-<ver>-r<release tag>.CSC<id>.<arch>.rpm` SMUs, and
LNT `<platform>-x64-<release>.iso` with `<package>-<release>v<ver>-<rel>.<arch>.rpm`
as documented in upstream gisobuild's README. Contents are placeholders; no
Cisco artifact is used. Each case asserts what an operator relies on: the
platform and engine detected, the matching package selected, a foreign one
excluded with a reason, the platform's own capabilities and expected outputs.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as module

EXR = [
    # platform id, base ISO, release tag, special capability
    ("asr9k", "asr9k-mini-x64-7.11.2.iso", "7112", "migration"),
    ("ncs1k", "ncs1k-mini-x-7.3.2.iso", "732", None),
    ("ncs1001", "ncs1001-mini-x-7.3.2.iso", "732", None),
    ("ncs1004", "ncs1004-mini-x-7.3.2.iso", "732", None),
    ("ncs5k", "ncs5k-mini-x-7.3.2.iso", "732", None),
    ("ncs540", "ncs540-mini-x-7.11.2.iso", "7112", None),
    ("ncs5500", "ncs5500-mini-x-25.1.2.iso", "2512", None),
    ("ncs560", "ncs560-mini-x-7.11.2.iso", "7112", None),
    ("ncs6k", "ncs6k-mini-x-6.6.3.iso", "663", None),
    ("iosxrwb", "iosxrwb-mini-x-7.3.2.iso", "732", None),
    ("iosxrwbd", "iosxrwbd-mini-x-7.3.2.iso", "732", None),
    ("xrv9k", "xrv9k-fullk9-x-7.11.2.iso", "7112", "full_iso"),
]
# src/exrmod/usb_zip/platform_scripts.yaml at the pinned gisobuild commit.
UPSTREAM_EXR_USB = {
    "ncs5500",
    "ncs540",
    "ncs1004",
    "ncs1k",
    "asr9k",
    "ncs560",
    "iosxrwbd",
}

LNT = [
    ("8000", "8000-x64-24.3.1.iso"),
    ("ncs1010", "ncs1010-x64-24.3.1.iso"),
    ("ncs540l", "ncs540l-x64-24.3.1.iso"),
    ("ncs57", "ncs5700-x64-24.3.1.iso"),
]


class PlatformFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        for name in ("uploads", "output", "work", "archive", "state"):
            (root / name).mkdir()
        module.DATA = (root / "uploads").resolve()
        module.OUTPUT = (root / "output").resolve()
        module.WORK = (root / "work").resolve()
        module.ARCHIVE = (root / "archive").resolve()
        module.STATE = (root / "state").resolve()
        module.JOB_DB = module.STATE / "jobs.sqlite3"
        module.store_initialized = False
        module.uploads.clear()
        module.jobs.clear()
        self.patches = [
            patch("app.build_environment_blockers", side_effect=lambda: ([], [])),
            patch("app.is_iso9660_image", return_value=True),
            patch(
                "app.shutil.disk_usage",
                return_value=SimpleNamespace(free=100 * 1024**3),
            ),
        ]
        for active in self.patches:
            active.start()

    def tearDown(self):
        for active in reversed(self.patches):
            active.stop()
        module.store_initialized = False
        self.temp.cleanup()

    def workspace(self, *names):
        for child in module.DATA.iterdir():
            child.unlink()
        for name in names:
            (module.DATA / name).write_bytes(name.encode())

    def automatic_plan(self, iso, **extra):
        return module.create_build_plan(
            {"iso": iso, "automatic_smu_selection": True, "pkglist": [], **extra}
        )

    def test_every_exr_platform(self):
        for platform, iso, tag, special in EXR:
            with self.subTest(platform=platform):
                rpm = f"{platform}-routing-1.0.0.1-r{tag}.CSCtest00001.x86_64.rpm"
                foreign_platform = "ncs5500" if platform != "ncs5500" else "asr9k"
                foreign = (
                    f"{foreign_platform}-routing-1.0.0.1-r{tag}.CSCtest00002.x86_64.rpm"
                )
                self.workspace(iso, rpm, foreign)
                # eXR needs no "Skip USB image": upstream's engine builds a USB
                # zip only where the platform has a USB script.
                plan = self.automatic_plan(iso)

                self.assertTrue(plan["ready"], plan["blockers"])
                self.assertEqual(plan["platform"], platform)
                self.assertEqual(plan["engine"], "exr")
                self.assertEqual(
                    [item["basename"] for item in plan["selected_packages"]], [rpm]
                )
                excluded = {
                    item["name"]: item["reason"] for item in plan["excluded_packages"]
                }
                self.assertEqual(excluded[foreign], "Different platform")
                self.assertEqual(
                    plan["expected_outputs"]["usb"], module.PLATFORMS[platform]["usb"]
                )
                self.assertEqual(
                    module.PLATFORMS[platform]["usb"], platform in UPSTREAM_EXR_USB
                )
                self.assertFalse(plan["capabilities"]["skip_usb_image"])
                self.assertTrue(plan["capabilities"]["script"])
                self.assertFalse(plan["capabilities"]["only_support_pids"])
                if special:
                    self.assertTrue(plan["capabilities"][special])
                self.assertEqual(plan["confidence"]["platform"]["value"], "INFERRED")

    def test_every_lnt_platform(self):
        for platform, iso in LNT:
            with self.subTest(platform=platform):
                packages = [
                    "xr-cdp-24.3.1v1.0.0-1.x86_64.rpm",
                    "xr-cdp-8101-32h-24.3.1v1.0.0-1.x86_64.rpm",
                ]
                other_release = "xr-cdp-24.2.1v1.0.0-1.x86_64.rpm"
                self.workspace(iso, *packages, other_release)
                plan = self.automatic_plan(iso)

                self.assertTrue(plan["ready"], plan["blockers"])
                self.assertEqual(plan["platform"], platform)
                self.assertEqual(plan["engine"], "lnt")
                self.assertEqual(
                    sorted(item["basename"] for item in plan["selected_packages"]),
                    sorted(packages),
                )
                excluded = {
                    item["name"]: item["reason"] for item in plan["excluded_packages"]
                }
                self.assertEqual(excluded[other_release], "Different IOS XR release")
                self.assertTrue(plan["capabilities"]["only_support_pids"])
                self.assertTrue(plan["capabilities"]["remove_packages"])
                self.assertFalse(plan["capabilities"]["script"])
                self.assertEqual(plan["release"], "24.3.1")
                self.assertTrue(plan["capabilities"]["skip_usb_image"])
                skipped = self.automatic_plan(iso, skip_usb_image=True)
                self.assertFalse(skipped["expected_outputs"]["usb"])

    def test_lnt_packages_built_for_another_release_block_a_manual_selection(self):
        iso = "8000-x64-24.3.1.iso"
        wrong = "xr-bgp-24.2.1v1.0.0-1.x86_64.rpm"
        self.workspace(iso, wrong)
        plan = module.create_build_plan(
            {
                "iso": iso,
                "platform": "8000",
                "pkglist": [wrong],
                "automatic_smu_selection": False,
            }
        )
        self.assertFalse(plan["ready"])
        self.assertIn(f"{wrong}: built for IOS XR 24.2.1, not 24.3.1", plan["blockers"])

    def test_unknown_future_platform_pauses_automatic_selection_until_overridden(self):
        iso = "cisco9999-x64-26.1.1.iso"
        self.workspace(iso, "xr-cdp-26.1.1v1.0.0-1.x86_64.rpm")
        paused = self.automatic_plan(iso)
        self.assertFalse(paused["ready"])
        self.assertIn(
            "The ISO platform could not be detected; select it in Expert settings",
            paused["blockers"],
        )

        manual = module.create_build_plan(
            {
                "iso": iso,
                "platform": "lnt-generic",
                "automatic_smu_selection": False,
                "skip_usb_image": True,
                "pkglist": ["xr-cdp-26.1.1v1.0.0-1.x86_64.rpm"],
            }
        )
        self.assertTrue(manual["ready"], manual["blockers"])
        self.assertEqual(manual["engine"], "lnt")
        self.assertFalse(
            manual["expected_outputs"]["usb"]
        )  # unknown hardware: conservative
        self.assertEqual(manual["confidence"]["platform"]["value"], "MANUAL")


if __name__ == "__main__":
    unittest.main()
