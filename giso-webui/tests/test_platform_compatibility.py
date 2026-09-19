import ast
import os
import re
import unittest
from itertools import zip_longest
from pathlib import Path

from platform_validation import (
    GENERIC_PLATFORM_IDS,
    OPTION_CAPABILITIES,
    OPTION_LABELS,
    PLATFORMS,
    RUNNER_GATED_CAPABILITIES,
    capabilities_for_platform,
    check_upgrade_matrix,
    classify_exclusion,
    compare_exr_rpm_labels,
    describe_package,
    infer_platform,
    infer_platform_pid,
    normalize_platform,
    platform_profile,
    platforms_supporting,
    recommend_smu_selection,
    validate_platform_options,
    validate_smu_selection,
)


def upstream_gisobuild_file(test: unittest.TestCase, relative: str) -> Path:
    """A file from the pinned upstream gisobuild source, or skip the test.

    Looked up under TOOL_ROOT (the self-contained image bundles the pinned
    commit at /opt/gisobuild) and then the developer checkout
    `.gisobuild-tool`. Neither exists in a plain CI checkout, so CI runs these
    tests inside the self-contained image with REQUIRE_UPSTREAM_GISOBUILD=1,
    which turns a missing source into a failure instead of a skip.
    """
    roots = [os.environ.get("TOOL_ROOT"), Path(__file__).parents[2] / ".gisobuild-tool"]
    for root in filter(None, roots):
        candidate = Path(root) / relative
        if candidate.is_file():
            return candidate
    if os.environ.get("REQUIRE_UPSTREAM_GISOBUILD") == "1":
        test.fail(f"pinned gisobuild source not found: {relative}")
    test.skipTest("pinned gisobuild source is not available")
    raise AssertionError("unreachable")


class PackageStatusTests(unittest.TestCase):
    def test_every_reason_the_selection_engine_writes_maps_to_a_status(self):
        # The engine's own wording, not invented examples: if a reason is
        # reworded without updating PACKAGE_STATUSES, it must still be
        # classified, and MANUAL_REVIEW_REQUIRED is the only safe fallback.
        expected = {
            "Different platform": "WRONG_PLATFORM",
            "Different IOS XR release": "WRONG_RELEASE",
            "Processor architecture does not match the base ISO": "WRONG_ARCHITECTURE",
            "Platform is missing from filename": "UNKNOWN",
            "Release is missing from filename": "UNKNOWN",
            "More than one fix changes this component; Cisco supersedence decides which remains": "CONFLICT",
            "Superseded by a newer fix per Cisco supersedence notes": "SUPERSEDED",
            "Needs ncs5500-dpa-1.0.0.0-r2512.CSCwt13701 which nothing provides": "MISSING_DEPENDENCY",
            "MD5 does not match the Cisco README for ncs5500-25.1.2.CSCwu14807": "INVALID",
            "The service cannot read this file; fix its ownership": "INVALID",
        }
        for reason, status in expected.items():
            self.assertEqual(classify_exclusion(reason), status, reason)
        self.assertEqual(
            classify_exclusion("a reason nobody has written yet"),
            "MANUAL_REVIEW_REQUIRED",
        )
        self.assertEqual(classify_exclusion(""), "MANUAL_REVIEW_REQUIRED")

    def test_describe_package_reads_identity_from_both_naming_schemes(self):
        exr = describe_package("ncs5500-mpls-1.0.0.0-r2512.CSCwu14807.x86_64.rpm")
        self.assertEqual(
            exr,
            {
                "name": "ncs5500-mpls-1.0.0.0-r2512.CSCwu14807.x86_64.rpm",
                "platform": "ncs5500",
                "release": "r2512",
                "architecture": "x86_64",
                "csc": "CSCwu14807",
            },
        )
        lnt = describe_package("xr-cdp-24.3.1v1.0.0-1.x86_64.rpm")
        self.assertEqual(lnt["release"], "24.3.1")
        self.assertIsNone(lnt["csc"])
        unknown = describe_package("some-file.rpm")
        self.assertEqual(
            [unknown["platform"], unknown["release"], unknown["csc"]],
            [None, None, None],
        )


