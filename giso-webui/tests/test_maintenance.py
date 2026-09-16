import unittest
from unittest.mock import patch

import maintenance


class MaintenanceTests(unittest.TestCase):
    def test_transient_os_error_does_not_crash_the_loop(self):
        stop = RuntimeError("stop the test loop")
        with patch.object(maintenance, "enforce_archive_policy",
                          side_effect=[OSError("disk hiccup"), []]) as policy, \
             patch.object(maintenance.time, "sleep", side_effect=[None, stop]) as sleep, \
             self.assertRaises(RuntimeError):
            maintenance.main()
        self.assertEqual(policy.call_count, 2)
        self.assertEqual(sleep.call_count, 2)

    def test_successful_cycle_reports_removed_jobs(self):
        stop = RuntimeError("stop the test loop")
        with patch.object(maintenance, "enforce_archive_policy", return_value=["job-1"]), \
             patch.object(maintenance.time, "sleep", side_effect=stop), \
             patch("builtins.print") as printed, \
             self.assertRaises(RuntimeError):
            maintenance.main()
        messages = " ".join(str(call.args[0]) for call in printed.call_args_list)
        self.assertIn("removed 1", messages)


if __name__ == "__main__":
    unittest.main()
