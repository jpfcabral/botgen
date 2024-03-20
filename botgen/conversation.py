import random
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Union

from botbuilder.core import MessageFactory
from botbuilder.dialogs import Dialog
from botbuilder.dialogs import DialogContext
from botbuilder.dialogs import DialogReason
from botbuilder.dialogs import DialogTurnResult
from botbuilder.dialogs import DialogTurnStatus
from botbuilder.schema import ActionTypes
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import CardAction
from loguru import logger

import botgen


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
    handler: Callable[[Any, Any], Any] = None
    default: bool = False


@dataclass
class BotMessageTemplate:
    text: Union[Callable[[Any, Any], str], List[str]] = None
    channel_data: dict = None
    type: str = None
    action: str = None
    execute: dict = None
    quick_replies: Union[Callable[[Any, Any], List[Any]], List[Any]] = None
    attachments: Union[Callable[[Any, Any], List[Any]], List[Any]] = None
    blocks: Union[Callable[[Any, Any], List[Any]], List[Any]] = None
    attachment: Union[Callable[[Any, Any], Any], Any] = None
    attachment_layout: str = None
    channelData: Any = None
    collect: Dict[str, BotConvoTrigger] = None


class BotConversation(Dialog):
    """
    An extension on the BotBuilder Dialog Class friendly interface for
    defining and interacting with multi-message dialogs. Dialogs can be constructed using `say()`, `ask()` and other helper methods.
    """

    def __init__(self, dialog_id: str, controller):
        super().__init__(dialog_id=dialog_id)

        self._prompt: str
        self._before_hooks: Dict = {}
        self._afterHooks: List = []
        self._changeHooks: Dict = {}
        self.script: Dict[str, List] = {}
        self._controller = controller

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

    def ask(
        self,
        message: Union[Dict[str, Any], str],
        handlers: Union[Callable[..., Any], List[Dict[str, Any]]],
        key: Union[Dict[str, str], str, None] = None,
    ):
        """
        Add a question to the default thread.

        In addition to a message template, receives either a single handler function to call when an answer is provided,
        or an array of handlers paired with trigger patterns. When providing multiple conditions to test, developers may also provide a
        handler marked as the default choice.

        [Learn more about building conversations &rarr;](../conversations.md#build-a-conversation)

        Args:
            message (Union[Dict[str, Any], str]): A message that will be used as the prompt.
            handlers (Union[Callable[..., Any], List[Dict[str, Any]]]): One or more handler functions defining possible conditional actions based on the response to the question.
            key (Union[Dict[str, str], str, None], optional): Name of variable to store response in.
        """
        self.add_question(message, handlers, key, "default")
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
        handler: Callable,
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
            convo = botgen.BotDialogWrapper(dc, step)

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

    def on_change(self, variable: str, handler: Callable) -> None:
        """
        Bind a function to run whenever a user answers a specific question.
        Can be used to validate input and take conditional actions.

        Args:
            variable (str): Name of the variable to watch for changes.
            handler (Callable): A handler function that will fire whenever a user's response is used to change the value of the watched variable.
        """
        if variable not in self._change_hooks:
            self._change_hooks[variable] = []
        self._change_hooks[variable].append(handler)

    async def _run_on_change(
        self, variable: str, value: any, dc: DialogContext, step: BotConversationStep
    ) -> None:
        """
        This private method is responsible for firing any bound onChange handlers when a variable changes.

        Args:
            variable (str): The name of the variable that is changing.
            value (any): The new value of the variable.
            dc (DialogContext): The current DialogContext.
            step (BotConversationStep): The current step object.
        """
        logger.debug("OnChange:", self.id, variable)

        if variable in self._change_hooks and self._change_hooks[variable]:
            bot = await self._controller.spawn(dc)

            convo = botgen.BotDialogWrapper(dc, step)

            for handler in self._change_hooks[variable]:
                await handler(value, convo, bot)

    async def begin_dialog(self, dc: DialogContext, options: any) -> any:
        """
        Called automatically when a dialog begins. Do not call this directly!

        Args:
            dc (DialogContext): The current DialogContext.
            options (any): An object containing initialization parameters passed to the dialog.
                           May include `thread` which will cause the dialog to begin with that thread instead of the `default` thread.

        Returns:
            any: The result of the dialog.
        """
        # Initialize the state
        state = dc.active_dialog.state
        state["options"] = options or {}
        state["values"] = {**options}

        # Run the first step
        return await self.run_step(
            dc, 0, state["options"].get("thread", "default"), DialogReason.BeginCalled
        )

    async def continue_dialog(self, dc: DialogContext) -> any:
        """
        Called automatically when an already active dialog is continued. Do not call this directly!

        Args:
            dc (DialogContext): The current DialogContext.

        Returns:
            any: The result of continuing the dialog.
        """
        # Don't do anything for non-message activities
        if dc.context.activity.type != ActivityTypes.message:
            return Dialog.end_of_turn

        # Run next step with the message text as the result.
        return await self.resume_dialog(dc, DialogReason.ContinueCalled, dc.context.activity)

    async def resume_dialog(
        self, dc: DialogContext, reason: DialogReason, result: any
    ) -> DialogTurnResult:
        """
        Called automatically when a dialog moves forward a step. Do not call this directly!

        Parameters:
            dc (DialogContext): The current DialogContext.
            reason (DialogReason): Reason for resuming the dialog.
            result (any): Result of the previous step.

        Returns:
            DialogTurnResult: Result of the dialog turn.
        """
        # Increment step index and run step
        if dc.active_dialog:
            state = dc.active_dialog.state
            return await self.run_step(
                dc, state["step_index"] + 1, state.get("thread", "default"), reason, result
            )
        else:
            return Dialog.end_of_turn

    async def run_after(self, context: DialogContext, results: any) -> None:
        """
        This private method is called at the end of the conversation, and causes any bound handler functions to be executed.

        Parameters:
            context (DialogContext): The current dialog context.
            results (any): An object containing the final results of the dialog.
        """
        logger.debug(f"After: {self.id}")
        if self._afterHooks:
            bot = await self._controller.spawn(context)
            for handler in self._afterHooks:
                await handler(results, bot)

    async def on_step(self, dc: DialogContext, step: BotConversationStep) -> Any:
        """
        Called automatically to process the turn, interpret the script, and take any necessary actions based on that script. Do not call this directly
        """
        # Let's interpret the current line of the script.
        thread = self.script[step["thread"]]

        if not thread:
            raise ValueError(
                f"Thread '{step['thread']}' not found, did you add any messages to it?"
            )

        # Capture the previous step value if there previous line included a prompt
        previous = thread[step["index"] - 1] if step["index"] >= 1 else None
        if step["result"] and previous and previous.collect:
            if previous.collect.key:
                # capture before values
                index = step["index"]
                thread_name = step["thread"]

                # capture the user input value into the array
                if step["values"][previous.collect.key] and previous.collect.multiple:
                    step["values"][previous.collect.key] = "\n".join(
                        [step["values"][previous.collect.key], step["result"]]
                    )
                else:
                    step["values"][previous.collect.key] = step["result"]

                # run onChange handlers
                await self.run_on_change(previous.collect.key, step["result"], dc, step)

                # did we just change threads? if so, restart this turn
                if index != step["index"] or thread_name != step["thread"]:
                    return await self.run_step(
                        dc, step["index"], step["thread"], DialogReason.next_called
                    )

            # handle conditions of previous step
            if previous.collect.options:
                paths = [option for option in previous.collect.options if not option.default]
                default_path = (
                    [option for option in previous.collect.options if option.default][0]
                    if any(option.default for option in previous.collect.options)
                    else None
                )
                path = None

                for condition in paths:
                    test = (
                        re.compile(condition.pattern, re.I)
                        if condition.type in ["string", "regex"]
                        else None
                    )
                    if (
                        step["result"]
                        and isinstance(step["result"], str)
                        and test
                        and test.match(step["result"])
                    ):
                        path = condition
                        break

                # take default path if one is set
                if not path:
                    path = default_path

                if path:
                    if path.action != "wait" and previous.collect and previous.collect.multiple:
                        pass  # TODO: remove the final line of input

                    res = await self.handle_action(path, dc, step)
                    if res is not False:
                        return res

        # was the dialog canceled during the last action?
        if not dc.active_dialog:
            return await self.end(dc)

        # Handle the current step
        if step["index"] < len(thread):
            line = thread[step["index"]]

            # If a prompt is defined in the script, use dc.prompt to call it.
            # This prompt must be a valid dialog defined somewhere in your code!
            if line.collect and line.action != "begin_dialog":
                try:
                    return await dc.prompt(
                        self._prompt, await self.make_outgoing(dc, line, step["values"])
                    )
                except Exception as err:
                    print(err)
                    await dc.context.send_activity(f"Failed to start prompt {self._prompt}")
                    return await step["next"]()
            else:
                # if there is text, attachments, or any channel data fields at all...
                if (
                    line.type
                    or line.text
                    or line.attachments
                    or line.attachment
                    or line.blocks
                    or (line.channel_data and len(line.channel_data))
                ):
                    await dc.context.send_activity(
                        await self.make_outgoing(dc, line, step["values"])
                    )
                elif not line.action:
                    print("Dialog contains invalid message", line)

                if line.action:
                    res = await self.handle_action(line, dc, step)
                    if res is not False:
                        return res

                return await step["next"](None)
        else:
            # End of script so just return to parent
            return await self.end(dc)

    async def run_step(
        self,
        dc: DialogContext,
        index: int,
        thread_name: str,
        reason: DialogReason,
        result: Any = None,
    ) -> Any:
        """
        Runs a dialog step based on the provided parameters.

        Args:
            dc (DialogContext): The current DialogContext.
            index (int): The index of the current step.
            thread_name (str): The name of the current thread.
            reason (DialogReason): The reason given for running this step.
            result (Any, optional): The result of the previous turn if any. Defaults to None.

        Returns:
            Promise[Any]: A promise representing the asynchronous operation.
        """
        # Update the step index
        state = dc.active_dialog.state
        state["step_index"] = index
        state["thread"] = thread_name

        # Create step context
        next_called = False
        step = {
            "index": index,
            "thread_length": len(self.script[thread_name]),
            "thread": thread_name,
            "state": state,
            "options": state["options"],
            "reason": reason,
            "result": result.text if result and result.text else result,
            "result_object": result,
            "values": state["values"],
            "next": lambda step_result: self.resume_dialog(dc, DialogReason.NextCalled, step_result)
            if not next_called
            else None,
        }

        # did we just start a new thread?
        # if so, run the before stuff.
        if index == 0:
            await self.run_before(step["thread"], dc, step)

            # did we just change threads? if so, restart
            if index != step["index"] or thread_name != step["thread"]:
                return await self.run_step(
                    dc, step["index"], step["thread"], DialogReason.NextCalled
                )  # , step["values"]);

        # Execute step
        res = await self.on_step(dc, step)

        return res

    async def end(self, dc: DialogContext) -> DialogTurnStatus:
        """
        Ends the dialog and triggers any handlers bound using `after()`.

        Args:
            dc (DialogContext): The current DialogContext.

        Returns:
            DialogTurnStatus: The status of the dialog turn.
        """
        # TODO: may have to move these around
        # shallow copy todo: may need deep copy
        # protect against canceled dialog.
        if dc.active_dialog and dc.active_dialog.state:
            result = {**dc.active_dialog.state["values"]}
            await dc.end_dialog(result)
            await self.run_after(dc, result)
        else:
            await dc.end_dialog()

        return DialogTurnStatus.Complete

    async def make_outgoing(self, dc: DialogContext, line: BotMessageTemplate, vars: dict) -> dict:
        """
        Translates a line from the dialog script into an Activity.
        Responsible for doing token replacement.

        Args:
            dc (Any): Dialog context.
            line (Dict[str, Any]): A message template from the script.
            vars (Dict[str, Any]): An object containing key/value pairs used to do token replacement
                                    on fields in the message template.

        Returns:
            Any: Processed output based on the provided line.
        """
        outgoing = None
        text = ""

        # If the text is just a string, use it.
        # Otherwise, if it is an array, pick a random element.
        if line.text and isinstance(line.text, str):
            text = line.text
        # If text is a function, call the function to get the actual text value.
        elif line.text and isinstance(line.text, Callable):
            text = await line.text(line, vars)
        elif isinstance(line.text, list):
            text = random.choice(line.text)

        # Use Bot Framework's message factory to construct the initial object.
        if line.quick_replies and not isinstance(line.quick_replies, callable):
            outgoing: Activity = MessageFactory.suggested_actions(
                [
                    CardAction(
                        type=ActionTypes.post_back,
                        title=reply["title"],
                        text=reply["payload"],
                        display_text=reply["title"],
                        value=reply["payload"],
                    )
                    for reply in line.quick_replies
                ],
                text,
            )
        else:
            outgoing: Activity = MessageFactory.text(text)

        outgoing.channel_data = outgoing.channel_data if outgoing.channel_data else {}

        if line.attachment_layout:
            outgoing.attachment_layout = line.attachment_layout

        if callable(line.quick_replies):
            quick_replies = await line.quick_replies(line, vars)
            outgoing.channel_data["quick_replies"] = quick_replies
            outgoing.suggested_actions = {
                "actions": [
                    {
                        "type": ActionTypes.PostBack,
                        "title": reply["title"],
                        "text": reply["payload"],
                        "display_text": reply["title"],
                        "value": reply["payload"],
                    }
                    for reply in quick_replies
                ]
            }

        if callable(line.attachment):
            outgoing.channel_data["attachment"] = await line.attachment(line, vars)

        if callable(line.attachments):
            attachments = await line.attachments(line, vars)
            outgoing.attachments = outgoing.channel_data["attachments"] = attachments

        if callable(line.blocks):
            outgoing.channel_data["blocks"] = await line.blocks(line, vars)

        # Quick replies are used by Facebook and Web adapters, but in a different way than they are for Bot Framework.
        # In order to make this as easy as possible, copy these fields for the developer into channelData.
        if line.quick_replies and not callable(line.quick_replies):
            outgoing.channel_data["quick_replies"] = deepcopy(line.quick_replies)

        # Similarly, attachment and blocks fields are platform specific.
        # Handle Slack Block attachments.
        if line.blocks and not callable(line.blocks):
            outgoing.channel_data["blocks"] = deepcopy(line.blocks)

        # Handle Facebook attachments.
        if line.attachment and not callable(line.attachment):
            outgoing.channel_data["attachment"] = deepcopy(line.attachment)

        # Set the type.
        if line.type:
            outgoing.type = deepcopy(line.type)

        # Copy all the values in channelData fields.
        if line.channel_data and len(line.channel_data) > 0:
            channel_data_parsed = self.parse_templates_recursive(deepcopy(line.channel_data), vars)

            # Merge channelData fields.
            outgoing.channel_data.update(channel_data_parsed)

        # bot_worker = self._controller.spawn(dc)
        # self._controller.middleware.send(bot_worker, outgoing, )

        return outgoing

    def parse_templates_recursive(self, attachments: any, vars: any) -> any:
        """
        Responsible for doing token replacements recursively in attachments and other multi-field properties of the message.

        Args:
            attachments (any): Some object or array containing values for which token replacements should be made.
            vars (any): An object defining key/value pairs used for the token replacements.

        Returns:
            any: The updated attachments with token replacements.
        """
        if attachments and isinstance(attachments, list):
            for a in range(len(attachments)):
                for key in attachments[a]:
                    if isinstance(attachments[a][key], str):
                        attachments[a][key] = attachments[a][key].format(**vars)
                    else:
                        attachments[a][key] = self.parse_templates_recursive(
                            attachments[a][key], vars
                        )
        elif isinstance(attachments, dict):
            for key in attachments:
                if isinstance(attachments[key], str):
                    attachments[key] = attachments[key].format(**vars)
                else:
                    attachments[key] = self.parse_templates_recursive(attachments[key], vars)

        return attachments

    async def goto_thread_action(
        self, thread: str, dc: DialogContext, step: BotConversationStep
    ) -> Any:
        """
        Handle the scripted "gotothread" action - requires an additional call to runStep.

        Args:
            thread (str): The name of the thread to jump to.
            dc (DialogContext): The current DialogContext.
            step (BotConversationStep): The current step object.

        Returns:
            Any: The result of running the step.
        """
        step["thread"] = thread
        step["index"] = 0

        return await self.run_step(
            dc, step["index"], step["thread"], DialogReason.nextCalled, step["values"]
        )

    async def handle_action(self, path: dict, dc: DialogContext, step: BotConversationStep) -> Any:
        """
        Accepts a Botkit script action, and performs that action.

        Args:
            path (dict): A conditional path.
            dc (DialogContext): The current DialogContext.
            step (BotConversationStep): The current step object.

        Returns:
            Any: The result of performing the action.
        """
        worker = None

        if "handler" in path:
            index = step["index"]
            thread_name = step["thread"]
            result = step["result"]
            response = result["text"] if result else None

            # spawn a bot instance so devs can use API or other stuff as necessary
            bot = await self._controller.spawn(dc)

            # create a convo controller object
            convo = botgen.BotDialogWrapper(dc, step)

            activedialog = dc.active_dialog.id

            await path["handler"](
                response,
                convo,
                bot,
                dc.context.turn_state.get("botkitMessage") or dc.context.activity,
            )

            if not dc.active_dialog:
                return False

            # did we change dialogs? if so, return an endofturn because the new dialog has taken over.
            if activedialog != dc.active_dialog.id:
                return Dialog.end_of_turn

            # did we just change threads? if so, restart this turn
            if index != step["index"] or thread_name != step["thread"]:
                return await self.run_step(
                    dc, step["index"], step["thread"], DialogReason.next_called, None
                )

            return False

        action = path.get("action")

        if action == "next":
            pass  # noop
        elif action == "complete":
            step["values"]["_status"] = "completed"
            return await self.end(dc)
        elif action == "stop":
            step["values"]["_status"] = "canceled"
            return await self.end(dc)
        elif action == "timeout":
            step["values"]["_status"] = "timeout"
            return await self.end(dc)
        elif action == "execute_script":
            worker = await self._controller.spawn(dc)

            await worker.replace_dialog(
                path["execute"]["script"], {"thread": path["execute"]["thread"], **step["values"]}
            )

            return DialogTurnStatus(DialogTurnStatus.Waiting)
        elif action == "beginDialog":
            worker = await self._controller.spawn(dc)

            await worker.begin_dialog(
                path["execute"]["script"], {"thread": path["execute"]["thread"], **step["values"]}
            )
            return DialogTurnStatus(DialogTurnStatus.waiting)
        elif action == "repeat":
            return await self.run_step(
                dc, step["index"] - 1, step["thread"], DialogReason.NextCalled
            )
        elif action == "wait":
            # reset the state so we're still on this step.
            step.state["stepIndex"] = step["index"] - 1
            # send a waiting status
            return DialogTurnStatus(DialogTurnStatus.Waiting)
        else:
            # the default behavior for unknown action in botkit is to gotothread
            if path["action"] in self.script:
                return await self.goto_thread_action(path["action"], dc, step)
            print("NOT SURE WHAT TO DO WITH THIS!!", path)
            return False
