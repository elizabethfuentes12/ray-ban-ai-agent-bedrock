#!/usr/bin/env python3
import os
import aws_cdk as cdk
from meta_agentcore_chat.meta_agentcore_chat_stack import MetaAgentcoreChatStack

aws_account = os.environ.get("CDK_DEFAULT_ACCOUNT") or os.environ.get("AWS_ACCOUNT_ID")
aws_region = os.environ.get("CDK_DEFAULT_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2"

env = cdk.Environment(account=aws_account, region=aws_region)

app = cdk.App()
MetaAgentcoreChatStack(
    app, "MetaChatAgentCoreStack",
    description="Meta Ray-Ban AI chat agent — voice commands via glasses → AgentCore Runtime",
    env=env,
)
app.synth()
