import pytest
from botgen.conversation_state import BotConversationState
from botbuilder.core import MemoryStorage
from unittest.mock import Mock

@pytest.fixture
def conversation_state():
    return BotConversationState(MemoryStorage())

def test_get_storage_key(conversation_state):
    # Mocking the necessary attributes of TurnContext
    activity_mock = Mock()
    activity_mock.channel_id = "test_channel"
    activity_mock.conversation = {"id": "test_conversation_id"}
    turn_context_mock = Mock()
    turn_context_mock.activity = activity_mock

    expected_key = "test_channel/conversations/test_conversation_id"
    actual_key = conversation_state.get_storage_key(turn_context_mock)
    assert actual_key == expected_key

def test_get_storage_key_missing_conversation(conversation_state):
    # Mocking the necessary attributes of TurnContext
    activity_mock = Mock()
    activity_mock.channel_id = "test_channel"
    activity_mock.conversation = None  # Simulating missing conversation
    turn_context_mock = Mock()
    turn_context_mock.activity = activity_mock

    with pytest.raises(Exception):
        conversation_state.get_storage_key(turn_context_mock)

def test_get_storage_key_missing_conversation_id(conversation_state):
    # Mocking the necessary attributes of TurnContext
    activity_mock = Mock()
    activity_mock.channel_id = "test_channel"
    activity_mock.conversation = {"id": None}  # Simulating missing conversation id
    turn_context_mock = Mock()
    turn_context_mock.activity = activity_mock

    with pytest.raises(Exception):
        conversation_state.get_storage_key(turn_context_mock)