class PlatformCompatibilityTests(unittest.TestCase):
    def test_exr_usb_support_matches_the_pinned_upstream_usb_scripts(self):
        # Upstream's eXR engine builds a USB boot zip exactly for the platforms
        # listed in src/exrmod/usb_zip/platform_scripts.yaml; PLATFORMS' "usb"
        # flag drives the plan's expected outputs, so it must not drift. (ncs1001
        # once claimed USB support upstream never had.)
        scripts = upstream_gisobuild_file(
            self, "src/exrmod/usb_zip/platform_scripts.yaml"
        )
        upstream = {
            line.split(":", 1)[0].strip()
            for line in scripts.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#") and ":" in line
        }
        local = {
            key
            for key, profile in PLATFORMS.items()
            if profile["architecture"] == "exr"
            and profile["usb"]
            and key not in GENERIC_PLATFORM_IDS
        }
        self.assertEqual(local, upstream)

    def test_exr_platform_list_matches_the_pinned_upstream_engine(self):
        # PLATFORMS in platform_validation.py is a locally maintained copy of
        # the eXR platform whitelist upstream gisobuild actually enforces
        # (Giso.SUPPORTED_PLATFORMS in
        # .gisobuild-tool/src/exrmod/gisobuild_exr_engine.py, which matches
        # src/utils/gisoglobals.py's EXR_SUPPORTED_PLATFORMS). Nothing ties
        # the two together today - if a future pinned-commit bump changes
        # upstream's list, this local copy would silently drift out of sync
        # instead of failing loudly, either blocking a now-supported platform
        # or (less likely but possible) accepting one upstream no longer
        # does. See 01-PLATFORM-UPSTREAM-TODO.md "Stop using a locally
        # maintained list as the authoritative support list".
        engine_path = upstream_gisobuild_file(
            self, "src/exrmod/gisobuild_exr_engine.py"
        )
        source = engine_path.read_text()
        match = re.search(r"SUPPORTED_PLATFORMS\s*=\s*(\[[^\]]*\])", source)
        self.assertIsNotNone(
            match,
            "Could not find SUPPORTED_PLATFORMS in the pinned gisobuild engine - "
            "has upstream renamed or restructured this list?",
        )
        upstream_platforms = set(ast.literal_eval(match.group(1)))
        local_exr_platforms = {
            key
            for key, profile in PLATFORMS.items()
            if profile["architecture"] == "exr" and key not in GENERIC_PLATFORM_IDS
        }
        missing_locally = upstream_platforms - local_exr_platforms
        self.assertFalse(
            missing_locally,
            f"Upstream gisobuild supports {sorted(missing_locally)} but "
            "platform_validation.PLATFORMS does not - add it (see "
            "01-PLATFORM-UPSTREAM-TODO.md).",
        )
        extra_locally = local_exr_platforms - upstream_platforms
        self.assertFalse(
            extra_locally,
            f"platform_validation.PLATFORMS claims eXR support for "
            f"{sorted(extra_locally)}, which the pinned gisobuild engine's "
            "own SUPPORTED_PLATFORMS does not list - this would let an "
            "operator select a platform gisobuild itself will reject.",
        )

    def test_unknown_upstream_platform_can_still_be_built_via_manual_override(self):
        # An ISO/RPM set for a real platform gisobuild supports but this
        # local marketing map does not (yet) recognize by name must not
        # dead-end the operator - see 01-PLATFORM-UPSTREAM-TODO.md
        # "Unknown-but-valid platforms". infer_platform() correctly returns
        # None for such a filename (it must not guess), but the operator can
        # still explicitly select the generic eXR/LNT fallback in Expert
        # settings and get a valid, capability-correct profile to build with
        # (in Manual package list mode - automatic selection still correctly
        # requires a recognizable platform, since there is nothing to
        # deterministically match RPM filenames against otherwise).
        self.assertIsNone(infer_platform("some-brand-new-platform-mini-x-30.1.1.iso"))
        # The generic profile's usb capability is False (real support is
        # unknown), so validate_platform_options() correctly refuses to
        # proceed until the operator acknowledges that with skip_usb_image -
        # the same gate any other no-USB platform (e.g. ncs5k) goes through.
        profile = validate_platform_options(
            {
                "iso": "some-brand-new-platform-mini-x-30.1.1.iso",
                "platform": "exr-generic",
                "skip_usb_image": True,
            }
        )
        self.assertEqual(profile["architecture"], "exr")
        self.assertFalse(profile["capabilities"]["migration"])
        self.assertFalse(profile["capabilities"]["full_iso"])
        self.assertFalse(profile["usb"])
        lnt_profile = validate_platform_options(
            {
                "iso": "some-brand-new-platform-mini-x-30.1.1.iso",
                "platform": "lnt-generic",
                "skip_usb_image": True,
            }
        )
        self.assertEqual(lnt_profile["architecture"], "lnt")
        self.assertTrue(lnt_profile["capabilities"]["remove_packages"])

    def test_hardware_pid_is_reported_separately_from_the_marketing_family(self):
        # 01-PLATFORM-UPSTREAM-TODO.md's "The application must distinguish"
        # list asked for Physical PID / SKU as its own fact. ALIASES already
        # routed an exact SKU spelling to the right family, but the SKU
        # itself was discarded - an operator could not tell "we matched your
        # exact NCS-57C3-MOD-SYS" from "we guessed the NCS 5700 family".
        self.assertEqual(infer_platform("NCS-57C3-MOD-SYS-25.1.2.iso"), "ncs57")
        self.assertEqual(
            infer_platform_pid("NCS-57C3-MOD-SYS-25.1.2.iso"), "ncs-57c3-mod-sys"
        )
        # A filename that matches a canonical platform ID directly carries no
        # separate SKU spelling - the family name *is* what was in the name.
        self.assertEqual(infer_platform("ncs5500-mini-x-25.1.2.iso"), "ncs5500")
        self.assertIsNone(infer_platform_pid("ncs5500-mini-x-25.1.2.iso"))
        self.assertIsNone(infer_platform_pid("mystery-platform-30.1.1.iso"))

    def test_generic_platform_fallbacks_are_never_inferred_from_a_filename(self):
        # These two IDs exist only as an explicit manual escape hatch: a
        # filename containing the literal substring "exr-generic" or
        # "lnt-generic" is not a real Cisco naming pattern, but infer_platform()
        # must never resolve to them even in principle, since a *guessed*
        # generic platform is worthless - the whole point is that the
        # operator affirmatively said "I know this is an eXR/LNT image, I
        # just can't tell you its exact name."
        for generic_id in GENERIC_PLATFORM_IDS:
            self.assertIsNone(infer_platform(f"{generic_id}-mini-x-25.1.1.iso"))

    def test_capabilities_follow_upstream_exr_and_lnt_option_maps(self):
        exr = capabilities_for_platform("ncs5500")
        lnt = capabilities_for_platform("ncs57")
        self.assertTrue(exr["optimize"])
        self.assertFalse(exr["remove_packages"])
        self.assertFalse(exr["key_request"])
        self.assertTrue(lnt["remove_packages"])
        self.assertTrue(lnt["key_request"])
        self.assertFalse(lnt["optimize"])

    def test_platform_specific_capabilities_are_narrow(self):
        self.assertTrue(capabilities_for_platform("asr9k")["migration"])
        self.assertFalse(capabilities_for_platform("ncs5500")["migration"])
        self.assertTrue(capabilities_for_platform("xrv9k")["full_iso"])

    def test_adapter_rejects_capability_not_supported_by_engine(self):
        # The message names the option, the platform that cannot do it and
        # where upstream does offer it - never a hardcoded platform condition.
        with self.assertRaisesRegex(
            ValueError,
            r"Remove packages is not supported on NCS 5500 \(EXR build engine\); "
            r"upstream gisobuild offers it on .+",
        ):
            validate_platform_options(
                {
                    "iso": "ncs5500-mini-x-26.1.2.iso",
                    "remove_packages": ["optional-pkg"],
                }
            )

    def test_platform_only_options_are_decided_by_capabilities_not_platform_names(self):
        # migration/full_iso used to be two hardcoded platform comparisons.
        for option, owner, other in (
            ("migration", "asr9k", "ncs5500"),
            ("full_iso", "xrv9k", "asr9k"),
        ):
            self.assertEqual(
                platforms_supporting(option), [PLATFORMS[owner]["label"]], option
            )
            validate_platform_options({"platform": owner, option: True})
            with self.assertRaisesRegex(ValueError, "is not supported on"):
                validate_platform_options({"platform": other, option: True})
        # Every option the validator gates is a real capability of the engines.
        known = set(capabilities_for_platform("ncs5500")) | set(
            capabilities_for_platform("8000")
        )
        self.assertTrue(
            set(OPTION_CAPABILITIES.values()) <= known,
            set(OPTION_CAPABILITIES.values()) - known,
        )
        self.assertEqual(set(OPTION_CAPABILITIES) - set(OPTION_LABELS), set())

    def test_optimize_capable_false_hides_optimize_and_full_iso_everywhere(self):
        # The self-contained image's gisobuild build never registers
        # --optimize/--full-iso (confirmed against the real image - see
        # platform_validation.RUNNER_GATED_CAPABILITIES); a deployment that
        # knows this must not offer either capability on any platform,
        # including ones that would otherwise have it.
        self.assertEqual(RUNNER_GATED_CAPABILITIES, {"optimize", "full_iso"})
        exr = capabilities_for_platform("ncs5500", optimize_capable=False)
        xrv9k = capabilities_for_platform("xrv9k", optimize_capable=False)
        self.assertFalse(exr["optimize"])
        self.assertFalse(xrv9k["full_iso"])
        # Unrelated capabilities on the same platforms are unaffected.
        self.assertTrue(exr["script"])
        self.assertTrue(xrv9k["x86_only"])
        # The default keeps today's (unverified-but-assumed) socket behavior.
        self.assertTrue(capabilities_for_platform("ncs5500")["optimize"])
        profile = platform_profile("xrv9k", optimize_capable=False)
        self.assertFalse(profile["capabilities"]["full_iso"])

    def test_optimize_capable_false_gives_an_engine_reason_not_a_platform_reason(self):
        # ncs5500 would normally support --optimize; when the deployment's
        # own gisobuild build cannot register it at all, the rejection must
        # say so, not claim the platform itself does not support it (which
        # would be false and would send an operator looking in the wrong
        # place).
        with self.assertRaisesRegex(
            ValueError,
            r"Optimized ISO needs gisobuild's optional eXR extension, which this "
            r"deployment's bundled gisobuild build does not include",
        ):
            validate_platform_options(
                {"platform": "ncs5500", "optimize": True}, optimize_capable=False
            )
        with self.assertRaisesRegex(
            ValueError,
            r"Full ISO needs gisobuild's optional eXR extension",
        ):
            validate_platform_options(
                {"platform": "xrv9k", "full_iso": True}, optimize_capable=False
            )
        # A platform that never had the capability, regardless of engine
        # build, still gets the ordinary platform-mismatch message.
        with self.assertRaisesRegex(ValueError, "is not supported on"):
            validate_platform_options(
                {"platform": "ncs5k", "full_iso": True}, optimize_capable=False
            )

    def test_adapter_rejects_exr_only_capability_on_lnt_platform(self):
        # The mirror image of the test above: remove_packages is LNT-only
        # and rejected on an eXR platform, but nothing checked the other
        # direction - an eXR-only capability (optimize) offered on an LNT
        # platform (Cisco 8000).
        with self.assertRaisesRegex(
            ValueError,
            r"Optimized ISO is not supported on Cisco 8000 / 8800 \(LNT build engine\)",
        ):
            validate_platform_options({"platform": "8000", "optimize": True})

    def test_ncs57c3_inventory_sku_normalizes_to_ncs57(self):
        self.assertEqual(normalize_platform("NCS-57C3-MODS-SYS"), "ncs57")
        self.assertEqual(normalize_platform("NCS-57C3-MOD-SYS"), "ncs57")

    def test_ncs57c3_filename_is_inferred_as_ncs57(self):
        self.assertEqual(infer_platform("NCS-57C3-MODS-SYS-26.1.2.iso"), "ncs57")
        self.assertEqual(infer_platform("ncs57c3modsys-25.1.2.iso"), "ncs57")

    def test_alias_matching_does_not_produce_false_positives_on_substrings(self):
        # "8800" is an alias for the Cisco 8000 family; it must not match when
        # it merely occurs inside an unrelated numeric run in the filename.
        self.assertIsNone(infer_platform("router-188005-image.iso"))
        self.assertIsNone(infer_platform("build-8800123-mini-x.iso"))
        # A real alias occurrence, properly bounded, still resolves.
        self.assertEqual(infer_platform("cisco-8800-mini-x-26.1.2.iso"), "8000")

    def test_automatic_selection_keeps_matching_repository_and_excludes_mismatches(
        self,
    ):
        result = recommend_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-mpls-te-rsvp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-bgp-1.0.0.1-r2512.CSCtest00002.x86_64.rpm",
                "asr9k-bgp-1.0.0.1-r2612.CSCtest00003.x86_64.rpm",
                "routing-1.0.0.1-r2612.CSCtest00004.x86_64.rpm",
            ],
        )
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["selected"]), 2)
        self.assertEqual(result["package_groups"][0]["count"], 2)
        self.assertIn(
            "keep these RPMs together", result["package_groups"][0]["relationship"]
        )
        self.assertEqual(
            {item["reason"] for item in result["excluded"]},
            {
                "Different IOS XR release",
                "Different platform",
                "Platform is missing from filename",
            },
        )

    def test_automatic_selection_surfaces_dependency_check_warning(self):
        # validate_smu_selection() always warns that filename checks cannot
        # prove RPM dependencies once at least one RPM was checked, but
        # recommend_smu_selection() computed that analysis and then silently
        # dropped its "warnings" key from the response - the operator-facing
        # automatic-selection preview (discover()/api/smu/recommendation)
        # never surfaced it, only the separately-triggered /api/compatibility
        # checker did.
        result = recommend_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            ],
        )
        self.assertTrue(result["ready"])
        self.assertTrue(
            any(
                "authoritative dependency check" in warning
                for warning in result["warnings"]
            )
        )

    def test_unparseable_rpm_metadata_is_excluded_with_a_specific_reason(self):
        # 06-UI-OPERATOR-TODO.md's "Explain decisions" list asks for
        # "malformed metadata" as its own explained exclusion category. An
        # RPM whose filename carries no release tag (or no platform token)
        # is exactly that: the metadata is not *wrong*, it is unreadable,
        # and saying "different release" for it would be a lie. Only the
        # missing-platform half of this had a test.
        result = recommend_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-bgp-no-release-tag.x86_64.rpm",
                "totally-unparseable.rpm",
            ],
        )
        reasons = {item["name"]: item["reason"] for item in result["excluded"]}
        self.assertEqual(
            reasons["ncs5500-bgp-no-release-tag.x86_64.rpm"],
            "Release is missing from filename",
        )
        self.assertEqual(
            reasons["totally-unparseable.rpm"], "Platform is missing from filename"
        )

    def test_automatic_selection_surfaces_a_real_blocking_issue(self):
        # Two RPMs for the same component and CSC, but different versions,
        # both pass the platform/release filename filters that gate automatic
        # selection - so recommend_smu_selection() happily selects both, yet
        # validate_smu_selection() flags this as an issue ("keep one RPM").
        # Before this fix, recommend_smu_selection() computed that issue via
        # its own validate_smu_selection() call but dropped it from the
        # response entirely (mirroring the same "warnings" bug already fixed
        # above for warnings) - so an operator relying on the default
        # automatic-selection preview (discover()/api/smu/recommendation)
        # never saw it until the final "Start build" click failed.
        result = recommend_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-mpls-1.0.0.2-r2612.CSCtest00001.x86_64.rpm",
            ],
        )
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["selected"]), 2)
        self.assertTrue(
            any("keep one RPM" in blocker for blocker in result["blockers"])
        )

    def test_automatic_selection_refuses_to_guess_unknown_iso_release(self):
        result = recommend_smu_selection(
            "ncs5500-mini-x.iso",
            [
                "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            ],
        )
        self.assertFalse(result["ready"])
        self.assertEqual(result["selected"], [])

    def test_matching_platform_and_release_are_accepted(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"],
        )
        self.assertTrue(result["compatible"])
        self.assertEqual(result["iso_release"], "26.1.2")

    def test_mixed_release_is_rejected(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2512.CSCtest00001.x86_64.rpm"],
        )
        self.assertFalse(result["compatible"])
        self.assertIn("does not match IOS XR 26.1.2", result["issues"][0])

    def test_multiple_fixes_for_same_component_require_supersedence_data(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-routing-1.0.0.2-r2612.CSCtest00002.x86_64.rpm",
            ],
        )
        self.assertTrue(result["compatible"])
        self.assertTrue(
            any("supersedence data" in warning for warning in result["warnings"])
        )

    def test_partial_multi_component_bundle_selection_is_rejected(self):
        # A real gap: CSCtest00001 is a multi-component fix requiring 3 RPMs
        # ("keep these RPMs together"). manual-packages.js's indeterminate
        # checkbox only *visually* hints that a group is partially selected -
        # nothing server-side ever validated it, so a manual selection of 2
        # of the 3 could reach gisobuild and produce an unintended (or
        # failing) Golden ISO with no warning at all.
        full_bundle = [
            "ncs5500-infra-1.0.0.8-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-iosxr-fwding-1.0.0.4-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-routing-1.0.0.2-r2612.CSCtest00001.x86_64.rpm",
        ]
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            full_bundle[:2],
            full_candidate_packages=full_bundle,
        )
        self.assertFalse(result["compatible"])
        issue = next(i for i in result["issues"] if "CSCTEST00001" in i)
        self.assertIn("2 of 3", issue)
        self.assertIn("ncs5500-routing-1.0.0.2-r2612.CSCtest00001.x86_64.rpm", issue)

    def test_complete_multi_component_bundle_selection_is_accepted(self):
        full_bundle = [
            "ncs5500-infra-1.0.0.8-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-iosxr-fwding-1.0.0.4-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-routing-1.0.0.2-r2612.CSCtest00001.x86_64.rpm",
        ]
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            full_bundle,
            full_candidate_packages=full_bundle,
        )
        self.assertTrue(result["compatible"])

    def test_bundle_completeness_is_not_checked_without_full_candidate_packages(self):
        # Automatic selection (recommend_smu_selection()'s own internal call)
        # always passes the same set as both "selected" and "full", so this
        # can never fire there by construction - but callers that genuinely
        # don't have the full inventory available must not get a false
        # positive from an argument they never passed.
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-infra-1.0.0.8-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-iosxr-fwding-1.0.0.4-r2612.CSCtest00001.x86_64.rpm",
            ],
        )
        self.assertTrue(result["compatible"])

    def test_multiple_versions_of_same_component_and_fix_are_rejected(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-routing-1.0.0.2-r2612.CSCtest00001.x86_64.rpm",
            ],
        )
        self.assertFalse(result["compatible"])
        self.assertTrue(any("Multiple versions" in issue for issue in result["issues"]))

    def test_csc_package_groups_show_components_that_belong_together(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            ],
        )
        self.assertEqual(
            result["package_groups"],
            [
                {
                    "csc": "CSCTEST00001",
                    "components": ["ncs5500-bgp", "ncs5500-routing"],
                    "count": 2,
                    "files": [
                        "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                        "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                    ],
                    "relationship": "Multi-component fix; keep these RPMs together",
                }
            ],
        )

    def test_overlapping_csc_fixes_are_explained(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-routing-1.0.0.2-r2612.CSCtest00002.x86_64.rpm",
            ],
        )
        self.assertEqual(
            result["component_conflicts"][0]["component"], "ncs5500-routing"
        )
        self.assertEqual(
            result["component_conflicts"][0]["cscs"], ["CSCTEST00001", "CSCTEST00002"]
        )

    def test_mixed_processor_architectures_are_rejected(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.aarch64.rpm",
            ],
        )
        self.assertFalse(result["compatible"])
        self.assertTrue(
            any("processor architecture" in issue for issue in result["issues"])
        )

    def test_rpm_architecture_mismatched_with_iso_is_rejected(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.aarch64.rpm"],
            iso_architectures=frozenset({"x86_64"}),
        )
        self.assertFalse(result["compatible"])
        self.assertTrue(
            any("processor architecture" in issue for issue in result["issues"])
        )
        self.assertEqual(result["iso_architectures"], ["x86_64"])

    def test_rpm_architecture_matching_iso_is_accepted(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"],
            iso_architectures=frozenset({"x86_64"}),
        )
        self.assertTrue(result["compatible"])

    def test_unknown_iso_architecture_does_not_block_selection(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.aarch64.rpm"],
            iso_architectures=None,
        )
        self.assertTrue(result["compatible"])
        self.assertEqual(result["iso_architectures"], [])

    def test_exr_arm_variant_token_normalizes_to_aarch64(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.corei7_64.rpm"],
            iso_architectures=frozenset({"aarch64"}),
        )
        self.assertFalse(result["compatible"])
        self.assertTrue(
            any("x86_64" in issue and "aarch64" in issue for issue in result["issues"])
        )

    def test_automatic_selection_excludes_wrong_architecture_rpms(self):
        result = recommend_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-bgp-1.0.0.1-r2612.CSCtest00002.aarch64.rpm",
            ],
            iso_architectures=frozenset({"x86_64"}),
        )
        self.assertTrue(result["ready"])
        self.assertEqual(
            result["selected"],
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"],
        )
        self.assertIn(
            {
                "name": "ncs5500-bgp-1.0.0.1-r2612.CSCtest00002.aarch64.rpm",
                "reason": "Processor architecture does not match the base ISO",
            },
            result["excluded"],
        )

    def test_upgrade_matrix_returns_bridge_smus_and_caveats(self):
        matrix = {
            "permitted": {
                "25.1.2": {
                    "26.1.2": [
                        {
                            "platform": "ncs5500",
                            "bridge_smus": ["bridge-placeholder.rpm"],
                            "caveats": ["Synthetic test caveat"],
                        }
                    ]
                }
            }
        }
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5500", [])
        self.assertTrue(result["permitted"])
        self.assertEqual(result["bridge_smus"], ["bridge-placeholder.rpm"])
        self.assertEqual(result["missing_bridge_smus"], ["bridge-placeholder.rpm"])

    def test_upgrade_matrix_uses_canonical_platform_normalization(self):
        matrix = {
            "permitted": {
                "25.1.2": {
                    "26.1.2": [
                        {
                            "platform": "NCS-57C3-MODS-SYS",
                            "bridge_smus": [],
                            "caveats": [],
                        }
                    ]
                }
            }
        }
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5700", [])
        self.assertTrue(result["permitted"])

    def test_bridge_smu_near_match_is_not_accepted(self):
        required = "ncs5500-routing-r2612.CSCabc123.x86_64.rpm"
        matrix = {
            "permitted": {
                "25.1.2": {
                    "26.1.2": [
                        {
                            "platform": "ncs5500",
                            "bridge_smus": [required],
                            "caveats": [],
                        }
                    ]
                }
            }
        }
        selected = ["ncs5500-routing-r2612.CSCabc1234.x86_64.rpm"]
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5500", selected)
        self.assertEqual(result["missing_bridge_smus"], [required])


