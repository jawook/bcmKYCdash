"""Create public-safe KYC CSVs from ignored raw panel-number exports."""

from pathlib import Path
import re

import pandas as pd
import tomllib

from poll_dashboard.parser import load_poll_results, parse_panel_answer_key


ROOT = Path(__file__).parents[1]
PRIVATE_DIR = ROOT / "Results" / "KYC-private"
PUBLIC_DIR = ROOT / "Results" / "KYC"
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
PUBLIC_COLUMNS = [
    "Activity",
    "Question",
    "Target",
    "Response",
    "Via",
    "Screen name",
    "Correct?",
    "Created At",
]


def main() -> None:
    with SECRETS_PATH.open("rb") as secrets_file:
        answer_key = tomllib.load(secrets_file)["kyc_panel_answer_key"]

    private_names = {
        name for (_, name) in parse_panel_answer_key(answer_key)
    }

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    for source in sorted(PRIVATE_DIR.glob("*.csv")):
        _, frame = load_poll_results(source, answer_key)
        screen_names = frame["Screen name"].fillna("").astype(str).str.strip()
        for index, screen_name in screen_names.items():
            if screen_name in private_names:
                preferred_name = re.search(r"\(([^)]+)\)", screen_name)
                frame.at[index, "Screen name"] = (
                    preferred_name.group(1)
                    if preferred_name
                    else screen_name.split()[0]
                )
        missing = [column for column in PUBLIC_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{source.name} is missing public columns: {missing}")
        destination = PUBLIC_DIR / source.name
        frame[PUBLIC_COLUMNS].to_csv(destination, index=False)
        print(f"Sanitized {source.name}")


if __name__ == "__main__":
    main()
