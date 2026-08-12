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

PANEL_SAMPLE = """KYC Check 07
Select the panel number that contains Example Person.<em> Collage 14</em>
Response,Via,Screen name,Registered participant,Correct?,Created At
4,Survey,student1,,No,2026-08-05 09:00:00
"""

PANEL_KEY = "Collage 14: 1. Alpha Example | 2. Example Person | 3. Gamma Example"


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

    def test_panel_questions_use_private_key_and_safe_target(self):
        _, results = load_poll_results(StringIO(PANEL_SAMPLE), PANEL_KEY)

        self.assertEqual(results.iloc[0]["Target"], "Example")
        self.assertEqual(results.iloc[0]["Question"], "Example")
        self.assertFalse(results.iloc[0]["Is Correct"])
        self.assertNotIn("Example Person", results.to_string())

    def test_panel_questions_require_private_key(self):
        with self.assertRaisesRegex(ValueError, "private answer key"):
            load_poll_results(StringIO(PANEL_SAMPLE))

    def test_sanitized_panel_csv_preserves_safe_metadata(self):
        safe_csv = """Activity,Question,Target,Response,Screen name,Correct?,Created At
KYC Check 06,Collage 14 - Panel 1,Collage 14 - Panel 1,Panel 1,student1,Yes,2026-08-05 09:00:00
"""

        title, results = load_poll_results(StringIO(safe_csv))

        self.assertEqual(title, "KYC Check 06")
        self.assertEqual(results.iloc[0]["Target"], "Collage 14 - Panel 1")

    def test_all_public_results_load_without_secrets(self):
        result_files = sorted((Path(__file__).parents[1] / "Results" / "KYC").glob("*.csv"))

        self.assertTrue(result_files)
        for result_file in result_files:
            with self.subTest(result_file=result_file.name):
                _, results = load_poll_results(result_file)
                self.assertFalse(results.empty)


if __name__ == "__main__":
    unittest.main()
