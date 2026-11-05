import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.cleaning_run import CleaningRun
from app.models.dataset import Dataset
from app.schemas.cleaning import (
    CleaningQualityMetrics,
    CleaningRequest,
    CleaningRunResponse,
    MissingValueOptions,
)
from app.services.csv_upload import CsvUploadError, resolve_original_path
from app.services.quality_analysis import analyze_frame

logger = logging.getLogger(__name__)
_FORMULA_PREFIX = re.compile(r"^[\s\x00-\x1f]*[=+\-@]")


def _read_frame_from_path(
    source_path: Path,
    expected_rows: int,
    expected_columns: int,
) -> pd.DataFrame:
    try:
        frame = pd.read_csv(
            source_path,
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
            on_bad_lines="error",
            engine="c",
        )
    except (OSError, EmptyDataError, ParserError, UnicodeDecodeError, ValueError) as error:
        logger.exception("Could not read stored CSV for cleaning.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The stored dataset could not be read for cleaning.",
        ) from error
    if len(frame) != expected_rows or len(frame.columns) != expected_columns:
        raise CsvUploadError(
            500,
            "storage_error",
            "The stored dataset no longer matches its saved metadata.",
        )
    return frame


def _read_frame(dataset: Dataset, settings: Settings) -> pd.DataFrame:
    source_path = resolve_original_path(settings, dataset)
    return _read_frame_from_path(source_path, dataset.row_count, dataset.column_count)


def _read_cleaned_frame(
    dataset: Dataset,
    run: CleaningRun,
    settings: Settings,
) -> pd.DataFrame:
    storage_root = settings.data_storage_dir.resolve()
    relative_path = Path(run.output_path)
    if relative_path.is_absolute() or relative_path.name != run.output_path:
        raise CsvUploadError(500, "storage_error", "The cleaned dataset path is invalid.")
    output_path = (storage_root / relative_path).resolve()
    try:
        output_path.relative_to(storage_root)
    except ValueError as error:
        raise CsvUploadError(
            500,
            "storage_error",
            "The cleaned dataset path is invalid.",
        ) from error
    return _read_frame_from_path(
        output_path,
        run.row_count_after,
        dataset.column_count,
    )


def serialize_cleaning_run(
    dataset: Dataset,
    run: CleaningRun,
    settings: Settings,
) -> CleaningRunResponse:
    try:
        rules = CleaningRequest.model_validate_json(run.rules_json)
        change_counts = json.loads(run.change_counts_json)
        quality_before = CleaningQualityMetrics.model_validate_json(run.quality_before_json)
        quality_after = CleaningQualityMetrics.model_validate_json(run.quality_after_json)
    except (ValueError, TypeError, KeyError) as error:
        logger.exception("Stored cleaning operation metadata is invalid.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The cleaning operation metadata could not be read.",
        ) from error

    cleaned_frame = _read_cleaned_frame(dataset, run, settings)
    return CleaningRunResponse(
        run_id=run.id,
        dataset_id=dataset.id,
        rules=rules,
        row_count_before=run.row_count_before,
        row_count_after=run.row_count_after,
        dropped_missing_rows=change_counts["dropped_missing_rows"],
        dropped_duplicate_rows=change_counts["dropped_duplicate_rows"],
        filled_missing_cells=change_counts["filled_missing_cells"],
        standardized_cells=change_counts["standardized_cells"],
        escaped_formula_cells=change_counts["escaped_formula_cells"],
        quality_before=quality_before,
        quality_after=quality_after,
        quality_after_report=analyze_frame(dataset.id, cleaned_frame),
        created_at=run.created_at,
    )


def _validate_columns(frame: pd.DataFrame, rules: CleaningRequest) -> None:
    known_columns = set(str(column) for column in frame.columns)
    unknown_columns = set(rules.standardize_columns) - known_columns
    unknown_columns.update(set(rules.missing_values.values) - known_columns)
    unknown_columns.update(set(rules.missing_values.columns) - known_columns)
    if unknown_columns:
        names = ", ".join(sorted(unknown_columns))
        raise CsvUploadError(
            422,
            "invalid_cleaning_rules",
            f"Cleaning rules reference unknown columns: {names}.",
        )
    if len(set(rules.missing_values.columns)) != len(rules.missing_values.columns):
        raise CsvUploadError(
            422,
            "invalid_cleaning_rules",
            "Statistical columns must not contain duplicates.",
        )
    if rules.missing_values.action == "fill":
        if rules.missing_values.value is None and not rules.missing_values.values:
            raise CsvUploadError(
                422,
                "invalid_cleaning_rules",
                "Provide a fill value or a value for each column with missing data.",
            )
        if rules.missing_values.value is not None and rules.missing_values.values:
            raise CsvUploadError(
                422,
                "invalid_cleaning_rules",
                "Use either one fill value or per-column values, not both.",
            )


