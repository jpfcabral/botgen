from botgen import Bot
from botgen.adapters import WebAdapter
from botgen import BotWorker
from botgen import BotMessage

adapter = WebAdapter()
bot = Bot(adapter=adapter)

async def hello(bot_worker: BotWorker, message: BotMessage):
    await bot_worker.say(f"hello: {message.user}")

async def bye(bot_worker: BotWorker, message: BotMessage):
    await bot_worker.reply(message, f"bye, {message.user}")

async def my_function(message: BotMessage):
    if message.text == "func":
        return True

    return False

async def resp(bot_worker: BotWorker, message: BotMessage):
    await bot_worker.reply(message, f"resp to func, {message.user}")

bot.hears(pattern="hello", event="message", handler=hello)
bot.hears(pattern=["bye", "goodbye", "tchau", "see you"], event="message", handler=bye)
bot.hears(pattern=my_function, event="message", handler=resp)

bot.start()
