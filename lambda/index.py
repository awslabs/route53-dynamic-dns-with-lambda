# Dynamic DNS via AWS API Gateway, Lambda & Route 53
# Script variables use lower_case_

from __future__ import print_function

import json
import re
import hashlib
import boto3
import os
from botocore.exceptions import ClientError

'''
This function pulls the json config data from DynamoDB and returns a python dictionary.
It is called by the run_set_mode function.
'''
def read_config(key_hostname):
    # Define the dynamoDB client
    dynamodb = boto3.client("dynamodb")
    # Retrieve data based on key_hostname
    response = dynamodb.get_item(
        TableName=os.environ.get("ddns_config_table"),
        Key={'hostname': {'S': key_hostname}}
    )
    # Return the json as a dictionary.
    return json.loads(response["Item"]["data"]["S"])

'''
    This function takes the python dictionary returned from read_configThis function defines the interaction with Route 53.
    It is called by the run_set_mode function.
    @param execution_mode defines whether to set or get a DNS record
    @param route_53_zone_id defines the id for the DNS zone
    @param route_53_record_name defines the record, ie www.acme.com.
    @param route_53_record_ttl defines defines the DNS record TTL
    @param route_53_record_type defines record type, should always be 'a'
    @param public_ip defines the current public ip of the client
'''
def route53_client(execution_mode, route_53_zone_id,
                   route_53_record_name, route_53_record_ttl,
                   route_53_record_type, public_ip):
    # Define the Route 53 client
    route53_client = boto3.client('route53')

    # Query Route 53 for the current DNS record.
    if execution_mode == 'get_record':
        try:
            current_route53_record_set = route53_client.list_resource_record_sets(
                HostedZoneId=route_53_zone_id,
                StartRecordName=route_53_record_name,
                StartRecordType=route_53_record_type,
                MaxItems='1'
            )
            try:
                if current_route53_record_set['ResourceRecordSets'][0]['Name'].rstrip('.') == route_53_record_name.rstrip('.'):
                    currentroute53_ip = current_route53_record_set['ResourceRecordSets'][0]['ResourceRecords'][0]['Value']
                else:
                    currentroute53_ip = '0'
            except:
                currentroute53_ip = '0'
            return {'return_status': 'success', 'return_message': currentroute53_ip}
        except ClientError as e:
            return {'return_status': 'fail', 'return_message': str(e)}
        except:
            return {'return_status': 'fail', 'return_message': 'Unknown error'}

    # Set the DNS record to the current IP.
    if execution_mode == 'set_record':
        try:
            change_route53_record_set = route53_client.change_resource_record_sets(
                HostedZoneId = route_53_zone_id,
                ChangeBatch = {
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': route_53_record_name,
                                'Type': route_53_record_type,
                                'TTL': route_53_record_ttl,
                                'ResourceRecords': [
                                    {
                                        'Value': public_ip
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            return [201, {'return_status': 'success', 'return_message': route_53_record_name+' has been updated to '+public_ip}]
        except ClientError as e:
            return [500, {'return_status': 'fail', 'return_message': str(e)}]
        except:
            return [500, {'return_status': 'fail', 'return_message': 'Unknown error'}]


'''
This function calls route53_client to see if the current Route 53 DNS record matches the client's current IP.
If not it calls route53_client to set the DNS record to the current IP.
It is called by the main lambda_handler function.
'''
def run_set_mode(ddns_hostname, validation_hash, source_ip):
    # Try to read the config, and error if you can't.
    try:
        full_config=read_config(ddns_hostname)
    except:
        return_status='fail'
        return_message='There was an issue finding '\
            'or reading '+ddns_hostname+' configuration from dynamoDB table: ' + \
            os.environ.get("ddns_config_table")
        return [403, {'return_status': return_status,
                'return_message': return_message}]

    # Get the section of the config related to the requested hostname.
    record_config_set=full_config  # [ddns_hostname]
    # the Route 53 Zone you created for the script
    route_53_zone_id=record_config_set['route_53_zone_id']
    # record TTL (Time To Live) in seconds tells DNS servers how long to cache
    # the record.
    route_53_record_ttl=record_config_set['route_53_record_ttl']
    route_53_record_type="A"
    shared_secret=record_config_set['shared_secret']

    # Validate that the client passed a sha256 hash
    # regex checks for a 64 character hex string.
    if not re.match(r'[0-9a-fA-F]{64}', validation_hash):
        return_status='fail'
        return_message='You must pass a valid sha256 hash in the '\
            'hash= argument.'
        return [400, {'return_status': return_status,
                'return_message': return_message}]
    # Calculate the validation hash.
    hashcheck=source_ip + ddns_hostname + shared_secret
    calculated_hash=hashlib.sha256(
        hashcheck.encode('utf-8')).hexdigest()
    # Compare the validation_hash from the client to the
    # calculated_hash.
    # If they don't match, error out.
    if not calculated_hash == validation_hash:
        return_status='fail'
        return_message='Validation hashes do not match.'
        return [401, {
                'return_status': return_status,
                'return_message': return_message}]
    # If they do match, get the current ip address associated with
    # the hostname DNS record from Route 53.
    else:
        route53_get_response=route53_client(
            'get_record',
            route_53_zone_id,
            ddns_hostname,
            route_53_record_ttl,
            route_53_record_type,
            '')
        # If no records were found, route53_client returns null.
        # Set route53_ip and stop evaluating the null response.
        if route53_get_response['return_status'] == "fail":
            return [500, route53_get_response]
        else:
            route53_ip = route53_get_response['return_message']
        # If the client's current IP matches the current DNS record
        # in Route 53 there is nothing left to do.
        if route53_ip == source_ip:
            return_status = 'success'
            return_message = 'Your IP address matches '\
                'the current Route53 DNS record.'
            return [200, {'return_status': return_status,
                    'return_message': return_message}]
        # If the IP addresses do not match or if the record does not exist,
        # Tell Route 53 to set the DNS record.
        else:
            return_status = route53_client(
                'set_record',
                route_53_zone_id,
                ddns_hostname,
                route_53_record_ttl,
                route_53_record_type,
                source_ip)
            return return_status


'''
The function that Lambda executes. It contains the main script logic.
'''


def lambda_handler(event, context):
    # Get execution mode and source IP
    execution_mode = json.loads(event['body'])['execution_mode']
    source_ip = event['requestContext']['http']['sourceIp']

    # Verify that the execution mode was set correctly.
    execution_modes = ('set', 'get')
    if execution_mode not in execution_modes:
        return_status = 'fail'
        return_message = 'You must pass mode=get or mode=set arguments.'
        return_dict = [400, {'return_status': return_status,
                             'return_message': return_message}]

    # For get mode, reflect the client's public IP address and exit.
    if execution_mode == 'get':
        return_status = 'success'
        return_message = source_ip
        return_dict = [200, {'return_status': return_status,
                             'return_message': return_message}]

    # Proceed with set mode to create or update the DNS record.
    else:
        # Set event data to variables.
        validation_hash = json.loads(event['body'])['validation_hash']
        ddns_hostname = json.loads(event['body'])['ddns_hostname']
        return_dict = run_set_mode(ddns_hostname, validation_hash, source_ip)

    # This Lambda function always exits as a success
    # and passes success or failure information in the json message.
    # return json.loads(return_dict)

    return {
        "statusCode": return_dict[0],
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET'
        },
        "body": json.dumps(return_dict[1])
    }
