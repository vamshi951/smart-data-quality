from pydantic import BaseModel


class NumericalSummary(BaseModel):
    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    standard_deviation: float | None


class ColumnQualityReport(BaseModel):
    name: str
    inferred_type: str
    non_missing_count: int
    missing_count: int
    inconsistent_value_count: int
    numerical_summary: NumericalSummary | None = None


class QualityIssue(BaseModel):
    code: str
    count: int
    affected_columns: list[str]
    suggested_action: str


class ScoreComponent(BaseModel):
    issue: str
    affected_rate: float
    maximum_penalty: float
    penalty: float
    rule: str


class QualityReport(BaseModel):
    dataset_id: str
    analyzed_at: str
    row_count: int
    column_count: int
    quality_score: float
    issue_counts: dict[str, int]
    columns: list[ColumnQualityReport]
    issues: list[QualityIssue]
    score_breakdown: list[ScoreComponent]
