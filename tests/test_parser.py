from io import StringIO
from pathlib import Path
import unittest

from poll_dashboard.parser import load_poll_results


SAMPLE = """Demo poll
Please click on the face of: Chris
Response,Screen name,Registered participant,Correct?,Created At
A,guest1,,Yes,2026-08-05 09:00:00
B,guest2,Student 2,No,2026-08-05 09:01:00

Please click on the face of: Caitlin
Response,Screen name,Registered participant,Correct?,Created At
C,guest1,,Yes,2026-08-05 09:02:00
"""


class ParserTests(unittest.TestCase):
    def test_loads_block_export(self):
        title, results = load_poll_results(StringIO(SAMPLE))

        self.assertEqual(title, "Demo poll")
        self.assertEqual(len(results), 3)
        self.assertEqual(results["Question"].nunique(), 2)
        self.assertEqual(results["Target"].tolist(), ["Chris", "Chris", "Caitlin"])
        self.assertTrue((results["Activity"] == "Demo poll").all())
        self.assertEqual(results["Is Correct"].sum(), 2)
        self.assertEqual(results.loc[1, "Participant"], "Student 2")

    def test_loads_included_activity(self):
        result_files = sorted((Path(__file__).parents[1] / "Results" / "KYC").glob("*.csv"))
        self.assertTrue(result_files, "Expected at least one activity CSV")

        title, results = load_poll_results(result_files[0])

        self.assertTrue(title)
        self.assertFalse(results.empty)
        self.assertGreaterEqual(results["Question"].nunique(), 1)
        self.assertEqual(results.iloc[0]["Target"], "Chris")


if __name__ == "__main__":
    unittest.main()