class ExrRpmLabelCompareTests(unittest.TestCase):
    """compare_exr_rpm_labels() vs. the real pinned upstream algorithm.

    See docs/todo/02-AUTOMATION-BUILDPLAN-TODO.md "SMUs that are incompatible
    with the rest of the selection": eXR's own filter_superseded_rpms() does
    not use rpmvercmp, so this must be verified against upstream's actual
    (non-rpmvercmp) comparator, not against version-comparison intuition.
    """

    @staticmethod
    def _extract_method(source: str, name: str) -> str:
        match = re.search(
            rf"^    def {re.escape(name)}\(.*?\n(?=    def |\Z)",
            source,
            re.DOTALL | re.MULTILINE,
        )
        if not match:
            raise AssertionError(
                f"pinned upstream gisobuild dropped or renamed {name}()"
            )
        return match.group(0)

    def _upstream_comparator(self):
        """Execute the real upstream functions from the pinned source itself.

        Deliberately does not trust a static local copy: if a future pinned-
        commit bump changes this algorithm, this fails loudly instead of
        compare_exr_rpm_labels() silently drifting out of sync - same intent
        as test_exr_platform_list_matches_the_pinned_upstream_engine above.
        """
        engine_path = upstream_gisobuild_file(
            self, "src/exrmod/gisobuild_exr_engine.py"
        )
        source = engine_path.read_text()
        pattern_match = re.search(
            r"^_subfield_pattern = re\.compile\(.*?\n\)\n",
            source,
            re.DOTALL | re.MULTILINE,
        )
        if not pattern_match:
            self.fail("pinned upstream gisobuild dropped or renamed _subfield_pattern")
        namespace: dict = {"re": re, "zip_longest": zip_longest}
        exec(pattern_match.group(0), namespace)  # noqa: S102 - trusted pinned source, test-only
        class_source = "class _Upstream:\n" + "".join(
            self._extract_method(source, name)
            for name in (
                "_iter_rpm_subfields",
                "_compare_rpm_field",
                "_compare_rpm_labels",
            )
        )
        exec(class_source, namespace)  # noqa: S102 - trusted pinned source, test-only
        return namespace["_Upstream"]()

    def test_ported_comparator_agrees_with_the_pinned_upstream_source(self):
        upstream = self._upstream_comparator()
        cases = [
            (("1.0.0", "1"), ("1.0.0", "1")),
            (("1.0.0", "2"), ("1.0.0", "1")),
            (("1.0.1", "1"), ("1.0.0", "9")),
            # Same IOS XR release tag, different CSC IDs baked into %{RELEASE} -
            # the real shape of a same-component conflict between two fixes.
            (("1.0.0", "r2512.CSCwv36143"), ("1.0.0", "r2512.CSCwu13268")),
            (("1.0", "1"), ("1.0.0", "1")),
            # Not rpmvercmp: a tilde suffix is just more subfields, so it
            # outranks the bare version instead of being a pre-release.
            (("1.0~rc1", "1"), ("1.0", "1")),
            (("2.0", "1"), ("1.0~rc1", "1")),
        ]
        for lhs, rhs in cases:
            expected = upstream._compare_rpm_labels(
                [0, lhs[0], lhs[1]], [0, rhs[0], rhs[1]]
            )
            self.assertEqual(
                compare_exr_rpm_labels(lhs, rhs), expected, f"{lhs} vs {rhs}"
            )
            expected_reverse = upstream._compare_rpm_labels(
                [0, rhs[0], rhs[1]], [0, lhs[0], lhs[1]]
            )
            self.assertEqual(
                compare_exr_rpm_labels(rhs, lhs), expected_reverse, f"{rhs} vs {lhs}"
            )

    def test_more_subfields_outranks_fewer_regardless_of_content(self):
        # Documented upstream quirk (see the module docstring in
        # platform_validation.py): this is why real rpmvercmp must not be
        # substituted in - it would reverse this exact comparison.
        self.assertEqual(compare_exr_rpm_labels(("1.0~rc1", "1"), ("1.0", "1")), 1)
        self.assertEqual(compare_exr_rpm_labels(("1.0", "1"), ("1.0~rc1", "1")), -1)

    def test_equal_labels_compare_equal(self):
        self.assertEqual(
            compare_exr_rpm_labels(
                ("1.0.0", "r2512.CSCabc123"), ("1.0.0", "r2512.CSCabc123")
            ),
            0,
        )

    def test_release_only_breaks_a_version_tie(self):
        self.assertEqual(compare_exr_rpm_labels(("1.0.0", "2"), ("1.0.0", "1")), 1)
        self.assertEqual(compare_exr_rpm_labels(("1.0.0", "1"), ("1.0.0", "2")), -1)


if __name__ == "__main__":
    unittest.main()
