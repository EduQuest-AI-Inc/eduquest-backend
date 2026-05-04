import json
import logging
import os
import tempfile

from openai import OpenAI

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger = logging.getLogger(__name__)


def create_empty(name: str) -> str:
    """Create a named vector store with a 365-day expiry. Returns vector_store_id."""
    vs = _client.vector_stores.create(
        name=name,
        expires_after={"anchor": "last_active_at", "days": 365},
    )
    return vs.id


def upload_files(vector_store_id: str, file_paths: list) -> None:
    """Open each path as binary and batch-upload to an existing vector store."""
    if not file_paths:
        return
    streams = [open(p, "rb") for p in file_paths]
    try:
        _client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store_id, files=streams
        )
    finally:
        for s in streams:
            s.close()


def upload_json(vector_store_id: str, data: dict) -> str:
    """Write data as a temp JSON file, upload to the files API, attach to the vector store.
    Returns the OpenAI file_id."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f, indent=2)
        temp_path = f.name
    try:
        with open(temp_path, "rb") as f:
            file_resp = _client.files.create(file=f, purpose="assistants")
        _client.vector_stores.files.create(
            vector_store_id=vector_store_id, file_id=file_resp.id
        )
        return file_resp.id
    finally:
        os.unlink(temp_path)


def delete_file(vector_store_id: str, file_id: str) -> None:
    try:
        _client.vector_stores.files.delete(
            vector_store_id=vector_store_id, file_id=file_id
        )
    except Exception as e:
        logger.warning("Failed to delete file %s from vector store: %s", file_id, e)


def delete_store(vector_store_id: str) -> None:
    try:
        _client.vector_stores.delete(vector_store_id)
    except Exception as e:
        logger.warning("Failed to delete vector store %s: %s", vector_store_id, e)
