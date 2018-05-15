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
route_53_region = os.environ['route_53_region']
api_cname = os.environ['api_cname']
create_acm = os.environ['create_acm']
#api_origin = os.environ['api_origin']
#Add a trailing '.' if not present.
#if not route_53_zone_name.endswith('.'):
#    route_53_zone_name = route_53_zone_name + '.'
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
    return response

def route53_set(route_53_region, route_53_zone_id,
                   route_53_record_name, route_53_record_ttl,
                   route_53_record_type, route_53_record_value):
    # Define the Route 53 client
    route53_client = boto3.client(
        'route53',
        region_name=route_53_region
    )
    # Set the DNS CNAME.
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

def acm_find(route_53_zone_name):
    acm_client = boto3.client('acm', region_name='us-east-1')
    cert_list = acm_client.list_certificates()
    for my_cert in (cert_list['CertificateSummaryList']):
        if (str(my_cert['DomainName'])) == str(route_53_zone_name) :
            return (my_cert['CertificateArn'])
    return 'fail'
    
def acm_request(route_53_zone_name):
    acm_client = boto3.client('acm', region_name='us-east-1')
    ## Ensure there is no trailing '.' for ACM
    route_53_zone_name=route_53_zone_name.rstrip('.')
    cert_request = acm_client.request_certificate(
        DomainName=route_53_zone_name,
        ValidationMethod='DNS',
        DomainValidationOptions=[
            {
                'DomainName': route_53_zone_name,
                'ValidationDomain': route_53_zone_name
            },
        ]
    )
    cert_arn=(cert_request['CertificateArn'])
    return cert_arn
    
def acm_info(cert_arn):
    ## ACM certs for CloudFront need to be in us-east-1
    acm_client = boto3.client('acm', region_name='us-east-1')
    try:
        cert_info = acm_client.describe_certificate(
            CertificateArn=cert_arn
        )
        cert_validation_status=(cert_info['Certificate']['DomainValidationOptions'][0]['ValidationStatus'])
        cert_validation_name=(cert_info['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Name'])
        cert_validation_value=(cert_info['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Value'])
        return {'cert_arn': cert_arn, 'cert_validation_name': cert_validation_name, 'cert_validation_value': cert_validation_value}
    except:
        return 'fail'

def run_acm_process(route_53_zone_name, api_cname, api_origin):
    ## Look to see if certificate already exists
    existing_cert = acm_find(route_53_zone_name)
    if existing_cert == 'fail':
        cert_arn = ''
        pass
    else:
        cert_arn = existing_cert
        print('Found existing cert: ' + cert_arn)
    
    ## If cert does not already exist, create it.
    if cert_arn == '':
        cert_arn = acm_request(route_53_zone_name)
        print('Created new cert: ' + str(cert_arn))
    ## ACM validation records are always the same for any zone.
    ## We will create the validation record regardless of whether the
    ## cert existed before.
    try:
        for loop_count in range(1, 6):
            time.sleep(loop_count*5)
            print("ACM info attempt: " + str(loop_count))
            acm_return_dict = acm_info(cert_arn)
            if acm_return_dict != 'fail' :
                break
    except:
        print('Failed to create Route53 DNS validation record.')
    cert_validation_name = (acm_return_dict['cert_validation_name'])
    cert_validation_value = (acm_return_dict['cert_validation_value'])
    print("Setting validation record: " + cert_validation_name + " CNAME " + cert_validation_value)
    route_53_return_dict = route53_set(route_53_region, route_53_zone_id, cert_validation_name, 300, 'CNAME', cert_validation_value)
    return cert_arn 
   
def populate_ddb(ddns_config_table, route_53_zone_name):
    try:
        # Define the DDB client.
        dynamodb = boto3.resource('dynamodb')
        dynamodb_table = dynamodb.Table(ddns_config_table)
        dynamodb_table.put_item(
          Item={
          'hostname': 'example-record.' + route_53_zone_name, 
          'record_type': 'A',
          'aws_region': route_53_region,
          'zone_id': route_53_zone_id, 
          'ttl': 60,
          'shared_secret': ''.join(random.choice('0123456789ABCDEF') for i in range(16)),
          'lock_record': False, 
          'ip_address': '1.1.1.1', 
          'last_checked': str(datetime.datetime.now()), 
          'last_updated': str(datetime.datetime.now()),
          'comment': 'sample comment'
          }
        )
        dynamodb_table.put_item(
          Item={
          'hostname': 'example-record.' + route_53_zone_name, 
          'record_type': 'AAAA',
          'aws_region': route_53_region,
          'zone_id': route_53_zone_id, 
          'ttl': 60,
          'shared_secret': ''.join(random.choice('0123456789ABCDEF') for i in range(16)), 
          'lock_record': False, 
          'ip_address': '2001:564:6045:96:d66:c133:2ab3:7b01', 
          'last_checked': str(datetime.datetime.now()), 
          'last_updated': str(datetime.datetime.now()),
          'comment': 'sample comment'
          }
        )
        print('Populated sample DDB entries')
    except:
        print('Failed to populate sample DDB entries')
      
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
        if create_acm == 'true' :
            cert_arn = run_acm_process(route_53_zone_name, api_cname, cloudfront_url)
            response['acmCertificateARN'] = cert_arn
            print('Using certificate: ' + cert_arn)
            
      elif run_mode == 'second_run':
        print("Setting api CloudFront cname: " + api_cname + " CNAME " + cloudfront_url)
        route_53_return_dict = route53_set(route_53_region, route_53_zone_id, api_cname, 300, 'CNAME', cloudfront_url)
      response['Reason'] = 'Event Succeeded'
    except ClientError as e:
      print("Unexpected error: %s" % e)
      response['Reason'] = 'Event Failed - See CloudWatch logs for the Lamba function backing the custom resource for details'
      ## Un-comment the line blow to send a true failure to CFN
      ## will cause a stack rollback on failure and can leave the stack in a state that requires deletion.
      #response['Status'] = 'FAILED'
    return send_response(event, response)
