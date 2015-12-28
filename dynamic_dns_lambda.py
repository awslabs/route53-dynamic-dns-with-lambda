# Dynamic DNS via AWS API Gateway, Lambda & Route 53
# Script variables use lower_case_
from __future__ import print_function

import json
import re
import hashlib
import boto3

# Tell the script where to find the configuration file.
config_s3_region = 'us-west-2'
config_s3_bucket = 'my_bucket_name'
config_s3_key = 'config.json'


''' This function pulls the json config file from S3 and
    returns a python dictionary.
    It is called by the run_set_mode function.'''


def read_s3_config():
    # Define the S3 client.
    s3_client = boto3.client(
        's3',
        config_s3_region,
    )

    # Download the config to /tmp
    s3_client.download_file(
        config_s3_bucket,
        config_s3_key,
        '/tmp/%s' % config_s3_key
    )
    # Open the config and return the json as a dictionary.
    full_config = (open('/tmp/%s' % config_s3_key).read())
    return json.loads(full_config)


''' This function defines the interaction with Route 53.
    It is called by the run_set_mode function.
    @param execution_mode defines whether to set or get a DNS record
    @param aws_region defines region to call
    @param route_53_zone_id defines the id for the DNS zone
    @param route_53_record_name defines the record, ie www.acme.com.
    @param route_53_record_ttl defines defines the DNS record TTL
    @param route_53_record_type defines record type, should always be 'a'
    @param public_ip defines the current public ip of the client
    '''


def route53_client(execution_mode, aws_region, route_53_zone_id,
                   route_53_record_name, route_53_record_ttl,
                   route_53_record_type, public_ip):
    # Define the Route 53 client
    route53_client = boto3.client(
        'route53',
        region_name=aws_region
    )

    # Query Route 53 for the current DNS record.
    if execution_mode == 'get_record':
        current_route53_record_set = route53_client.list_resource_record_sets(
            HostedZoneId=route_53_zone_id,
            StartRecordName=route_53_record_name,
            StartRecordType=route_53_record_type,
            MaxItems='2'
        )
        # boto3 returns a dictionary with a nested list of dictionaries
        # see: http://boto3.readthedocs.org/en/latest/reference/services/
        # route53.html#Route53.Client.list_resource_record_sets
        # Parse the dict to find the current IP for the hostname, if it exists.
        # If it doesn't exist, the function returns False.
        for eachRecord in current_route53_record_set['ResourceRecordSets']:
            if eachRecord['Name'] == route_53_record_name:
                # If there's a single record, pass it along.
                if len(eachRecord['ResourceRecords']) == 1:
                    for eachSubRecord in eachRecord['ResourceRecords']:
                        currentroute53_ip = eachSubRecord['Value']
                        return_status = 'success'
                        return_message = currentroute53_ip
                        return {'return_status': return_status,
                                'return_message': return_message}
                # Error out if there is more than one value for the record set.
                elif len(eachRecord['ResourceRecords']) > 1:
                    return_status = 'fail'
                    return_message = 'You should only have a single value for'\
                    ' your dynamic record.  You currently have more than one.'
                    return {'return_status': return_status,
                            'return_message': return_message}

    # Set the DNS record to the current IP.
    if execution_mode == 'set_record':
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
                                    'Value': public_ip
                                }
                            ]
                        }
                    }
                ]
            }
        )
        return 1

''' This function calls route53_client to see if the current Route 53 
    DNS record matches the client's current IP.
    If not it calls route53_client to set the DNS record to the current IP.
    It is called by the main lambda_handler function.
    '''


