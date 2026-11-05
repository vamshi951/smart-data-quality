from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.schemas.quality import QualityReport


MissingAction = Literal["keep", "drop_rows", "fill", "statistical"]
StatisticalStrategy = Literal["mean", "median", "mode"]
ColumnFormat = Literal["trim", "lowercase", "uppercase", "number", "integer", "date_iso"]


class MissingValueOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: MissingAction = "keep"
    value: str | None = None
    values: dict[str, str] = Field(default_factory=dict)
    strategy: StatisticalStrategy | None = None
    columns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_option_combinations(self) -> "MissingValueOptions":
        if self.action != "fill" and (self.value is not None or self.values):
            raise ValueError("value and values can only be used with action='fill'.")
        if self.action != "statistical" and (self.strategy is not None or self.columns):
            raise ValueError("strategy and columns can only be used with action='statistical'.")
        if self.action == "statistical" and self.strategy is None:
            raise ValueError("A statistical strategy is required for action='statistical'.")
        return self


class CleaningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remove_duplicate_rows: StrictBool = False
    trim_whitespace: StrictBool = False
    missing_values: MissingValueOptions = Field(default_factory=MissingValueOptions)
    standardize_columns: dict[str, ColumnFormat] = Field(default_factory=dict)


class CleaningQualityMetrics(BaseModel):
    row_count: int
    missing_cell_count: int
    duplicate_row_count: int


class CleaningRunResponse(BaseModel):
    run_id: str
    dataset_id: str
    rules: CleaningRequest
    row_count_before: int
    row_count_after: int
    dropped_missing_rows: int
    dropped_duplicate_rows: int
    filled_missing_cells: int
    standardized_cells: int
    escaped_formula_cells: int
    quality_before: CleaningQualityMetrics
    quality_after: CleaningQualityMetrics
    quality_after_report: QualityReport
    created_at: str
