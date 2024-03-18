import dataclasses
from datetime import datetime
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Coroutine
from typing import List

from aiohttp.web import Request
from botbuilder.core import BotAdapter
from botbuilder.core import TurnContext
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import ConversationReference
from botbuilder.schema import ResourceResponse
from loguru import logger

from botgen.core import BotMessage


class TelegramAdapter(BotAdapter):
    def __init__(self, on_turn_error: Callable[[TurnContext, Exception], Awaitable] = None):
        super().__init__(on_turn_error)

    def send_activities(
        self, context: TurnContext, activities: List[Activity]
    ) -> Coroutine[Any, Any, List[ResourceResponse]]:
        """"""
