# Dialogs

Botgen system for multi-turn conversations builds upon BotBuilder's dialog system, offering a range of powerful features such as persistent conversation state, typed prompts with validation, and other advanced functionalities. Now, all these capabilities can be seamlessly integrated with Botgen!

Dialogs serve as predefined "maps" for conversations, capable of being triggered in various ways. Consider a dialog as the script for an interactive conversation that the bot can navigate, potentially branching based on user input. Dialogs can include conditional tests, branching patterns, and dynamic content. You can create dialogs using Botgen's intuitive syntax or BotBuilder's WaterfallDialogs.

To utilize a dialog, it must first be defined and added to the bot's dialog stack. Below is an example demonstrating the use of BotgenConversation dialog type.

## Basic usage

In this basic usage you can define a onboarding dialog every time someone join the chat.

```python
from botgen import Bot
from botgen.adapters import WebAdapter
from botgen import BotWorker
from botgen import BotMessage
from botgen import BotConversation

adapter = WebAdapter()
bot = Bot(adapter=adapter)

dialog = BotConversation(dialog_id="onboarding", controller=bot)

dialog.say("Hello!")
dialog.say("This is the botgen onboarding")

bot.add_dialog(dialog=dialog)

async def onboarding_dialog(bot_worker: BotWorker, message: BotMessage):
    await bot_worker.begin_dialog("onboarding")

bot.on("channel_join", onboarding_dialog)
bot.start()

```
