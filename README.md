*Python-based open source developer tool for building chat bots, apps and custom integrations for major messaging platforms.*

This repository is inspired by the javascript library [Botkit](https://github.com/howdyai/botgen) and the [BotFramework SDK](https://github.com/microsoft/botframework-sdk) concepts.

### Adapters

You can connect major plataforms using the same bot core code by setting different adapters. Adapter is a interface between your bot and message plataforms.


| Adapter | Docs | Availability |
|---------| -----|--------------|
| Web     | | 0.0.1        |
| Telegram   | |              |
| Discord    | |              |
| Slack   | |              |
| Facebook   | |              |
| Twilio (SMS)   | |              |
| Whatsapp   | |              |

### Usage

Installation

`pip install botgen`

Copy and paste the code below to a file called `run.py`

```python
# run.py
from botgen import Bot
from botgen import BotMessage
from botgen import BotWorker
from botgen.adapters import WebAdapter

adapter = WebAdapter()
bot = Bot(adapter=adapter)

async def hello(bot_worker: BotWorker, message: BotMessage):
    await bot_worker.say("hello from bot")


bot.hears(pattern="hello", event="message", handler=hello)

bot.start()
```

So you can run the project using:

`python run.py`

Then start a conversation:

```bash
curl -L -X POST 'http://localhost:8080/api/messages' -H 'Content-Type: application/json' -d '{
	"user": "dummy",
    "text": "hello",
    "type": "message"
}'
```

### How to contribute
