from __future__ import annotations

from botbuilder.core import TurnContext
from botbuilder.schema import Activity

import botgen


class BotWorker:
    """
    A base class for a `bot` instance, an object that contains the information and functionality for taking action in response to an incoming message.
    Note that adapters are likely to extend this class with additional platform-specific methods - refer to the adapter documentation for these extensions.
    """

    def __init__(self, controller: botgen.Bot, config: dict) -> None:
        self._controller = controller
        self._config = config

    def get_controller(self):
        """Get a reference to the main Bot controller"""
        return self._controller

    def get_config(self):
        """Get a value from the BotWorker's configuration"""
        return self._config

    async def say(self, message: botgen.BotMessage | Activity | str):
        """Send a message using whatever context the `bot` was spawned"""
        activity = await self.ensure_message_format(message=message)

        return await self._config["context"].send_activity(activity)

    async def reply(self, message_src: botgen.BotMessage, message_resp: str):
        """
        Reply to an incoming message.
        Message will be sent using the context of the source message,
        which may in some cases be different than the context used to spawn the bot
        """
        activity = await self.ensure_message_format(message=message_resp)

        reference = TurnContext.get_conversation_reference(message_src.incoming_message)

        activity = TurnContext.apply_conversation_reference(activity, reference)

        return await self.say(activity)

    async def ensure_message_format(self, message: botgen.BotMessage | str) -> Activity:
        """
        Take a crudely-formed Bot message with any sort of field (may just be a string, may be a partial message object)
        and map it into a beautiful BotFramework Activity
        """
        if isinstance(message, str):
            return Activity(type="message", text=message, channel_data={})

        return Activity(**message.__dict__)

    async def begin_dialog(self, id: str, options: dict = None) -> None:
        """
        Begin a pre-defined dialog by specifying its ID. The dialog will be started in the same context
        (same user, same channel) in which the original incoming message was received.

        Args:
            id (str): The ID of the dialog.
            options (Any, optional): An object containing options to be passed into the dialog. Defaults to None.

        Returns:
            None
        """

        if not "dialog_context" in self._config:
            raise Exception(
                "Call to begin_dialog on a bot that did not receive a dialog_context during spawn"
            )

        await self._config["dialog_context"].begin_dialog(
            f"{id}:botgen-wrapper",
            {
                "user": self._config["context"].activity.id,
                "channel": self._config["context"].activity.conversation.id ** options,
            },
        )

        self._controller.save_state(self)
