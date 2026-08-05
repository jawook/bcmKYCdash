from pathlib import Path

import pandas as pd
import streamlit as st

from poll_dashboard.parser import load_poll_results


RESULTS_DIR = Path(__file__).parent / "Results"
KYC_RESULTS_DIR = RESULTS_DIR / "KYC"

st.set_page_config(page_title="Class Poll Dashboard", page_icon=":bar_chart:", layout="wide")
st.title("Class Poll Dashboard")
st.caption("View results from classroom activities.")


@st.cache_data
def load_activity_folder(folder: Path) -> tuple[pd.DataFrame, list[str]]:
    """Load every CSV in one activity-type folder."""
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for path in sorted(folder.glob("*.csv")):
        try:
            _, frame = load_poll_results(path)
            frame["Source File"] = path.name
            frames.append(frame)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")

    if not frames:
        return pd.DataFrame(), errors
    return pd.concat(frames, ignore_index=True), errors


def choices(frame: pd.DataFrame, column: str) -> list[str]:
    values = frame[column].fillna("").astype(str).str.strip()
    return sorted(value for value in values.unique() if value)


def apply_optional_filter(
    frame: pd.DataFrame, column: str, selected: list[str]
) -> pd.DataFrame:
    return frame[frame[column].isin(selected)] if selected else frame


kyc_tab = st.tabs(["KYC Checks"])[0]

with kyc_tab:
    results, load_errors = load_activity_folder(KYC_RESULTS_DIR)

    if load_errors:
        with st.expander("Some activity files could not be loaded"):
            for error in load_errors:
                st.warning(error)

    if results.empty:
        st.info("No KYC activity results are available yet.")
        st.stop()

    dashboard, filter_panel = st.columns([4, 1.25], gap="large")

    with filter_panel:
        st.markdown("### Filters")
        st.caption("Leave a filter empty to include everything.")
        selected_activities = st.multiselect(
            "Activity Name", choices(results, "Activity"), placeholder="All activities"
        )
        selected_targets = st.multiselect(
            "Target", choices(results, "Target"), placeholder="All targets"
        )
        selected_respondents = st.multiselect(
            "Respondent", choices(results, "Screen name"), placeholder="All respondents"
        )

    filtered = apply_optional_filter(results, "Activity", selected_activities)
    filtered = apply_optional_filter(filtered, "Target", selected_targets)
    filtered = apply_optional_filter(filtered, "Screen name", selected_respondents)

    with dashboard:
        correct = int(filtered["Is Correct"].sum())
        total = len(filtered)
        accuracy = correct / total if total else 0

        metric_1, metric_2, metric_3 = st.columns(3)
        metric_1.metric("Responses", f"{total:,}")
        metric_2.metric("Correct", f"{correct:,}")
        metric_3.metric("Accuracy", f"{accuracy:.0%}")

        if filtered.empty:
            st.info("No responses match the current filters.")
            st.stop()

        target_summary = (
            filtered.groupby("Target", as_index=False)
            .agg(Responses=("Response", "size"), Correct=("Is Correct", "sum"))
            .assign(Accuracy=lambda frame: frame["Correct"] / frame["Responses"])
        )

        st.markdown("### Accuracy by Question")
        st.bar_chart(target_summary, x="Target", y="Accuracy", horizontal=True)

        respondent_summary = (
            filtered.groupby("Screen name", as_index=False)
            .agg(Responses=("Response", "size"), Correct=("Is Correct", "sum"))
            .assign(Accuracy=lambda frame: frame["Correct"] / frame["Responses"])
            .sort_values(["Accuracy", "Correct"], ascending=False)
            .rename(columns={"Screen name": "Respondent"})
        )
        st.markdown("### Respondent Results")
        st.dataframe(
            respondent_summary,
            column_config={
                "Accuracy": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)
            },
            hide_index=True,
            use_container_width=True,
        )

        with st.expander("View response details"):
            display_columns = [
                "Activity",
                "Target",
                "Response",
                "Screen name",
                "Correct?",
                "Created At",
            ]
            st.dataframe(filtered[display_columns], hide_index=True, use_container_width=True)
