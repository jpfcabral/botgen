from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from botbuilder.core import BotAdapter
from botbuilder.core import TurnContext
from botbuilder.schema import Activity
from loguru import logger
from slack_sdk.web import WebClient


class SlackAdapter(BotAdapter):
    def __init__(
        self,
        verification_token: Optional[str] = None,
        client_signing_secret: Optional[str] = None,
        bot_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        oauth_version: Optional[str] = "v1",
        redirect_uri: Optional[str] = None,
        get_token_for_team: Optional[Callable[[str], str]] = None,
        get_bot_user_by_team: Optional[Callable[[str], str]] = None,
        enable_incomplete: Optional[bool] = False,
        **kwargs
    ) -> None:
        """
        Create a Slack adapter.

        The SlackAdapter can be used in 2 modes:
            * As an "[internal integration](https://api.slack.com/internal-integrations) connected to a single Slack workspace
            * As a "[Slack app](https://api.slack.com/slack-apps) that uses oauth to connect to multiple workspaces and can be submitted to the Slack app.

        Args:
            - verification_token: Legacy method for validating the origin of incoming webhooks. Prefer `client_signing_secret` instead.
            - client_signing_secret: A token used to validate that incoming webhooks originated with Slack.
            - bot_token: A token (provided by Slack) for a bot to work on a single workspace.
            - client_id: The oauth client id provided by Slack for multi-team apps.
            - client_secret: The oauth client secret provided by Slack for multi-team apps.
            - scopes: A list of scope names that are being requested during the oauth process. Must match the scopes defined at api.slack.com.
            - oauth_version: Which version of Slack's oauth protocol to use, v1 or v2. Defaults to v1.
            - redirect_uri: The URL users will be redirected to after an oauth flow. In most cases, should be `https://<mydomain.com>/install/auth`.
            - get_token_for_team: A method that receives a Slack team id and returns the bot token associated with that team. Required for multi-team apps.
            - get_bot_user_by_team: A method that receives a Slack team id and returns the bot user id associated with that team. Required for multi-team apps.
            - enable_incomplete: Allow the adapter to startup without a complete configuration. This is risky as it may result in a non-functioning or insecure adapter. This should only be used when getting started.
        """
        self.verification_token: str = verification_token
        self.client_signing_secret: str = client_signing_secret
        self.bot_token: str = bot_token
        self.client_id: str = client_id
        self.client_secret: str = client_secret
        self.scopes: str = scopes
        self.oauth_version: str = oauth_version
        self.redirect_uri: str = redirect_uri
        self.get_token_for_team: Callable = get_token_for_team
        self.get_bot_user_by_team: Callable = get_bot_user_by_team
        self.enable_incomplete: bool = enable_incomplete
        self.options = kwargs

    async def get_api(self, activity: Activity) -> WebClient:
        """
        Get a Slack API client with the correct credentials based on the team identified in the incoming activity.

        This is used by many internal functions to get access to the Slack API, and is exposed as `bot.api` on any bot worker instances.

        Parameters:
            activity (Partial[Activity]): An incoming message activity.

        Returns:
            WebClient: A WebClient instance with the correct credentials.
        """
        # use activity.channel_data.team.id (the slack team id) and get the appropriate token using getTokenForTeam
        if self.slack:
            return self.slack

        team_id = activity.conversation.get("team").get("id")

        if team_id:
            token = await self.options.get("getTokenForTeam")(team_id)
            if not token:
                raise ValueError("Missing credentials for team.")
            return WebClient(token)

        # No API can be created, this is
        logger.warning("Unable to create API based on activity: %s", activity)

    def activity_to_slack(self, activity: Activity) -> Dict[str, Union[str, Any]]:
        """
        Formats a BotBuilder activity into an outgoing Slack message.

        Parameters:
            activity (Activity): A BotBuilder Activity object.

        Returns:
            dict: A Slack message object with {text, attachments, channel, thread_ts} as well as any fields found in activity.channel_data.
        """
        channel_id = activity.conversation["id"]
        thread_ts = activity.conversation["thread_ts"]

        message = {
            "ts": activity.id,
            "text": activity.text,
            "attachments": activity.attachments,
            "channel": channel_id,
            "thread_ts": thread_ts,
        }

        # If channelData is specified, overwrite any fields in message object
        if activity.channel_data:
            for key, value in activity.channel_data.items():
                message[key] = value

        # Should this message be sent as an ephemeral message
        if message.get("ephemeral"):
            message["user"] = activity.recipient.id

        if message.get("icon_url") or message.get("icon_emoji") or message.get("username"):
            message["as_user"] = False

        # as_user flag is deprecated on v2
        if message.get("as_user") is False and self.options.get("oauthVersion") == "v2":
            del message["as_user"]

        return message

    async def send_activities(self, context: TurnContext, activities: List[Activity]) -> List:
        """
        Standard BotBuilder adapter method to send a message from the bot to the messaging API.

        [BotBuilder reference docs](https://docs.microsoft.com/en-us/javascript/api/botbuilder-core/botadapter?view=botbuilder-ts-latest#sendactivities).

        Parameters:
            context (TurnContext): A TurnContext representing the current incoming message and environment.
            activities (List[Partial[Activity]]): An array of outgoing activities to be sent back to the messaging API.

        Returns:
            List: A list of ResourceResponse objects representing the responses from the messaging API.
        """
        responses = []
        for activity in activities:
            if activity.type == "message":
                message = self.activity_to_slack(activity)

                try:
                    slack = await self.get_api(context.activity)
                    result = None

                    if message.get("ephemeral"):
                        logger.debug("chat.postEphemeral:", message)
                        result = await slack.chat_postEphemeral(message)
                    else:
                        logger.debug("chat.postMessage:", message)
                        result = await slack.chat_postMessage(message)

                    if result.get("ok") is True:
                        responses.append(
                            {
                                "id": result["ts"],
                                "activityId": result["ts"],
                                "conversation": {"id": result["channel"]},
                            }
                        )
                    else:
                        print("Error sending activity to API:", result)
                except Exception as err:
                    print("Error sending activity to API:", err)
            else:
                # If there are ever any non-message type events that need to be sent, do it here.
                logger.debug(
                    "Unknown message type encountered in sendActivities: ", activity["type"]
                )

        return responses
