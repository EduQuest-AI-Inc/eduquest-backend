from typing import Optional

from data_access.base_dao import SupabaseBaseDAO


class MaterialFilesDAO(SupabaseBaseDAO):
    def __init__(self) -> None:
        super().__init__('material_files')

    def get_by_hash(self, file_hash: str) -> Optional[dict]:
        return self._select_by_id('file_hash', file_hash)

    def insert(self, file_hash: str, openai_file_id: str, vector_store_id: str) -> None:
        self._insert({
            'file_hash': file_hash,
            'openai_file_id': openai_file_id,
            'vector_store_id': vector_store_id,
        })