def run_set_mode(set_hostname, validation_hash, source_ip):
    # Try to read the config, and error if you can't.
    try:
        full_config = read_s3_config()
    except:
        return_status = 'fail'
        return_message = 'There was an issue finding '\
            'or reading the S3 config file.'
        return {'return_status': return_status,
                'return_message': return_message}
    # Get the section of the config related to the requested hostname.
    record_config_set = full_config[set_hostname]
    aws_region = record_config_set['aws_region']
    # the Route 53 Zone you created for the script
    route_53_zone_id = record_config_set['route_53_zone_id']
    # record TTL (Time To Live) in seconds tells DNS servers how long to cache
    # the record.
    route_53_record_ttl = record_config_set['route_53_record_ttl']
    route_53_record_type = record_config_set['route_53_record_type']
    shared_secret = record_config_set['shared_secret']

    # Validate that the client passed a sha256 hash
    # regex checks for a 64 character hex string.
    if not re.match(r'[0-9a-fA-F]{64}', validation_hash):
        return_status = 'fail'
        return_message = 'You must pass a valid sha256 hash in the '\
            'hash= argument.'
        return {'return_status': return_status,
                'return_message': return_message}

    # Calculate the validation hash.
    calculated_hash = hashlib.sha256(
        source_ip + set_hostname + shared_secret).hexdigest()
    # Compare the validation_hash from the client to the
    # calculated_hash.
    # If they don't match, error out.
    if not calculated_hash == validation_hash:
        return_status = 'fail'
        return_message = 'Validation hashes do not match.'
        return {'return_status': return_status,
                'return_message': return_message}
    # If they do match, get the current ip address associated with
    # the hostname DNS record from Route 53.
    else:
        route53_get_response = route53_client(
            'get_record',
            aws_region,
            route_53_zone_id,
            set_hostname,
            route_53_record_ttl,
            route_53_record_type,
            '')
        # If no records were found, route53_client returns null.
        # Set route53_ip and stop evaluating the null response.
        if not route53_get_response:
            route53_ip = '0'
        # Pass the fail message up to the main function.
        elif route53_get_response['return_status'] == 'fail':
            return_status = route53_get_response['return_status']
            return_message = route53_get_response['return_message']
            return {'return_status': return_status,
                    'return_message': return_message}
        else:
            route53_ip = route53_get_response['return_message']
        # If the client's current IP matches the current DNS record
        # in Route 53 there is nothing left to do.
        if route53_ip == source_ip:
            return_status = 'success'
            return_message = 'Your IP address matches '\
                'the current Route53 DNS record.'
            return {'return_status': return_status,
                    'return_message': return_message}
        # If the IP addresses do not match or if the record does not exist,
        # Tell Route 53 to set the DNS record.
        else:
            return_status = route53_client(
                'set_record',
                aws_region,
                route_53_zone_id,
                set_hostname,
                route_53_record_ttl,
                route_53_record_type,
                source_ip)
            return_status = 'success'
            return_message = 'Your hostname record ' + set_hostname +\
                ' has been set to ' + source_ip
            return {'return_status': return_status,
                    'return_message': return_message}


''' The function that Lambda executes.
    It contains the main script logic, calls 
    and returns the output back to API Gateway'''


def lambda_handler(event, context):

    # Set event data from the API Gateway to variables.
    execution_mode = event['execution_mode']
    source_ip = event['source_ip']
    query_string = event['query_string']
    validation_hash = event['validation_hash']
    set_hostname = event['set_hostname']

    # Verify that the execution mode was set correctly.
    execution_modes = ('set', 'get')
    if execution_mode not in execution_modes:
        return_status = 'fail'
        return_message = 'You must pass mode=get or mode=set arguments.'
        return_dict = {'return_status': return_status,
                       'return_message': return_message}

    # For get mode, reflect the client's public IP address and exit.
    if execution_mode == 'get':
        return_status = 'success'
        return_message = source_ip
        return_dict = {'return_status': return_status,
                       'return_message': return_message}

    # Proceed with set mode to create or update the DNS record.
    else:
        return_dict = run_set_mode(set_hostname, validation_hash, source_ip)

    # This Lambda function always exits as a success
    # and passes success or failure information in the json message.
    return return_dict
