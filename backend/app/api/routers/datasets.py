import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cleaning_run import CleaningRun
from app.database.session import get_db_session
from app.models.dataset import Dataset
from app.schemas.cleaning import CleaningRequest, CleaningRunResponse
from app.schemas.datasets import DatasetPreviewResponse, DatasetResponse
from app.schemas.quality import QualityReport
from app.services.csv_upload import CsvUploadError, read_preview, store_csv_dataset
from app.services.data_cleaning import clean_dataset, serialize_cleaning_run
from app.services.quality_analysis import analyze_dataset

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _serialize_dataset(dataset: Dataset) -> DatasetResponse:
    return DatasetResponse(
        dataset_id=dataset.id,
        filename=dataset.original_filename,
        status=dataset.status,
        byte_size=dataset.byte_size,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=json.loads(dataset.columns_json),
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def _raise_upload_error(error: CsvUploadError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={
            "code": error.code,
            "message": error.message,
            "details": [],
        },
    ) from error


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> DatasetResponse:
    settings = request.app.state.settings
    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "file_too_large",
                "message": f"The uploaded file exceeds the {settings.max_upload_size_bytes}-byte limit.",
                "details": [],
            },
        )
    try:
        dataset = store_csv_dataset(session, file.filename, content, settings)
    except CsvUploadError as error:
        _raise_upload_error(error)
    return _serialize_dataset(dataset)


@router.get("", response_model=list[DatasetResponse])
def list_datasets(session: Session = Depends(get_db_session)) -> list[DatasetResponse]:
    datasets = session.scalars(
        select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc())
    ).all()
    return [_serialize_dataset(dataset) for dataset in datasets]


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: str,
    session: Session = Depends(get_db_session),
) -> DatasetResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dataset_not_found", "message": "Dataset not found.", "details": []},
        )
    return _serialize_dataset(dataset)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
) -> DatasetPreviewResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dataset_not_found", "message": "Dataset not found.", "details": []},
        )
    settings = request.app.state.settings
    if limit > settings.max_preview_rows:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_preview_limit",
                "message": f"The preview limit cannot exceed {settings.max_preview_rows}.",
                "details": [],
            },
        )
    columns = json.loads(dataset.columns_json)
    try:
        rows = read_preview(dataset, settings, limit, offset)
    except CsvUploadError as error:
        _raise_upload_error(error)
    return DatasetPreviewResponse(
        dataset_id=dataset.id,
        columns=columns,
        rows=rows,
        total_rows=dataset.row_count,
        limit=limit,
        offset=offset,
    )


@router.post("/{dataset_id}/analyze", response_model=QualityReport)
def analyze_dataset_quality(
    dataset_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
) -> QualityReport:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dataset_not_found", "message": "Dataset not found.", "details": []},
        )
    try:
        return analyze_dataset(dataset, request.app.state.settings, session)
    except CsvUploadError as error:
        _raise_upload_error(error)


@router.post(
    "/{dataset_id}/clean",
    response_model=CleaningRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def clean_uploaded_dataset(
    dataset_id: str,
    request: Request,
    rules: CleaningRequest,
    session: Session = Depends(get_db_session),
) -> CleaningRunResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dataset_not_found", "message": "Dataset not found.", "details": []},
        )
    try:
        return clean_dataset(dataset, request.app.state.settings, session, rules)
    except CsvUploadError as error:
        _raise_upload_error(error)


@router.get("/{dataset_id}/cleaning-runs/latest", response_model=CleaningRunResponse)
def get_latest_cleaning_run(
    dataset_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
) -> CleaningRunResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dataset_not_found", "message": "Dataset not found.", "details": []},
        )
    run = session.scalar(
        select(CleaningRun)
        .where(CleaningRun.dataset_id == dataset_id)
        .order_by(CleaningRun.created_at.desc(), CleaningRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "cleaning_run_not_found",
                "message": "No cleaning run is available for this dataset.",
                "details": [],
            },
        )
    try:
        return serialize_cleaning_run(dataset, run, request.app.state.settings)
    except CsvUploadError as error:
        _raise_upload_error(error)


@router.get("/{dataset_id}/download")
def download_cleaned_dataset(
    dataset_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
) -> FileResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dataset_not_found", "message": "Dataset not found.", "details": []},
        )

    run = session.scalar(
        select(CleaningRun)
        .where(CleaningRun.dataset_id == dataset_id)
        .order_by(CleaningRun.created_at.desc(), CleaningRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "cleaned_dataset_not_found",
                "message": "No cleaned dataset is available for download.",
                "details": [],
            },
        )

    storage_root = request.app.state.settings.data_storage_dir.resolve()
    relative_path = Path(run.output_path)
    if relative_path.is_absolute() or relative_path.name != run.output_path:
        raise HTTPException(
            status_code=500,
            detail={"code": "storage_error", "message": "The cleaned dataset is unavailable.", "details": []},
        )
    output_path = (storage_root / relative_path).resolve()
    try:
        output_path.relative_to(storage_root)
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail={"code": "storage_error", "message": "The cleaned dataset is unavailable.", "details": []},
        ) from error
    if not output_path.is_file():
        raise HTTPException(
            status_code=500,
            detail={"code": "storage_error", "message": "The cleaned dataset is unavailable.", "details": []},
        )

    filename = f"cleaned_{dataset.original_filename}"
    return FileResponse(
        output_path,
        media_type="text/csv",
        filename=filename,
    )
