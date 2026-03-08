import boto3
import json
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AgentCoreService:
    def __init__(self, agent_arn, client=None):
        self.client = client or boto3.client("bedrock-agentcore")
        self.agent_arn = agent_arn

    def invoke_agent(self, user_id: str, prompt: str, session_id: str) -> str:
        """
        Args:
            user_id:    Cognito sub — stable identity for long-term memory (actorId).
            prompt:     User message.
            session_id: Unique ID per conversation — same value for all messages in a
                        conversation, new UUID when the conversation starts fresh.
                        Must be at least 33 characters.
        """
        try:
            # actorId: stable per user, used for long-term memory across sessions
            actor_id = f"ioschat:{user_id}"

            payload = json.dumps({"prompt": prompt, "actor_id": actor_id})

            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_arn,
                runtimeSessionId=session_id,
                runtimeUserId=actor_id,
                payload=payload.encode(),
            )

            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode("utf-8"))

            if content:
                text = "".join(content)
                try:
                    return json.loads(text).get("result", text)
                except json.JSONDecodeError:
                    return text

            return "No response from agent"
        except ClientError as e:
            logger.error(f"AgentCore error: {e}")
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Error: {e}"
