from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'quality.db'}",
        data_storage_dir=tmp_path / "uploads",
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def _upload_and_analyze(client: TestClient, filename: str, csv_content: bytes) -> dict:
    upload_response = client.post(
        "/api/datasets",
        files={"file": (filename, csv_content, "text/csv")},
    )
    assert upload_response.status_code == 201
    dataset_id = upload_response.json()["dataset_id"]

    analysis_response = client.post(f"/api/datasets/{dataset_id}/analyze")
    assert analysis_response.status_code == 200
    assert analysis_response.json()["dataset_id"] == dataset_id
    return analysis_response.json()


def test_analysis_reports_missing_values_duplicates_and_explainable_score(
    client: TestClient,
) -> None:
    original = b"device_id,temperature_c,remarks\na,10,ok\nb,,ok\nb,,ok\n"
    report = _upload_and_analyze(client, "sensor-readings.csv", original)

    assert report["row_count"] == 3
    assert report["column_count"] == 3
    assert report["issue_counts"] == {
        "missing_cells": 2,
        "duplicate_rows": 1,
        "inconsistent_values": 0,
    }
    columns = {column["name"]: column for column in report["columns"]}
    assert columns["temperature_c"]["missing_count"] == 2
    assert columns["temperature_c"]["inferred_type"] == "integer"
    assert columns["temperature_c"]["numerical_summary"] == {
        "count": 1,
        "minimum": 10.0,
        "maximum": 10.0,
        "mean": 10.0,
        "median": 10.0,
        "standard_deviation": None,
    }
    issues = {issue["code"]: issue for issue in report["issues"]}
    assert issues["missing_values"]["affected_columns"] == ["temperature_c"]
    assert issues["duplicate_rows"]["count"] == 1
    assert issues["duplicate_rows"]["affected_columns"] == [
        "device_id",
        "temperature_c",
        "remarks",
    ]
    assert len(report["score_breakdown"]) == 3
    assert report["quality_score"] == 81.11

    stored_original = next(client.app.state.settings.data_storage_dir.glob("*.csv"))
    assert stored_original.read_bytes() == original


def test_analysis_detects_mixed_values_and_date_columns_without_schema_assumptions(
    client: TestClient,
) -> None:
    content = (
        b"sample_code,reading,recorded_on\n"
        b"alpha,1.5,2024-01-02\n"
        b"beta,oops,2024-01-03\n"
        b"gamma,2.5,not-a-date\n"
    )
    report = _upload_and_analyze(client, "lab-export.csv", content)

    columns = {column["name"]: column for column in report["columns"]}
    assert columns["sample_code"]["inferred_type"] == "string"
    assert columns["reading"]["inferred_type"] == "number"
    assert columns["reading"]["inconsistent_value_count"] == 1
    assert columns["reading"]["numerical_summary"]["count"] == 2
    assert columns["reading"]["numerical_summary"]["mean"] == 2.0
    assert columns["recorded_on"]["inferred_type"] == "datetime"
    assert columns["recorded_on"]["inconsistent_value_count"] == 1
    assert report["issue_counts"]["inconsistent_values"] == 2
    inconsistency = next(
        issue for issue in report["issues"] if issue["code"] == "inconsistent_values"
    )
    assert inconsistency["affected_columns"] == ["reading", "recorded_on"]
    assert inconsistency["suggested_action"]


def test_analysis_recognizes_month_name_dates_with_invalid_values(client: TestClient) -> None:
    report = _upload_and_analyze(
        client,
        "readable-dates.csv",
        b"recorded_when\nJan 3 2024\n2024-01-03\nnot-a-date\n",
    )

    column = report["columns"][0]
    assert column["inferred_type"] == "datetime"
    assert column["inconsistent_value_count"] == 1
    assert report["issue_counts"]["inconsistent_values"] == 1


def test_analysis_handles_unfamiliar_columns_and_preserves_no_null_tokens(
    client: TestClient,
) -> None:
    content = (
        b"xylophone,voltage_millivolts,freeform\n"
        b"violet,12,NA\n"
        b"indigo,18,null\n"
        b"amber,24,N/A\n"
    )
    report = _upload_and_analyze(client, "custom-export.csv", content)

    columns = {column["name"]: column for column in report["columns"]}
    assert set(columns) == {"xylophone", "voltage_millivolts", "freeform"}
    assert columns["xylophone"]["inferred_type"] == "string"
    assert columns["voltage_millivolts"]["inferred_type"] == "integer"
    assert columns["voltage_millivolts"]["numerical_summary"]["mean"] == 18.0
    assert columns["freeform"]["missing_count"] == 0
    assert report["issue_counts"]["missing_cells"] == 0
    assert report["issue_counts"]["duplicate_rows"] == 0


def test_analyze_unknown_dataset_returns_stable_error(client: TestClient) -> None:
    response = client.post("/api/datasets/unknown/analyze")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "dataset_not_found"
