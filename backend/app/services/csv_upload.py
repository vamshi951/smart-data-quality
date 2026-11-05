import csv
import io
import json
import logging
import os
import threading
from pathlib import Path
from uuid import uuid4

import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)
_CSV_FIELD_SIZE_LOCK = threading.Lock()


class CsvUploadError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _safe_filename(filename: str | None) -> str:
    if not filename:
        raise CsvUploadError(422, "invalid_filename", "A CSV filename is required.")
    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    if not basename or len(basename) > 255 or any(ord(char) < 32 for char in basename):
        raise CsvUploadError(422, "invalid_filename", "The filename is invalid.")
    if Path(basename).suffix.lower() != ".csv":
        raise CsvUploadError(415, "unsupported_media_type", "Only .csv files are supported.")
    return basename


def _remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove a partial CSV artifact.")


def resolve_original_path(settings: Settings, dataset: Dataset) -> Path:
    storage_root = settings.data_storage_dir.resolve()
    relative_path = Path(dataset.original_path)
    if relative_path.is_absolute() or relative_path.name != dataset.original_path:
        raise CsvUploadError(500, "storage_error", "The stored dataset path is invalid.")
    source_path = (storage_root / relative_path).resolve()
    try:
        source_path.relative_to(storage_root)
    except ValueError as error:
        raise CsvUploadError(
            500,
            "storage_error",
            "The stored dataset path is invalid.",
        ) from error
    return source_path


def _validate_csv(content: bytes, settings: Settings) -> tuple[list[str], int]:
    if not content:
        raise CsvUploadError(422, "invalid_csv", "The uploaded CSV is empty.")

    try:
        text = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise CsvUploadError(
            415,
            "unsupported_encoding",
            "The CSV must use UTF-8 encoding.",
        ) from error

    with _CSV_FIELD_SIZE_LOCK:
        previous_field_size_limit = csv.field_size_limit()
        try:
            csv.field_size_limit(max(previous_field_size_limit, settings.max_upload_size_bytes))
            reader = csv.reader(io.StringIO(text, newline=""), strict=True)
            try:
                headers = next(reader, None)
                if headers is None or not headers:
                    raise CsvUploadError(422, "invalid_headers", "The CSV must include a header row.")
                if len(headers) > settings.max_csv_columns:
                    raise CsvUploadError(
                        422,
                        "column_limit_exceeded",
                        f"The CSV exceeds the {settings.max_csv_columns}-column limit.",
                    )
                if any(not header.strip() for header in headers):
                    raise CsvUploadError(
                        422,
                        "invalid_headers",
                        "Column names must not be blank.",
                    )
                normalized_headers = [header.strip() for header in headers]
                if len(set(normalized_headers)) != len(normalized_headers):
                    raise CsvUploadError(
                        422,
                        "invalid_headers",
                        "Column names must be unique.",
                    )

                row_count = 0
                for row in reader:
                    if len(row) != len(headers):
                        raise CsvUploadError(
                            422,
                            "invalid_csv",
                            "Every CSV row must have the same number of fields as the header.",
                        )
                    row_count += 1
                    if row_count > settings.max_csv_rows:
                        raise CsvUploadError(
                            422,
                            "row_limit_exceeded",
                            f"The CSV exceeds the {settings.max_csv_rows}-row limit.",
                        )
            except csv.Error as error:
                raise CsvUploadError(
                    422,
                    "invalid_csv",
                    "The uploaded CSV contains malformed quoting or rows.",
                ) from error
        finally:
            csv.field_size_limit(previous_field_size_limit)

    if row_count == 0:
        raise CsvUploadError(422, "invalid_csv", "The CSV must contain at least one data row.")

    parsed_rows = 0
    try:
        frame_chunks = pd.read_csv(
            io.BytesIO(content),
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
            on_bad_lines="error",
            engine="c",
            chunksize=1_000,
        )
        for chunk in frame_chunks:
            parsed_rows += len(chunk)
    except (EmptyDataError, ParserError, UnicodeDecodeError, ValueError) as error:
        raise CsvUploadError(
            422,
            "invalid_csv",
            "The uploaded file could not be parsed as a supported CSV.",
        ) from error

    if parsed_rows != row_count:
        raise CsvUploadError(
            422,
            "invalid_csv",
            "The CSV structure could not be parsed consistently.",
        )
    return headers, row_count


def store_csv_dataset(
    session: Session,
    filename: str | None,
    content: bytes,
    settings: Settings,
) -> Dataset:
    safe_filename = _safe_filename(filename)
    if len(content) > settings.max_upload_size_bytes:
        raise CsvUploadError(
            413,
            "file_too_large",
            f"The uploaded file exceeds the {settings.max_upload_size_bytes}-byte limit.",
        )

    columns, row_count = _validate_csv(content, settings)
    dataset_id = str(uuid4())
    relative_path = f"{dataset_id}.csv"
    storage_dir = settings.data_storage_dir
    temporary_path: Path | None = None
    original_path = storage_dir / relative_path
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = storage_dir / f".{dataset_id}.tmp"
        with temporary_path.open("xb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, original_path)
    except OSError as error:
        if temporary_path is not None:
            _remove_file(temporary_path)
        logger.exception("Could not persist uploaded CSV.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The uploaded file could not be stored.",
        ) from error

    dataset = Dataset(
        id=dataset_id,
        original_filename=safe_filename,
        original_path=relative_path,
        status="ready",
        byte_size=len(content),
        row_count=row_count,
        column_count=len(columns),
        columns_json=json.dumps(columns, ensure_ascii=False),
    )
    try:
        session.add(dataset)
        session.flush()
        session.refresh(dataset)
        session.commit()
    except SQLAlchemyError as error:
        session.rollback()
        _remove_file(original_path)
        logger.exception("Could not save uploaded CSV metadata.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The uploaded dataset could not be saved.",
        ) from error

    return dataset


def read_preview(
    dataset: Dataset,
    settings: Settings,
    limit: int,
    offset: int,
) -> list[dict[str, str]]:
    source_path = resolve_original_path(settings, dataset)
    rows: list[dict[str, str]] = []
    current_offset = 0
    try:
        chunks = pd.read_csv(
            source_path,
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
            on_bad_lines="error",
            engine="c",
            chunksize=1_000,
        )
        for chunk in chunks:
            chunk_end = current_offset + len(chunk)
            if chunk_end > offset:
                start = max(0, offset - current_offset)
                available = limit - len(rows)
                selected = chunk.iloc[start : start + available]
                rows.extend(
                    {
                        str(column): "" if pd.isna(value) else str(value)
                        for column, value in row.items()
                    }
                    for row in selected.to_dict(orient="records")
                )
            current_offset = chunk_end
            if len(rows) >= limit:
                break
    except (OSError, EmptyDataError, ParserError, UnicodeDecodeError, ValueError) as error:
        logger.exception("Could not read stored CSV preview.")
        raise CsvUploadError(
            500,
            "storage_error",
            "The stored dataset could not be read.",
        ) from error
    return rows
