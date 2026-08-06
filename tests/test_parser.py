from io import StringIO
from pathlib import Path
import unittest

import pandas as pd

from poll_dashboard.parser import load_poll_results, retain_first_responses


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
        self.assertEqual(results.loc[1, "Respondent"], "Student 2")

    def test_loads_included_activity(self):
        result_files = sorted((Path(__file__).parents[1] / "Results" / "KYC").glob("*.csv"))
        self.assertTrue(result_files, "Expected at least one activity CSV")

        title, results = load_poll_results(result_files[0])

        self.assertTrue(title)
        self.assertFalse(results.empty)
        self.assertGreaterEqual(results["Question"].nunique(), 1)
        self.assertEqual(results.iloc[0]["Target"], "Chris")

    def test_retains_first_response_and_records_adjustment(self):
        _, results = load_poll_results(StringIO(SAMPLE))
        results["Source File"] = "activity.csv"
        repeated = results.iloc[[0]].copy()
        repeated["Response"] = "Later answer"
        repeated["Created At"] = repeated["Created At"] + pd.Timedelta(minutes=5)
        combined = pd.concat([results, repeated], ignore_index=True)

        cleaned, adjustments = retain_first_responses(combined)

        self.assertEqual(len(cleaned), 3)
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(cleaned.iloc[0]["Response"], "A")
        self.assertEqual(adjustments.iloc[0]["Response"], "Later answer")

    def test_screen_names_are_case_sensitive(self):
        _, results = load_poll_results(StringIO(SAMPLE))
        upper = results.iloc[[0]].copy()
        lower = results.iloc[[0]].copy()
        upper["Screen name"] = "B"
        lower["Screen name"] = "b"
        upper["Source File"] = "activity.csv"
        lower["Source File"] = "activity.csv"

        cleaned, adjustments = retain_first_responses(
            pd.concat([upper, lower], ignore_index=True)
        )

        self.assertEqual(len(cleaned), 2)
        self.assertTrue(adjustments.empty)


if __name__ == "__main__":
    unittest.main()
