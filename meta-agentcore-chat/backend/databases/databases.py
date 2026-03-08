from aws_cdk import RemovalPolicy, aws_dynamodb as ddb
from constructs import Construct

TABLE_CONFIG = dict(removal_policy=RemovalPolicy.DESTROY, billing_mode=ddb.BillingMode.PAY_PER_REQUEST)


class Tables(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.messages = ddb.Table(
            self, "Messages",
            partition_key=ddb.Attribute(name="id", type=ddb.AttributeType.STRING),
            **TABLE_CONFIG,
        )
