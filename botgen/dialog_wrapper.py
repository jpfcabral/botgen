from typing import Any

from botbuilder.dialogs import DialogContext

import botgen


class BotDialogWrapper:
    def __init__(self, dc: DialogContext, step: botgen.BotConversationStep):
        self.dc = dc
        self.step = step
        self.vars = self.step.values

    async def goto_thread(self, thread: str) -> None:
        """
        Jump immediately to the first message in a different thread.

        Args:
            thread (str): Name of a thread
        """
        self.step.index = 0
        self.step.thread = thread

    async def repeat(self) -> None:
        """
        Repeat the last message sent on the next turn.
        """
        # move back one step next turn the bot will repeat with the last message sent.
        self.step.index -= 1

    async def stop(self) -> None:
        """
        Stop the dialog.
        """
        # set this to 1 bigger than the total length of the thread.
        self.step.index = self.step.thread_length + 1

    def set_var(self, key: str, val: Any) -> None:
        """
        Set the value of a variable that will be available to messages in the conversation.

        Equivalent to convo.vars[key] = val;
        Results in {{vars.key}} being replaced with the value in val.

        Args:
            key (str): The name of the variable
            val (Any): The value for the variable
        """
        self.vars[key] = val
