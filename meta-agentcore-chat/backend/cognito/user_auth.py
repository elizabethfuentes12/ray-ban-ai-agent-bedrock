from aws_cdk import (
    RemovalPolicy,
    aws_cognito as cognito,
    Duration,
)
from constructs import Construct


class UserAuth(Construct):
    """Cognito User Pool and App Client for iOS authentication"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Cognito User Pool
        self.user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="MetaChatAgentUsers",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,  # RETAIN for production
        )

        # Create App Client for iOS
        self.app_client = self.user_pool.add_client(
            "iOSAppClient",
            user_pool_client_name="MetaChatAgent-iOS",
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True,
            ),
            generate_secret=False,  # iOS apps don't use client secret
            access_token_validity=Duration.hours(24),   # max allowed
            id_token_validity=Duration.hours(24),        # use glasses all day without interruption
            refresh_token_validity=Duration.days(3650),  # 10 years — effectively never re-login
        )
