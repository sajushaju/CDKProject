from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_s3 as s3,
    aws_iam as iam,
    BundlingOptions,
)
from constructs import Construct

class CdkApiPostgresStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Create a VPC (Network)
        vpc = ec2.Vpc(self, "MyApiVpc", max_azs=2)

        # 2. Create the S3 Bucket for Profile Images
        # This is the "Storage Room" for your .jpg files
        image_bucket = s3.Bucket(
            self, "ItemImageBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True, # Cleans up images when you delete the stack
            public_read_access=True,  # Allows images to be viewed via URL
            block_public_access=s3.BlockPublicAccess.BLOCK_ACLS_ONLY 
        )

        # 3. Create the PostgreSQL Database
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

        # 4. Create the Lambda Function
        api_lambda = _lambda.Function(
            self,
            "ApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.main",
            timeout=Duration.seconds(30),
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
                "BUCKET_NAME": image_bucket.bucket_name, # Tells Lambda where to upload
            },
        )

        # 5. Permissions & Networking
        db_instance.secret.grant_read(api_lambda)
        db_instance.connections.allow_default_port_from(api_lambda)
        
        # Grant Lambda permission to Write/Upload to the S3 Bucket
        image_bucket.grant_put(api_lambda)

        # 6. API Gateway Setup
        api = apigw.LambdaRestApi(self, "MyApi", handler=api_lambda, proxy=False)

        # Define /items resource
        items = api.root.add_resource("items")
        items.add_method("GET")
        items.add_method("POST")

        # Define /items/{id} resource
        item_detail = items.add_resource("{proxy+}")
        item_detail.add_method("GET")
        item_detail.add_method("PUT")
        item_detail.add_method("DELETE")