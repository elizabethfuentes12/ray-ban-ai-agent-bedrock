from aws_cdk import aws_bedrockagentcore as bedrockagentcore, aws_s3_assets as s3_assets
from constructs import Construct
from .agentcore_role import AgentcoreExecutionRole
import os
import subprocess


class AgentCoreRuntime(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

    def create_runtime(self, name, description, s3_bucket, environment_variables=None):
        directory = os.path.join(os.path.dirname(__file__), "..", "agent_files")
        if environment_variables is None:
            environment_variables = {}

        execution_role = AgentcoreExecutionRole(self, "ExecutionRole")

        zip_path = os.path.join(directory, "deployment_package.zip")
        if not os.path.exists(zip_path):
            script_path = os.path.join(os.path.dirname(__file__), "..", "create_deployment_package.sh")
            result = subprocess.run(["bash", script_path], cwd=os.path.join(os.path.dirname(__file__), ".."), capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create deployment package: {result.stderr}")

        code_asset = s3_assets.Asset(self, "AgentCodeAsset", path=zip_path)
        code_asset.grant_read(execution_role.role)

        self.runtime = bedrockagentcore.CfnRuntime(
            self, "Runtime",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                code_configuration=bedrockagentcore.CfnRuntime.CodeConfigurationProperty(
                    code=bedrockagentcore.CfnRuntime.CodeProperty(
                        s3=bedrockagentcore.CfnRuntime.S3LocationProperty(
                            bucket=code_asset.s3_bucket_name,
                            prefix=code_asset.s3_object_key,
                        )
                    ),
                    entry_point=["chat_agent.py"],
                    runtime="PYTHON_3_11",
                )
            ),
            agent_runtime_name=name,
            description=description,
            environment_variables=environment_variables,
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            role_arn=execution_role.role.role_arn,
        )
        self.runtime.node.add_dependency(execution_role.role)
        self.runtime.node.add_dependency(code_asset)
        self.execution_role = execution_role
        return self.runtime
