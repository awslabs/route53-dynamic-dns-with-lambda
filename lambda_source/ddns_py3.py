#force function to run by changing this: 0
# version works with DDB
# Dynamic DNS via AWS API Gateway, Lambda & Route 53
# Script variables use lower_case_

import json
import re
import hashlib
import boto3
import datetime
import os
from boto3.dynamodb.conditions import Key, Attr

# Import Lambda environment variables
ddns_config_table = os.environ['ddns_config_table']
route_53_zone_id_imported = os.environ['route_53_zone_id']
route_53_zone_name_imported = os.environ['route_53_zone_name']
default_ttl = int(os.environ['default_ttl'])
aws_region = os.environ['AWS_REGION']

''' This function pulls the config entry from DynamoDB 
    It is called by the run_set_mode function.'''
def ddb_config(route_53_record_name, route_53_record_type, set_ip, source_ip, read_write):
    # Define the DDB client.
    dynamodb = boto3.resource('dynamodb')
    dynamodb_table = dynamodb.Table(ddns_config_table)
    if read_write == 'read':
      try:
        config_record = dynamodb_table.get_item(
            Key={
            'hostname': route_53_record_name,
            'record_type': route_53_record_type
            })
        dynamodb_table.update_item(
            Key={
            'hostname': route_53_record_name,
            'record_type': route_53_record_type
            },
            UpdateExpression='SET last_checked = :now_time , last_accessed = :last_accessed',
            ConditionExpression='attribute_exists(hostname) AND attribute_exists(record_type)',
            ExpressionAttributeValues={
                ':now_time': str(datetime.datetime.now()),
                ':last_accessed': source_ip
            }
        )
      except:
        return_status = 'fail'
        return_message = 'ddb_config There was an issue finding '\
            'or reading the DyanmoDB config item for '+set_hostname+': '+record_type
        return {'return_status': return_status,
                'return_message': return_message}
      return config_record
    elif read_write == 'write':
        dynamodb_table.update_item(
            Key={
            'hostname': route_53_record_name,
            'record_type': route_53_record_type },
            UpdateExpression='SET last_updated = :now_time , ip_address = :ip , last_accessed = :last_accessed', 
            ExpressionAttributeValues={
                ':now_time': str(datetime.datetime.now()),
                ':ip': set_ip,
                ':last_accessed': source_ip
            },
            ConditionExpression='attribute_exists(hostname) AND attribute_exists(record_type)'
        )
        return

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
def route53_set(execution_mode, aws_region, route_53_zone_id,
                   route_53_record_name, route_53_record_ttl,
                   route_53_record_type, public_ip):
    # Define the Route 53 client
    route53_client = boto3.client(
        'route53',aws_region
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
                        current_route53_ip = eachSubRecord['Value']
                        return_status = 'success'
                        return_message = current_route53_ip
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
        
def validate_hash(set_hostname, source_ip, validation_hash, shared_secret):
    # Calculate the validation hash.
    calculated_hash = hashlib.sha256((
      source_ip + set_hostname + shared_secret).encode('utf-8')).hexdigest()
    # Compare the validation_hash from the client to the
    # calculated_hash.
    # If they don't match, error out.
    if not calculated_hash == validation_hash:
        return_status = 'fail'
        return_message = 'Validation hashes do not match.'
        return {'return_status': return_status,
                'return_message': return_message}
    else:
        return_status = 'success'
        return_message = 'Validation hashes match.'
        return {'return_status': return_status,
                'return_message': return_message}
                                
def run_list_hosts(set_hostname, record_type, validation_hash, source_ip):
    try:
        record_config_set = ddb_config(set_hostname, record_type, '', source_ip, 'read')
    except:
        return_status = 'fail'
        return_message = 'There was an issue finding '\
            'or reading the DyanmoDB config item for '+set_hostname+': '+record_type
        return {'return_status': return_status,
                'return_message': return_message}
    shared_secret = record_config_set['Item']['shared_secret']
    read_privilege = record_config_set['Item']['read_privilege']
    if not read_privilege :
            return_status = 'fail'
            return_message = 'record lacks read permissions'
            return {'return_status': return_status,
                    'return_message': return_message}            
    validation_status = validate_hash(set_hostname, source_ip, validation_hash, shared_secret)
    if validation_status['return_status'] == 'fail':
            return_status = validation_status['return_status']
            return_message = validation_status['return_message']
            return {'return_status': return_status,
                    'return_message': return_message}
                    
    dynamodb = boto3.resource('dynamodb')
    dynamodb_table = dynamodb.Table(ddns_config_table)
    dynamodb_response = dynamodb_table.query(
        IndexName='shared_secret-index',
        KeyConditionExpression=Key('shared_secret').eq(shared_secret),
        FilterExpression=Key('read_privilege').eq(True)
    )
    return_status = 'success'
    return_message = dynamodb_response['Items']
    # Strip unnecessary fields from response
    for record in return_message:
        del record['shared_secret']
        del record['read_privilege']
    return {'return_status': return_status,
            'return_message': return_message}                            
                
''' This function calls route53_set to see if the current Route 53 
    DNS record matches the client's current IP.
    If not it calls route53_set to set the DNS record to the current IP.
    It is called by the main lambda_handler function.
    '''
def run_set_mode(set_hostname, record_type, validation_hash, source_ip, set_ip ):
    # Try to read the config, and error if you can't.
    try:
        record_config_set = ddb_config(set_hostname, record_type, '', source_ip, 'read')
    except:
        return_status = 'fail'
        return_message = 'There was an issue finding '\
            'or reading the DyanmoDB config item for '+set_hostname+': '+record_type
        return {'return_status': return_status,
                'return_message': return_message}
    # Check to see if the record is locked 
    lock_record = record_config_set['Item']['lock_record']
    if lock_record:
        return_status = 'fail'
        return_message = 'The record for ' + set_hostname + ' is locked, update denied.'
        return {'return_status': return_status,
                'return_message': return_message}
      
    ## Deny update to internal IP if disallowed by DDB record.          
    allow_internal = record_config_set['Item']['allow_internal']
    if ( not allow_internal and not source_ip == set_ip):
        return_status = 'fail'
        return_message = 'DDB Permissions for ' + set_hostname + ' disallow internal IPs, update denied.'
        return {'return_status': return_status,
                'return_message': return_message}

    route_53_zone_id = route_53_zone_id_imported
    
    ## Left for possible future multi-zone capability
    #aws_region = record_config_set['Item']['aws_region']
    ## the Route 53 Zone you created for the script
    #try:
    #  route_53_zone_id = record_config_set['Item']['zone_id']
    #except: 
    #  route_53_zone_id = route_53_zone_id_imported

    # record TTL (Time To Live) in seconds tells DNS servers how long to cache
    # the record.
    try:
      route_53_record_ttl = int(record_config_set['Item']['ttl'])
    except: 
      route_53_record_ttl = default_ttl
      
    route_53_record_type = record_config_set['Item']['record_type']
    shared_secret = record_config_set['Item']['shared_secret']

    # debug former validation hash check location
    
    validation_status = validate_hash(set_hostname, source_ip, validation_hash, shared_secret)
    if validation_status['return_status'] == 'fail':
            return_status = validation_status['return_status']
            return_message = validation_status['return_message']
            return {'return_status': return_status,
                    'return_message': return_message}
    # If they do match, get the current ip address associated with
    # the hostname DNS record from Route 53.
    else:
        route53_get_response = route53_set(
            'get_record',
            aws_region,
            route_53_zone_id,
            set_hostname,
            route_53_record_ttl,
            route_53_record_type,
            '')
        # If no records were found, route53_set returns null.
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
        if route53_ip == set_ip:
            return_status = 'success'
            return_message = 'Your IP address matches '\
                'the current Route53 DNS record.'
            return {'return_status': return_status,
                    'return_message': return_message}
        # If the IP addresses do not match or if the record does not exist,
        # Tell Route 53 to set the DNS record.
        # Then update the record in DynamoDB
        else:
            route53_set_response = route53_set(
                'set_record',
                aws_region,
                route_53_zone_id,
                set_hostname,
                route_53_record_ttl,
                route_53_record_type,
                set_ip)
            # Update DynamoDB with IP and update timestamp
            ddb_config(set_hostname, route_53_record_type, set_ip, source_ip, 'write')
            return_status = 'success'
            return_message = 'Your hostname record ' + set_hostname +\
                ' has been set to ' + set_ip
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
    internal_ip = event['internal_ip']
    validation_hash = event['validation_hash']
    set_hostname = event['set_hostname']
    # Add a trailing . from the domain name to normalize the record key in DDB
    if not set_hostname.endswith('.'):
      set_hostname = set_hostname + '.'

    # Verify that the execution mode was set correctly.
    execution_modes = ('set', 'get', 'list_hosts')
    if execution_mode not in execution_modes:
        return_status = 'fail'
        return_message = 'You must pass mode=get, mode=set or mode=list_hosts arguments.'
        return_dict = {'return_status': return_status,
                       'return_message': return_message}
                       
    if not execution_mode == 'get':
        # Validate that the client passed a sha256 hash
        # regex checks for a 64 character hex string.
        if not re.match(r'[0-9a-fA-F]{64}', validation_hash):
            return_status = 'fail'
            return_message = 'You must pass a valid sha256 hash in the '\
                'hash= argument.'
            return {'return_status': return_status,
                    'return_message': return_message}
        # Check if internal_ip was set
        if internal_ip == "":
            set_ip = source_ip
        else:
            set_ip = internal_ip
        # Determine ipv4/ipv6, assumes AAAA if ipv4 regext does not match.
        if not re.match(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', set_ip):
          record_type = 'AAAA'
        else:
          record_type = 'A'
                
    if execution_mode == 'list_hosts':
        return_dict = run_list_hosts(set_hostname, record_type, validation_hash, source_ip)

    # Proceed with set mode to create or update the DNS record.
    elif execution_mode == 'set':
        return_dict = run_set_mode(set_hostname, record_type, validation_hash, source_ip, set_ip)
    else:
        # For get mode, reflect the client's public IP address and exit.
        # Assumes get since other choices exhausted
        return_status = 'success'
        return_message = source_ip
        return_dict = {'return_status': return_status,
                       'return_message': return_message}
                       
    # This Lambda function always exits as a success
    # and passes success or failure information in the json message.
    return return_dict

