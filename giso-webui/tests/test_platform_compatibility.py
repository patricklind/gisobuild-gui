import unittest

from platform_validation import (
    capabilities_for_platform,
    check_upgrade_matrix,
    infer_platform,
    normalize_platform,
    recommend_smu_selection,
    validate_platform_options,
    validate_smu_selection,
)


class PlatformCompatibilityTests(unittest.TestCase):
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
        with self.assertRaisesRegex(ValueError, "remove_packages not supported"):
            validate_platform_options({
                "iso": "ncs5500-mini-x-26.1.2.iso", "remove_packages": ["optional-pkg"]
            })

    def test_adapter_rejects_exr_only_capability_on_lnt_platform(self):
        # The mirror image of the test above: remove_packages is LNT-only
        # and rejected on an eXR platform, but nothing checked the other
        # direction - an eXR-only capability (optimize) offered on an LNT
        # platform (Cisco 8000).
        with self.assertRaisesRegex(ValueError, "optimize not supported"):
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

    def test_automatic_selection_keeps_matching_repository_and_excludes_mismatches(self):
        result = recommend_smu_selection("ncs5500-mini-x-26.1.2.iso", [
            "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-mpls-te-rsvp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-bgp-1.0.0.1-r2512.CSCtest00002.x86_64.rpm",
            "asr9k-bgp-1.0.0.1-r2612.CSCtest00003.x86_64.rpm",
            "routing-1.0.0.1-r2612.CSCtest00004.x86_64.rpm",
        ])
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["selected"]), 2)
        self.assertEqual(result["package_groups"][0]["count"], 2)
        self.assertIn("keep these RPMs together", result["package_groups"][0]["relationship"])
        self.assertEqual({item["reason"] for item in result["excluded"]},
                         {"Different IOS XR release", "Different platform",
                          "Platform is missing from filename"})

    def test_automatic_selection_surfaces_dependency_check_warning(self):
        # validate_smu_selection() always warns that filename checks cannot
        # prove RPM dependencies once at least one RPM was checked, but
        # recommend_smu_selection() computed that analysis and then silently
        # dropped its "warnings" key from the response - the operator-facing
        # automatic-selection preview (discover()/api/smu/recommendation)
        # never surfaced it, only the separately-triggered /api/compatibility
        # checker did.
        result = recommend_smu_selection("ncs5500-mini-x-26.1.2.iso", [
            "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
        ])
        self.assertTrue(result["ready"])
        self.assertTrue(any("authoritative dependency check" in warning
                            for warning in result["warnings"]))

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
        result = recommend_smu_selection("ncs5500-mini-x-26.1.2.iso", [
            "ncs5500-mpls-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            "ncs5500-mpls-1.0.0.2-r2612.CSCtest00001.x86_64.rpm",
        ])
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["selected"]), 2)
        self.assertTrue(any("keep one RPM" in blocker for blocker in result["blockers"]))

    def test_automatic_selection_refuses_to_guess_unknown_iso_release(self):
        result = recommend_smu_selection("ncs5500-mini-x.iso", [
            "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
        ])
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
        self.assertTrue(any("supersedence data" in warning for warning in result["warnings"]))

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
        self.assertEqual(result["package_groups"], [{
            "csc": "CSCTEST00001", "components": ["ncs5500-bgp", "ncs5500-routing"],
            "count": 2,
            "files": [
                "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
            ],
            "relationship": "Multi-component fix; keep these RPMs together",
        }])

    def test_overlapping_csc_fixes_are_explained(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-routing-1.0.0.2-r2612.CSCtest00002.x86_64.rpm",
            ],
        )
        self.assertEqual(result["component_conflicts"][0]["component"], "ncs5500-routing")
        self.assertEqual(result["component_conflicts"][0]["cscs"],
                         ["CSCTEST00001", "CSCTEST00002"])

    def test_mixed_processor_architectures_are_rejected(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            [
                "ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm",
                "ncs5500-bgp-1.0.0.1-r2612.CSCtest00001.aarch64.rpm",
            ],
        )
        self.assertFalse(result["compatible"])
        self.assertTrue(any("processor architecture" in issue for issue in result["issues"]))

    def test_rpm_architecture_mismatched_with_iso_is_rejected(self):
        result = validate_smu_selection(
            "ncs5500-mini-x-26.1.2.iso",
            ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.aarch64.rpm"],
            iso_architectures=frozenset({"x86_64"}),
        )
        self.assertFalse(result["compatible"])
        self.assertTrue(any("processor architecture" in issue for issue in result["issues"]))
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
        self.assertTrue(any("x86_64" in issue and "aarch64" in issue for issue in result["issues"]))

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
        self.assertEqual(result["selected"], ["ncs5500-routing-1.0.0.1-r2612.CSCtest00001.x86_64.rpm"])
        self.assertIn(
            {"name": "ncs5500-bgp-1.0.0.1-r2612.CSCtest00002.aarch64.rpm",
             "reason": "Processor architecture does not match the base ISO"},
            result["excluded"],
        )

    def test_upgrade_matrix_returns_bridge_smus_and_caveats(self):
        matrix = {"permitted": {"25.1.2": {"26.1.2": [{
            "platform": "ncs5500", "bridge_smus": ["bridge-placeholder.rpm"],
            "caveats": ["Synthetic test caveat"],
        }]}}}
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5500", [])
        self.assertTrue(result["permitted"])
        self.assertEqual(result["bridge_smus"], ["bridge-placeholder.rpm"])
        self.assertEqual(result["missing_bridge_smus"], ["bridge-placeholder.rpm"])

    def test_upgrade_matrix_uses_canonical_platform_normalization(self):
        matrix = {"permitted": {"25.1.2": {"26.1.2": [{
            "platform": "NCS-57C3-MODS-SYS", "bridge_smus": [], "caveats": [],
        }]}}}
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5700", [])
        self.assertTrue(result["permitted"])

    def test_bridge_smu_near_match_is_not_accepted(self):
        required = "ncs5500-routing-r2612.CSCabc123.x86_64.rpm"
        matrix = {"permitted": {"25.1.2": {"26.1.2": [{
            "platform": "ncs5500", "bridge_smus": [required], "caveats": [],
        }]}}}
        selected = ["ncs5500-routing-r2612.CSCabc1234.x86_64.rpm"]
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5500", selected)
        self.assertEqual(result["missing_bridge_smus"], [required])


if __name__ == "__main__":
    unittest.main()
