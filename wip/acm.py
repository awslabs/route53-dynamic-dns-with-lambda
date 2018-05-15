#!/usr/local/bin/python
import boto3
import datetime  
import random
import os   
import uuid
import httplib
import urlparse
import json
import time

route_53_region = 'us-west-2'
route_53_zone_name = 'foo.greathou.se'
route_53_zone_id = 'Z2PXLQ1OBZKR4O'
dev = boto3.session.Session(profile_name='sgreat-home')
boto3.setup_default_session(profile_name='sgreat-home')
api_origin = 'api.foo.net'
api_cname = 'apitest.greathou.se'
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
	if not cert_arn:
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
	print("Setting api cname: " + api_cname + " CNAME " + api_origin)
	route_53_return_dict = route53_set(route_53_region, route_53_zone_id, api_cname, 300, 'CNAME', api_origin)
	response['cert_arn'] = cert_arn
run_acm_process(route_53_zone_name, api_cname, api_origin)









