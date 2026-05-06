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


def upload_file(file_path: str) -> str:
    """Upload a single file to the OpenAI Files API. Returns file_id."""
    with open(file_path, "rb") as f:
        resp = _client.files.create(file=f, purpose="assistants")
    return resp.id


def create_file_store(file_path: str, name: str) -> tuple:
    """Create a named vector store containing one file. Returns (vs_id, file_id)."""
    vs_id = create_empty(name)
    file_id = upload_file(file_path)
    _client.vector_stores.file_batches.create_and_poll(
        vector_store_id=vs_id, file_ids=[file_id]
    )
    return vs_id, file_id


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
