import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from services.period.period_file_service import PeriodFileService

PERIOD_ID = "period-abc"
VS_ID = "vs-123"
FILE_ID = "file-456"
CANVAS_API_URL = "https://canvas.example.com"
CANVAS_API_KEY = "test-api-key"
CANVAS_COURSE_ID = "42"


# ---------------------------------------------------------------------------
# append_canvas_data
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch(
    "services.period.period_file_service.course_to_json",
    return_value='{"title": "CS 101"}',
)
@patch("services.period.period_file_service.CanvasCourse")
def test_append_canvas_data_happy_path(mock_canvas_course, mock_course_to_json):
    svc = PeriodFileService()
    file_paths = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        svc.append_canvas_data(
            tmp_dir, file_paths, CANVAS_API_URL, CANVAS_API_KEY, CANVAS_COURSE_ID
        )

    mock_canvas_course.assert_called_once_with(
        int(CANVAS_COURSE_ID), CANVAS_API_URL, CANVAS_API_KEY
    )
    mock_course_to_json.assert_called_once()
    assert len(file_paths) == 1
    assert file_paths[0].endswith("canvas_course.json")


@pytest.mark.unit
@patch("services.period.period_file_service.CanvasCourse")
def test_append_canvas_data_missing_creds(mock_canvas_course):
    svc = PeriodFileService()
    file_paths = []
    svc.append_canvas_data("", file_paths, None, CANVAS_API_KEY, CANVAS_COURSE_ID)
    mock_canvas_course.assert_not_called()
    assert file_paths == []


@pytest.mark.unit
@patch("services.period.period_file_service.CanvasCourse")
def test_append_canvas_data_canvas_error(mock_canvas_course):
    mock_canvas_course.side_effect = Exception("Canvas unavailable")
    svc = PeriodFileService()
    file_paths = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        # exception must be swallowed — no raise
        svc.append_canvas_data(
            tmp_dir, file_paths, CANVAS_API_URL, CANVAS_API_KEY, CANVAS_COURSE_ID
        )
    assert file_paths == []


# ---------------------------------------------------------------------------
# archive_to_s3
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch(
    "services.period.period_file_service.upload_file_to_s3",
    return_value="periods/period-abc/course materials/file.txt",
)
def test_archive_to_s3_happy_path(mock_upload):
    svc = PeriodFileService()
    result = svc.archive_to_s3(["/tmp/file.txt"], PERIOD_ID)
    assert result == ["periods/period-abc/course materials/file.txt"]
    mock_upload.assert_called_once_with(
        "/tmp/file.txt", folder=f"periods/{PERIOD_ID}/course materials"
    )


@pytest.mark.unit
@patch("services.period.period_file_service.upload_file_to_s3", return_value=None)
def test_archive_to_s3_upload_returns_none(mock_upload):
    svc = PeriodFileService()
    result = svc.archive_to_s3(["/tmp/file.txt"], PERIOD_ID)
    assert result == ["local/file.txt"]


@pytest.mark.unit
@patch("services.period.period_file_service.upload_file_to_s3")
def test_archive_to_s3_multiple_files(mock_upload):
    mock_upload.side_effect = ["s3-key-a", None]
    svc = PeriodFileService()
    result = svc.archive_to_s3(["/tmp/file_a.txt", "/tmp/file_b.txt"], PERIOD_ID)
    assert result == ["s3-key-a", "local/file_b.txt"]


# ---------------------------------------------------------------------------
# ingest_to_openai
# ---------------------------------------------------------------------------


@pytest.mark.unit
@patch("data_access.material_files_dao.MaterialFilesDAO")
@patch("services.period.period_file_service.openai_vector_store")
def test_ingest_to_openai_json_file(mock_vs, mock_dao_cls):
    canvas_data = {"title": "CS 101", "modules": []}
    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False
    ) as f:
        json.dump(canvas_data, f)
        json_path = f.name
    try:
        svc = PeriodFileService()
        result = svc.ingest_to_openai("vs-period", [json_path])
    finally:
        os.unlink(json_path)

    mock_vs.upload_json.assert_called_once_with("vs-period", canvas_data)
    assert result == []


@pytest.mark.unit
@patch(
    "services.period.period_file_service.preprocess_pdf",
    return_value="/tmp/processed.txt",
)
@patch("data_access.material_files_dao.MaterialFilesDAO")
@patch("services.period.period_file_service.openai_vector_store")
def test_ingest_to_openai_new_pdf(mock_vs, mock_dao_cls, mock_preprocess):
    mock_dao = MagicMock()
    mock_dao_cls.return_value = mock_dao
    mock_dao.get_by_hash.return_value = None
    mock_vs.create_file_store.return_value = (VS_ID, FILE_ID)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake pdf content")
        pdf_path = f.name
    try:
        svc = PeriodFileService()
        result = svc.ingest_to_openai("vs-period", [pdf_path])
    finally:
        os.unlink(pdf_path)

    mock_preprocess.assert_called_once_with(pdf_path)
    mock_vs.create_file_store.assert_called_once_with(
        "/tmp/processed.txt", name=os.path.basename(pdf_path)
    )
    mock_dao.insert.assert_called_once()
    assert result == [VS_ID]


@pytest.mark.unit
@patch("data_access.material_files_dao.MaterialFilesDAO")
@patch("services.period.period_file_service.openai_vector_store")
def test_ingest_to_openai_dedup_hit(mock_vs, mock_dao_cls):
    mock_dao = MagicMock()
    mock_dao_cls.return_value = mock_dao
    mock_dao.get_by_hash.return_value = {"vector_store_id": "existing-vs"}

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"some file content")
        pdf_path = f.name
    try:
        svc = PeriodFileService()
        result = svc.ingest_to_openai("vs-period", [pdf_path])
    finally:
        os.unlink(pdf_path)

    mock_vs.create_file_store.assert_not_called()
    assert result == ["existing-vs"]


@pytest.mark.unit
@patch("services.period.period_file_service.preprocess_pdf")
@patch("data_access.material_files_dao.MaterialFilesDAO")
@patch("services.period.period_file_service.openai_vector_store")
def test_ingest_to_openai_new_non_pdf(mock_vs, mock_dao_cls, mock_preprocess):
    mock_dao = MagicMock()
    mock_dao_cls.return_value = mock_dao
    mock_dao.get_by_hash.return_value = None
    mock_vs.create_file_store.return_value = (VS_ID, FILE_ID)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"plain text content")
        txt_path = f.name
    try:
        svc = PeriodFileService()
        result = svc.ingest_to_openai("vs-period", [txt_path])
    finally:
        os.unlink(txt_path)

    mock_preprocess.assert_not_called()
    mock_vs.create_file_store.assert_called_once_with(
        txt_path, name=os.path.basename(txt_path)
    )
    assert result == [VS_ID]


@pytest.mark.unit
@patch("data_access.material_files_dao.MaterialFilesDAO")
@patch("services.period.period_file_service.openai_vector_store")
def test_ingest_to_openai_openai_error(mock_vs, mock_dao_cls):
    mock_dao = MagicMock()
    mock_dao_cls.return_value = mock_dao
    mock_dao.get_by_hash.return_value = None
    mock_vs.create_file_store.side_effect = Exception("OpenAI API error")

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"some content")
        txt_path = f.name
    try:
        svc = PeriodFileService()
        with pytest.raises(Exception, match="OpenAI API error"):
            svc.ingest_to_openai("vs-period", [txt_path])
    finally:
        os.unlink(txt_path)
