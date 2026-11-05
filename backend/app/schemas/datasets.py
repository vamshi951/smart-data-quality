from pydantic import BaseModel, ConfigDict


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: str
    filename: str
    status: str
    byte_size: int
    row_count: int
    column_count: int
    columns: list[str]
    created_at: str
    updated_at: str


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, str]]
    total_rows: int
    limit: int
    offset: int
