import aws_cdk as core
import aws_cdk.assertions as assertions

from user_cdk_project.user_cdk_project_stack import UserCdkProjectStack

# example tests. To run these tests, uncomment this file along with the example
# resource in user_cdk_project/user_cdk_project_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = UserCdkProjectStack(app, "user-cdk-project")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
