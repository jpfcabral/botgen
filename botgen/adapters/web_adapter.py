import dataclasses
import json
from datetime import datetime
from typing import Awaitable
from typing import Callable
from typing import Dict

import websockets
from aiohttp.web import Request
from botbuilder.core import BotAdapter
from botbuilder.core import TurnContext
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import ConversationReference
from botbuilder.schema import ResourceResponse
from loguru import logger

from botgen.core import Bot
from botgen.core import BotMessage


clients = dict()


class WebAdapter(BotAdapter):
    """Connects PyBot to websocket or webhook"""

    name = "webadapter"

    def __init__(self, on_turn_error: Callable[[TurnContext, Exception], Awaitable] = None):
        super().__init__(on_turn_error)

    def init(self, bot: Bot):
        def _init_adapter():
            self.create_conversation(bot.handle_turn)

        bot.ready(_init_adapter)

    def create_socket_server(self, logic: callable):
        """Create a websocket server"""
        logger.debug("Initing websocket server")
        self.wss = websockets.serve(on_message, "localhost", 8765)

        async def on_message(payload: str, ws) -> None:
            try:
                message: Dict = json.loads(payload)

                # Note the websocket connection for this user
                ws.user = message["user"]
                clients[message["user"]] = ws

                # This stuff normally lives inside Botkit.congfigureWebhookEndpoint
                activity = Activity(
                    timestamp=datetime.now(),
                    channelId="websocket",
                    conversation={"id": message["user"]},
                    from_property={"id": message["user"]},
                    recipient={"id": "bot"},
                    channelData=message,
                    text=message.get("text", ""),
                    type=ActivityTypes.message
                    if message["type"] == "message"
                    else ActivityTypes.event,
                )

                # Set botkit's event type
                if activity["type"] != ActivityTypes.message:
                    activity["channelData"]["botkitEventType"] = message["type"]

                context = TurnContext(self, activity)
                await self.run_pipeline(context, logic)
            except json.JSONDecodeError as e:
                alert = ["Error parsing incoming message from websocket."]
                logger.warning("\n".join(alert))
                logger.warning(e)
            except Exception as ex:
                logger.warning("An error occurred:", ex)

    def activity_to_message(self, activity: Activity) -> BotMessage:
        """Caste a message to the simple format used by the websocket client"""
        message = BotMessage(
            type=activity.type,
            text=activity.text,
        )

        if activity.channel_data:
            message.__dict__ = activity.channel_data.__dict__

        return message

    async def send_activities(
        self, context: TurnContext, activities: list[Activity]
    ) -> ResourceResponse:
        """Standard BotBuilder adapter method to send a message from the bot to the messaging API"""

        responses = list()

        for i in range(len(activities)):
            activity = activities[i]
            message = self.activity_to_message(activity=activity)
            channel = context.activity.channel_id

            if channel == "websocket":
                raise NotImplementedError("Web socket not implemented")
            elif channel == "webhook":
                outbound = context.turn_state.get("httpBody")

                if not outbound:
                    outbound = []

                outbound.append(dataclasses.asdict(message))
                context.turn_state["httpBody"] = outbound

        return responses

    async def update_activity(self, context: TurnContext, activity: Activity) -> None:
        """ """
        raise NotImplementedError()

    async def delete_activity(self, context: TurnContext, reference: ConversationReference) -> None:
        """Accept an incoming webhook request and convert it into a TurnContext which can be processed by the bot's logic"""
        raise NotImplementedError()

    async def process_activity(self, request: Request, logic: callable):
        body = await request.json()
        message = BotMessage(**body)

        activity = Activity(
            timestamp=datetime.now(),
            channel_id="webhook",
            conversation={"id": message.user},
            from_property={"id": message.user},
            recipient={"id": "bot"},
            channel_data=message,
            text=message.text,
            type=message.type,
        )

        context = TurnContext(self, activity)

        context.turn_state["httpStatus"] = 200

        await self.run_pipeline(context=context, callback=logic)

        return context.turn_state.get("httpBody")
