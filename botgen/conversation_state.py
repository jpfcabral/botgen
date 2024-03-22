from botbuilder.core import ConversationState
from botbuilder.core import TurnContext


class BotConvoState(ConversationState):
    def get_storage_key(self, turn_context: TurnContext) -> str:
        """
        A customized version of [ConversationState](https://docs.microsoft.com/en-us/javascript/api/botbuilder-core/conversationstate?view=botbuilder-ts-latest) that  overide the [getStorageKey](#getStorageKey) method to create a more complex key value.
        This allows Bot to automatically track conversation state in scenarios where multiple users are present in a single channel,
        or when threads or sub-channels parent channel that would normally collide based on the information defined in the conversation address field.
        Note: This is used automatically inside Bot and developers should not need to directly interact with it.
        """

        activity = turn_context.activity
        channel_id = turn_context.activity.channel_id

        if not activity.conversation or not activity.conversation["id"]:
            raise Exception("missing activity.conversation")

        return f"{channel_id}/conversations/{activity.conversation['id']}"
