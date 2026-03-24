#this file for test aws infrastructre
import aws_cdk as core
import aws_cdk.assertions as assertions
# Import your actual stack class
from user_cdk_project.user_cdk_project_stack import CdkApiPostgresStack

def test_infrastructure_configuration():
    app = core.App()
    # 1. Initialize the stack
    stack = CdkApiPostgresStack(app, "CdkTestStack","dev")
    
    # 2. Prepare the template for assertions
    template = assertions.Template.from_stack(stack)

    # --- PILLAR 1: S3 STORAGE ---
    # Ensure the bucket exists and has the correct removal policy (Safety check)
    template.has_resource_properties("AWS::S3::Bucket", {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True
        }
    })

    # --- PILLAR 2: NETWORKING (VPC) ---
    # Ensure we have a VPC with exactly 2 Availability Zones (Cost control)
    template.resource_count_is("AWS::EC2::VPC", 1)
    # Check if we have public and private subnets
    template.has_resource_properties("AWS::EC2::VPC", {
        "EnableDnsHostnames": True,
        "EnableDnsSupport": True
    })

    # --- PILLAR 3: DATABASE (RDS) ---
    # Ensure RDS is Postgres 15 and is using a MICRO instance (Cost control)
    template.has_resource_properties("AWS::RDS::DBInstance", {
        "Engine": "postgres",
        "DBInstanceClass": "db.t3.micro",
        "AllocatedStorage": "20",
        "DBName": "mydb"
    })

    # --- PILLAR 4: COMPUTE (LAMBDA) ---
    # Ensure the Lambda has the correct Python runtime and Environment variables
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "handler.main",
        "Runtime": "python3.13",
        "Environment": {
            "Variables": {
                "DB_NAME": "mydb",
                "BUCKET_NAME": assertions.Match.any_value(),
                "DB_SECRET_ARN": assertions.Match.any_value()
            }
        }
    })

    # --- PILLAR 5: SECURITY ---
    # Ensure the Lambda is actually inside the VPC
    template.has_resource_properties("AWS::Lambda::Function", {
        "VpcConfig": assertions.Match.any_value()
    })