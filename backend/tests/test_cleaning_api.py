from collections.abc import Iterator
from csv import DictReader
from io import StringIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models.cleaning_run import CleaningRun


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'cleaning.db'}",
        data_storage_dir=tmp_path / "uploads",
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def _upload(client: TestClient, content: bytes, filename: str = "source.csv") -> str:
    response = client.post(
        "/api/datasets",
        files={"file": (filename, content, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["dataset_id"]


def _clean(client: TestClient, dataset_id: str, rules: dict) -> dict:
    response = client.post(f"/api/datasets/{dataset_id}/clean", json=rules)
    assert response.status_code == 201, response.text
    return response.json()


def _download_rows(client: TestClient, dataset_id: str) -> list[dict[str, str]]:
    response = client.get(f"/api/datasets/{dataset_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(DictReader(StringIO(response.text)))


def test_clean_removes_duplicates_preserves_original_and_downloads_cleaned_result(
    client: TestClient,
) -> None:
    original = b"specimen,reading\nA,10\nB,20\nB,20\n"
    dataset_id = _upload(client, original, "measurements.csv")

    run = _clean(client, dataset_id, {"remove_duplicate_rows": True})

    assert run["row_count_before"] == 3
    assert run["row_count_after"] == 2
    assert run["dropped_duplicate_rows"] == 1
    assert run["quality_before"]["duplicate_row_count"] == 1
    assert run["quality_after"]["duplicate_row_count"] == 0
    assert run["quality_after_report"]["row_count"] == 2
    assert run["quality_after_report"]["issue_counts"]["missing_cells"] == 0
    assert run["quality_after_report"]["columns"][1]["numerical_summary"]["mean"] == 15.0
    latest_run = client.get(f"/api/datasets/{dataset_id}/cleaning-runs/latest")
    assert latest_run.status_code == 200
    assert latest_run.json()["run_id"] == run["run_id"]
    assert latest_run.json()["quality_after_report"]["row_count"] == 2
    assert (
        latest_run.json()["quality_after_report"]["columns"][1]["numerical_summary"]["mean"]
        == 15.0
    )
    assert run["rules"]["remove_duplicate_rows"] is True
    assert _download_rows(client, dataset_id) == [
        {"specimen": "A", "reading": "10"},
        {"specimen": "B", "reading": "20"},
    ]

    original_file = next(
        path
        for path in client.app.state.settings.data_storage_dir.glob("*.csv")
        if path.name == f"{dataset_id}.csv"
    )
    assert original_file.read_bytes() == original
    with client.app.state.session_factory() as session:
        stored_run = session.scalar(
            select(CleaningRun).where(CleaningRun.id == run["run_id"])
        )
    assert stored_run is not None
    assert stored_run.rules_json == '{"remove_duplicate_rows": true, "trim_whitespace": false, "missing_values": {"action": "keep", "value": null, "values": {}, "strategy": null, "columns": []}, "standardize_columns": {}}'


def test_end_to_end_unfamiliar_dataset_quality_cleaned_insights_and_export(
    client: TestClient,
) -> None:
    original = (
        b"record_code,metric_42,observed_when\n"
        b"A,1,Jan 3 2024\n"
        b"A,1,Jan 3 2024\n"
        b"B,,2024-01-04\n"
        b"C,3,not-a-date\n"
    )
    upload = client.post(
        "/api/datasets",
        files={"file": ("unfamiliar.csv", original, "text/csv")},
    )
    assert upload.status_code == 201
    dataset_id = upload.json()["dataset_id"]
    assert upload.json()["columns"] == ["record_code", "metric_42", "observed_when"]

    preview = client.get(f"/api/datasets/{dataset_id}/preview?limit=2")
    assert preview.status_code == 200
    assert preview.json()["rows"][0] == {
        "record_code": "A",
        "metric_42": "1",
        "observed_when": "Jan 3 2024",
    }

    analysis = client.post(f"/api/datasets/{dataset_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["row_count"] == 4
    assert analysis.json()["issue_counts"]["missing_cells"] == 1
    columns = {column["name"]: column for column in analysis.json()["columns"]}
    assert columns["observed_when"]["inferred_type"] == "datetime"
    assert columns["observed_when"]["inconsistent_value_count"] == 1

    run = _clean(
        client,
        dataset_id,
        {
            "remove_duplicate_rows": True,
            "missing_values": {"action": "drop_rows"},
        },
    )
    assert run["row_count_before"] == 4
    assert run["row_count_after"] == 2
    assert run["quality_after"]["missing_cell_count"] == 0
    assert run["quality_after"]["duplicate_row_count"] == 0
    assert run["quality_after_report"]["row_count"] == 2
    assert run["quality_after_report"]["issue_counts"]["missing_cells"] == 0
    cleaned_columns = {
        column["name"]: column for column in run["quality_after_report"]["columns"]
    }
    assert cleaned_columns["metric_42"]["numerical_summary"]["mean"] == 2.0

    assert _download_rows(client, dataset_id) == [
        {"record_code": "A", "metric_42": "1", "observed_when": "Jan 3 2024"},
        {"record_code": "C", "metric_42": "3", "observed_when": "not-a-date"},
    ]
    stored_original = next(
        path
        for path in client.app.state.settings.data_storage_dir.glob("*.csv")
        if path.name == f"{dataset_id}.csv"
    )
    assert stored_original.read_bytes() == original


def test_clean_drops_rows_with_missing_cells(client: TestClient) -> None:
    dataset_id = _upload(client, b"record,zone\n1,north\n2,\n3,south\n")

    run = _clean(
        client,
        dataset_id,
        {"missing_values": {"action": "drop_rows"}},
    )

    assert run["dropped_missing_rows"] == 1
    assert run["row_count_after"] == 2
    assert run["quality_after"]["missing_cell_count"] == 0
    assert _download_rows(client, dataset_id) == [
        {"record": "1", "zone": "north"},
        {"record": "3", "zone": "south"},
    ]


@pytest.mark.parametrize(
    ("fill_options", "expected_rows"),
    [
        (
            {"value": "unspecified"},
            [
                {"glyph": "oak", "region": "unspecified"},
                {"glyph": "elm", "region": "west"},
            ],
        ),
        (
            {"values": {"region": "unknown", "glyph": "untitled"}},
            [
                {"glyph": "oak", "region": "unknown"},
                {"glyph": "elm", "region": "west"},
            ],
        ),
    ],
)
def test_clean_fills_missing_cells_with_explicit_values(
    client: TestClient,
    fill_options: dict,
    expected_rows: list[dict[str, str]],
) -> None:
    dataset_id = _upload(client, b"glyph,region\noak,\nelm,west\n")

    run = _clean(
        client,
        dataset_id,
        {"missing_values": {"action": "fill", **fill_options}},
    )

    assert run["filled_missing_cells"] == 1
    assert run["quality_after"]["missing_cell_count"] == 0
    assert _download_rows(client, dataset_id) == expected_rows


@pytest.mark.parametrize(
    ("strategy", "column", "expected_values"),
    [
        ("mean", "unknown_metric", ["1", "2", "4.33333333333333", "10"]),
        ("median", "unknown_metric", ["1", "2", "2", "10"]),
        ("mode", "odd_label", ["x", "x", "x", "z"]),
    ],
)
def test_clean_supports_statistical_missing_value_strategies(
    client: TestClient,
    strategy: str,
    column: str,
    expected_values: list[str],
) -> None:
    content = b"unknown_metric,odd_label\n1,x\n2,x\n,\n10,z\n"
    dataset_id = _upload(client, content)

    run = _clean(
        client,
        dataset_id,
        {
            "missing_values": {
                "action": "statistical",
                "strategy": strategy,
                "columns": [column],
            }
        },
    )

    assert run["filled_missing_cells"] == 1
    assert [row[column] for row in _download_rows(client, dataset_id)] == expected_values


def test_clean_standardizes_unfamiliar_columns_and_escapes_spreadsheet_formulas(
    client: TestClient,
) -> None:
    content = (
        b"artifact_code,quantity_unknown,observed_when,freeform,label\n"
        b"  AB-1  ,001,2024-01-02,=2+2,MiXeD\n"
        b"  CD-2  ,2,Jan 3 2024,plain,plain\n"
    )
    dataset_id = _upload(client, content, "custom.csv")

    run = _clean(
        client,
        dataset_id,
        {
            "standardize_columns": {
                "artifact_code": "trim",
                "quantity_unknown": "integer",
                "observed_when": "date_iso",
                "freeform": "lowercase",
                "label": "lowercase",
            }
        },
    )

    assert run["standardized_cells"] == 6
    assert run["escaped_formula_cells"] == 1
    assert _download_rows(client, dataset_id) == [
        {
            "artifact_code": "AB-1",
            "quantity_unknown": "1",
            "observed_when": "2024-01-02T00:00:00",
            "freeform": "'=2+2",
            "label": "mixed",
        },
        {
            "artifact_code": "CD-2",
            "quantity_unknown": "2",
            "observed_when": "2024-01-03T00:00:00",
            "freeform": "plain",
            "label": "plain",
        },
    ]


def test_clean_rejects_locale_grouped_numbers_without_creating_a_run(
    client: TestClient,
) -> None:
    original = b"metric_unknown\n\"1,234.50\"\n"
    dataset_id = _upload(client, original)

    response = client.post(
        f"/api/datasets/{dataset_id}/clean",
        json={"standardize_columns": {"metric_unknown": "number"}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cleaning_rules"
    assert client.get(f"/api/datasets/{dataset_id}/download").status_code == 404
    stored_original = next(client.app.state.settings.data_storage_dir.glob(f"{dataset_id}.csv"))
    assert stored_original.read_bytes() == original


@pytest.mark.parametrize(
    "rules",
    [
        {"missing_values": {"action": "fill"}},
        {"missing_values": {"action": "drop_rows", "value": "x"}},
        {"standardize_columns": {"unknown_column": "trim"}},
        {
            "missing_values": {
                "action": "fill",
                "values": {"region": "unknown"},
            }
        },
        {"standardize_columns": {"quantity": "integer"}},
        {"remove_duplicate_rows": "yes"},
        {"unexpected_option": True},
    ],
)
def test_invalid_cleaning_parameters_are_rejected_without_creating_a_run(
    client: TestClient,
    rules: dict,
) -> None:
    dataset_id = _upload(client, b"quantity,region\n,\nnot-a-number,west\n")

    response = client.post(f"/api/datasets/{dataset_id}/clean", json=rules)

    assert response.status_code == 422
    assert response.json()["error"]["code"] in {
        "invalid_cleaning_rules",
        "validation_error",
    }
    assert client.get(f"/api/datasets/{dataset_id}/download").status_code == 404


def test_download_requires_a_successful_cleaning_run(client: TestClient) -> None:
    dataset_id = _upload(client, b"entry\nvalue\n")

    response = client.get(f"/api/datasets/{dataset_id}/download")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "cleaned_dataset_not_found"
    latest_run = client.get(f"/api/datasets/{dataset_id}/cleaning-runs/latest")
    assert latest_run.status_code == 404
    assert latest_run.json()["error"]["code"] == "cleaning_run_not_found"


def test_clean_retries_always_start_from_original_and_latest_run_is_downloaded(
    client: TestClient,
) -> None:
    original = b"item,group\nx, red \nx, red \ny, blue\n"
    dataset_id = _upload(client, original)
    first_run = _clean(client, dataset_id, {"remove_duplicate_rows": True})
    second_run = _clean(client, dataset_id, {"trim_whitespace": True})

    assert first_run["row_count_before"] == 3
    assert second_run["row_count_before"] == 3
    assert _download_rows(client, dataset_id) == [
        {"item": "x", "group": "red"},
        {"item": "x", "group": "red"},
        {"item": "y", "group": "blue"},
    ]
