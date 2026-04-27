import os
from dotenv import load_dotenv
from pathlib import Path
import httpx
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_DIR / '.env')

_client: Client | None = None


def get_supabase_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        if not url or not key:
            raise RuntimeError(
                'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env'
            )
        _client = create_client(
            url, key,
            options=SyncClientOptions(httpx_client=httpx.Client()),
        )
    return _client
