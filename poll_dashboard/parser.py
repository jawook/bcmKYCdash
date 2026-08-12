from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd


EXPECTED_HEADER = "Response"
PANEL_QUESTION_PATTERN = re.compile(
    r"Select\s+the\s+panel\s+number\s+that\s+contains\s+(.+?)\.\s*"
    r"<em>\s*Collage\s+(\d+)\s*</em>",
    re.IGNORECASE,
)
ANSWER_KEY_LINE_PATTERN = re.compile(r"^Collage\s+(\d+)\s*:\s*(.+)$", re.IGNORECASE)
ANSWER_KEY_ENTRY_PATTERN = re.compile(r"(?:^|\|)\s*(\d+)\.\s*(.+?)\s*(?=\||$)")


def _read_text(source: str | Path | BinaryIO | TextIO) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).read_text(encoding="utf-8-sig")

    content = source.read()
    if isinstance(content, bytes):
        return content.decode("utf-8-sig")
    return content


def _clean_rows(text: str) -> list[list[str]]:
    rows = list(csv.reader(io.StringIO(text)))
    return [[cell.strip() for cell in row] for row in rows]


def parse_panel_answer_key(text: str) -> dict[tuple[int, str], int]:
    """Parse private collage/name mappings into panel numbers."""
    answers: dict[tuple[int, str], int] = {}
    for raw_line in text.splitlines():
        line_match = ANSWER_KEY_LINE_PATTERN.match(raw_line.strip())
        if not line_match:
            continue
        collage = int(line_match.group(1))
        for entry_match in ANSWER_KEY_ENTRY_PATTERN.finditer(line_match.group(2)):
            panel = int(entry_match.group(1))
            name = entry_match.group(2).strip()
            answers[(collage, name)] = panel
    return answers


def public_given_name(full_name: str) -> str:
    """Return a public-safe preferred or given name from a private full name."""
    preferred_name = re.search(r"\(([^)]+)\)", full_name)
    if preferred_name:
        return preferred_name.group(1).strip()
    return full_name.strip().split()[0]


def _apply_panel_metadata(
    frame: pd.DataFrame, answer_key: dict[tuple[int, str], int]
) -> pd.DataFrame:
    """Replace private panel-question names with safe public labels."""
    result = frame.copy()
    for index, question in result["Question"].items():
        match = PANEL_QUESTION_PATTERN.search(str(question))
        if not match:
            continue
        name = match.group(1).strip()
        collage = int(match.group(2))
        panel = answer_key.get((collage, name))
        if panel is None:
            raise ValueError(
                f"the private answer key has no entry for collage {collage:02d}"
            )
        safe_label = public_given_name(name)
        result.at[index, "Question"] = safe_label
        result.at[index, "Target"] = safe_label
        result.at[index, "Expected Panel"] = panel
        response_match = re.search(r"\d+", str(result.at[index, "Response"]))
        if response_match:
            result.at[index, "Is Correct"] = int(response_match.group()) == panel
    return result


def load_poll_results(
    source: str | Path | BinaryIO | TextIO,
    panel_answer_key_text: str = "",
) -> tuple[str, pd.DataFrame]:
    """Parse a block-style poll export or a conventional CSV table."""
    text = _read_text(source)
    rows = _clean_rows(text)
    nonempty = [row for row in rows if any(row)]
    if not nonempty:
        raise ValueError("the file is empty")

    header_indexes = [i for i, row in enumerate(rows) if row and row[0] == EXPECTED_HEADER]
    if not header_indexes:
        frame = pd.read_csv(io.StringIO(text))
        title = (
            str(frame["Activity"].dropna().iloc[0])
            if "Activity" in frame.columns and not frame["Activity"].dropna().empty
            else "Poll results"
        )
        return title, _normalise_frame(frame, title)

    title = next((row[0] for row in rows[: header_indexes[0]] if row and row[0]), "Poll results")
    records: list[dict[str, str]] = []

    for header_index in header_indexes:
        question = next(
            (
                rows[i][0]
                for i in range(header_index - 1, -1, -1)
                if rows[i] and any(rows[i]) and rows[i][0] != title
            ),
            "Question",
        )
        headers = rows[header_index]
        for row in rows[header_index + 1 :]:
            if not any(row) or (row and row[0] == EXPECTED_HEADER):
                break
            padded = row + [""] * (len(headers) - len(row))
            record = dict(zip(headers, padded))
            record["Question"] = question
            records.append(record)

    result = _normalise_frame(pd.DataFrame(records), title)
    has_panel_questions = result["Question"].map(
        lambda question: bool(PANEL_QUESTION_PATTERN.search(str(question)))
    ).any()
    if has_panel_questions:
        if not panel_answer_key_text.strip():
            raise ValueError("panel-number activities require the private answer key secret")
        result = _apply_panel_metadata(
            result, parse_panel_answer_key(panel_answer_key_text)
        )
    return title, result


def _target_from_question(question: object) -> str:
    text = str(question).strip()
    match = re.search(r":\s*([^:]+?)\s*$", text)
    return match.group(1) if match else text


def _normalise_frame(frame: pd.DataFrame, activity: str) -> pd.DataFrame:
    if "Response" not in frame.columns:
        raise ValueError("a 'Response' column was not found")

    result = frame.copy()
    if "Question" not in result.columns:
        result["Question"] = "All responses"

    if "Activity" not in result.columns:
        result["Activity"] = activity
    else:
        result["Activity"] = result["Activity"].fillna(activity)
    if "Target" not in result.columns:
        result["Target"] = result["Question"].map(_target_from_question)

    for column in ["Screen name", "Registered participant", "Correct?", "Created At"]:
        if column not in result.columns:
            result[column] = ""

    registered = result["Registered participant"].fillna("").astype(str).str.strip()
    screen_name = result["Screen name"].fillna("").astype(str).str.strip()
    result["Screen name"] = screen_name
    result["Respondent"] = registered.where(registered.ne(""), screen_name)
    result["Is Correct"] = (
        result["Correct?"].fillna("").astype(str).str.strip().str.casefold().eq("yes")
    )
    result["Created At"] = pd.to_datetime(result["Created At"], errors="coerce")
    return result


def retain_first_responses(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the earliest response per named user, question, and source file."""
    if frame.empty:
        return frame.copy(), frame.copy()

    working = frame.copy()
    working["_Input Order"] = range(len(working))
    working["_Participant Key"] = (
        working["Screen name"].fillna("").astype(str).str.strip()
    )

    identified = working["_Participant Key"].ne("")
    source_column = "Source File" if "Source File" in working.columns else "Activity"
    duplicate_keys = [source_column, "Question", "_Participant Key"]

    ordered_identified = working[identified].sort_values(
        duplicate_keys + ["Created At", "_Input Order"],
        kind="stable",
        na_position="last",
    )
    removed_mask = ordered_identified.duplicated(duplicate_keys, keep="first")
    adjustments = ordered_identified[removed_mask].copy()
    kept_identified = ordered_identified[~removed_mask]
    kept = pd.concat([kept_identified, working[~identified]], ignore_index=False)

    internal_columns = ["_Input Order", "_Participant Key"]
    cleaned = (
        kept.sort_values("_Input Order", kind="stable")
        .drop(columns=internal_columns)
        .reset_index(drop=True)
    )
    adjustments = (
        adjustments.sort_values("_Input Order", kind="stable")
        .drop(columns=internal_columns)
        .reset_index(drop=True)
    )
    return cleaned, adjustments
