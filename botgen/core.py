from abc import ABC
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

from aiohttp import web
from botbuilder.core import BotAdapter
from botbuilder.core import MemoryStorage
from botbuilder.core import Storage
from botbuilder.core import TurnContext
from botbuilder.dialogs import Dialog
from botbuilder.dialogs import DialogContext
from botbuilder.dialogs import DialogSet
from botbuilder.dialogs import DialogTurnStatus
from botbuilder.dialogs import WaterfallDialog
from botbuilder.schema import Activity
from botbuilder.schema import ConversationReference
from loguru import logger

from botgen.bot_worker import BotWorker
from botgen.conversation_state import BotConversationState


@dataclass
class BotMessage:
    type: Optional[str] = None
    text: Optional[str] = None
    value: Optional[str] = None
    user: Optional[str] = None
    channel: Optional[str] = None
    reference: Optional[ConversationReference] = None
    incoming_message: Optional[Activity] = None


class BotPlugin(ABC):
    name: str
    middlewares: dict


@dataclass
class BotTrigger:
    type: str
    pattern: str | BotMessage
    handler: Callable


@dataclass
class Middleware:
    spawn: Callable
    ingest: Callable
    send: Callable
    receive: Callable
    interpret: Callable


class BotPlugin:
    """
    A plugin for Bot that can be loaded into the core bot object.
    """

    def __init__(
        self,
        name: str,
        middlewares: Optional[Dict[str, Any]] = None,
        init: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        """
        Create a new BotPlugin instance.

        Args:
            name (str): The name of the plugin.
            middlewares (dict): A dictionary of middleware functions that can be used to extend the bot's functionality.
            init (Callable): A function that will be called when the plugin is loaded.
            **kwargs: Additional arguments that can be used to configure the plugin.
        """
        self.name = name
        self.middlewares = middlewares
        self.init = init
        self.__annotations__ = kwargs


class Bot:
    version: str
    middleware = Middleware
    plugins: list
    storage: Storage
    webserver: any  # TODO: Select a default python web framework
    http: any
    adapter: BotAdapter
    dialog_set: DialogSet
    path: str
    booted: bool

    def __init__(
        self,
        webhook_uri: str = "/api/messages",
        dialog_state_property: str = "dialogState",
        adapter: BotAdapter = None,
        adapter_config: dict = None,
        webserver: any = None,
        webserver_middlewares: str = None,
        storage: Storage = None,
        disable_webserver: bool = None,
        disable_console: bool = None,
        json_limit: str = "100kb",
        url_encoded_limit: str = "100kb",
    ) -> None:

        self.webhook_uri = webhook_uri
        self.dialog_state_property = dialog_state_property
        self.adapter = adapter
        self.adapter_config = adapter_config
        self.webserver = webserver
        self.webserver_middlewares = webserver_middlewares
        self.storage = storage
        self.disable_webserver = disable_webserver
        self.disable_console = disable_console
        self.json_limit = json_limit
        self.url_encoded_limit = url_encoded_limit

        self._events: dict[list] = {}
        self._triggers: dict[list[BotTrigger]] = {}
        self._interrupts: dict[list[BotTrigger]] = {}
        self._dependencies: dict = {}
        self._boot_complete_handlers: list[Callable] = []

        self.booted = False
        self.add_dep("booted")

        self._storage = MemoryStorage()

        self._conversation_state = BotConversationState(storage=self._storage)

        dialog_state = self._conversation_state.create_property(self.dialog_state_property)

        self.dialog_set = DialogSet(dialog_state=dialog_state)

        self.webserver = web.Application()

        if self.webserver:
            self.configure_webhook()

        self.plugin_list = []
        self._plugins = {}

        if self.adapter:
            self.use_plugin(self.adapter)

        self.complete_dep("booted")

    async def process_incoming_message(self, request: web.Request):
        """ """
        body = await self.adapter.process_activity(request, self.handle_turn)

        return web.json_response(body)

    def configure_webhook(self):
        """ """
        self.add_dep("webadapter")
        self.webserver.add_routes([web.post(self.webhook_uri, self.process_incoming_message)])
        self.complete_dep("webadapter")

    async def handle_turn(self, turn_context: TurnContext):
        """ """

        message = BotMessage(
            type=turn_context.activity.type,
            user=turn_context.activity.from_property["id"],
            text=turn_context.activity.text,
            channel=turn_context.activity.conversation["id"],
            value=turn_context.activity.value,
            reference=TurnContext.get_conversation_reference(turn_context.activity),
            incoming_message=turn_context.activity,
        )

        turn_context.turn_state["BotMessage"] = message

        dialog_context = await self.dialog_set.create_context(turn_context=turn_context)

        bot_worker = await self.spawn(dialog_context)

        await self._process_trigger_and_events(bot_worker=bot_worker, message=message)

    async def _process_trigger_and_events(self, bot_worker: BotWorker, message: BotMessage):
        """ """
        listen_results = await self._listen_for_triggers(bot_worker=bot_worker, message=message)

        if listen_results:
            return listen_results

        trigger_results = await self.trigger(message.type, bot_worker, message)

        return trigger_results

    async def trigger(self, event: str, bot_worker: BotWorker, message: BotMessage):
        """ """
        if event in self._events:
            for ev in self._events[event]:
                handler_result = await ev(bot_worker, message)

                if handler_result:
                    break

    async def _listen_for_triggers(self, bot_worker: BotWorker, message: BotMessage):
        """ """
        if message.type in self._triggers:
            triggers: list[Callable] = self._triggers[message.type]

            for trigger in triggers:
                test_results = await self._test_trigger(trigger=trigger, message=message)

                if test_results:
                    trigger_results = await trigger.handler(bot_worker, message)
                    return trigger_results

        return False

    async def _test_trigger(self, trigger: BotTrigger, message: BotMessage):
        """ """

        if isinstance(trigger.pattern, str):
            return True if message.text == trigger.pattern else False

        if isinstance(trigger.pattern, list):
            return True if message.text in trigger.pattern else False

        if isinstance(trigger.pattern, Callable):
            return await trigger.pattern(message)

        return False

    def ready(self, handler: Callable) -> None:
        """ """

        if self.booted:
            handler(self)
        else:
            self._boot_complete_handlers.append(handler)

    def hears(self, pattern: str | list, handler: Callable, event: str = "message") -> None:
        """
        Configures handler by looking for specific incoming word(s). You can add as many
        hears you want, but the bot will stop processing in the first pattern is matched.

        Args:
            pattern (str|list): string or list of string to trigger specific handler. e.g: hello
            handler (Callable): function to be called when pattern matches
            event (str): message type
        """
        bot_trigger = BotTrigger(type=None, pattern=pattern, handler=handler)

        if not event in self._triggers:
            self._triggers[event] = []

        self._triggers[event].append(bot_trigger)

    def on(self, event: str, handler: Callable):

        if not event in self._events:
            self._events[event] = []

        self._events[event].append(handler)

    async def spawn(
        self, config: TurnContext | DialogContext = None, custom_adapter: BotAdapter = None
    ) -> BotWorker:
        """ """
        _config = dict()

        if isinstance(config, DialogContext):
            _config = {
                "dialog_context": config,
                "reference": TurnContext.get_conversation_reference(config.context.activity),
                "context": config.context,
                "activity": config.context.activity,
            }

            return BotWorker(self, config=_config)

    def start(self):
        web.run_app(self.webserver)

    def add_dep(self, name: str) -> None:
        """
        Add a dependency to Bot's bootup process that must be marked as completed using complete_dep().

        Parameters:
            name (str): The name of the dependency that is being loaded.
        """
        logger.debug(f"Waiting for {name}")
        self._dependencies[name] = False

    def complete_dep(self, name: str) -> bool:
        """
        Mark a bootup dependency as loaded and ready to use.

        Parameters:
            name (str): The name of the dependency that has completed loading.

        Returns:
            bool: True if all dependencies have been marked complete, otherwise False.
        """
        logger.debug(f"{name} ready")

        self._dependencies[name] = True

        if all(self._dependencies.values()):
            # Everything is done!
            self._signal_boot_complete()
            return True
        else:
            return False

    def _signal_boot_complete(self) -> None:
        """
        This function gets called when all of the bootup dependencies are completely loaded.
        """
        self.booted = True
        for handler in self._boot_complete_handlers:
            handler()

    def use_plugin(self, plugin_or_function: Callable | BotPlugin) -> None:
        """
        Load a plugin module and bind all included middlewares to their respective endpoints.

        Parameters:
            plugin_or_function (Callable or BotPlugin): A plugin module in the form of a function(bot) {...}
                that returns {name, middlewares, init} or an object in the same form.
        """
        if callable(plugin_or_function):
            plugin = plugin_or_function(self)
        else:
            plugin = plugin_or_function

        if plugin.name:
            try:
                self._register_plugin(plugin.name, plugin)
            except Exception as err:
                logger.warning(f"ERROR IN PLUGIN REGISTER: {err}")

    def _register_plugin(self, name: str, endpoints: BotPlugin) -> None:
        """
        Called from usePlugin to do the actual binding of middlewares for a plugin that is being loaded.

        Parameters:
            name (str): Name of the plugin.
            endpoints (BotPlugin): The plugin object that contains middleware endpoint definitions.
        """

        if name in self.plugin_list:
            logger.debug("Plugin already enabled:", name)
            return

        self.plugin_list.append(name)

        if endpoints.init:
            try:
                endpoints.init(self)
            except Exception as err:
                if err:
                    raise err

        logger.debug("Plugin Enabled:", name)
