from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from aiohttp import web
from botbuilder.core import BotAdapter
from botbuilder.core import MemoryStorage
from botbuilder.core import TurnContext
from botbuilder.dialogs import DialogContext
from botbuilder.dialogs import DialogSet

from botgen import Bot
from botgen.bot_worker import BotWorker
from botgen.core import BotMessage


@pytest.fixture
def bot():
    return Bot()


@pytest.fixture
def mock_request():
    return Mock()


@pytest.fixture
def mock_turn_context():
    return MagicMock(spec=TurnContext)


@pytest.fixture
def mock_bot_worker():
    return Mock(spec=BotWorker)


@pytest.fixture
def mock_bot_message():
    return Mock(spec=BotMessage)


@pytest.fixture
def mock_trigger():
    return Mock()


@pytest.fixture
def mock_dialog_context():
    return Mock(spec=DialogContext)


@pytest.fixture
def mock_bot_adapter():
    return Mock(spec=BotAdapter)


def test_bot_initialization(bot):
    assert bot.webhook_uri == "/api/messages"
    assert bot.dialog_state_property == "dialogState"
    assert bot.adapter is None
    assert bot.adapter_config is None
    assert bot.webserver is not None
    assert bot.webserver_middlewares is None
    assert bot.storage is None
    assert bot.disable_webserver is None
    assert bot.disable_console is None
    assert bot.json_limit == "100kb"
    assert bot.url_encoded_limit == "100kb"
    assert bot.booted is False
    assert isinstance(bot._storage, MemoryStorage)
    assert isinstance(bot.dialog_set, DialogSet)


def test_configure_webhook(bot):
    bot.webserver = Mock()
    bot.configure_webhook()


@pytest.mark.asyncio
async def test_process_incoming_message(bot, mock_request):
    bot.adapter = Mock()
    bot.handle_turn = Mock()
    bot.adapter.process_activity = AsyncMock(return_value={"response": "message"})

    response = await bot.process_incoming_message(mock_request)

    bot.adapter.process_activity.assert_called_once_with(mock_request, bot.handle_turn)
    assert response.status == 200


def test_configure_webhook(bot):
    bot.webserver = Mock()
    bot.webserver.add_routes = Mock()

    bot.configure_webhook()

    bot.webserver.add_routes.assert_called_once_with(
        [web.post(bot.webhook_uri, bot.process_incoming_message)]
    )


@pytest.mark.asyncio
async def test_handle_turn(bot, mock_turn_context):
    # Set up the mocked TurnContext
    activity = Mock()
    activity.type = "message"
    activity.from_property = {"id": "user_id"}
    activity.text = "Test message"
    activity.conversation = {"id": "channel_id"}
    activity.value = "message_value"
    TurnContext.get_conversation_reference = Mock(
        return_value={"reference": "conversation_reference"}
    )
    mock_turn_context.activity = activity

    # Set up expectations for BotMessage creation
    expected_bot_message = BotMessage(
        type="message",
        user="user_id",
        text="Test message",
        channel="channel_id",
        value="message_value",
        reference={"reference": "conversation_reference"},
        incoming_message=activity,
    )

    # Mock the dialog set and create_context method
    dialog_context_mock = Mock()
    bot.dialog_set.create_context = AsyncMock(return_value=dialog_context_mock)

    # Mock the spawn method
    bot.spawn = AsyncMock()

    # Mock _process_trigger_and_events method
    bot._process_trigger_and_events = AsyncMock()

    # Call the handle_turn method
    await bot.handle_turn(mock_turn_context)

    # Assertions
    bot.dialog_set.create_context.assert_called_once_with(turn_context=mock_turn_context)
    bot.spawn.assert_called_once_with(dialog_context_mock)
    bot._process_trigger_and_events.assert_called_once_with(
        bot_worker=bot.spawn.return_value, message=expected_bot_message
    )


@pytest.mark.asyncio
async def test_process_trigger_and_events_with_listen_results(
    bot, mock_bot_worker, mock_bot_message
):
    # Mock _listen_for_triggers method to return some results
    bot._listen_for_triggers = AsyncMock(return_value=["listen_result"])

    # Mock trigger method
    bot.trigger = AsyncMock()

    # Call the _process_trigger_and_events method
    result = await bot._process_trigger_and_events(
        bot_worker=mock_bot_worker, message=mock_bot_message
    )

    # Assertions
    assert result == ["listen_result"]
    bot._listen_for_triggers.assert_called_once_with(
        bot_worker=mock_bot_worker, message=mock_bot_message
    )
    bot.trigger.assert_not_called()  # Since listen_results is not empty, trigger should not be called


@pytest.mark.asyncio
async def test_process_trigger_and_events_with_trigger_results(
    bot, mock_bot_worker, mock_bot_message
):
    # Mock _listen_for_triggers method to return None
    bot._listen_for_triggers = AsyncMock(return_value=None)

    # Mock trigger method to return some results
    bot.trigger = AsyncMock(return_value=["trigger_result"])

    # Call the _process_trigger_and_events method
    result = await bot._process_trigger_and_events(
        bot_worker=mock_bot_worker, message=mock_bot_message
    )

    # Assertions
    assert result == ["trigger_result"]
    bot._listen_for_triggers.assert_called_once_with(
        bot_worker=mock_bot_worker, message=mock_bot_message
    )
    bot.trigger.assert_called_once_with(mock_bot_message.type, mock_bot_worker, mock_bot_message)


