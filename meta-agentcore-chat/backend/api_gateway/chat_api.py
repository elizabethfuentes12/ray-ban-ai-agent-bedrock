from aws_cdk import (
    aws_apigateway as apigw,
    aws_lambda,
    aws_cognito as cognito,
)
from constructs import Construct


class ChatAPI(Construct):
    """API Gateway with Cognito authorization for chat endpoints"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_pool: cognito.UserPool,
        chat_handler: aws_lambda.Function,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create API Gateway
        self.api = apigw.RestApi(
            self, "ChatApi",
            rest_api_name="MetaChatAgentCore",
            description="API for iOS Chat + AgentCore with Cognito auth",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["POST", "GET", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
                allow_credentials=True,
            ),
        )

        # Cognito Authorizer
        self.authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
            authorizer_name="CognitoAuth",
        )

        integration = apigw.LambdaIntegration(chat_handler, proxy=True)

        # POST /chat - protected with Cognito JWT token
        chat_resource = self.api.root.add_resource("chat")
        chat_resource.add_method(
            "POST",
            integration,
            authorizer=self.authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # GET / endpoint - Meta AI redirect (NO AUTH)
        self.api.root.add_method("GET", integration)

        # GET /.well-known/apple-app-site-association - Universal Links (NO AUTH)
        well_known = self.api.root.add_resource(".well-known")
        well_known.add_resource("apple-app-site-association").add_method("GET", integration)

        # Create API Key (for backward compatibility or public endpoints)
        self.api_key = self.api.add_api_key(
            "ChatApiKey",
            api_key_name="metachat-agent-key"
        )

        # Usage Plan
        usage_plan = self.api.add_usage_plan(
            "ChatUsagePlan",
            name="ChatUsagePlan",
            throttle=apigw.ThrottleSettings(rate_limit=50, burst_limit=100),
        )
        usage_plan.add_api_key(self.api_key)
        usage_plan.add_api_stage(stage=self.api.deployment_stage)
