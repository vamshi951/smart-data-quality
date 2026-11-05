from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.dataset import Dataset
from app.services.csv_upload import CsvUploadError, read_preview


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'datasets.db'}",
        data_storage_dir=tmp_path / "uploads",
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_upload_list_detail_preview_and_preserve_original(client: TestClient) -> None:
    content = b'\xef\xbb\xbfname,city\n"Ada, Lovelace",London\nGrace,New York\n'
    response = client.post(
        "/api/datasets",
        files={"file": ("people.csv", content, "text/csv")},
    )

    assert response.status_code == 201
    dataset = response.json()
    dataset_id = dataset["dataset_id"]
    assert dataset["filename"] == "people.csv"
    assert dataset["status"] == "ready"
    assert dataset["row_count"] == 2
    assert dataset["column_count"] == 2
    assert dataset["columns"] == ["name", "city"]
    assert "original_path" not in dataset

    listed = client.get("/api/datasets")
    assert listed.status_code == 200
    assert [item["dataset_id"] for item in listed.json()] == [dataset_id]

    detail = client.get(f"/api/datasets/{dataset_id}")
    assert detail.status_code == 200
    assert detail.json() == dataset

    preview = client.get(f"/api/datasets/{dataset_id}/preview?limit=1&offset=1")
    assert preview.status_code == 200
    assert preview.json() == {
        "dataset_id": dataset_id,
        "columns": ["name", "city"],
        "rows": [{"name": "Grace", "city": "New York"}],
        "total_rows": 2,
        "limit": 1,
        "offset": 1,
    }

    original_files = list((client.app.state.settings.data_storage_dir).glob("*.csv"))
    assert len(original_files) == 1
    assert original_files[0].read_bytes() == content


@pytest.mark.parametrize(
    ("filename", "content", "expected_status", "expected_code"),
    [
        ("empty.csv", b"", 422, "invalid_csv"),
        ("header-only.csv", b"name,city\n", 422, "invalid_csv"),
        ("missing-headers.csv", b"\nAda,Lovelace\n", 422, "invalid_headers"),
        ("duplicate.csv", b"name,name\nAda,Lovelace\n", 422, "invalid_headers"),
        ("malformed-row.csv", b"name,city\nAda\n", 422, "invalid_csv"),
        ("malformed-quote.csv", b'name,city\n"Ada,London\n', 422, "invalid_csv"),
        ("invalid-encoding.csv", b"name\n\xff\n", 415, "unsupported_encoding"),
        ("data.txt", b"name\nAda\n", 415, "unsupported_media_type"),
    ],
)
def test_invalid_uploads_are_rejected_without_persistence(
    client: TestClient,
    filename: str,
    content: bytes,
    expected_status: int,
    expected_code: str,
) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert client.get("/api/datasets").json() == []
    assert not list(client.app.state.settings.data_storage_dir.glob("*.csv"))


def test_upload_rejects_files_over_configured_size(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'small-limit.db'}",
        data_storage_dir=tmp_path / "uploads",
        max_upload_size_bytes=8,
    )
    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/datasets",
            files={"file": ("large.csv", b"name\nAda\n", "text/csv")},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_large_csv_field_works_through_preview_analysis_clean_and_download(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'large-field.db'}",
        data_storage_dir=tmp_path / "uploads",
        max_upload_size_bytes=512_000,
    )
    large_value = "x" * 200_000
    content = f"payload\n{large_value}\n".encode()

    with TestClient(create_app(settings=settings)) as client:
        upload = client.post(
            "/api/datasets",
            files={"file": ("large-field.csv", content, "text/csv")},
        )
        assert upload.status_code == 201
        dataset_id = upload.json()["dataset_id"]

        preview = client.get(f"/api/datasets/{dataset_id}/preview?limit=1")
        assert preview.status_code == 200
        assert preview.json()["rows"] == [{"payload": large_value}]

        analysis = client.post(f"/api/datasets/{dataset_id}/analyze")
        assert analysis.status_code == 200
        assert analysis.json()["row_count"] == 1

        clean = client.post(f"/api/datasets/{dataset_id}/clean", json={})
        assert clean.status_code == 201
        latest_run = client.get(f"/api/datasets/{dataset_id}/cleaning-runs/latest")
        assert latest_run.status_code == 200
        assert latest_run.json()["quality_after_report"]["row_count"] == 1
        download = client.get(f"/api/datasets/{dataset_id}/download")
        assert download.status_code == 200
        assert download.text == content.decode()


@pytest.mark.parametrize(
    ("limit_name", "limit", "content", "expected_code"),
    [
        ("max_csv_rows", 1, b"name\nAda\nGrace\n", "row_limit_exceeded"),
        ("max_csv_columns", 1, b"name,city\nAda,London\n", "column_limit_exceeded"),
    ],
)
def test_upload_rejects_configured_row_and_column_limits(
    tmp_path,
    limit_name: str,
    limit: int,
    content: bytes,
    expected_code: str,
) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'bounded.db'}",
        data_storage_dir=tmp_path / "uploads",
        **{limit_name: limit},
    )
    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/datasets",
            files={"file": ("bounded.csv", content, "text/csv")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == expected_code
    assert not list(settings.data_storage_dir.glob("*.csv"))


def test_preview_limit_is_bounded_and_missing_dataset_is_not_found(client: TestClient) -> None:
    missing_response = client.get("/api/datasets/not-a-dataset")
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "dataset_not_found"

    upload = client.post(
        "/api/datasets",
        files={"file": ("people.csv", b"name\nAda\n", "text/csv")},
    )
    dataset_id = upload.json()["dataset_id"]
    preview_response = client.get(f"/api/datasets/{dataset_id}/preview?limit=101")
    assert preview_response.status_code == 422
    assert preview_response.json()["error"]["code"] == "invalid_preview_limit"


def test_preview_rejects_a_stored_path_outside_the_upload_directory(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'paths.db'}",
        data_storage_dir=tmp_path / "uploads",
    )
    dataset = Dataset(original_path="../outside.csv")

    with pytest.raises(CsvUploadError, match="stored dataset path is invalid"):
        read_preview(dataset, settings, limit=1, offset=0)
