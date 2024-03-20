import pytest
from unittest.mock import AsyncMock, Mock
from botgen.adapters import WebAdapter
from botbuilder.schema import Activity, ConversationReference, ResourceResponse
from botbuilder.core import TurnContext

@pytest.fixture
def web_adapter():
    return WebAdapter()

def test_activity_to_message(web_adapter):
    activity = Activity(type="message", text="Test message")
    message = web_adapter.activity_to_message(activity)
    assert message.type == activity.type
    assert message.text == activity.text

@pytest.mark.asyncio
async def test_send_activities_webhook(web_adapter):
    context = Mock()
    context.activity.channel_id = "websocket"
    context.turn_state.get.return_value = None
    activities = [Activity(type="message", text="Test message")]

    with pytest.raises(NotImplementedError):
        await web_adapter.send_activities(context, activities)

@pytest.mark.asyncio
async def test_update_activity(web_adapter):
    context = Mock()
    activity = Mock()
    with pytest.raises(NotImplementedError):
        await web_adapter.update_activity(context, activity)

@pytest.mark.asyncio
async def test_delete_activity(web_adapter):
    context = Mock()
    reference = Mock()
    with pytest.raises(NotImplementedError):
        await web_adapter.delete_activity(context, reference)

@pytest.mark.asyncio
async def test_process_activity(web_adapter):
    request = Mock()
    request.json = AsyncMock(return_value={"type": "message", "text": "Test message", "user": "user_id"})
    logic_callback = AsyncMock()
    response = await web_adapter.process_activity(request, logic_callback)
    assert response == None
