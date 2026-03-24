#!/usr/bin/env python3
import os
import aws_cdk as cdk
from user_cdk_project.user_cdk_project_stack import CdkApiPostgresStack

app = cdk.App()

# 1. Get the 'env' flag from the command line (e.g., cdk deploy -c env=dev)
# If no flag is passed, we default to 'dev' for safety.
target_env = app.node.try_get_context("env") or "dev"

# 2. Keep your existing environment detection
env_context = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
    region=os.getenv('CDK_DEFAULT_REGION')
)

# 3. Use the target_env to give the Stack a UNIQUE ID
# Instead of "CdkApiPostgresStack", it will be "CdkApiPostgresStack-dev"
CdkApiPostgresStack(
    app, 
    f"CdkApiPostgresStack-{target_env}", # This is the unique ID
    env=env_context,
    target_env=target_env # We pass this so your Stack can name resources
)

app.synth()