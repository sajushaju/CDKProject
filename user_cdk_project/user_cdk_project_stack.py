from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    BundlingOptions,
)
from constructs import Construct


class CdkApiPostgresStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Create a VPC (Network)
        # This creates the private space for your DB and Lambda to talk safely
        vpc = ec2.Vpc(self, "MyApiVpc", max_azs=2)

        # 2. Create the PostgreSQL Database
        db_instance = rds.DatabaseInstance(
            self,
            "PostgresInstance",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            database_name="mydb",
            allocated_storage=20,
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
        )

        # 3. Create the Lambda Function
        # We use Python 3.13 to match your local installation
        api_lambda = _lambda.Function(
            self,
            "ApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.main",
            timeout=Duration.seconds(30),
            # This part uses Docker to package pg8000
            code=_lambda.Code.from_asset(
                "lambda",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -r . /asset-output",
                    ],
                ),
            ),
            vpc=vpc,
            environment={
                "DB_SECRET_ARN": db_instance.secret.secret_arn,
                "DB_NAME": "mydb",
            },
        )

        # 4. Permissions & Networking (The "Security Bridge")
        # Allows Lambda to read the DB password from Secrets Manager
        db_instance.secret.grant_read(api_lambda)

        # Opens the network port (5432) so Lambda can talk to Postgres
        db_instance.connections.allow_default_port_from(api_lambda)

        # 5. API Gateway
        # This creates the public URL for your Lambda
        api = apigw.LambdaRestApi(self, "MyApi", handler=api_lambda, proxy=False)

     # 1. This handles the base /items (GET all and POST)
        items = api.root.add_resource("items")
        items.add_method("GET")
        items.add_method("POST")

        # 2. This handles /items/{id} (GET one, PUT, and DELETE)
        # We use your 'items' variable to add a sub-resource
        item_detail = items.add_resource("{proxy+}")
        item_detail.add_method("GET")
        item_detail.add_method("PUT")
        item_detail.add_method("DELETE")
