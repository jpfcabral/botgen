import pytest
from unittest.mock import Mock, AsyncMock
from botgen.bot_worker import BotWorker
from botbuilder.schema import Activity
from botbuilder.core import TurnContext

@pytest.fixture
def bot_worker():
    # Mock Bot and config
    bot_mock = Mock()
    config = {"context": Mock()}
    return BotWorker(bot_mock, config)

def test_get_controller(bot_worker):
    controller = bot_worker.get_controller()
    assert controller == bot_worker._controller

def test_get_config(bot_worker):
    config = bot_worker.get_config()
    assert config == bot_worker._config

@pytest.mark.asyncio
async def test_say(bot_worker):
    # Mock the context's send_activity method
    bot_worker._config["context"].send_activity = AsyncMock()

    message = "Test message"
    await bot_worker.say(message)

    bot_worker._config["context"].send_activity.assert_called_once()

@pytest.mark.asyncio
async def test_reply(bot_worker):
    # Mock methods and objects needed for reply
    activity = Activity(type="message", text="Reply message", channel_data={})
    bot_worker.ensure_message_format = AsyncMock(return_value=activity)
    TurnContext.get_conversation_reference = Mock(return_value={"conversation": {"id": "123"}})
    TurnContext.apply_conversation_reference = Mock(return_value=activity)
    bot_worker.say = AsyncMock()

    message_src = Mock()
    message_src.incoming_message = Mock()
    message_resp = "Replying to the message"

    await bot_worker.reply(message_src, message_resp)

    bot_worker.ensure_message_format.assert_called_once_with(message=message_resp)
    TurnContext.get_conversation_reference.assert_called_once_with(message_src.incoming_message)
    TurnContext.apply_conversation_reference.assert_called_once_with(activity, {"conversation": {"id": "123"}})
    bot_worker.say.assert_called_once_with(activity)

@pytest.mark.asyncio
async def test_ensure_message_format_string(bot_worker):
    message = "Test message"
    activity = await bot_worker.ensure_message_format(message)
    assert isinstance(activity, Activity)
    assert activity.type == "message"
    assert activity.text == message

@pytest.mark.asyncio
async def test_ensure_message_format_message_object(bot_worker):
    message = Mock()
    message.__dict__ = {"type": "test", "text": "Test message"}
    activity = await bot_worker.ensure_message_format(message)
    assert isinstance(activity, Activity)
    assert activity.type == message.type
    assert activity.text == message.text

if __name__ == '__main__':
    pytest.main()
