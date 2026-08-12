from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from poll_dashboard.parser import load_poll_results, retain_first_responses


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
            # Public result files are already sanitized offline. Secrets and raw
            # name-bearing exports must never be required by the deployed app.
            _, frame = load_poll_results(path)
            frame["Source File"] = path.name
            frames.append(frame)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            errors.append(f"{path.name}: {type(exc).__name__}")

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


def percentage_bar_chart(frame: pd.DataFrame, category: str) -> None:
    """Display a horizontal accuracy chart with percentage labels."""
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X(
                "Accuracy:Q",
                title="Accuracy",
                axis=alt.Axis(format=".0%"),
                scale=alt.Scale(domain=[0, 1]),
            ),
            y=alt.Y(f"{category}:N", title=None, sort="-x"),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=category),
                alt.Tooltip("Accuracy:Q", title="Accuracy", format=".1%"),
            ],
        )
        .properties(height=max(300, len(frame) * 28))
    )
    st.altair_chart(chart, use_container_width=True)


def top_ten_bar_chart(frame: pd.DataFrame, metric: str, percentage: bool = False) -> None:
    """Display consistently sized respondent ranking charts."""
    axis = alt.Axis(format=".0%") if percentage else alt.Axis(format="d")
    tooltip = (
        alt.Tooltip(f"{metric}:Q", title=metric, format=".1%")
        if percentage
        else alt.Tooltip(f"{metric}:Q", title=metric, format=",")
    )
    chart = (
        alt.Chart(frame)
        .mark_bar(size=20)
        .encode(
            x=alt.X(f"{metric}:Q", title=metric, axis=axis),
            y=alt.Y("Participant:N", title=None, sort="-x"),
            tooltip=[
                alt.Tooltip("Participant:N", title="Participant"),
                tooltip,
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)


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

    results, adjustments = retain_first_responses(results)

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
            "Participant", choices(results, "Screen name"), placeholder="All participants"
        )

    filtered = apply_optional_filter(results, "Activity", selected_activities)
    filtered = apply_optional_filter(filtered, "Target", selected_targets)
    filtered = apply_optional_filter(filtered, "Screen name", selected_respondents)

    filtered_adjustments = apply_optional_filter(
        adjustments, "Activity", selected_activities
    )
    filtered_adjustments = apply_optional_filter(
        filtered_adjustments, "Target", selected_targets
    )
    filtered_adjustments = apply_optional_filter(
        filtered_adjustments, "Screen name", selected_respondents
    )

    with dashboard:
        correct = int(filtered["Is Correct"].sum())
        total = len(filtered)
        accuracy = correct / total if total else 0
        unique_participants = filtered["Screen name"].nunique()

        metric_1, metric_2, metric_3, metric_4 = st.columns(4)
        metric_1.metric("Responses", f"{total:,}")
        metric_2.metric("Correct", f"{correct:,}")
        metric_3.metric("Accuracy", f"{accuracy:.0%}")
        metric_4.metric("Unique Participants", f"{unique_participants:,}")

        if filtered.empty:
            st.info("No responses match the current filters.")
            st.stop()

        target_summary = (
            filtered.groupby("Target", as_index=False)
            .agg(
                Responses=("Response", "size"),
                Correct=("Is Correct", "sum"),
                **{"Unique Participants": ("Screen name", "nunique")},
            )
            .assign(Accuracy=lambda frame: frame["Correct"] / frame["Responses"])
            .sort_values(["Accuracy", "Correct", "Responses"], ascending=False)
        )

        st.markdown("### Top Ten Targets by Accuracy %")
        percentage_bar_chart(target_summary.head(10), "Target")

        with st.expander("Results for All Targets", expanded=False):
            st.dataframe(
                target_summary,
                column_config={
                    "Accuracy": st.column_config.ProgressColumn(
                        format="percent", min_value=0, max_value=1
                    )
                },
                hide_index=True,
                use_container_width=True,
            )

        respondent_summary = (
            filtered.groupby("Screen name", as_index=False)
            .agg(Responses=("Response", "size"), Correct=("Is Correct", "sum"))
            .assign(Accuracy=lambda frame: frame["Correct"] / frame["Responses"])
            .sort_values(["Accuracy", "Correct"], ascending=False)
            .rename(columns={"Screen name": "Participant"})
        )

        top_by_accuracy = respondent_summary.sort_values(
            ["Accuracy", "Correct", "Responses"], ascending=False
        ).head(10)
        st.markdown("### Top Ten Participants by Accuracy %")
        top_ten_bar_chart(top_by_accuracy, "Accuracy", percentage=True)

        top_by_correct = respondent_summary.sort_values(
            ["Correct", "Accuracy", "Responses"], ascending=False
        ).head(10)
        st.markdown("### Top Ten Participants by # Correct")
        top_ten_bar_chart(top_by_correct, "Correct")

        with st.expander("Results for All Participants", expanded=False):
            st.dataframe(
                respondent_summary,
                column_config={
                    "Accuracy": st.column_config.ProgressColumn(
                        format="percent", min_value=0, max_value=1
                    )
                },
                hide_index=True,
                use_container_width=True,
            )

        with st.expander("Response Adjustments", expanded=False):
            st.caption(
                "For each activity question, only a participant's first response is "
                "included in the dashboard. Original CSV files are unchanged."
            )
            if filtered_adjustments.empty:
                st.success("No response adjustments were needed for the current filters.")
            else:
                adjustment_summary = (
                    filtered_adjustments.groupby(
                        ["Activity", "Target", "Screen name"], as_index=False
                    )
                    .agg(**{"Responses Removed": ("Response", "size")})
                    .rename(columns={"Screen name": "Participant"})
                    .sort_values(
                        ["Responses Removed", "Activity", "Target"],
                        ascending=[False, True, True],
                    )
                )
                st.info(
                    f"Adjusted responses for "
                    f"{adjustment_summary['Participant'].nunique():,} participant(s)."
                )
                st.dataframe(
                    adjustment_summary,
                    hide_index=True,
                    use_container_width=True,
                )

        with st.expander("Potential Gaming", expanded=False):
            st.caption(
                "Flags participants with more than one response to the same question "
                "within an activity after first-response adjustments. This section "
                "follows the filters above."
            )

            gaming_source = filtered[
                filtered["Screen name"].fillna("").astype(str).str.strip().ne("")
            ]
            repeated_responses = (
                gaming_source.groupby(
                    ["Activity", "Question", "Target", "Screen name"], as_index=False
                )
                .agg(Responses=("Response", "size"))
                .query("Responses > 1")
                .assign(**{"Extra Responses": lambda frame: frame["Responses"] - 1})
                .rename(columns={"Screen name": "Participant"})
                .sort_values(
                    ["Extra Responses", "Responses", "Activity", "Target"],
                    ascending=[False, False, True, True],
                )
            )

            if repeated_responses.empty:
                st.success("No repeated responses detected for the current filters.")
            else:
                affected = repeated_responses["Participant"].nunique()
                extra = int(repeated_responses["Extra Responses"].sum())
                st.warning(
                    f"Detected {extra:,} extra response(s) across "
                    f"{affected:,} participant(s)."
                )
                st.dataframe(
                    repeated_responses[
                        [
                            "Activity",
                            "Target",
                            "Participant",
                            "Responses",
                            "Extra Responses",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
