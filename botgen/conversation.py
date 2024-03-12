from dataclasses import dataclass
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import List
from typing import Union

from botbuilder.dialogs import Dialog
from botbuilder.dialogs import DialogContext

import botgen
from botgen.dialog_wrapper import BotDialogWrapper


@dataclass
class BotConversationStep:
    index: int
    thread: str
    thread_length: int
    state: Any
    options: Any
    reason: str
    result: Any
    values: Any
    next: Callable


@dataclass
class BotConvoTrigger:
    type: str = None
    pattern: str = None
    handler: Callable[[Any, Any], Any]
    default: bool = False


@dataclass
class BotMessageTemplate:
    text: Union[Callable[[Any, Any], str], List[str]] = None
    action: str = None
    execute: dict = None
    quick_replies: Union[Callable[[Any, Any], List[Any]], List[Any]] = None
    attachments: Union[Callable[[Any, Any], List[Any]], List[Any]] = None
    blocks: Union[Callable[[Any, Any], List[Any]], List[Any]] = None
    attachment: Union[Callable[[Any, Any], Any], Any] = None
    attachmentLayout: str = None
    channelData: Any = None
    collect: Dict[str, BotConvoTrigger] = None


class BotConversation(Dialog):
    """
    An extension on the BotBuilder Dialog Class friendly interface for
    defining and interacting with multi-message dialogs. Dialogs can be constructed using `say()`, `ask()` and other helper methods.
    """

    def __init__(self, dialog_id: str, controller: botgen.Bot):
        super().__init__(dialog_id=dialog_id)

        self._prompt: str
        self._beforeHooks: Dict = {}
        self._afterHooks: List = []
        self._changeHooks: Dict = {}
        self.script: Dict[List] = {}
        self._controller: botgen.Bot = controller

    def add_message(self, message: BotMessageTemplate | str, thread_name: str = None):
        """
        Adds a message template to a specific thread.

        This method adds a message template to a specified thread in the conversation.
        Messages added using `say()` or `add_message()` will be sent one after another without a pause.

        Args:
            message (Union[BotMessageTemplate, str]):
                The message template to be added. It can be a BotMessageTemplate object or a string.
            thread_name (Optional[str], optional):
                The name of the thread to which the message will be added.
                If not provided, the message will be added to the default thread.
                Defaults to None.

        Returns:
            BotkitConversation:
                The instance of the BotkitConversation class to support method chaining.
        """
        thread_name = thread_name if thread_name else "default"

        if not thread_name in self.script:
            self.script[thread_name] = []

        if isinstance(message, str):
            message = BotMessageTemplate(text=[message])

        self.script[thread_name].append(message)

        return self

    def say(self, message: BotMessageTemplate | str, thread_name: str = None):
        """
        Add a non-interactive message to the default thread
        Messages added with `say()` and `addMessage()` will _not_ wait for a response, will be sent one after another without a pause
        """
        self.add_message(message=message, thread_name="default")
        return self

    def add_action(self, action: str, thread_name: str = "default"):
        """
        Adds an action to the conversation timeline.

        This method adds an action to the conversation timeline, allowing the bot to perform specific actions
        such as switching threads or ending the dialog. If the provided action is the name of another thread
        in the conversation, the bot will transition immediately to that thread.

        Otherwise, you can use one of the following keywords for built-in actions:
        - `stop`: Stops the conversation.
        - `repeat`: Repeats the previous message.
        - `complete`: Completes the conversation successfully.
        - `timeout`: Marks the conversation as timed out.

        Args:
            action (str):
                The action to add to the conversation timeline.
                This can be the name of another thread or one of the built-in keywords.
            thread_name (str, optional):
                The name of the thread to which the action will be added.
                Defaults to "default".

        Returns:
            BotkitConversation:
                The instance of the BotkitConversation class to support method chaining.
        """
        self.add_message(BotMessageTemplate(action=action), thread_name=thread_name)
        return self

    def add_question(
        self,
        message: Union[BotMessageTemplate, str],
        handlers: Union[Callable, List[BotConvoTrigger]],
        key: Union[str, Dict[str, str], None],
        thread_name: str,
    ):
        """
        Adds a question to the conversation thread.

        Args:
            message (Union[Partial[BotkitMessageTemplate], str]):
                A message that will be used as the prompt.
            handlers (Union[BotkitConvoHandler, List[BotkitConvoTrigger]]):
                One or more handler functions defining possible conditional actions based on the response to the question.
            key (Union[str, Dict[str, str], None]):
                Name of the variable to store the response in.
            thread_name (str):
                Name of the thread to which the message will be added.

        Returns:
            BotkitConversation:
                The instance of the BotkitConversation class.
        """
        if not thread_name:
            thread_name = "default"

        if thread_name not in self.script:
            self.script[thread_name] = []

        if isinstance(message, str):
            message = BotMessageTemplate(text=[message])

        if not message.collect:
            message.collect = {}

        if key:
            message.collect["key"] = key if isinstance(key, str) else key["key"]

        if isinstance(handlers, list):
            message.collect["options"] = handlers
        elif callable(handlers):
            message.collect["options"] = [{"default": True, "handler": handlers}]
        else:
            raise ValueError(f"Unsupported handlers type: {type(handlers)}")

        # Ensure all options have a type field
        for option in message.collect["options"]:
            if "type" not in option:
                option["type"] = "string"

        self.script[thread_name].append(message)
        self.script[thread_name].append({"action": "next"})
        return self

    def add_child_dialog(self, dialog_id: str, key_name: str = None, thread_name: str = "default"):
        """
        Causes the dialog to call a child dialog, wait for it to complete,
        then store the results in a variable and resume the parent dialog.

        Args:
            dialog_id (str): The id of another dialog.
            key_name (str, optional): The variable name in which to store the results of the child dialog.
                                      If not provided, defaults to dialog_id.
            thread_name (str, optional): The name of a thread to which this call should be added. Defaults to 'default'.

        Returns:
            BotkitConversation: The instance of the BotkitConversation class.
        """
        action = {"action": "beginDialog", "execute": {"script": dialog_id}}

        message_template = BotMessageTemplate(action=action)
        key = {"key": key_name or dialog_id}

        self.add_question(message_template, [], key, thread_name)
        return self

    def add_goto_dialog(self, dialog_id: str, thread_name: str = "default"):
        """
        Causes the current dialog to handoff to another dialog.

        The parent dialog will not resume when the child dialog completes.
        However, the afterDialog event will not fire for the parent dialog until all child dialogs complete.

        Args:
            dialog_id (str): The id of another dialog.
            thread_name (str, optional): The name of a thread to which this call should be added. Defaults to 'default'.

        Returns:
            BotkitConversation: The instance of the BotkitConversation class.
        """
        action = {"action": "execute_script", "execute": {"script": dialog_id}}

        self.add_message(BotMessageTemplate(action=action), thread_name)
        return self

    def before(
        self,
        thread_name: str,
        handler: Callable[[BotDialogWrapper, botgen.BotWorker], Awaitable[Any]],
    ) -> None:
        """
        Register a handler function that will fire before a given thread begins.

        Use this hook to set variables, call APIs, or change the flow of the conversation using `convo.goto_thread`.

        Args:
            thread_name (str): A valid thread defined in this conversation.
            handler (Callable[['BotkitDialogWrapper', 'BotWorker'], Awaitable[Any]]):
                A handler function in the form async(convo, bot) => { ... }
        """
        if thread_name not in self._before_hooks:
            self._before_hooks[thread_name] = []

        self._before_hooks[thread_name].append(handler)

    async def run_before(
        self, thread_name: str, dc: DialogContext, step: BotConversationStep
    ) -> None:
        """
        This private method is called before a thread begins, and causes any bound handler functions to be executed.

        Args:
            thread_name (str): The thread about to begin.
            dc (DialogContext): The current DialogContext.
            step (BotConversationStep): The current step object.
        """

        if self._before_hooks.get(thread_name):
            # spawn a bot instance so devs can use API or other stuff as necessary
            bot = await self._controller.spawn(dc)

            # create a convo controller object
            convo = BotDialogWrapper(dc, step)

            for handler in self._before_hooks[thread_name]:
                await handler(self, convo, bot)

    def after(self, handler):
        """
        Bind a function to run after the dialog has completed.

        Args:
            handler (Callable[[Any, BotWorker], None]): A handler function taking results and bot as arguments.
        """
        self._after_hooks.append(handler)

    async def _run_after(self, context: DialogContext, results: Any) -> None:
        """
        This private method is called at the end of the conversation, and causes any bound handler functions to be executed.

        Args:
            context (DialogContext): The current dialog context.
            results (Any): An object containing the final results of the dialog.
        """
        if self._after_hooks:
            bot = await self._controller.spawn(context)
            for handler in self._after_hooks:
                await handler(results, bot)
