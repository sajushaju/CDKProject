#!/usr/bin/env python3
import os
import aws_cdk as cdk
from user_cdk_project.user_cdk_project_stack import CdkApiPostgresStack

app = cdk.App()

# This part ensures the VPC and API are created in the correct place
env_context = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
    region=os.getenv('CDK_DEFAULT_REGION')
)

CdkApiPostgresStack(app, "CdkApiPostgresStack", env=env_context)

app.synth()