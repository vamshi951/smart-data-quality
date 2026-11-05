import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.dataset import Dataset
from app.schemas.quality import (
    ColumnQualityReport,
    NumericalSummary,
    QualityIssue,
    QualityReport,
    ScoreComponent,
)
from app.services.csv_upload import CsvUploadError, resolve_original_path

logger = logging.getLogger(__name__)

_MONTH_NAME = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_PATTERN = re.compile(
    rf"^(?:\d{{4}}[-/]\d{{1,2}}[-/]\d{{1,2}}|\d{{1,2}}[-/]\d{{1,2}}[-/]\d{{2,4}}|"
    rf"{_MONTH_NAME}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{2,4}})?|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_NAME}\.?\s+\d{{2,4}})"
    r"(?:[ T].*)?$",
    re.IGNORECASE,
)
_BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n", "t", "f"}
_DOMINANT_TYPE_THRESHOLD = 0.6


def _read_original(dataset: Dataset, settings: Settings) -> pd.DataFrame:
    source_path = resolve_original_path(settings, dataset)
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
        logger.exception("Could not read stored CSV for quality analysis.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The stored dataset could not be read for analysis.",
        ) from error

    if len(frame) != dataset.row_count or len(frame.columns) != dataset.column_count:
        raise CsvUploadError(
            500,
            "storage_error",
            "The stored dataset no longer matches its saved metadata.",
        )
    return frame


def _numeric_summary(values: pd.Series) -> NumericalSummary | None:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric[numeric.map(lambda value: math.isfinite(float(value)))]
    if numeric.empty:
        return None

    standard_deviation = numeric.std()
    return NumericalSummary(
        count=int(numeric.count()),
        minimum=float(numeric.min()),
        maximum=float(numeric.max()),
        mean=float(numeric.mean()),
        median=float(numeric.median()),
        standard_deviation=(
            float(standard_deviation) if math.isfinite(float(standard_deviation)) else None
        ),
    )


def _classify_values(values: pd.Series) -> tuple[str, int, NumericalSummary | None]:
    if values.empty:
        return "unknown", 0, None

    numeric = pd.to_numeric(values, errors="coerce")
    numeric_mask = numeric.notna() & numeric.map(
        lambda value: math.isfinite(float(value)) if pd.notna(value) else False
    )
    boolean_mask = values.str.strip().str.lower().isin(_BOOLEAN_VALUES)
    date_candidates = values.str.strip().str.match(_DATE_PATTERN)
    parsed_dates = pd.to_datetime(
        values.where(date_candidates),
        format="mixed",
        errors="coerce",
        utc=True,
    )
    datetime_mask = date_candidates & parsed_dates.notna()

    categories = pd.Series("string", index=values.index, dtype="object")
    categories.loc[numeric_mask] = "number"
    categories.loc[datetime_mask] = "datetime"
    categories.loc[boolean_mask] = "boolean"
    counts = Counter(categories.tolist())
    dominant_type, dominant_count = counts.most_common(1)[0]
    inconsistent_count = len(values) - dominant_count

    if len(counts) == 1:
        inferred_type = dominant_type
    elif dominant_count / len(values) >= _DOMINANT_TYPE_THRESHOLD:
        inferred_type = dominant_type
    else:
        inferred_type = "mixed"

    if inferred_type == "number":
        numeric_values = numeric[numeric_mask]
        if not numeric_values.empty and numeric_values.map(
            lambda value: float(value).is_integer()
        ).all():
            inferred_type = "integer"

    return inferred_type, inconsistent_count, _numeric_summary(values)


def _score_component(issue: str, affected: int, total: int, maximum: float) -> ScoreComponent:
    rate = affected / total if total else 0.0
    penalty = float(
        (Decimal(str(maximum)) * affected / total if total else Decimal(0)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )
    return ScoreComponent(
        issue=issue,
        affected_rate=round(rate, 6),
        maximum_penalty=maximum,
        penalty=penalty,
        rule=f"Deduct {maximum:g} × affected rate ({affected}/{total}).",
    )


def analyze_frame(dataset_id: str, frame: pd.DataFrame) -> QualityReport:
    missing_masks = frame.apply(lambda column: column.str.strip().eq(""))
    columns: list[ColumnQualityReport] = []
    missing_by_column: dict[str, int] = {}
    inconsistent_by_column: dict[str, int] = {}

    for column_name in frame.columns:
        values = frame.loc[~missing_masks[column_name], column_name].astype(str)
        inferred_type, inconsistent_count, numerical_summary = _classify_values(values)
        missing_count = int(missing_masks[column_name].sum())
        missing_by_column[str(column_name)] = missing_count
        inconsistent_by_column[str(column_name)] = inconsistent_count
        columns.append(
            ColumnQualityReport(
                name=str(column_name),
                inferred_type=inferred_type,
                non_missing_count=len(values),
                missing_count=missing_count,
                inconsistent_value_count=inconsistent_count,
                numerical_summary=numerical_summary,
            )
        )

    missing_count = sum(missing_by_column.values())
    duplicate_count = int(frame.duplicated(keep="first").sum())
    invalid_count = sum(inconsistent_by_column.values())
    row_count = len(frame)
    cell_count = row_count * len(frame.columns)
    score_breakdown = [
        _score_component("missing_values", missing_count, cell_count, 40.0),
        _score_component("duplicate_rows", duplicate_count, row_count, 30.0),
        _score_component("inconsistent_values", invalid_count, cell_count, 30.0),
    ]
    quality_score = float(
        max(
            Decimal(0),
            Decimal(100)
            - sum(
                (Decimal(str(item.penalty)) for item in score_breakdown),
                start=Decimal(0),
            ),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    issues: list[QualityIssue] = []
    if missing_count:
        issues.append(
            QualityIssue(
                code="missing_values",
                count=missing_count,
                affected_columns=[
                    name for name, count in missing_by_column.items() if count > 0
                ],
                suggested_action=(
                    "Review affected columns; fill values explicitly or drop rows only "
                    "when appropriate for the analysis."
                ),
            )
        )
    if duplicate_count:
        issues.append(
            QualityIssue(
                code="duplicate_rows",
                count=duplicate_count,
                affected_columns=[str(name) for name in frame.columns],
                suggested_action=(
                    "Review exact duplicate rows and remove them only if repeated records "
                    "are not meaningful."
                ),
            )
        )
    if invalid_count:
        issues.append(
            QualityIssue(
                code="inconsistent_values",
                count=invalid_count,
                affected_columns=[
                    name for name, count in inconsistent_by_column.items() if count > 0
                ],
                suggested_action=(
                    "Inspect values that differ from the predominant detectable type; "
                    "correct them only after checking the source semantics."
                ),
            )
        )

    report = QualityReport(
        dataset_id=dataset_id,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        row_count=row_count,
        column_count=len(frame.columns),
        quality_score=quality_score,
        issue_counts={
            "missing_cells": missing_count,
            "duplicate_rows": duplicate_count,
            "inconsistent_values": invalid_count,
        },
        columns=columns,
        issues=issues,
        score_breakdown=score_breakdown,
    )
    return report


def analyze_dataset(
    dataset: Dataset,
    settings: Settings,
    session: Session,
) -> QualityReport:
    frame = _read_original(dataset, settings)
    report = analyze_frame(dataset.id, frame)
    try:
        dataset.initial_quality_json = json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
        )
        session.commit()
    except (SQLAlchemyError, ValueError) as error:
        session.rollback()
        logger.exception("Could not persist quality analysis report.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The quality analysis report could not be saved.",
        ) from error

    return report
