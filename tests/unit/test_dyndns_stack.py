import aws_cdk as core
import aws_cdk.assertions as assertions

from dyndns.dyndns_stack import DyndnsStack

# example tests. To run these tests, uncomment this file along with the example
# resource in dyndns/dyndns_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = DyndnsStack(app, "dyndns")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