@pytest.mark.asyncio
async def test_trigger_with_registered_event_handler(bot, mock_bot_worker, mock_bot_message):
    # Register some event handlers
    mock_event_handler = AsyncMock()
    bot._events = {"some_event": [mock_event_handler]}

    # Call the trigger method with the event that has a registered handler
    await bot.trigger("some_event", mock_bot_worker, mock_bot_message)

    # Assertions
    mock_event_handler.assert_called_once_with(mock_bot_worker, mock_bot_worker, mock_bot_message)


@pytest.mark.asyncio
async def test_trigger_with_unregistered_event_handler(bot, mock_bot_worker, mock_bot_message):
    # Call the trigger method with an event that doesn't have any registered handler
    await bot.trigger("unregistered_event", mock_bot_worker, mock_bot_message)

    # No event handler should be called, so assert that it's not called
    assert not mock_bot_worker.called


@pytest.mark.asyncio
async def test_listen_for_triggers_with_matching_trigger(bot, mock_bot_worker, mock_bot_message):
    # Mock a trigger and its handler
    mock_trigger = Mock()
    mock_trigger.pattern = "hello"
    mock_trigger.handler = AsyncMock(return_value="trigger_results")
    bot._triggers = {"message": [mock_trigger]}
    mock_bot_message.type = "message"
    mock_bot_message.text = "hello"

    # Call the _listen_for_triggers method with a message of type "message"
    result = await bot._listen_for_triggers(mock_bot_worker, mock_bot_message)

    # Assertions
    assert result == "trigger_results"
    mock_trigger.handler.assert_called_once_with(mock_bot_worker, mock_bot_message)


@pytest.mark.asyncio
async def test_listen_for_triggers_with_no_matching_trigger(bot, mock_bot_worker, mock_bot_message):
    # Call the _listen_for_triggers method with a message of type "unregistered_type"
    result = await bot._listen_for_triggers(mock_bot_worker, mock_bot_message)

    # Assertions
    assert result == False  # No trigger matched, so the result should be False


@pytest.mark.asyncio
async def test_test_trigger_with_string_pattern(bot, mock_trigger, mock_bot_message):
    # Set up the trigger with a string pattern
    mock_trigger.pattern = "test_pattern"

    # Call the _test_trigger method with a message that matches the pattern
    mock_bot_message.text = "test_pattern"
    result = await bot._test_trigger(mock_trigger, mock_bot_message)

    # Assertions
    assert result == True

    # Call the _test_trigger method with a message that does not match the pattern
    mock_bot_message.text = "different_pattern"
    result = await bot._test_trigger(mock_trigger, mock_bot_message)

    # Assertions
    assert result == False


@pytest.mark.asyncio
async def test_test_trigger_with_list_pattern(bot, mock_trigger, mock_bot_message):
    # Set up the trigger with a list pattern
    mock_trigger.pattern = ["pattern1", "pattern2"]

    # Call the _test_trigger method with a message that matches one of the patterns
    mock_bot_message.text = "pattern1"
    result = await bot._test_trigger(mock_trigger, mock_bot_message)

    # Assertions
    assert result == True

    # Call the _test_trigger method with a message that does not match any pattern
    mock_bot_message.text = "pattern3"
    result = await bot._test_trigger(mock_trigger, mock_bot_message)

    # Assertions
    assert result == False


@pytest.mark.asyncio
async def test_test_trigger_with_callable_pattern(bot, mock_trigger, mock_bot_message):
    # Set up the trigger with a callable pattern
    mock_trigger.pattern = AsyncMock(return_value=True)

    # Call the _test_trigger method with any message (the pattern will always return True)
    result = await bot._test_trigger(mock_trigger, mock_bot_message)

    # Assertions
    assert result == True


@pytest.mark.asyncio
async def test_test_trigger_with_invalid_pattern(bot, mock_trigger, mock_bot_message):
    # Set up the trigger with an invalid pattern (None in this case)
    mock_trigger.pattern = None

    # Call the _test_trigger method with any message
    result = await bot._test_trigger(mock_trigger, mock_bot_message)

    # Assertions
    assert result == False


def test_hears_adds_trigger(bot):
    # Mock the handler and pattern
    handler = Mock()
    pattern = "hello"

    # Call the hears method
    bot.hears(pattern, handler)

    # Assert that the trigger is added to the list of triggers for the "message" event
    assert len(bot._triggers["message"]) == 1
    assert bot._triggers["message"][0].pattern == pattern
    assert bot._triggers["message"][0].handler == handler


def test_on_adds_event_handler(bot):
    # Mock the handler
    handler = Mock()
    event = "some_event"

    # Call the on method
    bot.on(event, handler)
    print(bot._events)
    # Assert that the event handler is added to the list of events
    assert len(bot._events[event]) == 1
    assert bot._events[event][0] == handler


@pytest.mark.asyncio
async def test_spawn_with_dialog_context(bot, mock_dialog_context):
    # Mock DialogContext configuration
    mock_dialog_context.context.activity = Mock()
    mock_dialog_context.context.activity.channel_id = "channel_id"

    # Call the spawn method with DialogContext
    bot_worker = await bot.spawn(config=mock_dialog_context)

    # Assertions
    assert isinstance(bot_worker, BotWorker)
    assert bot_worker._controller == bot
    assert bot_worker._config["context"] == mock_dialog_context.context
    assert bot_worker._config["activity"] == mock_dialog_context.context.activity
