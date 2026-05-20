"""Unit tests for SupabaseAuthService."""
import pytest
from unittest.mock import MagicMock

from services.auth.supabase_auth_service import SupabaseAuthService

_TEST_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def mock_client():
    client = MagicMock()
    user_response = MagicMock()
    user_response.user.id = _TEST_UUID
    client.auth.admin.create_user.return_value = user_response
    return client


@pytest.fixture
def mock_user_dao():
    dao = MagicMock()
    dao.get_by_id.return_value = {"user_id": "johndoe", "email": "john@eduquestai.org", "supabase_auth_id": None}
    return dao


@pytest.fixture
def service(mock_client, mock_user_dao):
    return SupabaseAuthService(supabase_client=mock_client, user_dao=mock_user_dao)


class TestProvisionUser:

    @pytest.mark.unit
    def test_creates_supabase_auth_user_and_stores_uuid(self, service, mock_client, mock_user_dao):
        result = service.provision_user("johndoe", "john@eduquestai.org", "SecurePass1", "student")
        assert result == _TEST_UUID
        mock_client.auth.admin.create_user.assert_called_once_with({
            "email": "john@eduquestai.org",
            "password": "SecurePass1",
            "email_confirm": True,
            "app_metadata": {"username": "johndoe", "role": "student"},
        })
        mock_user_dao.update.assert_called_once_with("johndoe", {"supabase_auth_id": _TEST_UUID})

    @pytest.mark.unit
    def test_skips_provisioning_when_already_set(self, service, mock_client, mock_user_dao):
        mock_user_dao.get_by_id.return_value = {
            "user_id": "johndoe",
            "email": "john@eduquestai.org",
            "supabase_auth_id": "existing-uuid",
        }
        result = service.provision_user("johndoe", "john@eduquestai.org", "SecurePass1", "student")
        assert result == "existing-uuid"
        mock_client.auth.admin.create_user.assert_not_called()

    @pytest.mark.unit
    def test_returns_none_on_supabase_error(self, service, mock_client, mock_user_dao):
        mock_client.auth.admin.create_user.side_effect = Exception("network error")
        result = service.provision_user("johndoe", "john@eduquestai.org", "SecurePass1", "student")
        assert result is None
        mock_user_dao.update.assert_not_called()

    @pytest.mark.unit
    def test_sets_username_and_role_in_app_metadata(self, service, mock_client, mock_user_dao):
        service.provision_user("tuser", "t@eduquestai.org", "SecurePass1", "teacher")
        args = mock_client.auth.admin.create_user.call_args[0][0]
        assert args["app_metadata"] == {"username": "tuser", "role": "teacher"}

    @pytest.mark.unit
    def test_returns_none_on_dao_update_error(self, service, mock_client, mock_user_dao):
        mock_user_dao.update.side_effect = Exception("db error")
        result = service.provision_user("johndoe", "john@eduquestai.org", "SecurePass1", "student")
        assert result is None


class TestStoreOAuthAuthId:

    @pytest.mark.unit
    def test_stores_uuid_and_sets_app_metadata(self, service, mock_client, mock_user_dao):
        service.store_oauth_auth_id("oauthuser", "oauth-uuid-1234", "teacher")
        mock_user_dao.update.assert_called_once_with("oauthuser", {"supabase_auth_id": "oauth-uuid-1234"})
        mock_client.auth.admin.update_user_by_id.assert_called_once_with(
            "oauth-uuid-1234",
            {"app_metadata": {"username": "oauthuser", "role": "teacher"}},
        )

    @pytest.mark.unit
    def test_swallows_dao_update_error(self, service, mock_user_dao):
        mock_user_dao.update.side_effect = Exception("db error")
        service.store_oauth_auth_id("oauthuser", "oauth-uuid-1234", "student")  # must not raise

    @pytest.mark.unit
    def test_swallows_update_user_by_id_error(self, service, mock_client, mock_user_dao):
        mock_client.auth.admin.update_user_by_id.side_effect = Exception("supabase error")
        service.store_oauth_auth_id("oauthuser", "oauth-uuid-1234", "parent")  # must not raise


class TestSyncPassword:

    @pytest.mark.unit
    def test_calls_update_user_by_id(self, service, mock_client):
        service.sync_password("uuid-abc", "NewPass123")
        mock_client.auth.admin.update_user_by_id.assert_called_once_with(
            "uuid-abc", {"password": "NewPass123"}
        )

    @pytest.mark.unit
    def test_no_op_when_uuid_is_empty(self, service, mock_client):
        service.sync_password("", "NewPass123")
        mock_client.auth.admin.update_user_by_id.assert_not_called()

    @pytest.mark.unit
    def test_no_op_when_uuid_is_none(self, service, mock_client):
        service.sync_password(None, "NewPass123")
        mock_client.auth.admin.update_user_by_id.assert_not_called()

    @pytest.mark.unit
    def test_swallows_error(self, service, mock_client):
        mock_client.auth.admin.update_user_by_id.side_effect = Exception("supabase down")
        service.sync_password("uuid-abc", "NewPass123")  # must not raise
