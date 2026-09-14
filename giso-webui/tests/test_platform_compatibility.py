import unittest

from platform_validation import check_upgrade_matrix, validate_smu_selection


class PlatformCompatibilityTests(unittest.TestCase):
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
        }])

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

    def test_upgrade_matrix_returns_bridge_smus_and_caveats(self):
        matrix = {"permitted": {"25.1.2": {"26.1.2": [{
            "platform": "ncs5500", "bridge_smus": ["bridge-placeholder.rpm"],
            "caveats": ["Synthetic test caveat"],
        }]}}}
        result = check_upgrade_matrix(matrix, "25.1.2", "26.1.2", "ncs5500", [])
        self.assertTrue(result["permitted"])
        self.assertEqual(result["bridge_smus"], ["bridge-placeholder.rpm"])
        self.assertEqual(result["missing_bridge_smus"], ["bridge-placeholder.rpm"])


if __name__ == "__main__":
    unittest.main()
