from aws_cdk import (
    RemovalPolicy,
    aws_bedrockagentcore as bedrockagentcore,
    aws_iam as iam,
)
from constructs import Construct

# How many days to retain memories
MEMORY_EXPIRY_DAYS = 90


class AgentCoreMemory(Construct):
    """AgentCore Memory Store for long-term user memory across sessions.

    Stores two namespaces per user:
    - /users/{actor_id}/facts       → semantic facts about the user
    - /users/{actor_id}/preferences → user preferences and habits
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Execution role for the memory store
        memory_role = iam.Role(
            self, "MemoryRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
            ],
        )
        memory_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:*", "bedrock-agentcore:*"],
            resources=["*"],
        ))

        self.memory = bedrockagentcore.CfnMemory(
            self, "Memory",
            name="MetaChatAgentMemory",
            description="Long-term memory for Meta Chat Agent — stores user facts and preferences across sessions",
            event_expiry_duration=MEMORY_EXPIRY_DAYS,
            memory_execution_role_arn=memory_role.role_arn,
            memory_strategies=[
                bedrockagentcore.CfnMemory.MemoryStrategyProperty(
                    semantic_memory_strategy=bedrockagentcore.CfnMemory.SemanticMemoryStrategyProperty(
                        name="UserFacts",
                    )
                ),
                bedrockagentcore.CfnMemory.MemoryStrategyProperty(
                    user_preference_memory_strategy=bedrockagentcore.CfnMemory.UserPreferenceMemoryStrategyProperty(
                        name="UserPreferences",
                    )
                ),
            ],
        )
