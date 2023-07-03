#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import Aspects
from cdk_nag import AwsSolutionsChecks


from dyndns.dyndns_stack import DyndnsStack


app = cdk.App()
DyndnsStack(app, "DyndnsStack")
Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
app.synth()
