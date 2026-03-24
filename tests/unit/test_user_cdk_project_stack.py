import aws_cdk as core
import aws_cdk.assertions as assertions

# Update this line to match your actual project folder name!
from user_cdk_project.user_cdk_project_stack import CdkApiPostgresStack


def test_production_resources_created():
    app = core.App()
    
    # 1. Create the stack instance
    stack = CdkApiPostgresStack(app, "CdkTestStack","dev")
    
    # 2. Capture the CloudFormation template
    template = assertions.Template.from_stack(stack)

    # 3. Check for VPC (Virtual Private Cloud)
    # This ensures your "Private Fence" is built
    template.resource_count_is("AWS::EC2::VPC", 1)

    # 4. Check for RDS (Database)
    # Ensures it's the correct engine and size for your budget
    template.has_resource_properties("AWS::RDS::DBInstance", {
        "Engine": "postgres",
        "DBInstanceClass": "db.t3.micro"
    })

    # 5. Check for S3 (Image Storage)
    # Ensures public access is blocked for security
    template.has_resource_properties("AWS::S3::Bucket", {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True
        }
    })

    # 6. Check for Lambda (The Logic)
    # Ensures it has the right "Entry Point" and Environment variables
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "handler.main",
        "Environment": {
            "Variables": {
                "DB_NAME": "mydb"
            }
        }
    })