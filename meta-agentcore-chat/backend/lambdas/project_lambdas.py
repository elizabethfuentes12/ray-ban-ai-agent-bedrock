from aws_cdk import (
    Duration,
    aws_lambda,
    aws_iam as iam,
)
from constructs import Construct


LAMBDA_TIMEOUT = 300  # 5 minutes

BASE_LAMBDA_CONFIG = dict(
    timeout=Duration.seconds(LAMBDA_TIMEOUT),
    memory_size=512,
    tracing=aws_lambda.Tracing.ACTIVE
)

COMMON_LAMBDA_CONF = dict(
    runtime=aws_lambda.Runtime.PYTHON_3_11,
    **BASE_LAMBDA_CONFIG
)


class ProjectLambdas(Construct):
    """Lambda functions for Meta Chat Agent"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Lambda IAM Role with AgentCore permissions
        lambda_role = iam.Role(
            self, "ChatHandlerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=["*"],
            )
        )

        # Chat Handler Lambda
        self.chat_handler = aws_lambda.Function(
            self, "ChatHandler",
            handler="lambda_function.lambda_handler",
            description="Process chat requests and invoke AgentCore",
            code=aws_lambda.Code.from_asset("./lambdas/code/chat_handler"),
            role=lambda_role,
            **COMMON_LAMBDA_CONF
        )
