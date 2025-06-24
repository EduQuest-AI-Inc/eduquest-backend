import unittest
from unittest.mock import patch, MagicMock
from assistants import create_class, ltg_response_format, ltg_inst

class TestCreateClassLTGAssistant(unittest.TestCase):
    @patch('assistants.client')
    def test_create_ltg_assistant(self, mock_client):
        # Setup
        mock_vector_store = MagicMock()
        mock_vector_store.id = 'mock_vector_store_id'
        mock_client.vector_stores.create.return_value = mock_vector_store
        mock_assistant = MagicMock()
        mock_assistant.id = 'mock_assistant_id'
        mock_client.beta.assistants.create.return_value = mock_assistant
        mock_client.beta.assistants.update.return_value = mock_assistant

        # Instantiate and call
        class_name = 'TestClass'
        c = create_class(class_name)
        c.create_ltg_assistant()

        # Assertions
        mock_client.beta.assistants.create.assert_called_with(
            name=f"{class_name} LTG Assistant",
            instructions=ltg_inst,
            model="gpt-4.1-mini",
            tools=[{"type": "file_search"}],
            response_format=ltg_response_format
        )
        mock_client.beta.assistants.update.assert_called_with(
            assistant_id=mock_assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [mock_vector_store.id]}}
        )
        self.assertEqual(c.ltg_assistant, mock_assistant)

if __name__ == '__main__':
    unittest.main()