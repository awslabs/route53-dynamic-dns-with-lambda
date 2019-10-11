#force function to run by changing this: 0
from __future__ import print_function
import boto3
import datetime  
import random
import os   
import uuid
import httplib
import urlparse
import json
import time

print('Loading function')
from botocore.client import Config
from botocore.exceptions import ClientError

# Import Lambda environment variables
ddns_config_table = os.environ['ddns_config_table']
route_53_zone_id = os.environ['route_53_zone_id']
route_53_zone_name = os.environ['route_53_zone_name']
aws_region = os.environ['aws_region']
api_cname = os.environ['api_cname']
api_key_id = os.environ['api_key_id']
def send_response(request, response, status=None, reason=None):
    """ Send our response to the pre-signed URL supplied by CloudFormation"""
    if status is not None:
        response['Status'] = status
    if reason is not None:
        response['Reason'] = reason
    if 'ResponseURL' in request and request['ResponseURL']:
        url = urlparse.urlparse(request['ResponseURL'])
        body = json.dumps(response)
        https = httplib.HTTPSConnection(url.hostname)
        https.request('PUT', url.path+'?'+url.query, body)
        print(url.hostname)
        print('PUT', url.path+'?'+url.query, body)
    print(response)
    return response

def route53_set(aws_region, route_53_zone_id,
                   route_53_record_name, route_53_record_ttl,
                   route_53_record_type, route_53_record_value):
    # Define the Route 53 client
    route53_client = boto3.client(
        'route53',aws_region
    )
    change_route53_record_set = route53_client.change_resource_record_sets(
        HostedZoneId=route_53_zone_id,
        ChangeBatch={
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': route_53_record_name,
                        'Type': route_53_record_type,
                        'TTL': route_53_record_ttl,
                        'ResourceRecords': [
                            {
                                'Value': route_53_record_value
                            }
                        ]
                    }
                }
            ]
        }
    )
    return change_route53_record_set
   
def populate_ddb(ddns_config_table, route_53_zone_name):
    try:
        # Define the DDB client.
        dynamodb = boto3.resource('dynamodb')
        dynamodb_table = dynamodb.Table(ddns_config_table)
        dynamodb_table.put_item(
          Item={
          'hostname': 'example-record.' + route_53_zone_name + '.', 
          'record_type': 'A',
          'ttl': 60,
          'shared_secret': ''.join(random.choice('0123456789ABCDEF') for i in range(16)),
          'lock_record': False, 
          'read_privilege': False, 
          'allow_internal': True,
          'ip_address': '1.1.1.1', 
          'mac_address': '0A:0A:0A:0A:0A:0A',
          'last_checked': str(datetime.datetime.now()), 
          'last_updated': str(datetime.datetime.now()),
          'last_accessed': '1.2.3.4',
          'comment': 'example record'
          }
        )
        dynamodb_table.put_item(
          Item={
          'hostname': 'example-record.' + route_53_zone_name + '.', 
          'record_type': 'AAAA',
          'ttl': 60,
          'shared_secret': ''.join(random.choice('0123456789ABCDEF') for i in range(16)), 
          'lock_record': False, 
          'read_privilege': False, 
          'allow_internal': True,
          'ip_address': '1:1:1:1:1:1:1:1', 
          'mac_address': '0A:0A:0A:0A:0A:0A', 
          'last_checked': str(datetime.datetime.now()), 
          'last_updated': str(datetime.datetime.now()),
          'last_accessed': '2:2:2:2:2:2:2:2',
          'comment': 'example record'
          }
        )
        print('Populated sample DDB entries')
    except:
        print('Failed to populate sample DDB entries')

def get_api_key(api_key_id):
    apigateway = boto3.client('apigateway')
    api_key_response = apigateway.get_api_key(apiKey=api_key_id, includeValue=True)
    print('Getting api key')
    print(api_key_response['value'])
    try:
      return api_key_response['value']
    except:
      print('fail')
                  
## Main Lambda handler
def lambda_handler(event, context):
    response = {
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Status': 'SUCCESS'
    }
    ## Pass the run mode argument so lambda can tell if this is the first setup run,
    ## Or the second run (post CF creation) that cnames CloudFront
    run_mode=event['ResourceProperties']['run_mode']
    cloudfront_url=event['ResourceProperties']['cloudfront_url']
    # PhysicalResourceId is meaningless here, but CloudFormation requires it
    if 'PhysicalResourceId' in event:
        response['PhysicalResourceId'] = event['PhysicalResourceId']
    else:
        response['PhysicalResourceId'] = str(uuid.uuid4())

    # There is nothing to do for a delete request
    if event['RequestType'] == 'Delete':
        return send_response(event, response)
        
    ## Main function logic    
    try:  
      print('Run mode: '+run_mode)
      if run_mode == 'first_run':
        populate_ddb(ddns_config_table, route_53_zone_name)
        if api_key_id:
           api_key = get_api_key(api_key_id)
           response['Data'] = {'api_key': api_key }
      elif run_mode == 'second_run':
        print("Setting api CloudFront cname: " + api_cname + " CNAME " + cloudfront_url)
        route_53_return_dict = route53_set(aws_region, route_53_zone_id, api_cname, 300, 'CNAME', cloudfront_url)
      response['Reason'] = 'Event Succeeded'
    except ClientError as e:
      print("Unexpected error: %s" % e)
      response['Reason'] = 'Event Failed - See CloudWatch logs for the Lamba function backing the custom resource for details'
      ## Un-comment the line blow to send a true failure to CFN
      ## will cause a stack rollback on failure and can leave the stack in a state that requires deletion.
      #response['Status'] = 'FAILED'
    return send_response(event, response)

