import os
from pathlib import Path
import httpx
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_DIR / '.env')

_admin_client: Client | None = None


def get_admin_supabase_client() -> Client:
    global _admin_client
    if _admin_client is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        if not url or not key:
            raise RuntimeError(
                'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env'
            )
        _admin_client = create_client(
            url, key,
            options=SyncClientOptions(httpx_client=httpx.Client()),
        )
    return _admin_client


def get_user_supabase_client(jwt: str) -> Client:
    url = os.getenv('SUPABASE_URL')
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    if not url or not anon_key:
        raise RuntimeError(
            'SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env'
        )
    client = create_client(
        url, anon_key,
        options=SyncClientOptions(httpx_client=httpx.Client()),
    )
    client.postgrest.auth(jwt)
    return client