def _missing_mask(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(lambda column: column.astype(str).str.strip().eq(""))


def _quality_metrics(frame: pd.DataFrame) -> CleaningQualityMetrics:
    return CleaningQualityMetrics(
        row_count=len(frame),
        missing_cell_count=int(_missing_mask(frame).to_numpy().sum()),
        duplicate_row_count=int(frame.duplicated(keep="first").sum()),
    )


def _normalize_number(value: float | int) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Number is not finite.")
    return format(value, ".15g")


def _is_finite_number(value: object) -> bool:
    if pd.isna(value):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _standardize_column(
    series: pd.Series,
    column_name: str,
    format_name: str,
) -> pd.Series:
    original = series.astype(str)
    non_missing = original.str.strip().ne("")

    if format_name == "trim":
        standardized = original.str.strip()
    elif format_name == "lowercase":
        standardized = original.str.lower()
    elif format_name == "uppercase":
        standardized = original.str.upper()
    elif format_name in {"number", "integer"}:
        parsed = pd.to_numeric(original.where(non_missing), errors="coerce")
        finite = parsed.map(_is_finite_number)
        invalid = non_missing & (parsed.isna() | ~finite)
        if invalid.any():
            raise CsvUploadError(
                422,
                "invalid_cleaning_rules",
                f"Column '{column_name}' contains values that cannot be converted to {format_name}.",
            )
        if format_name == "integer":
            fractional = parsed.notna() & parsed.mod(1).ne(0)
            if fractional.any():
                raise CsvUploadError(
                    422,
                    "invalid_cleaning_rules",
                    f"Column '{column_name}' contains non-integer values.",
                )
        standardized = original.copy()
        standardized.loc[parsed.notna()] = parsed.loc[parsed.notna()].map(_normalize_number)
    elif format_name == "date_iso":
        parsed_dates = pd.to_datetime(original.where(non_missing), errors="coerce", format="mixed")
        invalid = non_missing & parsed_dates.isna()
        if invalid.any():
            raise CsvUploadError(
                422,
                "invalid_cleaning_rules",
                f"Column '{column_name}' contains values that cannot be converted to ISO dates.",
            )
        standardized = original.copy()
        standardized.loc[parsed_dates.notna()] = parsed_dates.loc[parsed_dates.notna()].map(
            lambda value: value.isoformat()
        )
    else:
        raise CsvUploadError(
            422,
            "invalid_cleaning_rules",
            f"Unsupported format '{format_name}'.",
        )

    return standardized.astype(str)


def _apply_missing_value_action(
    frame: pd.DataFrame,
    options: MissingValueOptions,
) -> tuple[pd.DataFrame, int, int]:
    missing = _missing_mask(frame)
    dropped_rows = 0
    filled_cells = 0
    action = options.action
    if action == "keep":
        return frame, dropped_rows, filled_cells
    if action == "drop_rows":
        rows_to_drop = missing.any(axis=1)
        dropped_rows = int(rows_to_drop.sum())
        return frame.loc[~rows_to_drop].reset_index(drop=True), dropped_rows, filled_cells
    if action == "fill":
        for column_name in frame.columns:
            column = str(column_name)
            mask = missing[column_name]
            if not mask.any():
                continue
            if options.value is not None:
                replacement = options.value
            elif column in options.values:
                replacement = options.values[column]
            else:
                raise CsvUploadError(
                    422,
                    "invalid_cleaning_rules",
                    f"Provide a fill value for column '{column}'.",
                )
            frame.loc[mask, column_name] = replacement
            filled_cells += int(mask.sum())
        return frame, dropped_rows, filled_cells
    if action == "statistical":
        selected_columns = options.columns or [
            str(column)
            for column in frame.columns
            if missing[column].any()
        ]
        if not selected_columns or not any(missing[column].any() for column in selected_columns):
            raise CsvUploadError(
                422,
                "invalid_cleaning_rules",
                "No columns with missing values were selected for statistical filling.",
            )
        for column in selected_columns:
            mask = missing[column]
            if not mask.any():
                continue
            values = frame.loc[~mask, column].astype(str)
            if options.strategy == "mode":
                modes = values.mode(dropna=True)
                if modes.empty:
                    raise CsvUploadError(
                        422,
                        "invalid_cleaning_rules",
                        f"Column '{column}' has no values to use for mode imputation.",
                    )
                replacement = str(modes.iloc[0])
            else:
                numeric = pd.to_numeric(values, errors="coerce")
                if numeric.isna().any() or numeric.empty or not numeric.map(_is_finite_number).all():
                    raise CsvUploadError(
                        422,
                        "invalid_cleaning_rules",
                        f"Column '{column}' must contain only numeric values for {options.strategy} imputation.",
                    )
                statistic = numeric.mean() if options.strategy == "mean" else numeric.median()
                replacement = _normalize_number(float(statistic))
            frame.loc[mask, column] = replacement
            filled_cells += int(mask.sum())
        return frame, dropped_rows, filled_cells
    raise CsvUploadError(422, "invalid_cleaning_rules", "Unsupported missing-value action.")


def _safe_export_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    safe_frame = frame.copy(deep=True)
    escaped_count = 0
    for column in safe_frame.columns:
        values = safe_frame[column].astype(str)
        unsafe = values.str.match(_FORMULA_PREFIX)
        escaped_count += int(unsafe.sum())
        safe_frame.loc[unsafe, column] = "'" + values.loc[unsafe]
    return safe_frame, escaped_count


def _remove_partial_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove partial cleaned CSV.")


def clean_dataset(
    dataset: Dataset,
    settings: Settings,
    session: Session,
    rules: CleaningRequest,
) -> CleaningRunResponse:
    frame = _read_frame(dataset, settings)
    _validate_columns(frame, rules)
    original_frame = frame.copy(deep=True)
    quality_before = _quality_metrics(original_frame)
    standardized_cells = 0
    standardized_masks = pd.DataFrame(False, index=frame.index, columns=frame.columns)

    if rules.trim_whitespace:
        for column in frame.columns:
            original_values = frame[column].astype(str)
            frame[column] = _standardize_column(frame[column], str(column), "trim")
            standardized_masks[column] |= original_values != frame[column]
    for column_name, format_name in rules.standardize_columns.items():
        original_values = frame[column_name].astype(str)
        frame[column_name] = _standardize_column(
            frame[column_name],
            column_name,
            format_name,
        )
        standardized_masks[column_name] |= original_values != frame[column_name]
    standardized_cells = int(standardized_masks.to_numpy().sum())

    frame, dropped_missing_rows, filled_missing_cells = _apply_missing_value_action(
        frame,
        rules.missing_values,
    )
    dropped_duplicate_rows = 0
    if rules.remove_duplicate_rows:
        before_dedupe = len(frame)
        frame = frame.drop_duplicates(keep="first").reset_index(drop=True)
        dropped_duplicate_rows = before_dedupe - len(frame)

    safe_frame, escaped_formula_cells = _safe_export_frame(frame)
    quality_after = _quality_metrics(safe_frame)
    quality_after_report = analyze_frame(dataset.id, safe_frame)

    run_id = str(uuid4())
    relative_output_path = f"{dataset.id}-{run_id}-cleaned.csv"
    storage_dir = settings.data_storage_dir
    output_path = storage_dir / relative_output_path
    temporary_path = storage_dir / f".{run_id}.tmp"
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        with temporary_path.open("x", encoding="utf-8", newline="") as output_file:
            safe_frame.to_csv(output_file, index=False, lineterminator="\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, output_path)
    except (OSError, ValueError) as error:
        _remove_partial_file(temporary_path)
        logger.exception("Could not persist cleaned CSV.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The cleaned dataset could not be stored.",
        ) from error

    now = datetime.now(timezone.utc).isoformat()
    run = CleaningRun(
        id=run_id,
        dataset_id=dataset.id,
        rules_json=json.dumps(rules.model_dump(mode="json"), ensure_ascii=False),
        output_path=relative_output_path,
        row_count_before=len(original_frame),
        row_count_after=len(frame),
        change_counts_json=json.dumps(
            {
                "dropped_missing_rows": dropped_missing_rows,
                "dropped_duplicate_rows": dropped_duplicate_rows,
                "filled_missing_cells": filled_missing_cells,
                "standardized_cells": standardized_cells,
                "escaped_formula_cells": escaped_formula_cells,
            },
            ensure_ascii=False,
        ),
        quality_before_json=json.dumps(quality_before.model_dump(mode="json")),
        quality_after_json=json.dumps(quality_after.model_dump(mode="json")),
        created_at=now,
    )
    try:
        session.add(run)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        _remove_partial_file(output_path)
        logger.exception("Could not save cleaning operation metadata.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The cleaning operation could not be saved.",
        ) from error

    return CleaningRunResponse(
        run_id=run.id,
        dataset_id=dataset.id,
        rules=rules,
        row_count_before=run.row_count_before,
        row_count_after=run.row_count_after,
        dropped_missing_rows=dropped_missing_rows,
        dropped_duplicate_rows=dropped_duplicate_rows,
        filled_missing_cells=filled_missing_cells,
        standardized_cells=standardized_cells,
        escaped_formula_cells=escaped_formula_cells,
        quality_before=quality_before,
        quality_after=quality_after,
        quality_after_report=quality_after_report,
        created_at=run.created_at,
    )
