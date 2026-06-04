"""Purge expired transient COPPA intake records."""
import logging

from dotenv import load_dotenv

load_dotenv()

from data_access.config import get_admin_supabase_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s - %(message)s")


def main() -> None:
    get_admin_supabase_client().rpc("cleanup_coppa_intake_records", {}).execute()
    print("COPPA intake cleanup complete")


if __name__ == "__main__":
    main()
