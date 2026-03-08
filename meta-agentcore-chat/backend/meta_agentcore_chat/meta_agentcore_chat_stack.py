"""
Meta AgentCore Chat Stack

Architecture:
  iOS App → API Gateway → Lambda → AgentCore Runtime (with tools) → Response
"""

from aws_cdk import Stack, RemovalPolicy, CfnOutput, aws_s3 as s3, aws_iam as iam
from constructs import Construct
from agentcore import AgentCoreRuntime
from lambdas import ProjectLambdas
from databases import Tables
from cognito import UserAuth
from api_gateway import ChatAPI
from memory import AgentCoreMemory


class MetaAgentcoreChatStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stk = Stack.of(self)
        region = stk.region

        # Configurable via cdk deploy -c model_id=... -c tavily_api_key=... -c team_id=... -c bundle_id=...
        model_id = self.node.try_get_context("model_id") or "anthropic.claude-3-haiku-20240307-v1:0"
        tavily_api_key = self.node.try_get_context("tavily_api_key") or ""
        team_id = self.node.try_get_context("team_id") or ""
        bundle_id = self.node.try_get_context("bundle_id") or "com.example.MetaChatAgent"
        obsidian_bucket = self.node.try_get_context("obsidian_bucket") or "your-obsidian-s3-bucket"
        personal_account_role_arn = self.node.try_get_context("personal_account_role_arn") or ""

        # S3 bucket
        self.s3_bucket = s3.Bucket(self, "S3Bucket", removal_policy=RemovalPolicy.DESTROY, versioned=True)

        # AgentCore Memory (long-term user memory across sessions)
        memory = AgentCoreMemory(self, "Memory")

        # AgentCore Runtime — chat agent with tools including save_to_obsidian
        self.agent_core_runtime = AgentCoreRuntime(self, "AgentCore")
        agent_runtime = self.agent_core_runtime.create_runtime(
            name="MetaChatAgent",
            description="Conversational chat agent with tools for iOS app",
            s3_bucket=self.s3_bucket,
            environment_variables={
                "S3_BUCKET": self.s3_bucket.bucket_name,
                "AWS_REGION": region,
                "MODEL_ID": model_id,
                "BEDROCK_AGENTCORE_MEMORY_ID": memory.memory.attr_memory_id,
                "OBSIDIAN_BUCKET": obsidian_bucket,
                "PERSONAL_ACCOUNT_ROLE_ARN": personal_account_role_arn,
                "SSM_TAVILY_API_KEY": "/metachat/tavily_api_key",
                "SSM_GITHUB_PAT": "/metachat/github_pat",
                "SSM_ANTHROPIC_API_KEY": "/metachat/anthropic_api_key",
                "SSM_OPENAI_API_KEY": "/metachat/openai_api_key",   # optional
            },
        )

        # Grant execution role write-only access to the Obsidian bucket (same account)
        if obsidian_bucket and not personal_account_role_arn:
            self.agent_core_runtime.execution_role.role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:PutObject"],
                    resources=[f"arn:aws:s3:::{obsidian_bucket}/*"],
                )
            )

        # DynamoDB
        databases = Tables(self, "Databases")

        # Cognito authentication
        auth = UserAuth(self, "UserAuth")

        # Lambda functions
        lambdas = ProjectLambdas(self, "Lambdas")
        databases.messages.grant_read_write_data(lambdas.chat_handler)
        lambdas.chat_handler.add_environment("TABLE_NAME", databases.messages.table_name)
        lambdas.chat_handler.add_environment("AGENT_ARN", agent_runtime.attr_agent_runtime_arn)
        lambdas.chat_handler.add_environment("TEAM_ID", team_id)
        lambdas.chat_handler.add_environment("BUNDLE_ID", bundle_id)

        # API Gateway with Cognito authorization
        api_gateway = ChatAPI(
            self, "ChatAPI",
            user_pool=auth.user_pool,
            chat_handler=lambdas.chat_handler,
        )

        # Outputs
        CfnOutput(self, "ApiUrl", value=api_gateway.api.url)
        CfnOutput(self, "ApiKeyId", value=api_gateway.api_key.key_id)
        CfnOutput(self, "AgentRuntimeArn", value=agent_runtime.attr_agent_runtime_arn)
        CfnOutput(self, "MessagesTableName", value=databases.messages.table_name)
        CfnOutput(self, "ModelId", value=model_id, description="Model ID used by the agent")
        CfnOutput(self, "UniversalLinkDomain", value=f"{api_gateway.api.rest_api_id}.execute-api.{region}.amazonaws.com",
                  description="Domain for Universal Links in Meta Developer Center")
        CfnOutput(self, "UserPoolId", value=auth.user_pool.user_pool_id,
                  description="Cognito User Pool ID for iOS app")
        CfnOutput(self, "AppClientId", value=auth.app_client.user_pool_client_id,
                  description="Cognito App Client ID for iOS app")
        CfnOutput(self, "MemoryId", value=memory.memory.attr_memory_id,
                  description="AgentCore Memory ID for long-term user memory")
